#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @Time    : 2026/03/04
# @Author  : huidong.bai
# @File    : wakeup_accuracy.py
# @Software: PyCharm
# @Mail    : MasterBai2018@outlook.com
"""
WAKEUP_ACCURACY 指令实现

用于计算唤醒词检测的 FA/FR 准确率，支持：
- False Acceptance (FA) 误检率
- False Rejection  (FR) 漏检率
- 关键词错误率
- 断句 / 连句统计
- 每条音频唤醒率
- 每个唤醒词维度统计

判定规则：
1. 时间重叠 且 result 关键词命中 ref 关键词或其 | 分隔同义表达 = 正确匹配
2. 时间重叠 但 关键词不一致 = 关键词错误（单独统计，不计 FA/FR）
3. 无重叠：ref 有但 result 没有 = FR（漏检）；result 有但 ref 没有 = FA（误检）
4. 断句：1个 ref 段，对应 ≥2 个 result 段且全部重叠且关键词命中（不计 FA/FR）
5. 连句：≥2 个 ref 段，对应 1 个 result 段且全部重叠且关键词命中（不计 FA/FR）

输入文件格式：
  ref   文件：无表头，列顺序为 音频路径,关键词,开始时间(s),结束时间(s)[,channel]；
        列分隔符支持制表符 \\t、英文分号 ;、英文逗号 ,（按此顺序尝试解析每一行）
  result 文件：有表头 CSV，字段为  audio,result,start,end[,channel]

使用示例:
    [TSR]WAKEUP_ACCURACY result=wakeup.csv ref=ref.csv [output=report.xlsx]
"""
import os
import sys
import csv
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
from loguru import logger

# 支持独立运行和作为模块导入两种方式
try:
    from . import register_tsr_command
    from .base import BaseTSRHandler
except ImportError:
    _current_dir = os.path.dirname(os.path.abspath(__file__))
    _project_root = os.path.abspath(os.path.join(_current_dir, '..', '..', '..', '..', '..'))
    if _project_root not in sys.path:
        sys.path.insert(0, _project_root)
    from src.testsuite.NANO.tools.tsr import register_tsr_command
    from src.testsuite.NANO.tools.tsr.base import BaseTSRHandler


# ─── 数据结构 ──────────────────────────────────────────────────────────────────

class WakeupSegment:
    """唤醒时间段"""

    def __init__(
        self,
        audio_path: str,
        keyword: str,
        start: float,
        end: float,
        line_num: int = 0,
        channel: str = "",
    ):
        self.audio_path = audio_path
        self.keyword    = keyword
        self.start      = start
        self.end        = end
        self.line_num   = line_num
        self.channel    = channel
        self.matched    = False

    def has_overlap(self, other: 'WakeupSegment') -> bool:
        """判断两个时间段是否有重叠"""
        return not (other.start >= self.end or other.end <= self.start)

    def is_keyword_match(self, other: 'WakeupSegment') -> bool:
        """判断关键词是否一致；ref 侧支持使用 | 定义多个可接受表达"""
        return bool(self.accepted_keywords & other.accepted_keywords)

    def is_full_match(self, other: 'WakeupSegment') -> bool:
        """判断是否完全匹配（时间重叠 且 关键词一致）"""
        return self.has_overlap(other) and self.is_keyword_match(other)

    @property
    def accepted_keywords(self) -> set:
        """ref keyword 可用 | 分隔多个同义表达；result 通常只有一个词"""
        return {
            _normalize_keyword(alias)
            for alias in self.keyword.split('|')
            if _normalize_keyword(alias)
        }

    def __repr__(self) -> str:
        return (
            f"WakeupSegment({self.audio_path}, {self.keyword}, "
            f"{self.start:.3f}, {self.end:.3f}, channel={self.channel})"
        )


@dataclass
class WakeupAccuracyStats:
    """唤醒准确率汇总统计"""
    total_ref:             int = 0
    total_result:          int = 0
    matched_count:         int = 0
    fa_count:              int = 0
    fr_count:              int = 0
    keyword_error_count:   int = 0
    break_count:           int = 0
    join_count:            int = 0
    channel_check_count:   int = 0
    channel_check_pass:    int = 0
    channel_check_fail:    int = 0
    total_actual_effective:int = 0

    # 明细列表
    fa_segments:           List[WakeupSegment]       = field(default_factory=list)
    fr_segments:           List[WakeupSegment]       = field(default_factory=list)
    keyword_error_cases:   List[Dict]                = field(default_factory=list)
    break_cases:           List[Dict]                = field(default_factory=list)
    join_cases:            List[Dict]                = field(default_factory=list)
    channel_check_cases:   List[Dict]                = field(default_factory=list)
    matched_pairs:         List[Tuple]               = field(default_factory=list)

    # 原始数据（用于 Ref / Signal Sheet 输出）
    all_ref_segments:      List[WakeupSegment]       = field(default_factory=list)
    all_result_segments:   List[WakeupSegment]       = field(default_factory=list)

    # 每条音频的统计
    audio_stats:           Dict[str, Dict]           = field(default_factory=dict)
    keyword_stats:         Dict[str, Dict]           = field(default_factory=dict)
    ref_has_channel:       bool                      = False

    @property
    def fa_rate(self) -> float:
        """误检率 = FA 数 / result 总数"""
        return self.fa_count / self.total_result if self.total_result > 0 else 0.0

    @property
    def fr_rate(self) -> float:
        """漏检率 = FR 数 / ref 总数"""
        return self.fr_count / self.total_ref if self.total_ref > 0 else 0.0

    @property
    def wakeup_rate(self) -> float:
        """
        唤醒率：
        - ref 无 channel： (ref 总数 - FR 数) / ref 总数
        - ref 有 channel： 实际正确音区唤醒数 / ref 总数
        """
        if self.total_ref <= 0:
            return 0.0
        if self.ref_has_channel:
            return self.total_actual_effective / self.total_ref
        return (self.total_ref - self.fr_count) / self.total_ref

    @property
    def keyword_error_rate(self) -> float:
        """关键词错误率 = 关键词错误数 / ref 总数"""
        return self.keyword_error_count / self.total_ref if self.total_ref > 0 else 0.0

    @property
    def channel_check_pass_rate(self) -> float:
        """音区检测通过率 = 通过数 / 音区检测总数"""
        return self.channel_check_pass / self.channel_check_count if self.channel_check_count > 0 else 0.0


# ─── 文件解析 ──────────────────────────────────────────────────────────────────

def _split_ref_line_to_fields(line: str) -> Optional[List[str]]:
    """
    将 ref 文件中的一行文本解析为字段列表：
    - 4列：[音频路径, 关键词, 开始, 结束]
    - 5列：[音频路径, 关键词, 开始, 结束, channel]

    依次尝试分隔符：制表符 \\t、英文分号 ;、英文逗号 ,。
    使用 csv.reader 以支持引号包裹字段（列内含分隔符时）。

    兼容关键词中未加引号但包含分隔符的场景：
    - 无 channel：若列数 > 4 且末两列为时间，则将第 2 列到倒数第 3 列拼回关键词
    - 有 channel：若列数 > 5 且倒数第 3/2 列为时间，则将第 2 列到倒数第 4 列拼回关键词
    """
    text = line.strip()
    if not text:
        return None

    for delim in ('\t', ';', ','):
        try:
            row = next(csv.reader([text], delimiter=delim))
        except csv.Error:
            continue
        if not row:
            continue
        row = [c.strip() for c in row]
        while row and row[-1] == '':
            row.pop()
        if len(row) < 4:
            continue

        # 优先识别「带 channel」格式：..., start, end, channel
        if len(row) >= 5:
            try:
                float(row[-3])
                float(row[-2])
                audio_path = row[0]
                keyword    = delim.join(row[1:-3]).strip()
                channel    = row[-1].strip()
                return [audio_path, keyword, row[-3], row[-2], channel]
            except ValueError:
                pass

        # 再识别「不带 channel」格式：..., start, end
        try:
            float(row[-2])
            float(row[-1])
            audio_path = row[0]
            keyword    = delim.join(row[1:-2]).strip()
            return [audio_path, keyword, row[-2], row[-1]]
        except ValueError:
            continue

    return None


