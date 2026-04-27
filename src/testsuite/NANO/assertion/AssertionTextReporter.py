#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2025/10/14
# @Author  : huidong.bai
# @File    : AssertionTextReporter.py
# @Software: PyCharm
# @Mail    : MasterBai2018@outlook.com

"""
NANO 断言纯文本报告器

架构：
    每个 xdist Worker（gw0/gw1/... 或单进程 main）独立写 result_{worker_id}.txt，
    文件中只含 Case 块，无头部，无 Summary。

    pytest session 结束后，Controller（pytest_sessionfinish is_master）调用
    AssertionTextReporter.merge_worker_reports()，将所有 Worker 文件合并为
    最终的 result.txt，包含完整的头部、Summary 和按 case.index 排序的 Case 块，
    合并成功后删除所有 Worker 临时文件。

调用方（NANORunner）：
    reporter = AssertionTextReporter(report_path, suite_info)
    reporter.begin_case(dsl_case)      # execute_case 开始时
    reporter.record(expectation)       # do_assertion 结束时（由 AssertionEngine 调用）
    reporter.flush_case()              # execute_case 结束时

调用方（conftest.pytest_sessionfinish Controller 分支）：
    AssertionTextReporter.merge_worker_reports(suite_dir, final_path, suite_info)
"""

import os
import re
import glob
import time
import threading
from datetime import datetime
from typing import List, Optional, Tuple, Any
from dataclasses import dataclass, field

from loguru import logger
from src.testsuite.NANO.assertion.AssertionParser import (
    AssertionExpectation,
    AssertionStatus,
)


# ══════════════════════════════════════════════════════════════════
#  常量
# ══════════════════════════════════════════════════════════════════

HEADER_WIDTH   = 68   # 报告头和 Summary 框的固定总宽（字符数，含两侧边框）
MIN_CASE_INNER = 84   # Case 框内容区最小显示宽度

# Case 框右侧状态区固定格式：' PASS   ─────┐' 或 ' FAIL   ─────┐'，共 14 字符
_STATUS_RIGHT_LEN = 14


# ══════════════════════════════════════════════════════════════════
#  内部数据结构
# ══════════════════════════════════════════════════════════════════

@dataclass
class _AssertRecord:
    index         : int
    callback_type : str
    channel_id    : str
    status        : int    # AssertionStatus 值
    expect_infos  : str
    actual_infos  : str


@dataclass
class _CaseRecord:
    dsl_case : Any
    asserts  : List[_AssertRecord] = field(default_factory=list)


# ══════════════════════════════════════════════════════════════════
#  工具函数
# ══════════════════════════════════════════════════════════════════

def _dw(text: str) -> int:
    """计算字符串的终端显示宽度（CJK 宽字符 = 2，其余 = 1）"""
    w = 0
    for c in text:
        cp = ord(c)
        if (0x1100 <= cp <= 0x115F or
                0x2E80 <= cp <= 0x303E or
                0x3040 <= cp <= 0x33FF or
                0x3400 <= cp <= 0x4DBF or
                0x4E00 <= cp <= 0x9FFF or
                0xA000 <= cp <= 0xA4CF or
                0xAC00 <= cp <= 0xD7AF or
                0xF900 <= cp <= 0xFAFF or
                0xFE10 <= cp <= 0xFE1F or
                0xFE30 <= cp <= 0xFE4F or
                0xFF00 <= cp <= 0xFF60 or
                0xFFE0 <= cp <= 0xFFE6 or
                0x20000 <= cp <= 0x2FFFD or
                0x30000 <= cp <= 0x3FFFD):
            w += 2
        else:
            w += 1
    return w


def _inner_line(content: str, inner_w: int) -> str:
    """将 content 填充为 inner_w 显示宽的内容区，并加上两侧 │ 边框。"""
    pad = max(0, inner_w - _dw(content))
    return f'│ {content}{" " * pad} │'


def _sort_key(index_str: str) -> tuple:
    """
    case.index 排序键，支持：
      '0'    → (0,)
      '0_P1' → (0, 'P', 1)
      '1_P3' → (1, 'P', 3)
      '0_S2' → (0, 'S', 2)
    """
    parts = str(index_str).split('_')
    result: list = []
    try:
        result.append(int(parts[0]))
    except ValueError:
        result.append(parts[0])
    for p in parts[1:]:
        if p and p[0].isalpha():
            result.append(p[0])
            try:
                result.append(int(p[1:]))
            except ValueError:
                result.append(p[1:])
        else:
            try:
                result.append(int(p))
            except ValueError:
                result.append(p)
    return tuple(result)