def _parse_ref_file(file_path: str) -> List[WakeupSegment]:
    """
    解析 ref 文件（无表头）
    列顺序：
      - 音频路径, 关键词, 开始时间(s), 结束时间(s)
      - 音频路径, 关键词, 开始时间(s), 结束时间(s), channel
    每行分隔符可为制表符 \\t、英文分号 ; 或英文逗号 ,（按顺序自动尝试）
    """
    segments: List[WakeupSegment] = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line_num, raw_line in enumerate(f, 1):
            row = _split_ref_line_to_fields(raw_line)
            if row is None:
                if raw_line.strip():
                    logger.warning(
                        f"ref 文件第 {line_num} 行格式不正确（需 4 列或 5 列，且时间列可解析），跳过：{raw_line.strip()}"
                    )
                continue
            try:
                audio_path = row[0].strip()
                keyword    = row[1].strip()
                start_time = float(row[2].strip())
                end_time   = float(row[3].strip())
                channel    = row[4].strip() if len(row) >= 5 else ""
                if start_time >= end_time:
                    logger.warning(f"ref 文件第 {line_num} 行 start >= end，跳过")
                    continue
                segments.append(
                    WakeupSegment(audio_path, keyword, start_time, end_time, line_num, channel=channel)
                )
            except (ValueError, IndexError) as e:
                logger.warning(f"ref 文件第 {line_num} 行解析失败，跳过：{e}")
    return segments


def _parse_result_file(file_path: str) -> List[WakeupSegment]:
    """
    解析 result 文件（有表头 CSV）
    字段：audio, result, start, end[, channel]
    """
    segments: List[WakeupSegment] = []
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            logger.warning("result 文件缺少表头，无法解析")
            return segments

        # 兼容字段大小写、首尾空格和 BOM
        field_map: Dict[str, str] = {}
        for raw_name in reader.fieldnames:
            if raw_name is None:
                continue
            normalized = raw_name.strip().lstrip('\ufeff').lower()
            field_map[normalized] = raw_name

        audio_key = field_map.get('audio')
        result_key = field_map.get('result')
        start_key = field_map.get('start')
        end_key = field_map.get('end')
        channel_key = field_map.get('channel')

        if not all([audio_key, result_key, start_key, end_key]):
            logger.warning(
                "result 文件表头缺少必需字段，需包含 audio,result,start,end"
            )
            return segments

        for line_num, row in enumerate(reader, 2):
            try:
                audio_path = (row.get(audio_key) or "").strip()
                keyword    = (row.get(result_key) or "").strip()
                start_time = float((row.get(start_key) or "").strip())
                end_time   = float((row.get(end_key) or "").strip())
                channel    = (row.get(channel_key) or "").strip() if channel_key else ""

                if not audio_path:
                    logger.warning(f"result 文件第 {line_num} 行 audio 为空，跳过")
                    continue
                if not keyword:
                    logger.warning(f"result 文件第 {line_num} 行 result 为空，跳过")
                    continue
                if start_time >= end_time:
                    logger.warning(f"result 文件第 {line_num} 行 start >= end，跳过")
                    continue
                segments.append(
                    WakeupSegment(audio_path, keyword, start_time, end_time, line_num, channel=channel)
                )
            except (KeyError, ValueError, TypeError, AttributeError) as e:
                logger.warning(f"result 文件第 {line_num} 行解析失败，跳过：{e}")
    return segments


def _collect_channel_check_cases(stats: WakeupAccuracyStats) -> List[Dict]:
    """
    汇总唤醒音区检测明细。
    仅在 ref 中存在 channel 标注时启用；以已配对关系为检测样本：
    - 常规匹配 matched_pairs
    - 断句 break_cases（1 ref 对多 result）
    - 连句 join_cases（多 ref 对 1 result）
    """
    if not stats.ref_has_channel:
        return []

    cases: List[Dict] = []

    def _append_case(ref_seg: WakeupSegment, result_seg: WakeupSegment) -> None:
        # 仅统计 ref 有明确 channel 标注的样本
        if not ref_seg.channel:
            return
        check_result = "Pass" if ref_seg.channel == result_seg.channel else "Faild"
        cases.append({
            "audio_path": ref_seg.audio_path,
            "ref": ref_seg,
            "result": result_seg,
            "check_result": check_result,
        })

    for ref_seg, result_seg in stats.matched_pairs:
        _append_case(ref_seg, result_seg)
    for case in stats.break_cases:
        for result_seg in case["result_segments"]:
            _append_case(case["ref"], result_seg)
    for case in stats.join_cases:
        result_seg = case["result"]
        for ref_seg in case["ref_segments"]:
            _append_case(ref_seg, result_seg)

    return cases


def _group_by_audio(segments: List[WakeupSegment]) -> Dict[str, List[WakeupSegment]]:
    """按音频路径分组，并按开始时间排序"""
    grouped: Dict[str, List[WakeupSegment]] = defaultdict(list)
    for seg in segments:
        grouped[seg.audio_path].append(seg)
    for segs in grouped.values():
        segs.sort(key=lambda s: (s.start, s.end))
    return grouped


def _normalize_keyword(keyword: str) -> str:
    """关键词：去首尾空格"""
    return (keyword or "").strip()


def _build_keyword_stats(stats: WakeupAccuracyStats) -> Dict[str, Dict]:
    """
    构建按关键词统计。
    分组键：ref keyword 原始串 strip 后的值；ref keyword 可用 | 分隔多个可接受表达。
    """
    per_kw: Dict[str, Dict] = defaultdict(lambda: {
        'keyword': '',
        'expected': 0,
        'actual_raw': 0,
        'actual': 0,
        'actual_effective': 0,
        'matched': 0,
        'fr': 0,
        'fa': 0,
        'keyword_error': 0,
        'channel_error': 0,
        'wakeup_rate': 0.0,
        'fr_rate': 0.0,
        'fa_rate': 0.0,
        'keyword_error_rate': 0.0,
    })
    alias_to_ref_keywords: Dict[str, set] = defaultdict(set)

    for seg in stats.all_ref_segments:
        kw = _normalize_keyword(seg.keyword)
        per_kw[kw]['keyword'] = kw
        per_kw[kw]['expected'] += 1
        for alias in seg.accepted_keywords:
            alias_to_ref_keywords[alias].add(kw)

    for ref_seg, _ in stats.matched_pairs:
        kw = _normalize_keyword(ref_seg.keyword)
        per_kw[kw]['keyword'] = kw
        per_kw[kw]['actual_raw'] += 1
        per_kw[kw]['matched'] += 1

    for case in stats.break_cases:
        ref_seg = case['ref']
        kw = _normalize_keyword(ref_seg.keyword)
        per_kw[kw]['keyword'] = kw
        per_kw[kw]['actual_raw'] += len(case['result_segments'])
        per_kw[kw]['matched'] += len(case['result_segments'])

    for case in stats.join_cases:
        ref_segs = case['ref_segments']
        if not ref_segs:
            continue
        result_counted_keys = set()
        for ref_seg in ref_segs:
            kw = _normalize_keyword(ref_seg.keyword)
            per_kw[kw]['keyword'] = kw
            per_kw[kw]['matched'] += 1
            if kw not in result_counted_keys:
                per_kw[kw]['actual_raw'] += 1
                result_counted_keys.add(kw)

    for seg in stats.fr_segments:
        kw = _normalize_keyword(seg.keyword)
        per_kw[kw]['keyword'] = kw
        per_kw[kw]['fr'] += 1

    for seg in stats.fa_segments:
        ref_keys = alias_to_ref_keywords.get(_normalize_keyword(seg.keyword), set())
        if len(ref_keys) != 1:
            continue
        kw = next(iter(ref_keys))
        per_kw[kw]['actual_raw'] += 1
        per_kw[kw]['fa'] += 1

    # 关键词错误归属到 ref 词
    for case in stats.keyword_error_cases:
        kw = _normalize_keyword(case['ref'].keyword)
        per_kw[kw]['keyword'] = kw
        per_kw[kw]['actual_raw'] += 1
        per_kw[kw]['keyword_error'] += 1

    if stats.ref_has_channel:
        for case in stats.channel_check_cases:
            if case['check_result'] == "Faild":
                kw = _normalize_keyword(case['ref'].keyword)
                per_kw[kw]['keyword'] = kw
                per_kw[kw]['channel_error'] += 1

    for kw, s in per_kw.items():
        expected = s['expected']
        actual_raw = s['actual_raw']
        fr = s['fr']
        fa = s['fa']
        ke = s['keyword_error']
        channel_error = s['channel_error']

        if stats.ref_has_channel:
            actual_effective = max(actual_raw - channel_error, 0)
        else:
            actual_effective = max(expected - fr, 0)
        s['actual'] = actual_effective
        s['actual_effective'] = actual_effective
        s['wakeup_rate'] = (actual_effective / expected) if expected > 0 else 0.0
        s['fr_rate'] = (fr / expected) if expected > 0 else 0.0
        s['fa_rate'] = (fa / actual_raw) if actual_raw > 0 else 0.0
        s['keyword_error_rate'] = (ke / expected) if expected > 0 else 0.0
        s['keyword'] = kw

    return dict(per_kw)