def _extract_audio_paths(dsl_case) -> List[str]:
    """
    从 DSLCase 的 commands 中提取音频路径。
    在 flush_case() 时调用，此时环境变量已由 NANORunner 替换完毕。
    """
    seen  = set()
    paths = []
    for cmd in dsl_case.commands:
        if cmd.command in ('DATA', 'TEXT_DATA') and cmd.params:
            p = cmd.params[0]
            # 跳过命名参数（如 text=xxx、frame=xxx）
            if '=' not in p and p not in seen:
                seen.add(p)
                paths.append(p)
    return paths


# ══════════════════════════════════════════════════════════════════
#  文本块构建函数
# ══════════════════════════════════════════════════════════════════

def _build_header_block(suite_info: dict,
                        start_ts: Optional[float],
                        end_ts: Optional[float],
                        case_total: int) -> str:
    """
    构建固定宽度（HEADER_WIDTH）的报告头块。

    ╔══════════════════════════════════════════════════════════════════╗
    ║  NANO Assertion Report                                           ║
    ╠══════════════════════════════════════════════════════════════════╣
    ║  Suite      NANO  ·  DSL自定义语言测试Suite                      ║
    ║  Solution   weather_solution.yaml                                ║
    ...
    ╚══════════════════════════════════════════════════════════════════╝
    """
    def _ts(ts):
        return datetime.fromtimestamp(ts).strftime('%Y-%m-%d  %H:%M:%S') if ts else '-'

    solution  = suite_info.get('solution', '-') or '-'
    define    = suite_info.get('define', '-') or '-'
    sname     = suite_info.get('suite_name', 'NANO') or 'NANO'
    sabstract = suite_info.get('suite_abstract', '') or ''
    mgo       = suite_info.get('mgo', '-') or '-'
    caselist  = suite_info.get('caselist', '-') or '-'

    suite_display = f'{sname}  ·  {sabstract}' if sabstract else sname

    rows = [
        ('Suite',    suite_display),
        ('Solution', solution),
        ('Define',   define),
        ('MGO',      mgo),
        ('Caselist', caselist),
        ('Started',  _ts(start_ts)),
        ('Finished', _ts(end_ts)),
        ('Cases',    f'{case_total} total'),
    ]

    title_content = '  NANO Assertion Report'
    all_contents = [title_content] + [f'  {label:<10}{value}' for label, value in rows]
    W = max(HEADER_WIDTH, max(_dw(c) for c in all_contents) + 2)
    inner = W - 2

    def _row(label: str, value: str) -> str:
        content = f'  {label:<10}{value}'
        pad     = max(0, inner - _dw(content))
        return f'║{content}{" " * pad}║'

    title_content = '  NANO Assertion Report'
    title_pad     = max(0, inner - _dw(title_content))

    lines = [
        '╔' + '═' * inner + '╗',
        f'║{title_content}{" " * title_pad}║',
        '╠' + '═' * inner + '╣',
    ]
    for label, value in rows:
        lines.append(_row(label, value))
    lines.append('╚' + '═' * inner + '╝')

    return '\n'.join(lines) + '\n'


def _build_summary_block(total_cases: int,  passed_cases: int,
                         total_asserts: int, passed_asserts: int) -> str:
    """
    构建固定宽度（HEADER_WIDTH）的 Summary 块。

    ╔══════════════════════════════════════════════════════════════════╗
    ║ SUMMARY   Cases   Total:12  Pass:11  Fail:1    Pass Rate:91.67%  ║
    ║           Asserts Total:28  Pass:26  Fail:2    Pass Rate:92.86%  ║
    ╚══════════════════════════════════════════════════════════════════╝
    """
    failed_c = total_cases   - passed_cases
    failed_a = total_asserts - passed_asserts
    rate_c   = (passed_cases   / total_cases   * 100) if total_cases   > 0 else 0.0
    rate_a   = (passed_asserts / total_asserts * 100) if total_asserts > 0 else 0.0

    line1 = (f' SUMMARY   Cases   Total:{total_cases}  Pass:{passed_cases}  '
             f'Fail:{failed_c}    Pass Rate:{rate_c:.2f}%')
    line2 = (f'           Asserts Total:{total_asserts}  Pass:{passed_asserts}  '
             f'Fail:{failed_a}    Pass Rate:{rate_a:.2f}%')

    W     = max(HEADER_WIDTH, max(_dw(line1), _dw(line2)) + 2)
    inner = W - 2

    def _row(content: str) -> str:
        pad = max(0, inner - _dw(content))
        return f'║{content}{" " * pad}║'

    lines = [
        '╔' + '═' * inner + '╗',
        _row(line1),
        _row(line2),
        '╚' + '═' * inner + '╝',
    ]
    return '\n'.join(lines) + '\n'