# ─── 核心匹配算法（修复版：支持多段音频内的断句/连句检测）────────────────────────

def _process_audio_segments(
    ref_segs: List[WakeupSegment],
    result_segs: List[WakeupSegment],
) -> Tuple[
    List[Tuple[WakeupSegment, WakeupSegment]],  # matched_pairs
    List[WakeupSegment],                         # fa_segments
    List[WakeupSegment],                         # fr_segments
    List[Dict],                                  # keyword_error_cases
    List[Dict],                                  # break_cases
    List[Dict],                                  # join_cases
]:
    """
    处理单个音频的唤醒段匹配（修复版）

    修复说明：
    - 原版仅在整个音频恰好是 1段ref/多段result（或反之）时检测断句/连句；
      当音频中有多条 ref 时，即使某一对存在断句/连句，也会退化为常规匹配。
    - 修复后：先遍历每个 ref/result 段，逐段检测断句和连句，再做常规匹配。

    匹配优先级：
      1. 断句检测（1 ref → ≥2 result，全部完全匹配）
      2. 连句检测（≥2 ref → 1 result，全部完全匹配）
      3. 常规 1-to-1 匹配（时间重叠 + 关键词一致）
      4. 关键词错误检测（时间重叠 但 关键词不一致）
      5. 剩余 ref → FR；剩余 result → FA
    """
    # 重置匹配状态
    for seg in ref_segs:    seg.matched = False
    for seg in result_segs: seg.matched = False

    matched_pairs:       List[Tuple] = []
    fa_segments:         List[WakeupSegment] = []
    fr_segments:         List[WakeupSegment] = []
    keyword_error_cases: List[Dict] = []
    break_cases:         List[Dict] = []
    join_cases:          List[Dict] = []

    # ── Step 1：断句检测 ─────────────────────────────────────────────────────
    # 对每个未匹配的 ref 段，统计有多少个未匹配的 result 段与它完全匹配
    for ref_seg in ref_segs:
        if ref_seg.matched:
            continue
        full_match_indices = [
            i for i, r in enumerate(result_segs)
            if not r.matched and ref_seg.is_full_match(r)
        ]
        if len(full_match_indices) >= 2:
            # 断句：1 ref → ≥2 result
            for idx in full_match_indices:
                result_segs[idx].matched = True
            ref_seg.matched = True
            break_cases.append({
                'audio_path':      ref_seg.audio_path,
                'ref':             ref_seg,
                'result_segments': [result_segs[i] for i in full_match_indices],
                'result_indices':  full_match_indices,
            })

    # ── Step 2：连句检测 ─────────────────────────────────────────────────────
    # 对每个未匹配的 result 段，统计有多少个未匹配的 ref 段与它完全匹配
    for result_seg in result_segs:
        if result_seg.matched:
            continue
        full_match_indices = [
            i for i, r in enumerate(ref_segs)
            if not r.matched and result_seg.is_full_match(r)
        ]
        if len(full_match_indices) >= 2:
            # 连句：≥2 ref → 1 result
            for idx in full_match_indices:
                ref_segs[idx].matched = True
            result_seg.matched = True
            join_cases.append({
                'audio_path':   result_seg.audio_path,
                'ref_segments': [ref_segs[i] for i in full_match_indices],
                'ref_indices':  full_match_indices,
                'result':       result_seg,
            })

    # ── Step 3：常规 1-to-1 匹配 ─────────────────────────────────────────────
    # 对剩余未匹配的 ref 段，找第一个未匹配的完全匹配 result 段
    for ref_seg in ref_segs:
        if ref_seg.matched:
            continue
        match_idx = next(
            (i for i, r in enumerate(result_segs)
             if not r.matched and ref_seg.is_full_match(r)),
            None
        )
        if match_idx is not None:
            result_segs[match_idx].matched = True
            ref_seg.matched = True
            matched_pairs.append((ref_seg, result_segs[match_idx]))

    # ── Step 4：关键词错误检测 ────────────────────────────────────────────────
    # 时间重叠但关键词不一致的，不计 FR（ref 侧）也不计 FA（result 侧）
    for ref_seg in ref_segs:
        if ref_seg.matched:
            continue
        mismatch_indices = [
            i for i, r in enumerate(result_segs)
            if not r.matched and ref_seg.has_overlap(r) and not ref_seg.is_keyword_match(r)
        ]
        if mismatch_indices:
            for mi in mismatch_indices:
                result_segs[mi].matched = True
                keyword_error_cases.append({
                    'audio_path': ref_seg.audio_path,
                    'ref':        ref_seg,
                    'result':     result_segs[mi],
                })
            ref_seg.matched = True  # 关键词错误不计 FR

    # ── Step 5：剩余未匹配段统计 FA / FR ─────────────────────────────────────
    for ref_seg in ref_segs:
        if not ref_seg.matched:
            fr_segments.append(ref_seg)
    for result_seg in result_segs:
        if not result_seg.matched:
            fa_segments.append(result_seg)

    return matched_pairs, fa_segments, fr_segments, keyword_error_cases, break_cases, join_cases