def _build_case_block(dsl_case,
                      asserts: List[_AssertRecord],
                      audio_paths: List[str]) -> str:
    """
    构建单个 Case 的文本块（动态宽度）。

    ┌─[CASE 0][15-28][3-3]─────────────────────────── PASS   ─────────────────────┐
    │  Bref    今天天气查询-普通话                                                  │
    │  Audio   Test/Case/weather/cmn_01.wav                                        │
    │  #1 [预期][NLPResult] [0]text:你好;skill:WakeUp                              │
    │     [实际][NLPResult] [0]text:你好;skill:WakeUp                       PASS   │
    └──────────────────────────────────────────────────────────────────────────────┘
    """
    # ── 1. 构建标题 ID ──
    idx      = str(dsl_case.index)
    mgo_r    = dsl_case.case_line_range or ''
    csv_r    = dsl_case.param_line_range
    title_id = (f'[CASE {idx}][{mgo_r}][{csv_r}]' if csv_r
                else f'[CASE {idx}][{mgo_r}]')

    case_passed = (all(a.status == AssertionStatus.SUCCESS for a in asserts)
                   if asserts else True)
    result_str  = 'PASS' if case_passed else 'FAIL'

    # ── 2. 收集内容项 ──
    # 每项：(display_text, status_str_or_None)
    # status_str 非 None 时，该字符串右对齐附在行末（"   PASS" / "   FAIL"）
    items: List[Tuple[str, Optional[str]]] = []

    bref = dsl_case.comment or ''
    if bref:
        items.append((f'  Bref    {bref}', None))

    for audio in audio_paths:
        items.append((f'  Audio   {audio}', None))

    for rec in asserts:
        exp = f'  #{rec.index} [预期][{rec.callback_type}] [{rec.channel_id}]{rec.expect_infos}'
        act = f'     [实际][{rec.callback_type}] [{rec.channel_id}]{rec.actual_infos}'
        st  = 'PASS' if rec.status == AssertionStatus.SUCCESS else 'FAIL'
        items.append((exp, None))
        items.append((act, st))

    # ── 3. 计算 Case 框内容区宽度（动态撑宽）──
    # 普通行需要：dw(text)
    # 状态行需要：dw(text) + len('   PASS') = dw(text) + 7
    inner_w = MIN_CASE_INNER

    for text, status in items:
        needed  = _dw(text) + (7 if status else 0)
        inner_w = max(inner_w, needed)

    # 标题行约束：
    # '┌─' + title_id + fill(>=1) + ' PASS   ─────┐' = total_w
    # total_w = inner_w + 4
    # fill = total_w - 2 - len(title_id) - _STATUS_RIGHT_LEN >= 1
    # => inner_w >= len(title_id) + _STATUS_RIGHT_LEN - 2
    inner_w = max(inner_w, len(title_id) + _STATUS_RIGHT_LEN - 2)

    total_w = inner_w + 4   # │ + space + inner_w + space + │

    # ── 4. 构建顶部和底部边框 ──
    right_part  = f' {result_str}   ─────┐'          # 固定 14 字符
    left_part   = f'┌─{title_id}'
    fill_len    = total_w - len(left_part) - len(right_part)
    top_line    = left_part + '─' * fill_len + right_part
    bottom_line = '└' + '─' * (total_w - 2) + '┘'

    # ── 5. 构建内容行 ──
    content_lines = []
    for text, status in items:
        if status is None:
            content_lines.append(_inner_line(text, inner_w))
        else:
            # 状态行：内容 + 空格 + '   PASS/FAIL'，总显示宽 = inner_w
            status_part = f'   {status}'              # 3 空格 + PASS/FAIL = 7 字符
            pad = max(0, inner_w - _dw(text) - len(status_part))
            content_lines.append(f'│ {text}{" " * pad}{status_part} │')

    if not items:
        content_lines.append(_inner_line('  (no assertions)', inner_w))

    # ── 6. 拼装 ──
    block = '\n'.join([top_line] + content_lines + [bottom_line, ''])
    return block + '\n'


# ══════════════════════════════════════════════════════════════════
#  Worker 文件解析
# ══════════════════════════════════════════════════════════════════

def _parse_worker_file(filepath: str) -> List[Tuple[str, str]]:
    """
    从 Worker 文件中解析所有 Case 块。
    返回 [(case_index_str, block_text), ...] 列表。

    Case 块以 '┌─[CASE' 开头，以 '└' 开头的行结束（含后续空行）。
    """
    results: List[Tuple[str, str]] = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        logger.error(f'[TextReporter] 读取 Worker 文件失败: {filepath} → {e}')
        return results

    in_block    = False
    block_lines = []
    index_str   = '?'

    for line in lines:
        stripped = line.rstrip('\n')

        if not in_block:
            if stripped.startswith('┌─[CASE'):
                in_block    = True
                block_lines = [stripped]
                m = re.search(r'\[CASE\s+([^\]]+)\]', stripped)
                index_str = m.group(1).strip() if m else '?'
        else:
            block_lines.append(stripped)
            if stripped.startswith('└'):
                # 块结束（追加空行保留格式）
                block_lines.append('')
                results.append((index_str, '\n'.join(block_lines) + '\n'))
                in_block    = False
                block_lines = []

    return results


def _count_stats_from_blocks(all_blocks: List[Tuple[str, str]]) -> Tuple[int, int, int, int]:
    """
    从 Case 块文本统计：(total_cases, passed_cases, total_asserts, passed_asserts)

    判断规则：
    - 包含 '[实际]' 的行是断言实际行。
    - 行末匹配 'PASS   │' → 该断言通过。
    - Case 所有断言均通过（或无断言）→ Case 通过。
    """
    total_cases    = len(all_blocks)
    passed_cases   = 0
    total_asserts  = 0
    passed_asserts = 0

    for _, block_text in all_blocks:
        case_total  = 0
        case_passed = 0

        for line in block_text.split('\n'):
            if '[实际]' not in line:
                continue
            case_total    += 1
            total_asserts += 1
            # 状态在行末：'   PASS │' 中 PASS 后跟空格再 │
            if re.search(r'PASS\s+│\s*$', line):
                case_passed    += 1
                passed_asserts += 1

        if case_total == 0 or case_passed == case_total:
            passed_cases += 1

    return total_cases, passed_cases, total_asserts, passed_asserts


# ══════════════════════════════════════════════════════════════════
#  主类
# ══════════════════════════════════════════════════════════════════