def _calculate_stats(ref_file: str, result_file: str) -> WakeupAccuracyStats:
    """读取文件、分组、逐音频匹配，汇总统计结果"""
    ref_segments    = _parse_ref_file(ref_file)
    result_segments = _parse_result_file(result_file)

    logger.info(f"ref 文件共 {len(ref_segments)} 条记录")
    logger.info(f"result 文件共 {len(result_segments)} 条记录")

    ref_grouped    = _group_by_audio(ref_segments)
    result_grouped = _group_by_audio(result_segments)
    all_audio_paths = set(ref_grouped.keys()) | set(result_grouped.keys())

    stats = WakeupAccuracyStats(
        total_ref=len(ref_segments),
        total_result=len(result_segments),
        all_ref_segments=ref_segments,
        all_result_segments=result_segments,
        ref_has_channel=any(bool(seg.channel) for seg in ref_segments),
    )

    for audio_path in sorted(all_audio_paths):
        ref_segs    = ref_grouped.get(audio_path, [])
        result_segs = result_grouped.get(audio_path, [])

        mp, fa, fr, ke, bk, jn = _process_audio_segments(ref_segs, result_segs)

        stats.matched_pairs.extend(mp)
        stats.fa_segments.extend(fa)
        stats.fr_segments.extend(fr)
        stats.keyword_error_cases.extend(ke)
        stats.break_cases.extend(bk)
        stats.join_cases.extend(jn)

        expected = len(ref_segs)
        fr_n = len(fr)
        fa_n = len(fa)
        actual_raw = len(result_segs)
        wk_rate = ((expected - fr_n) / expected * 100.0) if expected > 0 else 0.0
        stats.audio_stats[audio_path] = {
            'expected': expected,
            'actual_raw': actual_raw,
            'actual': actual_raw,
            'actual_effective': actual_raw,
            'channel_error': 0,
            'fr': fr_n,
            'fa': fa_n,
            'wakeup_rate': wk_rate,
        }

    stats.matched_count       = len(stats.matched_pairs)
    stats.fa_count            = len(stats.fa_segments)
    stats.fr_count            = len(stats.fr_segments)
    stats.keyword_error_count = len(stats.keyword_error_cases)
    stats.break_count         = len(stats.break_cases)
    stats.join_count          = len(stats.join_cases)
    stats.channel_check_cases = _collect_channel_check_cases(stats)
    stats.channel_check_count = len(stats.channel_check_cases)
    stats.channel_check_pass  = len([c for c in stats.channel_check_cases if c["check_result"] == "Pass"])
    stats.channel_check_fail  = len([c for c in stats.channel_check_cases if c["check_result"] == "Faild"])
    stats.total_actual_effective = stats.total_ref - stats.fr_count

    if stats.ref_has_channel:
        # 音区错误按“唤醒结果条数”统计：时间匹配+关键词匹配但 channel 不一致
        channel_fail_by_audio: Dict[str, int] = defaultdict(int)
        for case in stats.channel_check_cases:
            if case["check_result"] == "Faild":
                channel_fail_by_audio[case["audio_path"]] += 1

        total_actual_effective = 0
        for audio_path, audio_stat in stats.audio_stats.items():
            channel_error = channel_fail_by_audio.get(audio_path, 0)
            actual_effective = max(audio_stat["actual_raw"] - channel_error, 0)
            expected = audio_stat["expected"]
            wakeup_rate = (actual_effective / expected * 100.0) if expected > 0 else 0.0
            audio_stat["channel_error"] = channel_error
            audio_stat["actual"] = actual_effective
            audio_stat["actual_effective"] = actual_effective
            audio_stat["wakeup_rate"] = wakeup_rate
            total_actual_effective += actual_effective
        stats.total_actual_effective = total_actual_effective

    stats.keyword_stats = _build_keyword_stats(stats)

    return stats


# ─── TSR 指令处理器 ───────────────────────────────────────────────────────────