class AssertionTextReporter:
    """
    NANO 断言纯文本报告器。

    Worker 实例负责：
        begin_case(dsl_case)   → 接收新 Case
        record(expectation)    → 记录断言结果（由 AssertionEngine 调用）
        flush_case()           → 将当前 Case 块写入 Worker 文件

    Controller 通过静态方法完成最终合并（并删除 Worker 临时文件）：
        merge_worker_reports(suite_dir, final_path, suite_info)
    """

    def __init__(self, report_path: str, suite_info: dict):
        """
        Args:
            report_path: Worker 临时文件路径，如 suite_dir/result_gw0.txt
            suite_info:  包含 solution/define/suite_name/suite_abstract/mgo/caselist 的字典
        """
        self._report_path = report_path
        self._suite_info  = suite_info
        self._lock        = threading.Lock()
        self._current_case: Optional[_CaseRecord] = None

        os.makedirs(os.path.dirname(os.path.abspath(report_path)), exist_ok=True)
        # 清空或创建文件
        open(report_path, 'w', encoding='utf-8').close()

    # ── 公开 API ──────────────────────────────────────────────────

    def begin_case(self, dsl_case) -> None:
        """
        Case 开始时调用（execute_case 最开头，commands 执行前）。
        若上一个 Case 未正常结束，强制刷写。
        """
        with self._lock:
            if self._current_case is not None:
                logger.warning(
                    f'[TextReporter] Case {self._current_case.dsl_case.index} '
                    f'未调用 flush_case，强制刷写'
                )
                self._flush_locked()
            self._current_case = _CaseRecord(dsl_case=dsl_case)

    def record(self, expectation: AssertionExpectation) -> None:
        """
        每次断言结束后调用（AssertionEngine.do_assertion 末尾、return 之前）。
        """
        with self._lock:
            if self._current_case is None:
                return
            idx = len(self._current_case.asserts) + 1
            self._current_case.asserts.append(_AssertRecord(
                index         = idx,
                callback_type = expectation.callback_type or '',
                channel_id    = expectation.channel_id or '0',
                status        = expectation.status,
                expect_infos  = expectation.expect_infos or '',
                actual_infos  = expectation.actual_infos or '',
            ))

    def flush_case(self) -> None:
        """
        Case 结束时调用（execute_case 末尾，在 commit_log_pointers 之后）。
        此时 commands 的环境变量已替换，音频路径可正确提取。
        """
        with self._lock:
            if self._current_case is None:
                return
            self._flush_locked()

    # ── 内部 ──────────────────────────────────────────────────────

    def _flush_locked(self) -> None:
        """将当前 Case 块写入 Worker 文件（调用前须已持锁）。"""
        case_record = self._current_case
        self._current_case = None

        dsl_case    = case_record.dsl_case
        asserts     = case_record.asserts
        audio_paths = _extract_audio_paths(dsl_case)

        block_text = _build_case_block(dsl_case, asserts, audio_paths)

        try:
            with open(self._report_path, 'a', encoding='utf-8') as f:
                f.write(block_text)
        except Exception as e:
            logger.error(f'[TextReporter] 写 Worker 文件失败: {e}')

    # ── 静态合并方法（Controller 调用） ───────────────────────────

    @staticmethod
    def merge_worker_reports(suite_dir: str,
                             final_path: str,
                             suite_info: dict) -> None:
        """
        将 suite_dir 下所有 result_gw*.txt / result_main.txt 合并为 result.txt，
        合并成功后删除所有 Worker 临时文件。

        Args:
            suite_dir:   Worker 临时文件所在目录（= --mongo_suite_dir）
            final_path:  最终报告路径（= suite_dir/result.txt）
            suite_info:  包含以下键的字典：
                         solution, define, suite_name, suite_abstract,
                         mgo, caselist, start_time (float 或 None)
        """
        end_ts   = time.time()
        start_ts = suite_info.get('start_time')

        # 1. 收集 Worker 文件
        worker_files: List[str] = []
        for pat in [
            os.path.join(suite_dir, 'result_gw*.txt'),
            os.path.join(suite_dir, 'result_main.txt'),
        ]:
            worker_files.extend(glob.glob(pat))

        if not worker_files:
            logger.warning(f'[TextReporter] 未找到 Worker 报告文件，跳过合并: {suite_dir}')
            return

        # 2. 解析所有 Case 块
        all_blocks: List[Tuple[str, str]] = []
        for wf in sorted(worker_files):
            blocks = _parse_worker_file(wf)
            all_blocks.extend(blocks)
            logger.debug(f'[TextReporter] {os.path.basename(wf)} → {len(blocks)} 个 Case 块')

        if not all_blocks:
            logger.warning(f'[TextReporter] 所有 Worker 文件均无有效 Case 块')
            return

        # 3. 按 case.index 排序
        all_blocks.sort(key=lambda x: _sort_key(x[0]))

        # 4. 统计
        total_cases, passed_cases, total_asserts, passed_asserts = \
            _count_stats_from_blocks(all_blocks)

        # 5. 一次性写入最终文件, 按顶部边框里的 PASS/FAIL 标记拆分两组，顺序保持不变
        pass_blocks = [(i, b) for i, b in all_blocks if 'PASS   ─────┐' in b.split('\n')[0]]
        fail_blocks = [(i, b) for i, b in all_blocks if 'FAIL   ─────┐' in b.split('\n')[0]]

        def _section_divider(label: str, count: int, width: int) -> str:
            tag   = f'  {label} ({count})  '
            dashes = '─' * max(0, width - len(tag))
            return tag + dashes + '\n\n'

        try:
            with open(final_path, 'w', encoding='utf-8') as f:
                f.write(_build_header_block(suite_info, start_ts, end_ts, total_cases))
                f.write(_build_summary_block(total_cases, passed_cases, total_asserts, passed_asserts))
                f.write('\n')

                # FAIL 区
                if fail_blocks:
                    sample_w = len(fail_blocks[0][1].split('\n')[0])
                    f.write(_section_divider('FAIL', len(fail_blocks), sample_w))
                    for _, block_text in fail_blocks:
                        f.write(block_text)

                # PASS 区
                if pass_blocks:
                    # 取第一个块的行宽作为分隔线宽度基准
                    sample_w = len(pass_blocks[0][1].split('\n')[0])
                    f.write(_section_divider('PASS', len(pass_blocks), sample_w))
                    for _, block_text in pass_blocks:
                        f.write(block_text)

            logger.info(
                f'[TextReporter] result.txt 已生成: {final_path}  '
                f'Cases {passed_cases}/{total_cases}  '
                f'Asserts {passed_asserts}/{total_asserts}'
            )

            # 6. 删除 Worker 临时文件
            for wf in worker_files:
                try:
                    os.remove(wf)
                    logger.debug(f'[TextReporter] 已删除 Worker 文件: {os.path.basename(wf)}')
                except Exception as remove_err:
                    logger.warning(f'[TextReporter] 删除 Worker 文件失败: {wf} → {remove_err}')

        except Exception as e:
            logger.error(f'[TextReporter] 写 result.txt 失败: {e}')