@register_tsr_command("WAKEUP_ACCURACY")
class WakeupAccuracyHandler(BaseTSRHandler):
    """
    唤醒词 FA/FR 准确率计算处理器

    指令格式:
        [TSR]WAKEUP_ACCURACY result=<result_csv> ref=<ref_csv> [output=<report_xlsx>]

    参数说明:
        result : 识别结果 CSV 文件路径，有表头（audio,result,start,end[,channel]）（必需）
        ref    : 参考唤醒文件路径，无表头（音频路径,关键词,开始时间,结束时间[,channel]）；
                 列分隔符支持 \\t、;、,（必需）
        output : Excel 报告输出路径（可选，默认在 suite_dir/mango_report 下生成）
    """

    COMMAND_NAME = "WAKEUP_ACCURACY"

    def execute(self, params: list, output_report: str = None) -> str:
        """执行唤醒准确率计算"""
        result_file, ref_file, xlsx_path, output_was_specified = self._parse_params(
            params, output_report
        )

        if not os.path.exists(result_file):
            raise FileNotFoundError(f"识别结果文件不存在: {result_file}")
        if not os.path.exists(ref_file):
            raise FileNotFoundError(f"参考唤醒文件不存在: {ref_file}")

        logger.info(f"WAKEUP_ACCURACY: result={result_file}, ref={ref_file}")

        stats = _calculate_stats(ref_file, result_file)

        # 生成 Excel 报告（含按关键词统计）
        self._generate_excel_report(stats, ref_file, result_file, xlsx_path)

        # 生成 HTML 报告（保存到 allure_result/mango_report/{define}/{suite}/）
        html_content  = self._build_wakeup_html(stats)
        html_filename = "wakeup_accuracy.html"
        self.save_html_report(html_content, html_filename, "唤醒词 FA/FR 报告", "wakeup_accuracy")

        # 本地副本（与 xlsx 同目录）
        local_html = os.path.splitext(xlsx_path)[0] + '.html'
        os.makedirs(os.path.dirname(local_html) or '.', exist_ok=True)
        with open(local_html, 'w', encoding='utf-8') as f:
            f.write(html_content)
        logger.info(f"本地 HTML 报告已生成: {local_html}")

        return self._generate_summary(stats, xlsx_path)

    # ── 参数解析 ──────────────────────────────────────────────────────────────

    def _parse_params(
        self, params: list, default_output: str = None
    ) -> Tuple[str, str, str, bool]:
        """
        解析参数，返回 (result_file, ref_file, xlsx_path, output_was_specified)
        """
        result_file = None
        ref_file    = None
        output_path = default_output

        for param in params:
            if   param.startswith("result="):
                result_file = param[7:]
            elif param.startswith("ref="):
                ref_file    = param[4:]
            elif param.startswith("output="):
                output_path = param[7:]

        if not result_file:
            raise ValueError("缺少必需参数: result=<result_csv>")
        if not ref_file:
            raise ValueError("缺少必需参数: ref=<ref_csv>")

        output_was_specified = output_path is not None
        if not output_path:
            suite_mango_dir = self._get_suite_mango_dir()
            output_path     = os.path.join(suite_mango_dir, "wakeup_accuracy.xlsx")

        return result_file, ref_file, output_path, output_was_specified

    # ── HTML 报告 ─────────────────────────────────────────────────────────────

    def generate_html_report(self, *args, **kwargs) -> Optional[str]:
        """实现抽象方法：generate_html_report(stats) → Optional[str]"""
        stats = args[0] if args else kwargs.get('stats')
        if stats is None:
            return None
        html = self._build_wakeup_html(stats)
        return self.save_html_report(html, "wakeup_accuracy.html", "唤醒词 FA/FR 报告", "wakeup_accuracy")

    def _build_wakeup_html(self, stats: WakeupAccuracyStats) -> str:
        """根据 WakeupAccuracyStats 构建自包含 HTML"""

        # ── 汇总卡片 ──────────────────────────────────────────────────────────
        wk_cls  = 'card-success' if stats.wakeup_rate  >= 0.95 else (
                  'card-warning' if stats.wakeup_rate  >= 0.80 else 'card-failure')
        fa_cls  = 'card-success' if stats.fa_rate      <= 0.05 else (
                  'card-warning' if stats.fa_rate      <= 0.10 else 'card-failure')
        fr_cls  = 'card-success' if stats.fr_rate      <= 0.05 else (
                  'card-warning' if stats.fr_rate      <= 0.10 else 'card-failure')

        cards_html = (
            '<div class="summary-cards">'
            f'<div class="card"><div class="card-value">{stats.total_ref}</div>'
            f'<div class="card-label">Ref 总数</div></div>'
            f'<div class="card"><div class="card-value">{stats.total_result}</div>'
            f'<div class="card-label">Result 总数</div></div>'
            f'<div class="card card-success"><div class="card-value">{stats.matched_count}</div>'
            f'<div class="card-label">匹配数</div></div>'
            f'<div class="card {wk_cls}"><div class="card-value">{stats.wakeup_rate * 100:.2f}%</div>'
            f'<div class="card-label">唤醒率</div></div>'
            f'<div class="card {fa_cls}"><div class="card-value">{stats.fa_rate * 100:.2f}%</div>'
            f'<div class="card-label">FA 误检率</div></div>'
            f'<div class="card {fr_cls}"><div class="card-value">{stats.fr_rate * 100:.2f}%</div>'
            f'<div class="card-label">FR 漏检率</div></div>'
            f'<div class="card card-warning"><div class="card-value">{stats.break_count}</div>'
            f'<div class="card-label">断句数</div></div>'
            f'<div class="card card-warning"><div class="card-value">{stats.join_count}</div>'
            f'<div class="card-label">连句数</div></div>'
            + (
                f'<div class="card {"card-success" if stats.channel_check_fail == 0 else "card-warning"}">'
                f'<div class="card-value">{stats.channel_check_fail}</div>'
                f'<div class="card-label">音区检测失败数</div></div>'
                if stats.ref_has_channel else ''
            ) +
            f'</div>'
        )

        # ── Tab 1：每条音频统计 ────────────────────────────────────────────────
        audio_rows = ''
        for audio_path in sorted(stats.audio_stats.keys()):
            s = stats.audio_stats[audio_path]
            wk = s['wakeup_rate']
            row_cls = ('tag-fail' if wk < 80 else ('tag-pass' if wk >= 95 else 'tag-warn'))
            channel_error_col = f'<td>{s["channel_error"]}</td>' if stats.ref_has_channel else ''
            audio_rows += (
                f'<tr>'
                f'<td>{audio_path}</td>'
                f'<td>{s["expected"]}</td><td>{s["actual"]}</td>'
                f'<td>{s["fr"]}</td><td>{s["fa"]}</td>'
                f'{channel_error_col}'
                f'<td><span class="{row_cls}">{wk:.2f}%</span></td>'
                f'</tr>'
            )
        channel_error_hdr = '<th>音区错误</th>' if stats.ref_has_channel else ''
        tab1_html = (
            '<table class="report-table"><thead>'
            '<tr><th>音频文件</th><th>预期唤醒数</th><th>实际唤醒数</th>'
            f'<th>FR</th><th>FA</th>{channel_error_hdr}<th>唤醒率</th></tr>'
            f'</thead><tbody>{audio_rows}</tbody></table>'
        )

        # ── Tab 2：FA 详情 ─────────────────────────────────────────────────────
        fa_rows = ''.join(
            f'<tr><td>{i}</td><td>{s.audio_path}</td>'
            f'<td>{s.keyword}</td><td>{s.start:.3f}</td><td>{s.end:.3f}</td>'
            f'<td>{s.end - s.start:.3f}</td></tr>'
            for i, s in enumerate(stats.fa_segments, 1)
        )
        tab2_html = (
            '<table class="report-table"><thead>'
            '<tr><th>#</th><th>音频</th><th>关键词</th>'
            '<th>开始(s)</th><th>结束(s)</th><th>时长(s)</th></tr>'
            f'</thead><tbody>{fa_rows}</tbody></table>'
        )

        # ── Tab 3：FR 详情 ─────────────────────────────────────────────────────
        fr_rows = ''.join(
            f'<tr><td>{i}</td><td>{s.audio_path}</td>'
            f'<td>{s.keyword}</td><td>{s.start:.3f}</td><td>{s.end:.3f}</td>'
            f'<td>{s.end - s.start:.3f}</td></tr>'
            for i, s in enumerate(stats.fr_segments, 1)
        )
        tab3_html = (
            '<table class="report-table"><thead>'
            '<tr><th>#</th><th>音频</th><th>关键词</th>'
            '<th>开始(s)</th><th>结束(s)</th><th>时长(s)</th></tr>'
            f'</thead><tbody>{fr_rows}</tbody></table>'
        )

        # ── Tab 4：关键词错误 ──────────────────────────────────────────────────
        ke_rows = ''.join(
            f'<tr><td>{i}</td><td>{c["ref"].audio_path}</td>'
            f'<td>{c["ref"].keyword}</td><td>{c["result"].keyword}</td>'
            f'<td>{c["ref"].start:.3f}</td><td>{c["ref"].end:.3f}</td></tr>'
            for i, c in enumerate(stats.keyword_error_cases, 1)
        )
        tab4_html = (
            '<table class="report-table"><thead>'
            '<tr><th>#</th><th>音频</th><th>参考关键词</th><th>识别关键词</th>'
            '<th>开始(s)</th><th>结束(s)</th></tr>'
            f'</thead><tbody>{ke_rows}</tbody></table>'
        )

        # ── Tab 5：唤醒音区检测 ────────────────────────────────────────────────
        cc_rows = ''.join(
            f'<tr><td>{i}</td><td>{c["ref"].audio_path}</td>'
            f'<td>{c["ref"].keyword}</td><td>{c["ref"].start:.3f}</td><td>{c["ref"].end:.3f}</td>'
            f'<td>{c["ref"].channel}</td>'
            f'<td>{c["result"].keyword}</td><td>{c["result"].start:.3f}</td><td>{c["result"].end:.3f}</td>'
            f'<td>{c["result"].channel}</td>'
            f'<td>{"✅ Pass" if c["check_result"] == "Pass" else "❌ Faild"}</td></tr>'
            for i, c in enumerate(stats.channel_check_cases, 1)
        )
        tab5_html = (
            '<table class="report-table"><thead>'
            '<tr><th>#</th><th>音频</th><th>参考关键词</th><th>参考开始(s)</th><th>参考结束(s)</th>'
            '<th>参考channel</th><th>实际关键词</th><th>实际开始(s)</th><th>实际结束(s)</th>'
            '<th>实际channel</th><th>检测结果</th></tr>'
            f'</thead><tbody>{cc_rows}</tbody></table>'
        )

        # ── Tab 6：按关键词统计 ────────────────────────────────────────────────
        kw_rows = ''
        for kw in sorted(stats.keyword_stats.keys()):
            s = stats.keyword_stats[kw]
            wk = s['wakeup_rate'] * 100.0
            kw_display = kw if kw else '<empty>'
            row_cls = ('tag-fail' if wk < 80 else ('tag-pass' if wk >= 95 else 'tag-warn'))
            channel_error_col = f'<td>{s["channel_error"]}</td>' if stats.ref_has_channel else ''
            kw_rows += (
                f'<tr>'
                f'<td>{kw_display}</td>'
                f'<td>{s["expected"]}</td><td>{s["actual"]}</td><td>{s["matched"]}</td>'
                f'<td>{s["fr"]}</td><td>{s["fa"]}</td><td>{s["keyword_error"]}</td>'
                f'{channel_error_col}'
                f'<td><span class="{row_cls}">{wk:.2f}%</span></td>'
                f'<td>{s["fr_rate"] * 100:.2f}%</td>'
                f'<td>{s["fa_rate"] * 100:.2f}%</td>'
                f'<td>{s["keyword_error_rate"] * 100:.2f}%</td>'
                f'</tr>'
            )
        kw_channel_error_hdr = '<th>音区错误</th>' if stats.ref_has_channel else ''
        tab6_html = (
            '<table class="report-table"><thead>'
            '<tr><th>唤醒词</th><th>预期唤醒数</th><th>实际唤醒数</th><th>匹配数</th>'
            f'<th>FR</th><th>FA</th><th>关键词错误</th>{kw_channel_error_hdr}'
            '<th>唤醒率</th><th>FR率</th><th>FA率</th><th>关键词错误率</th></tr>'
            f'</thead><tbody>{kw_rows}</tbody></table>'
        )

        channel_tab_html = (
            '<div class="inner-tab" onclick="switchTab(this,\'wk6\')">唤醒音区检测 ({cc_n})</div>'
            if stats.ref_has_channel else ''
        )
        channel_pane_html = (
            f'<div id="wk6" class="inner-pane">{tab5_html}</div>'
            if stats.ref_has_channel else ''
        )
        section_html = (
            '<div class="section">'
            '<div class="section-header">📋 唤醒检测详情</div>'
            '<div class="section-body">'
            '<div class="inner-tabs">'
            '<div class="inner-tab active"  onclick="switchTab(this,\'wk1\')">音频统计</div>'
            '<div class="inner-tab" onclick="switchTab(this,\'wk2\')">FA 误检 ({fa_n})</div>'
            '<div class="inner-tab" onclick="switchTab(this,\'wk3\')">FR 漏检 ({fr_n})</div>'
            '<div class="inner-tab" onclick="switchTab(this,\'wk4\')">关键词错误 ({ke_n})</div>'
            '<div class="inner-tab" onclick="switchTab(this,\'wk5\')">按关键词统计 ({kw_n})</div>'
            f'{channel_tab_html}'
            '</div>'
            f'<div id="wk1" class="inner-pane active">{tab1_html}</div>'
            f'<div id="wk2" class="inner-pane">{tab2_html}</div>'
            f'<div id="wk3" class="inner-pane">{tab3_html}</div>'
            f'<div id="wk4" class="inner-pane">{tab4_html}</div>'
            f'<div id="wk5" class="inner-pane">{tab6_html}</div>'
            f'{channel_pane_html}'
            '</div></div>'
        ).replace('{fa_n}', str(stats.fa_count)) \
         .replace('{fr_n}', str(stats.fr_count)) \
         .replace('{ke_n}', str(stats.keyword_error_count)) \
         .replace('{kw_n}', str(len(stats.keyword_stats))) \
         .replace('{cc_n}', str(stats.channel_check_count))

        return self.build_html_page("唤醒词 FA/FR 报告", cards_html + section_html)

    # ── Excel 报告 ────────────────────────────────────────────────────────────

    def _generate_excel_report(
        self,
        stats: WakeupAccuracyStats,
        ref_file: str,
        result_file: str,
        output_path: str,
    ) -> None:
        """生成 Excel 报告"""
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment
            from openpyxl.utils import get_column_letter
        except ImportError:
            raise ImportError("生成 Excel 报告需要安装 openpyxl：pip install openpyxl")

        wb = openpyxl.Workbook()
        if 'Sheet' in wb.sheetnames:
            wb.remove(wb['Sheet'])

        # 公共样式
        header_fill  = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        header_font  = Font(bold=True, color="FFFFFF", size=11)
        title_font   = Font(bold=True, size=12)
        center_align = Alignment(horizontal='center', vertical='center')
        left_align   = Alignment(horizontal='left',   vertical='center')
        red_fill     = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
        green_fill   = PatternFill(start_color="C5E0B4", end_color="C5E0B4", fill_type="solid")
        yellow_fill  = PatternFill(start_color="FFE699", end_color="FFE699", fill_type="solid")
        blue_fill    = PatternFill(start_color="DDEBF7", end_color="DDEBF7", fill_type="solid")

        def _write_header(ws, row: int, headers: list) -> None:
            for c, h in enumerate(headers, 1):
                cell           = ws.cell(row=row, column=c, value=h)
                cell.fill      = header_fill
                cell.font      = header_font
                cell.alignment = center_align

        # ── Sheet 1：概要 ──────────────────────────────────────────────────────
        ws_sum = wb.create_sheet("概要", 0)
        sum_last_col = 'G' if stats.ref_has_channel else 'F'
        ws_sum['A1'] = '唤醒词 FA/FR 分析结果'
        ws_sum['A1'].font = Font(bold=True, size=14)
        ws_sum.merge_cells(f'A1:{sum_last_col}1')

        r = 3
        for label, value in [('参考文件：', ref_file), ('结果文件：', result_file)]:
            ws_sum.cell(row=r, column=1, value=label)
            ws_sum.cell(row=r, column=2, value=value)
            ws_sum.merge_cells(f'B{r}:{sum_last_col}{r}')
            r += 1

        r += 1
        ws_sum.cell(row=r, column=1, value='汇总统计').font = title_font
        ws_sum.merge_cells(f'A{r}:{sum_last_col}{r}')
        r += 1

        total_wakeup_rate = stats.wakeup_rate * 100.0
        summary_items = [
            ('Ref 总段数',                 stats.total_ref),
            ('Result 总段数',              stats.total_result),
            ('成功匹配段数',               stats.matched_count),
            ('断句数量',                   stats.break_count),
            ('连句数量',                   stats.join_count),
            ('', ''),
            ('False Acceptance (FA)',
             f'{stats.fa_count} 段 ({stats.fa_rate * 100:.2f}%)'),
            ('False Rejection (FR)',
             f'{stats.fr_count} 段 ({stats.fr_rate * 100:.2f}%)'),
            ('关键词错误',
             f'{stats.keyword_error_count} 段 ({stats.keyword_error_rate * 100:.2f}%)'),
        ]
        if stats.ref_has_channel:
            summary_items.append(
                ('唤醒音区检测',
                 f'Faild {stats.channel_check_fail} / {stats.channel_check_count} '
                 f'(Pass率 {stats.channel_check_pass_rate * 100:.2f}%)')
            )

        for label, value in summary_items:
            cell_a = ws_sum.cell(row=r, column=1, value=label)
            cell_b = ws_sum.cell(row=r, column=2, value=value)
            if label in ('False Acceptance (FA)', 'False Rejection (FR)', '关键词错误', '唤醒音区检测'):
                cell_a.font = Font(bold=True)
                cell_b.font = Font(bold=True)
            r += 1

        ws_sum.cell(row=r, column=1, value='总唤醒率')
        ws_sum.cell(row=r, column=2, value=f'{total_wakeup_rate:.2f}%')
        ws_sum.cell(row=r, column=1).font = Font(bold=True, color="0000FF")
        ws_sum.cell(row=r, column=2).font = Font(bold=True, color="0000FF")
        r += 2

        # 每条音频统计
        ws_sum.cell(row=r, column=1, value='每条音频唤醒统计详情').font = title_font
        ws_sum.merge_cells(f'A{r}:{sum_last_col}{r}')
        r += 1

        audio_hdrs = ['音频路径', '预期唤醒数', '实际唤醒数', 'FR 数量', 'FA 数量']
        if stats.ref_has_channel:
            audio_hdrs.append('音区错误')
        audio_hdrs.append('唤醒率')
        _write_header(ws_sum, r, audio_hdrs)
        r += 1

        for ap in sorted(stats.audio_stats.keys()):
            s   = stats.audio_stats[ap]
            wk  = s['wakeup_rate']
            row_fill = (red_fill   if wk < 80 else
                        green_fill if wk >= 95 else None)
            ws_sum.cell(row=r, column=1, value=ap).alignment = left_align
            ws_sum.cell(row=r, column=2, value=s['expected']).alignment  = center_align
            ws_sum.cell(row=r, column=3, value=s['actual']).alignment    = center_align
            ws_sum.cell(row=r, column=4, value=s['fr']).alignment        = center_align
            ws_sum.cell(row=r, column=5, value=s['fa']).alignment        = center_align
            next_col = 6
            if stats.ref_has_channel:
                ws_sum.cell(row=r, column=6, value=s['channel_error']).alignment = center_align
                next_col = 7
            ws_sum.cell(row=r, column=next_col, value=f"{wk:.2f}%").alignment = center_align
            if row_fill:
                for col in range(1, len(audio_hdrs) + 1):
                    ws_sum.cell(row=r, column=col).fill = row_fill
            r += 1

        # 总计行
        tot_exp    = sum(s['expected'] for s in stats.audio_stats.values())
        tot_actual = sum(s['actual']   for s in stats.audio_stats.values())
        tot_fr     = sum(s['fr']       for s in stats.audio_stats.values())
        tot_fa     = sum(s['fa']       for s in stats.audio_stats.values())
        total_cells = [('总计', None), (tot_exp, center_align), (tot_actual, center_align),
                       (tot_fr, center_align), (tot_fa, center_align)]
        if stats.ref_has_channel:
            tot_channel_error = sum(s['channel_error'] for s in stats.audio_stats.values())
            total_cells.append((tot_channel_error, center_align))
        total_cells.append((f'{total_wakeup_rate:.2f}%', center_align))

        rate_col_idx = len(total_cells)
        for c, v in enumerate(total_cells, 1):
            val, align = v
            cell       = ws_sum.cell(row=r, column=c, value=val)
            cell.font  = Font(bold=True, color="0000FF") if c == rate_col_idx else Font(bold=True)
            cell.fill  = blue_fill
            if align:
                cell.alignment = align
            else:
                cell.alignment = center_align

        ws_sum.column_dimensions['A'].width = 60
        summary_col_widths = [15, 15, 12, 12]
        if stats.ref_has_channel:
            summary_col_widths.append(12)
        summary_col_widths.append(12)
        summary_col_letters = ['B', 'C', 'D', 'E', 'F', 'G'][:len(summary_col_widths)]
        for col_letter, w in zip(summary_col_letters, summary_col_widths):
            ws_sum.column_dimensions[col_letter].width = w

        # ── Sheet 2 / 3：FA / FR 详情 ──────────────────────────────────────────
        seg_hdrs = ['音频路径', '关键词', '开始时间', '结束时间', '时长(秒)', '行号']
        col_widths_seg = [60, 20, 15, 15, 12, 10]

        for sheet_idx, (title, segments) in enumerate([
            ("FA详情", stats.fa_segments),
            ("FR详情", stats.fr_segments),
        ], 1):
            ws = wb.create_sheet(title, sheet_idx)
            _write_header(ws, 1, seg_hdrs)
            for ri, seg in enumerate(segments, 2):
                ws.cell(row=ri, column=1, value=seg.audio_path)
                ws.cell(row=ri, column=2, value=seg.keyword)
                ws.cell(row=ri, column=3, value=seg.start)
                ws.cell(row=ri, column=4, value=seg.end)
                ws.cell(row=ri, column=5, value=round(seg.end - seg.start, 6))
                ws.cell(row=ri, column=6, value=seg.line_num)
            for ci, w in enumerate(col_widths_seg, 1):
                ws.column_dimensions[get_column_letter(ci)].width = w
            ws.freeze_panes = 'A2'

        # ── Sheet 4：关键词错误详情 ────────────────────────────────────────────
        ws_ke = wb.create_sheet("关键词错误", 3)
        ke_hdrs = ['音频路径', '参考关键词', '参考开始', '参考结束',
                   '识别关键词', '识别开始', '识别结束', '参考行号', '识别行号']
        _write_header(ws_ke, 1, ke_hdrs)
        for ri, case in enumerate(stats.keyword_error_cases, 2):
            ref_s, res_s = case['ref'], case['result']
            for ci, v in enumerate([
                ref_s.audio_path, ref_s.keyword, ref_s.start, ref_s.end,
                res_s.keyword,    res_s.start,   res_s.end,
                ref_s.line_num,   res_s.line_num,
            ], 1):
                cell      = ws_ke.cell(row=ri, column=ci, value=v)
                cell.fill = yellow_fill
        for ci, w in enumerate([60,20,15,15,20,15,15,12,12], 1):
            ws_ke.column_dimensions[get_column_letter(ci)].width = w
        ws_ke.freeze_panes = 'A2'

        # ── Sheet 5：Signal（result 全览）──────────────────────────────────────
        ws_signal = wb.create_sheet("Signal", 4)
        _write_header(ws_signal, 1, ['音频路径', '关键词', '开始时间', '结束时间', '时长(秒)', '行号', '状态'])

        matched_result_set      = {res for _, res in stats.matched_pairs}
        fa_result_set           = set(stats.fa_segments)
        ke_result_set           = {c['result'] for c in stats.keyword_error_cases}
        break_result_set        = {seg for case in stats.break_cases
                                   for seg in case['result_segments']}
        join_result_set         = {case['result'] for case in stats.join_cases}

        for ri, seg in enumerate(stats.all_result_segments, 2):
            if   seg in matched_result_set: status, fill = '匹配',     green_fill
            elif seg in ke_result_set:      status, fill = '关键词错误', yellow_fill
            elif seg in fa_result_set:      status, fill = 'FA',        red_fill
            elif seg in break_result_set:   status, fill = '断句',      yellow_fill
            elif seg in join_result_set:    status, fill = '连句',      yellow_fill
            else:                           status, fill = '其他',      None
            for ci, v in enumerate([seg.audio_path, seg.keyword, seg.start,
                                    seg.end, round(seg.end - seg.start, 6),
                                    seg.line_num, status], 1):
                cell = ws_signal.cell(row=ri, column=ci, value=v)
                if fill:
                    cell.fill = fill
        for ci, w in enumerate([60,20,15,15,12,10,12], 1):
            ws_signal.column_dimensions[get_column_letter(ci)].width = w
        ws_signal.freeze_panes = 'A2'

        # ── Sheet 6：Ref（ref 全览）────────────────────────────────────────────
        ws_ref = wb.create_sheet("Ref", 5)
        _write_header(ws_ref, 1, ['音频路径', '关键词', '开始时间', '结束时间', '时长(秒)', '行号', '状态'])

        matched_ref_set = {ref for ref, _ in stats.matched_pairs}
        fr_ref_set      = set(stats.fr_segments)
        ke_ref_set      = {c['ref'] for c in stats.keyword_error_cases}
        break_ref_set   = {case['ref'] for case in stats.break_cases}
        join_ref_set    = {seg for case in stats.join_cases
                          for seg in case['ref_segments']}

        for ri, seg in enumerate(stats.all_ref_segments, 2):
            if   seg in matched_ref_set: status, fill = '匹配',     green_fill
            elif seg in fr_ref_set:      status, fill = 'FR',        red_fill
            elif seg in ke_ref_set:      status, fill = '关键词错误', yellow_fill
            elif seg in break_ref_set:   status, fill = '断句',      yellow_fill
            elif seg in join_ref_set:    status, fill = '连句',      yellow_fill
            else:                        status, fill = '其他',      None
            for ci, v in enumerate([seg.audio_path, seg.keyword, seg.start,
                                    seg.end, round(seg.end - seg.start, 6),
                                    seg.line_num, status], 1):
                cell = ws_ref.cell(row=ri, column=ci, value=v)
                if fill:
                    cell.fill = fill
        for ci, w in enumerate([60,20,15,15,12,10,15], 1):
            ws_ref.column_dimensions[get_column_letter(ci)].width = w
        ws_ref.freeze_panes = 'A2'

        # ── Sheet 7：按关键词统计 ──────────────────────────────────────────────
        ws_kw = wb.create_sheet("按关键词统计", 6)
        kw_hdrs = ['唤醒词', '预期唤醒数', '实际唤醒数', '匹配数', 'FR 数量', 'FA 数量', '关键词错误']
        if stats.ref_has_channel:
            kw_hdrs.append('音区错误')
        kw_hdrs.extend(['唤醒率', 'FR率', 'FA率', '关键词错误率'])
        _write_header(ws_kw, 1, kw_hdrs)

        for ri, kw in enumerate(sorted(stats.keyword_stats.keys()), 2):
            s = stats.keyword_stats[kw]
            kw_display = kw if kw else '<empty>'
            values = [
                kw_display,
                s['expected'],
                s['actual'],
                s['matched'],
                s['fr'],
                s['fa'],
                s['keyword_error'],
            ]
            if stats.ref_has_channel:
                values.append(s['channel_error'])
            values.extend([
                f"{s['wakeup_rate'] * 100:.2f}%",
                f"{s['fr_rate'] * 100:.2f}%",
                f"{s['fa_rate'] * 100:.2f}%",
                f"{s['keyword_error_rate'] * 100:.2f}%",
            ])

            wk = s['wakeup_rate'] * 100.0
            row_fill = (red_fill if wk < 80 else (green_fill if wk >= 95 else None))

            for ci, v in enumerate(values, 1):
                cell = ws_kw.cell(row=ri, column=ci, value=v)
                cell.alignment = center_align if ci != 1 else left_align
                if row_fill:
                    cell.fill = row_fill

        kw_widths = [24, 12, 12, 10, 10, 10, 12]
        if stats.ref_has_channel:
            kw_widths.append(10)
        kw_widths.extend([10, 10, 10, 14])
        for ci, w in enumerate(kw_widths, 1):
            ws_kw.column_dimensions[get_column_letter(ci)].width = w
        ws_kw.freeze_panes = 'A2'

        # ── Sheet 8：唤醒音区检测 ──────────────────────────────────────────────
        ws_cc = wb.create_sheet("唤醒音区检测", 7)
        _write_header(ws_cc, 1, [
            '参考关键字', '参考开始时间', '参考结束时间', '参考channel',
            '实际关键字', '实际开始时间', '实际结束时间', '实际channel',
            '唤醒音区检测结果（Pass/Faild）'
        ])

        if stats.ref_has_channel:
            for ri, case in enumerate(stats.channel_check_cases, 2):
                ref_s, res_s = case['ref'], case['result']
                result_text = case['check_result']
                fill = green_fill if result_text == 'Pass' else red_fill
                values = [
                    ref_s.keyword, ref_s.start, ref_s.end, ref_s.channel,
                    res_s.keyword, res_s.start, res_s.end, res_s.channel,
                    result_text
                ]
                for ci, v in enumerate(values, 1):
                    cell = ws_cc.cell(row=ri, column=ci, value=v)
                    if fill:
                        cell.fill = fill
        else:
            ws_cc.cell(row=2, column=1, value='Ref 未提供 channel 列，未启用唤醒音区检测。')
            ws_cc.merge_cells('A2:I2')

        for ci, w in enumerate([20, 14, 14, 14, 20, 14, 14, 14, 28], 1):
            ws_cc.column_dimensions[get_column_letter(ci)].width = w
        ws_cc.freeze_panes = 'A2'

        # 保存
        parent = os.path.dirname(output_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        wb.save(output_path)
        logger.info(f"Excel 报告已生成: {output_path}")

    # ── Summary 文本 ──────────────────────────────────────────────────────────

    def _generate_summary(self, stats: WakeupAccuracyStats, output_path: str) -> str:
        content_lines = [
            f"*  Ref 总数:   {stats.total_ref}  |  Result 总数: {stats.total_result}",
            f"*  匹配数:     {stats.matched_count}  |  断句: {stats.break_count}  |  连句: {stats.join_count}",
            f"",
            (
                f"*  总唤醒率:      {stats.wakeup_rate * 100:6.2f}%  "
                f"({stats.total_actual_effective}/{stats.total_ref})"
                if stats.ref_has_channel else
                f"*  总唤醒率:      {stats.wakeup_rate * 100:6.2f}%  ({stats.total_ref - stats.fr_count}/{stats.total_ref})"
            ),
            f"*  FA 误检率:     {stats.fa_rate            * 100:6.2f}%  ({stats.fa_count}/{stats.total_result})",
            f"*  FR 漏检率:     {stats.fr_rate            * 100:6.2f}%  ({stats.fr_count}/{stats.total_ref})",
            f"*  关键词错误率:  {stats.keyword_error_rate * 100:6.2f}%  ({stats.keyword_error_count}/{stats.total_ref})",
            f"",
            f"*  详细报告: {output_path}",
        ]
        if stats.ref_has_channel:
            content_lines.insert(
                8,
                (
                    f"*  唤醒音区检测:  Pass {stats.channel_check_pass} / "
                    f"Faild {stats.channel_check_fail} / Total {stats.channel_check_count}"
                ),
            )
        if stats.keyword_stats:
            content_lines.insert(-1, "")
            content_lines.insert(-1, "*  按关键词统计:")
            for kw in sorted(stats.keyword_stats.keys()):
                s = stats.keyword_stats[kw]
                kw_display = kw if kw else "<empty>"
                content_lines.insert(
                    -1,
                    (
                        f"*    {kw_display}: 唤醒率 {s['wakeup_rate'] * 100:6.2f}%"
                        f" | FR率 {s['fr_rate'] * 100:6.2f}% ({s['fr']}/{s['expected']})"
                        f" | FA率 {s['fa_rate'] * 100:6.2f}% ({s['fa']}/{s['actual_raw']})"
                        f" | 关键词错误率 {s['keyword_error_rate'] * 100:6.2f}%"
                        f" ({s['keyword_error']}/{s['expected']})"
                    ),
                )
        return self.format_summary_box("WAKEUP_ACCURACY", "\n".join(content_lines), width=90)


# ─── CLI 入口 ─────────────────────────────────────────────────────────────────

def main() -> None:
    """
    命令行入口函数

    使用示例:
        python3 wakeup_accuracy.py -r result.csv -ref ref.csv
        python3 wakeup_accuracy.py -r result.csv -ref ref.csv -o report.xlsx
    """
    import argparse

    parser = argparse.ArgumentParser(
        description='唤醒词 FA/FR 准确率计算工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python3 %(prog)s -r result.csv -ref ref.csv
  python3 %(prog)s -r result.csv -ref ref.csv -o report.xlsx

输入文件格式:
  result.csv : 有表头 CSV，字段为 audio,result,start,end[,channel]
  ref.csv    : 无表头，列顺序为 音频路径,关键词,开始时间(s),结束时间(s)[,channel]；分隔符可为 \\t / ; / ,

输出:
  - 终端打印 Summary 统计报告
  - 生成 Excel 详细报告（概要/FA详情/FR详情/关键词错误/Signal/Ref/按关键词统计/唤醒音区检测）
  - 生成同路径下的 HTML 报告
        '''
    )

    parser.add_argument('-r', '--result',    required=True,  help='识别结果 CSV 文件路径')
    parser.add_argument('-ref', '--reference', required=True,
                        help='参考唤醒文件路径（无表头；列分隔符支持 \\t、;、,）')
    parser.add_argument('-o', '--output',    default=None,   help='Excel 报告输出路径（默认: 当前目录/mango_report/）')

    args = parser.parse_args()

    params = [
        f"result={args.result}",
        f"ref={args.reference}",
    ]
    if args.output:
        params.append(f"output={args.output}")

    handler = WakeupAccuracyHandler(config=None)
    try:
        summary = handler.execute(params)
        print(summary)
    except FileNotFoundError as e:
        print(f"错误: {e}")
        exit(1)
    except ValueError as e:
        print(f"参数错误: {e}")
        exit(1)
    except Exception as e:
        print(f"执行失败: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


if __name__ == '__main__':
    main()
