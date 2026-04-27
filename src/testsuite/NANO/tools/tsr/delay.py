#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2026/03/03
# @Author  : huidong.bai
# @File    : delay.py
# @Software: PyCharm
# @Mail    : MasterBai2018@outlook.com
"""
DELAY 指令实现

用于计算 ASR 时延，支持：
- 实时上屏时延（type 以 Temp 结尾）
- 最终结果时延（type 不以 Temp 结尾）

使用示例:
    [TSR]DELAY ref=label.txt result=callback.jsonl type=PSTTASRResultTemp output=delay.xlsx
    [TSR]DELAY ref=label.txt result=callback.jsonl type=PSTTASRResult    output=delay.xlsx

标注文件格式（卡拉OK式）:
    TestAudio/1.wav   <0.3>打<0.5>开<0.8>车<1.2>窗<1.5>
    其中：每个字的结束时间 = 它后面的时间标记；最后一个 <time> 是整句结束时间点。
"""

import os
import sys
import re
import json
import math
import statistics
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from loguru import logger

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

# assert_key_value.yaml 中存放了各 callback_type 的字段 JSON 路径，用于动态解析
from src.utils.common import assert_key_value_config
from src.utils.jsonUtil import JsonUtil


# ─── Constants ────────────────────────────────────────────────────────────────

REALTIME_MATCH_TOLERANCE = 3.0    # seconds: start-time tolerance for real-time utterance matching
FINAL_MATCH_TOLERANCE    = 2.0    # seconds: start-time tolerance for final-result utterance matching
GROUP_TOLERANCE          = 0.05   # seconds (50 ms): same start_sec → same utterance group
INSTANT_THRESHOLD_MS     = 10.0   # ms: gap ≤ this → 连续吐字
STUTTER_THRESHOLD_MS     = 350.0  # ms: gap ≥ this → 识别卡顿


# ─── Data Structures ──────────────────────────────────────────────────────────

@dataclass
class CharLabel:
    """One text segment in the label with its end time."""
    char: str           # text content (may be 1 char or multi-char)
    end_time: float     # seconds: when this segment's speech ends
    cum_count: int      # cumulative character count up to and including this segment


@dataclass
class UtteranceLabelEntry:
    """One utterance read from the label file."""
    audio: str              # normalized audio path
    audio_basename: str     # stem of the audio filename (no extension)
    sentence_start: float   # seconds: first time marker
    sentence_end: float     # seconds: last time marker
    chars: List[CharLabel]  # parsed segments in order
    full_text: str          # complete utterance text
    # cumulative char count → end time, built from chars
    char_count_map: Dict[int, float] = field(default_factory=dict)


@dataclass
class CallbackRecord:
    """One record parsed from callback.jsonl."""
    client_name: str
    callback_type: str
    audio: str          # normalized audio path
    audio_basename: str # stem of audio filename
    audiotime: float    # seconds
    asr: str
    start_sec: float    # data.start / 1000
    end_sec: float      # data.end   / 1000


@dataclass
class UtteranceGroup:
    """Callback records that belong to the same utterance."""
    audio: str
    audio_basename: str
    start_sec: float
    end_sec: float
    records: List[CallbackRecord]   # sorted by audiotime


@dataclass
class DelayRecord:
    """One measured delay data point."""
    audio: str
    utterance_text: str
    result_text: str
    char_count: int
    label_end_time: float   # seconds
    audiotime: float        # seconds
    delay_ms: float         # (audiotime - label_end_time) * 1000，负值归零为 0
    screen_type: str = ""   # 首字上屏 / 中间上屏 / 尾字上屏（实时模式专有）


@dataclass
class GapRecord:
    """Gap between two consecutive real-time results in the same utterance."""
    audio: str
    utterance_text: str
    prev_asr: str
    curr_asr: str
    gap_ms: float
    is_instant: bool    # gap <= INSTANT_THRESHOLD_MS
    is_stutter: bool    # gap >= STUTTER_THRESHOLD_MS


@dataclass
class MissingRecord:
    """Missing intermediate up-screen steps for one utterance."""
    audio: str
    utterance_text: str
    expected_count: int         # total expected steps (= number of distinct char counts in char_count_map)
    actual_count: int           # steps that actually appeared in results
    missing_count: int
    missing_rate: float         # missing_count / expected_count
    missing_positions: List[int]  # which cumulative char counts are missing


@dataclass
class DelayStats:
    """Aggregated delay statistics for one run."""
    mode: str               # "realtime" | "final"
    result_type: str        # callback type string
    total_matched: int = 0
    total_unmatched: int = 0

    delay_records: List[DelayRecord] = field(default_factory=list)
    min_delay_ms: float = 0.0
    max_delay_ms: float = 0.0
    avg_delay_ms: float = 0.0

    # real-time only
    gap_records: List[GapRecord] = field(default_factory=list)
    gap_std_ms: float = 0.0   # 上屏间隔标准差（ms），与 gap_records 中 gap_ms 同量纲
    instant_rate: float = 0.0              # 连续吐字率（间隔 ≤ INSTANT_THRESHOLD_MS）
    stutter_rate: float = 0.0
    missing_records: List[MissingRecord] = field(default_factory=list)
    overall_missing_rate: float = 0.0
    first_char_avg_delay_ms: float = 0.0   # 首字上屏平均时延
    last_char_avg_delay_ms: float = 0.0    # 尾字上屏平均时延


# ─── Label File Parser ────────────────────────────────────────────────────────

def parse_label_file(label_file: str) -> List[UtteranceLabelEntry]:
    """
    Parse a karaoke-style label file.

    Each non-empty line format:
        audio_path   <t0>text0<t1>text1...<tN>

    Rules:
    - text[i] ends at times[i+1]; the final <tN> (no text after it) = sentence end.
    - sentence_start = times[0].
    - sentence_end   = times[-1].
    """
    entries: List[UtteranceLabelEntry] = []
    with open(label_file, 'r', encoding='utf-8') as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            try:
                entry = _parse_label_line(line)
                if entry:
                    entries.append(entry)
            except Exception as exc:
                logger.warning(f"标注文件第 {lineno} 行解析失败: {exc} | 内容: {line}")

    logger.info(f"标注文件解析完成：共 {len(entries)} 条发话标注")
    return entries


def _parse_label_line(line: str) -> Optional[UtteranceLabelEntry]:
    # Split audio path from annotation at first whitespace
    parts = line.split(None, 1)
    if len(parts) < 2:
        return None

    audio_raw   = parts[0].strip()
    annotation  = parts[1].strip()

    audio_norm     = os.path.normpath(audio_raw).replace('\\', '/')
    audio_basename = os.path.splitext(os.path.basename(audio_norm))[0]

    # Extract all (time, text) pairs with regex
    pattern = re.compile(r'<(\d+\.?\d*)>([^<]*)')
    matches = pattern.findall(annotation)
    if not matches:
        logger.warning(f"标注行无时间标记: {line}")
        return None

    times = [float(m[0]) for m in matches]
    texts = [m[1]        for m in matches]

    sentence_start = times[0]
    sentence_end   = times[-1]

    # Build CharLabel list: text[i] ends at times[i+1]
    chars: List[CharLabel] = []
    cum_count = 0
    for i, text in enumerate(texts):
        if not text:        # empty → sentence-end boundary marker, skip
            continue
        end_time  = times[i + 1] if i + 1 < len(times) else times[i]
        cum_count += len(text)
        chars.append(CharLabel(char=text, end_time=end_time, cum_count=cum_count))

    if not chars:
        return None

    full_text      = ''.join(c.char for c in chars)
    char_count_map = {c.cum_count: c.end_time for c in chars}

    return UtteranceLabelEntry(
        audio=audio_norm,
        audio_basename=audio_basename,
        sentence_start=sentence_start,
        sentence_end=sentence_end,
        chars=chars,
        full_text=full_text,
        char_count_map=char_count_map,
    )


# ─── JSONL Parser ─────────────────────────────────────────────────────────────

def parse_callback_jsonl(jsonl_file: str, filter_type: str) -> List[CallbackRecord]:
    """
    读取 callback.jsonl，仅保留 callback_type == filter_type 的记录。

    不同 callback_type 的 asr/start/end 字段路径各不相同（如 SpeechASRResultTemp
    是 result.text/result.startMts/result.endMts，而 PSTTASRResultTemp 则是
    asr/start/end）。这里从 assert_key_value.yaml 动态读取路径配置，
    再通过 JsonUtil.parse 解析，保证各类型均能正确取值。

    start/end 统一从毫秒转换为秒。
    """
    # 从 assert_key_value.yaml 获取该 callback_type 的字段路径配置
    type_cfg   = assert_key_value_config.get(filter_type, {})
    asr_path   = type_cfg.get('asr',   'asr')    # 默认直接取 asr 字段
    start_path = type_cfg.get('start', 'start')  # 默认直接取 start 字段
    end_path   = type_cfg.get('end',   'end')    # 默认直接取 end 字段
    logger.debug(f"[{filter_type}] 字段路径 → asr={asr_path}, start={start_path}, end={end_path}")

    records: List[CallbackRecord] = []
    with open(jsonl_file, 'r', encoding='utf-8') as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj           = json.loads(line)
                callback_type = obj.get('callback_type', '')
                if callback_type != filter_type:
                    continue

                client_name = obj.get('client_name') or obj.get('client', '')
                data        = obj.get('data', {})
                audio_raw   = str(data.get('audio', '') or '')
                if not audio_raw:
                    continue

                audiotime  = float(data.get('audiotime', 0) or 0)

                # 动态解析 asr/start/end，适配多种 callback_type 的 JSON 结构
                asr      = str(JsonUtil.parse(data, asr_path)   or '')
                start_ms = float(JsonUtil.parse(data, start_path) or 0)
                end_ms   = float(JsonUtil.parse(data, end_path)   or 0)

                audio_norm     = os.path.normpath(audio_raw).replace('\\', '/')
                audio_basename = os.path.splitext(os.path.basename(audio_norm))[0]

                records.append(CallbackRecord(
                    client_name=client_name,
                    callback_type=callback_type,
                    audio=audio_norm,
                    audio_basename=audio_basename,
                    audiotime=audiotime,
                    asr=asr,
                    start_sec=start_ms / 1000.0,
                    end_sec=end_ms   / 1000.0,
                ))
            except Exception as exc:
                logger.warning(f"JSONL 第 {lineno} 行解析失败: {exc}")

    logger.info(f"JSONL 解析完成：共 {len(records)} 条 {filter_type} 记录")
    return records


# ─── Utterance Grouper ────────────────────────────────────────────────────────

def group_into_utterances(records: List[CallbackRecord]) -> Dict[str, List[UtteranceGroup]]:
    """
    Group callback records into utterance-level groups, keyed by audio_basename.

    Grouping logic: records whose start_sec is within GROUP_TOLERANCE of the
    current group's start belong to the same utterance.
    Sorting: by start_sec then audiotime.
    """
    # Bucket by audio first
    by_audio: Dict[str, List[CallbackRecord]] = {}
    for rec in records:
        by_audio.setdefault(rec.audio_basename, []).append(rec)

    result: Dict[str, List[UtteranceGroup]] = {}

    for audio_key, recs in by_audio.items():
        sorted_recs = sorted(recs, key=lambda r: (r.start_sec, r.audiotime))

        groups: List[UtteranceGroup] = []
        grp_start  = sorted_recs[0].start_sec
        grp_bucket = [sorted_recs[0]]

        for rec in sorted_recs[1:]:
            if abs(rec.start_sec - grp_start) <= GROUP_TOLERANCE:
                grp_bucket.append(rec)
            else:
                groups.append(_make_group(audio_key, grp_start, grp_bucket))
                grp_start  = rec.start_sec
                grp_bucket = [rec]

        groups.append(_make_group(audio_key, grp_start, grp_bucket))
        result[audio_key] = groups

    total = sum(len(v) for v in result.values())
    logger.info(f"发话分组完成：共 {total} 个发话组")
    return result


def _make_group(audio_key: str, grp_start: float, bucket: List[CallbackRecord]) -> UtteranceGroup:
    return UtteranceGroup(
        audio=bucket[0].audio,
        audio_basename=audio_key,
        start_sec=grp_start,
        end_sec=max(r.end_sec for r in bucket),
        records=sorted(bucket, key=lambda r: r.audiotime),
    )


# ─── Matcher & Delay Calculator ───────────────────────────────────────────────

def match_and_calculate(
    labels: List[UtteranceLabelEntry],
    utterance_groups: Dict[str, List[UtteranceGroup]],
    is_realtime: bool,
) -> DelayStats:
    """
    For each label utterance, find the best-matching callback group,
    then compute delays, gaps, and missing rates.
    """
    tolerance = REALTIME_MATCH_TOLERANCE if is_realtime else FINAL_MATCH_TOLERANCE
    stats = DelayStats(mode="realtime" if is_realtime else "final", result_type="")

    for label in labels:
        groups = _find_groups_for_label(label, utterance_groups)
        best   = _find_best_group(label, groups, tolerance)

        if best is None:
            stats.total_unmatched += 1
            logger.debug(
                f"未匹配: {label.audio_basename} "
                f"[{label.sentence_start:.2f}s-{label.sentence_end:.2f}s] '{label.full_text}'"
            )
            continue

        stats.total_matched += 1

        if is_realtime:
            stats.delay_records.extend(_calc_realtime_delays(label, best))
            stats.gap_records.extend(_calc_gaps(label, best))
            stats.missing_records.append(_calc_missing(label, best))
        else:
            delay = _calc_final_delay(label, best)
            if delay:
                stats.delay_records.append(delay)

    _compute_aggregate_stats(stats, is_realtime)
    return stats


def _find_groups_for_label(
    label: UtteranceLabelEntry,
    utterance_groups: Dict[str, List[UtteranceGroup]],
) -> List[UtteranceGroup]:
    """Return groups for this label's audio (by basename, with fallback to path suffix)."""
    groups = utterance_groups.get(label.audio_basename)
    if groups:
        return groups
    # Fallback: try any key that is a suffix of (or contained in) the label audio path
    for key, grp_list in utterance_groups.items():
        if label.audio.endswith(key) or key in label.audio:
            return grp_list
    return []


def _find_best_group(
    label: UtteranceLabelEntry,
    groups: List[UtteranceGroup],
    tolerance: float,
) -> Optional[UtteranceGroup]:
    """
    Find the group whose start_sec is closest to label.sentence_start,
    within ±tolerance seconds.
    """
    best: Optional[UtteranceGroup] = None
    best_diff = float('inf')

    for grp in groups:
        diff = abs(grp.start_sec - label.sentence_start)
        if diff <= tolerance and diff < best_diff:
            best      = grp
            best_diff = diff

    return best


def _calc_realtime_delays(
    label: UtteranceLabelEntry, group: UtteranceGroup
) -> List[DelayRecord]:
    """
    For each Temp callback record, match it to the label by cumulative char count,
    then delay = audiotime - label_char_end_time（负值归零，不计入负时延）.

    同时根据字数位置判断上屏类型：
      首字上屏 — 累计字数等于 char_count_map 最小键
      尾字上屏 — 累计字数等于 char_count_map 最大键
      中间上屏 — 其余位置
    """
    if not label.char_count_map:
        return []

    min_count = min(label.char_count_map.keys())
    max_count = max(label.char_count_map.keys())

    records: List[DelayRecord] = []
    for cb in group.records:
        if not cb.asr:
            continue
        char_count     = len(cb.asr)
        label_end_time = label.char_count_map.get(char_count)
        if label_end_time is None:
            continue   # 无匹配的字数位置，跳过

        raw_delay_ms = (cb.audiotime - label_end_time) * 1000.0
        delay_ms     = max(0.0, raw_delay_ms)   # 负值归零

        if char_count == min_count:
            screen_type = "首字上屏"
        elif char_count == max_count:
            screen_type = "尾字上屏"
        else:
            screen_type = "中间上屏"

        records.append(DelayRecord(
            audio=label.audio,
            utterance_text=label.full_text,
            result_text=cb.asr,
            char_count=char_count,
            label_end_time=label_end_time,
            audiotime=cb.audiotime,
            delay_ms=delay_ms,
            screen_type=screen_type,
        ))
    return records


def _calc_final_delay(
    label: UtteranceLabelEntry, group: UtteranceGroup
) -> Optional[DelayRecord]:
    """
    Final result: take the record with the latest audiotime and compute
    delay = audiotime - label.sentence_end.
    """
    if not group.records:
        return None
    final_cb = max(group.records, key=lambda r: r.audiotime)
    raw_delay_ms = (final_cb.audiotime - label.sentence_end) * 1000.0
    delay_ms     = max(0.0, raw_delay_ms)   # 负值归零，与实时模式一致
    return DelayRecord(
        audio=label.audio,
        utterance_text=label.full_text,
        result_text=final_cb.asr,
        char_count=len(final_cb.asr) if final_cb.asr else 0,
        label_end_time=label.sentence_end,
        audiotime=final_cb.audiotime,
        delay_ms=delay_ms,
    )


def _calc_gaps(label: UtteranceLabelEntry, group: UtteranceGroup) -> List[GapRecord]:
    """Compute audiotime differences between consecutive Temp results."""
    records: List[GapRecord] = []
    sorted_recs = sorted(group.records, key=lambda r: r.audiotime)
    for i in range(1, len(sorted_recs)):
        prev    = sorted_recs[i - 1]
        curr    = sorted_recs[i]
        gap_ms  = (curr.audiotime - prev.audiotime) * 1000.0
        records.append(GapRecord(
            audio=label.audio,
            utterance_text=label.full_text,
            prev_asr=prev.asr,
            curr_asr=curr.asr,
            gap_ms=gap_ms,
            is_instant=gap_ms <= INSTANT_THRESHOLD_MS,
            is_stutter=gap_ms >= STUTTER_THRESHOLD_MS,
        ))
    return records


def _calc_missing(label: UtteranceLabelEntry, group: UtteranceGroup) -> MissingRecord:
    """
    Compare expected intermediate steps (1..N based on char_count_map keys)
    with the actual char counts present in the group's results.
    """
    expected_counts = set(label.char_count_map.keys())
    actual_counts   = {
        len(cb.asr) for cb in group.records
        if cb.asr and len(cb.asr) in expected_counts
    }
    missing_positions = sorted(expected_counts - actual_counts)
    expected_n        = len(expected_counts)
    return MissingRecord(
        audio=label.audio,
        utterance_text=label.full_text,
        expected_count=expected_n,
        actual_count=len(actual_counts),
        missing_count=len(missing_positions),
        missing_rate=len(missing_positions) / expected_n if expected_n > 0 else 0.0,
        missing_positions=missing_positions,
    )


def _compute_aggregate_stats(stats: DelayStats, is_realtime: bool) -> None:
    """Fill min/max/avg delay and real-time-only statistics."""
    delays = [r.delay_ms for r in stats.delay_records]
    if delays:
        stats.min_delay_ms = min(delays)
        stats.max_delay_ms = max(delays)
        stats.avg_delay_ms = statistics.mean(delays)

    if not is_realtime:
        return

    gaps = [r.gap_ms for r in stats.gap_records]
    if gaps:
        # 样本标准差，单位与 gap_ms 一致为 ms
        stats.gap_std_ms = statistics.stdev(gaps) if len(gaps) >= 2 else 0.0
        total              = len(gaps)
        stats.instant_rate = sum(1 for r in stats.gap_records if r.is_instant) / total
        stats.stutter_rate = sum(1 for r in stats.gap_records if r.is_stutter) / total

    if stats.missing_records:
        total_expected = sum(r.expected_count for r in stats.missing_records)
        total_missing  = sum(r.missing_count  for r in stats.missing_records)
        stats.overall_missing_rate = (
            total_missing / total_expected if total_expected > 0 else 0.0
        )

    # 首字/尾字上屏平均时延（仅实时模式有 screen_type 标记）
    first_delays = [r.delay_ms for r in stats.delay_records if r.screen_type == "首字上屏"]
    last_delays  = [r.delay_ms for r in stats.delay_records if r.screen_type == "尾字上屏"]
    stats.first_char_avg_delay_ms = statistics.mean(first_delays) if first_delays else 0.0
    stats.last_char_avg_delay_ms  = statistics.mean(last_delays)  if last_delays  else 0.0


# ─── Excel Report ─────────────────────────────────────────────────────────────

def generate_excel_report(stats: DelayStats, output_path: str, filter_type: str) -> None:
    """Write all result sheets to an Excel workbook."""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        raise ImportError("生成 Excel 报告需要安装 openpyxl：pip install openpyxl")

    wb = openpyxl.Workbook()
    # Remove default sheet created by openpyxl
    default = wb.active
    if default:
        wb.remove(default)

    _write_summary_sheet(wb, stats, filter_type)
    _write_delay_detail_sheet(wb, stats)
    if stats.mode == "realtime":
        _write_gap_sheet(wb, stats)
        _write_missing_sheet(wb, stats)

    out_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(out_dir, exist_ok=True)
    wb.save(output_path)
    logger.info(f"Excel 报告已生成: {output_path}")


# ── shared Excel helpers ──

def _header_style():
    from openpyxl.styles import Font, PatternFill
    return (
        Font(bold=True, color="FFFFFF"),
        PatternFill(start_color="366092", end_color="366092", fill_type="solid"),
    )


def _set_col_widths(ws, widths: List[int]) -> None:
    from openpyxl.utils import get_column_letter
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w


def _write_header_row(ws, row: int, headers: List[str]) -> None:
    font, fill = _header_style()
    for c, h in enumerate(headers, 1):
        cell       = ws.cell(row=row, column=c, value=h)
        cell.font  = font
        cell.fill  = fill


# ── Sheet 1: Summary ──

def _write_summary_sheet(wb, stats: DelayStats, filter_type: str) -> None:
    from openpyxl.styles import Font
    ws = wb.create_sheet("汇总")

    bold    = Font(bold=True)
    big     = Font(bold=True, size=14)
    section = Font(bold=True, size=12)

    mode_name = "实时上屏时延" if stats.mode == "realtime" else "最终结果时延"

    r = 1
    ws.cell(row=r, column=1, value=f"ASR 时延分析报告 — {mode_name}").font = big
    r += 2

    # Basic info block
    info_rows = [
        ("分析类型",   mode_name),
        ("回调类型",   filter_type),
        ("已匹配发话", stats.total_matched),
        ("未匹配发话", stats.total_unmatched),
    ]
    for name, val in info_rows:
        ws.cell(row=r, column=1, value=name).font = bold
        ws.cell(row=r, column=2, value=val)
        r += 1
    r += 1

    # Delay statistics
    ws.cell(row=r, column=1, value="时延统计（ms）").font = section
    r += 1
    _write_header_row(ws, r, ["指标", "数值"])
    r += 1

    delay_rows = [
        ("最小时延 (ms)", f"{stats.min_delay_ms:.1f}"),
        ("最大时延 (ms)", f"{stats.max_delay_ms:.1f}"),
        ("平均时延 (ms)", f"{stats.avg_delay_ms:.1f}"),
    ]
    if stats.mode == "realtime":
        delay_rows += [
            ("首字上屏平均时延 (ms)",           f"{stats.first_char_avg_delay_ms:.1f}"),
            ("尾字上屏平均时延 (ms)",           f"{stats.last_char_avg_delay_ms:.1f}"),
            ("上屏间隔标准差 (ms)",              f"{stats.gap_std_ms:.2f}"),
            (f"连续吐字率（间隔 ≤{INSTANT_THRESHOLD_MS:.0f}ms）",
             f"{stats.instant_rate * 100:.1f}%"),
            (f"识别卡顿率（间隔 ≥{STUTTER_THRESHOLD_MS:.0f}ms）",
             f"{stats.stutter_rate * 100:.1f}%"),
            ("上屏结果缺失率",                  f"{stats.overall_missing_rate * 100:.1f}%"),
        ]
    for name, val in delay_rows:
        ws.cell(row=r, column=1, value=name)
        ws.cell(row=r, column=2, value=val)
        r += 1

    _set_col_widths(ws, [42, 22])


# ── Sheet 2: Delay Detail ──

def _write_delay_detail_sheet(wb, stats: DelayStats) -> None:
    from openpyxl.styles import PatternFill

    ws = wb.create_sheet("时延明细")

    label_col = "发话结束时间(s)" if stats.mode == "final" else "标注结束时间(s)"
    # 实时模式增加「上屏类型」列；时延列按 350ms 阈值标绿/标红
    if stats.mode == "realtime":
        headers = [
            "音频文件", "标注文本", "识别结果", "上屏类型",
            "字数", label_col, "AudioTime(s)", "时延(ms)",
        ]
    else:
        headers = ["音频文件", "标注文本", "识别结果", "字数", label_col, "AudioTime(s)", "时延(ms)"]
    _write_header_row(ws, 1, headers)

    fill_green = PatternFill(start_color="C6E0B4", end_color="C6E0B4", fill_type="solid")  # 时延 ≤350ms
    fill_red   = PatternFill(start_color="F8CBAD", end_color="F8CBAD", fill_type="solid")  # 时延 >350ms

    for r, rec in enumerate(stats.delay_records, 2):
        if stats.mode == "realtime":
            ws.cell(row=r, column=1, value=os.path.basename(rec.audio))
            ws.cell(row=r, column=2, value=rec.utterance_text)
            ws.cell(row=r, column=3, value=rec.result_text)
            ws.cell(row=r, column=4, value=rec.screen_type or "-")
            ws.cell(row=r, column=5, value=rec.char_count)
            ws.cell(row=r, column=6, value=round(rec.label_end_time, 3))
            ws.cell(row=r, column=7, value=round(rec.audiotime,      3))
            c_delay = ws.cell(row=r, column=8, value=round(rec.delay_ms, 1))
            c_delay.fill = fill_green if rec.delay_ms <= STUTTER_THRESHOLD_MS else fill_red
        else:
            ws.cell(row=r, column=1, value=os.path.basename(rec.audio))
            ws.cell(row=r, column=2, value=rec.utterance_text)
            ws.cell(row=r, column=3, value=rec.result_text)
            ws.cell(row=r, column=4, value=rec.char_count)
            ws.cell(row=r, column=5, value=round(rec.label_end_time, 3))
            ws.cell(row=r, column=6, value=round(rec.audiotime,      3))
            c_delay = ws.cell(row=r, column=7, value=round(rec.delay_ms, 1))
            c_delay.fill = fill_green if rec.delay_ms <= STUTTER_THRESHOLD_MS else fill_red

    if stats.mode == "realtime":
        _set_col_widths(ws, [40, 22, 22, 12, 8, 18, 15, 12])
    else:
        _set_col_widths(ws, [40, 22, 22, 8, 18, 15, 12])


# ── Sheet 3: Gap Distribution ──

def _write_gap_sheet(wb, stats: DelayStats) -> None:
    ws = wb.create_sheet("上屏间隔分布")

    headers = [
        "音频文件", "发话文本",
        "前一结果", "当前结果",
        "间隔(ms)",
        f"连续吐字(≤{INSTANT_THRESHOLD_MS:.0f}ms)",
        f"卡顿(≥{STUTTER_THRESHOLD_MS:.0f}ms)",
    ]
    _write_header_row(ws, 1, headers)

    for r, rec in enumerate(stats.gap_records, 2):
        ws.cell(row=r, column=1, value=os.path.basename(rec.audio))
        ws.cell(row=r, column=2, value=rec.utterance_text)
        ws.cell(row=r, column=3, value=rec.prev_asr)
        ws.cell(row=r, column=4, value=rec.curr_asr)
        ws.cell(row=r, column=5, value=round(rec.gap_ms, 1))
        ws.cell(row=r, column=6, value="是" if rec.is_instant else "否")
        ws.cell(row=r, column=7, value="是" if rec.is_stutter else "否")

    _set_col_widths(ws, [40, 22, 22, 22, 10, 14, 14])


# ── Sheet 4: Missing Detail ──

def _write_missing_sheet(wb, stats: DelayStats) -> None:
    ws = wb.create_sheet("上屏缺失明细")

    headers = [
        "音频文件", "发话文本",
        "期望上屏次数", "实际上屏次数", "缺失次数",
        "缺失率", "缺失的字数位置",
    ]
    _write_header_row(ws, 1, headers)

    for r, rec in enumerate(stats.missing_records, 2):
        ws.cell(row=r, column=1, value=os.path.basename(rec.audio))
        ws.cell(row=r, column=2, value=rec.utterance_text)
        ws.cell(row=r, column=3, value=rec.expected_count)
        ws.cell(row=r, column=4, value=rec.actual_count)
        ws.cell(row=r, column=5, value=rec.missing_count)
        ws.cell(row=r, column=6, value=f"{rec.missing_rate * 100:.1f}%")
        ws.cell(row=r, column=7,
                value=str(rec.missing_positions) if rec.missing_positions else "无")

    _set_col_widths(ws, [40, 22, 14, 14, 10, 12, 32])


# ─── Handler ──────────────────────────────────────────────────────────────────

@register_tsr_command("DELAY")
class ASRDelayHandler(BaseTSRHandler):
    """
    ASR 时延分析处理器

    指令格式:
        [TSR]DELAY ref=<label_txt> result=<callback_jsonl> type=<callback_type> [output=<report_xlsx>]

    参数说明:
        ref    : 卡拉OK式标注文件路径（必需）
        result : callback.jsonl 文件路径（必需）
        type   : 回调类型，以 Temp 结尾 → 实时上屏模式，否则 → 最终结果模式（必需）
        output : Excel 报告输出路径（可选，默认 delay.xlsx）
    """

    COMMAND_NAME = "DELAY"

    def execute(self, params: list, output_report: str = None) -> str:
        label_file, jsonl_file, filter_type, xlsx_path, output_was_specified = (
            self._parse_params(params, output_report)
        )

        if not os.path.exists(label_file):
            raise FileNotFoundError(f"标注文件不存在: {label_file}")
        if not os.path.exists(jsonl_file):
            raise FileNotFoundError(f"JSONL 结果文件不存在: {jsonl_file}")

        is_realtime = filter_type.endswith("Temp")

        labels           = parse_label_file(label_file)
        callback_records = parse_callback_jsonl(jsonl_file, filter_type)

        if not labels:
            raise ValueError(f"标注文件为空或解析失败: {label_file}")
        if not callback_records:
            logger.warning(f"JSONL 中没有 {filter_type} 类型的记录，报告将为空")

        utterance_groups  = group_into_utterances(callback_records)
        stats             = match_and_calculate(labels, utterance_groups, is_realtime)
        stats.result_type = filter_type

        # 生成 Excel 报告
        generate_excel_report(stats, xlsx_path, filter_type)

        # 生成 HTML 报告（保存到 allure_result/mango_report/{define}/{suite}/）
        html_content   = self._build_delay_html(stats, filter_type)
        html_filename  = f"delay_{filter_type}.html"
        report_title   = f"{'实时上屏' if is_realtime else '最终结果'}时延分析 — {filter_type}"
        self.save_html_report(html_content, html_filename, report_title, "delay")

        # 本地副本（suite_mango_dir 或 -o 目录下）
        if output_was_specified:
            # -o 传了：HTML 放到与 xlsx 相同目录
            local_html = os.path.splitext(xlsx_path)[0] + '.html'
        else:
            # -o 未传：HTML 也放到 suite_mango_dir（xlsx 已在那里）
            local_html = os.path.splitext(xlsx_path)[0] + '.html'

        os.makedirs(os.path.dirname(local_html), exist_ok=True)
        with open(local_html, 'w', encoding='utf-8') as f:
            f.write(html_content)
        logger.info(f"本地 HTML 报告已生成: {local_html}")

        return self._build_summary(stats, xlsx_path, filter_type)

    # ── parameter parsing ──

    def _parse_params(
        self, params: list, default_output: str = None
    ) -> Tuple[str, str, str, str, bool]:
        """
        解析参数，返回 (label_file, jsonl_file, filter_type, xlsx_path, output_was_specified)。

        - output_was_specified=True  表示调用方通过 -o 或 params 中的 output= 显式指定了路径。
        - output_was_specified=False 时 xlsx_path 指向 suite_mango_dir/{safe_type}.xlsx。
        """
        label_file  = None
        jsonl_file  = None
        filter_type = None
        output_path = default_output

        for param in params:
            if   param.startswith("ref="):
                label_file  = param[4:]
            elif param.startswith("result="):
                jsonl_file  = param[7:]
            elif param.startswith("type="):
                filter_type = param[5:]
            elif param.startswith("output="):
                output_path = param[7:]

        if not label_file:
            raise ValueError("缺少必需参数: ref=<label_txt>")
        if not jsonl_file:
            raise ValueError("缺少必需参数: result=<callback_jsonl>")
        if not filter_type:
            raise ValueError("缺少必需参数: type=<callback_type>")

        output_was_specified = output_path is not None
        if not output_path:
            # -o 未传：放到 suite_mango_dir
            suite_mango_dir = self._get_suite_mango_dir()
            output_path = os.path.join(suite_mango_dir, f"delay_{filter_type}.xlsx")

        return label_file, jsonl_file, filter_type, output_path, output_was_specified

    # ── HTML report builder ──

    def generate_html_report(self, *args, **kwargs) -> Optional[str]:
        """
        实现 BaseTSRHandler 的抽象方法。
        对外接口：generate_html_report(stats, filter_type) → Optional[str]
        通常在 execute() 内部已调用，外部亦可单独调用。
        """
        if len(args) >= 2:
            stats, filter_type = args[0], args[1]
        else:
            stats       = kwargs.get('stats')
            filter_type = kwargs.get('filter_type', '')
        if stats is None:
            return None
        is_realtime   = filter_type.endswith("Temp")
        html_content  = self._build_delay_html(stats, filter_type)
        html_filename = f"delay_{filter_type}.html"
        report_title  = f"{'实时上屏' if is_realtime else '最终结果'}时延分析 — {filter_type}"
        return self.save_html_report(html_content, html_filename, report_title, "delay")

    def _build_delay_html(self, stats: 'DelayStats', filter_type: str) -> str:
        """根据 DelayStats 数据构建完整的自包含 HTML 字符串"""
        is_realtime = filter_type.endswith("Temp")
        mode_name   = "实时上屏时延" if is_realtime else "最终结果时延"

        # ── 汇总卡片 ─────────────────────────────────────────────────────────
        cards_html = (
            '<div class="summary-cards">'
            f'<div class="card"><div class="card-value">{stats.avg_delay_ms:.1f} ms</div>'
            f'<div class="card-label">平均时延</div></div>'
            f'<div class="card"><div class="card-value">{stats.min_delay_ms:.1f} ms</div>'
            f'<div class="card-label">最小时延</div></div>'
            f'<div class="card"><div class="card-value">{stats.max_delay_ms:.1f} ms</div>'
            f'<div class="card-label">最大时延</div></div>'
            f'<div class="card"><div class="card-value">{stats.total_matched}</div>'
            f'<div class="card-label">已匹配发话</div></div>'
            f'<div class="card card-warning"><div class="card-value">{stats.total_unmatched}</div>'
            f'<div class="card-label">未匹配发话</div></div>'
        )
        if is_realtime:
            cards_html += (
                f'<div class="card card-success"><div class="card-value">'
                f'{stats.first_char_avg_delay_ms:.1f} ms</div>'
                f'<div class="card-label">首字上屏平均时延</div></div>'
                f'<div class="card card-success"><div class="card-value">'
                f'{stats.last_char_avg_delay_ms:.1f} ms</div>'
                f'<div class="card-label">尾字上屏平均时延</div></div>'
                f'<div class="card"><div class="card-value">'
                f'{stats.gap_std_ms:.1f} ms</div>'
                f'<div class="card-label">上屏间隔标准差</div></div>'
                f'<div class="card"><div class="card-value">'
                f'{stats.instant_rate * 100:.1f}%</div>'
                f'<div class="card-label">连续吐字率</div></div>'
                f'<div class="card card-failure"><div class="card-value">'
                f'{stats.stutter_rate * 100:.1f}%</div>'
                f'<div class="card-label">识别卡顿率</div></div>'
                f'<div class="card card-warning"><div class="card-value">'
                f'{stats.overall_missing_rate * 100:.1f}%</div>'
                f'<div class="card-label">上屏缺失率</div></div>'
            )
        cards_html += '</div>'

        # ── 内嵌 Tab 区域 ────────────────────────────────────────────────────
        # Tab1: 时延明细（>350ms 标红，≤350ms 标绿；实时模式增加上屏类型列 + 筛选）
        def _delay_tag_cls(delay_ms: float) -> str:
            return "pass" if delay_ms <= STUTTER_THRESHOLD_MS else "fail"

        if is_realtime:
            delay_rows = ''.join(
                f'<tr data-type="{r.screen_type}">'
                f'<td>{i}</td>'
                f'<td>{os.path.basename(r.audio)}</td>'
                f'<td>{r.utterance_text}</td>'
                f'<td>{r.result_text}</td>'
                f'<td>{r.screen_type or "-"}</td>'
                f'<td>{r.char_count}</td>'
                f'<td>{r.label_end_time:.3f}</td>'
                f'<td>{r.audiotime:.3f}</td>'
                f'<td><span class="tag-{_delay_tag_cls(r.delay_ms)}">'
                f'{r.delay_ms:.1f} ms</span></td>'
                f'</tr>'
                for i, r in enumerate(stats.delay_records, 1)
            )
            filter_bar = (
                '<div style="padding:8px 12px;background:#fafafa;border-bottom:1px solid #e0e0e0;">'
                '<label style="margin-right:8px;">上屏类型筛选：</label>'
                '<select id="screenTypeFilter" onchange="filterDelayRows(this.value)" '
                'style="padding:4px 8px;border-radius:4px;border:1px solid #ccc;">'
                '<option value="all">全部</option>'
                '<option value="首字上屏">首字上屏</option>'
                '<option value="中间上屏">中间上屏</option>'
                '<option value="尾字上屏">尾字上屏</option>'
                '</select></div>'
                '<script>'
                'function filterDelayRows(v){'
                'var rows=document.querySelectorAll("#delayDetailBody tr[data-type]");'
                'rows.forEach(function(tr){'
                'tr.style.display=(v==="all"||tr.getAttribute("data-type")===v)?"":"none";'
                '});}'
                '</script>'
            )
            tab1_html = (
                filter_bar
                + '<table class="report-table">'
                + '<thead><tr><th>#</th><th>音频</th><th>发话文本</th><th>识别结果</th>'
                + '<th>上屏类型</th><th>字数</th><th>标注结束(s)</th><th>音频时间(s)</th><th>时延</th></tr></thead>'
                + f'<tbody id="delayDetailBody">{delay_rows}</tbody>'
                + '</table>'
            )
        else:
            delay_rows = ''.join(
                f'<tr>'
                f'<td>{i}</td>'
                f'<td>{os.path.basename(r.audio)}</td>'
                f'<td>{r.utterance_text}</td>'
                f'<td>{r.result_text}</td>'
                f'<td>{r.char_count}</td>'
                f'<td>{r.label_end_time:.3f}</td>'
                f'<td>{r.audiotime:.3f}</td>'
                f'<td><span class="tag-{_delay_tag_cls(r.delay_ms)}">'
                f'{r.delay_ms:.1f} ms</span></td>'
                f'</tr>'
                for i, r in enumerate(stats.delay_records, 1)
            )
            tab1_html = (
                '<table class="report-table">'
                '<thead><tr><th>#</th><th>音频</th><th>发话文本</th><th>识别结果</th>'
                '<th>字数</th><th>标注结束(s)</th><th>音频时间(s)</th><th>时延</th></tr></thead>'
                f'<tbody>{delay_rows}</tbody>'
                '</table>'
            )

        tab_nav  = '<div class="inner-tabs">'
        tab_nav += '<div class="inner-tab active" onclick="switchTab(this,\'dt1\')">时延明细</div>'
        tab_body = f'<div id="dt1" class="inner-pane active">{tab1_html}</div>'

        if is_realtime:
            # Tab2: 上屏间隔分布
            gap_rows = ''.join(
                f'<tr>'
                f'<td>{i}</td>'
                f'<td>{os.path.basename(r.audio)}</td>'
                f'<td>{r.prev_asr}</td>'
                f'<td>{r.curr_asr}</td>'
                f'<td><span class="tag-{"warn" if r.is_instant else ("fail" if r.is_stutter else "pass")}">'
                f'{r.gap_ms:.1f} ms</span></td>'
                f'<td>{"是" if r.is_stutter else "否"}</td>'
                f'</tr>'
                for i, r in enumerate(stats.gap_records, 1)
            )
            tab2_html = (
                '<table class="report-table">'
                '<thead><tr><th>#</th><th>音频</th><th>上一结果</th><th>当前结果</th>'
                '<th>间隔</th><th>卡顿</th></tr></thead>'
                f'<tbody>{gap_rows}</tbody>'
                '</table>'
            )
            # Tab3: 上屏缺失明细
            miss_rows = ''.join(
                f'<tr>'
                f'<td>{i}</td>'
                f'<td>{os.path.basename(r.audio)}</td>'
                f'<td>{r.utterance_text}</td>'
                f'<td>{r.expected_count}</td>'
                f'<td>{r.actual_count}</td>'
                f'<td>{r.missing_count}</td>'
                f'<td><span class="tag-{"pass" if r.missing_rate < 0.1 else "fail"}">'
                f'{r.missing_rate * 100:.1f}%</span></td>'
                f'</tr>'
                for i, r in enumerate(stats.missing_records, 1)
            )
            tab3_html = (
                '<table class="report-table">'
                '<thead><tr><th>#</th><th>音频</th><th>发话文本</th><th>期望次数</th>'
                '<th>实际次数</th><th>缺失次数</th><th>缺失率</th></tr></thead>'
                f'<tbody>{miss_rows}</tbody>'
                '</table>'
            )
            tab_nav  += ('<div class="inner-tab" onclick="switchTab(this,\'dt2\')">上屏间隔分布</div>'
                         '<div class="inner-tab" onclick="switchTab(this,\'dt3\')">上屏缺失明细</div>')
            tab_body += (f'<div id="dt2" class="inner-pane">{tab2_html}</div>'
                         f'<div id="dt3" class="inner-pane">{tab3_html}</div>')

        tab_nav += '</div>'

        section_html = (
            f'<div class="section">'
            f'<div class="section-header">📋 {mode_name} — {filter_type}</div>'
            f'<div class="section-body">{tab_nav}{tab_body}</div>'
            f'</div>'
        )

        body_html = cards_html + section_html
        return self.build_html_page(f"时延分析报告 — {filter_type}", body_html)

    # ── summary text ──

    def _build_summary(self, stats: DelayStats, output_path: str, filter_type: str) -> str:
        mode_name = "实时上屏时延" if stats.mode == "realtime" else "最终结果时延"
        lines = [
            f"  分析类型    : {mode_name}",
            f"  回调类型    : {filter_type}",
            f"  已匹配发话  : {stats.total_matched}",
            f"  未匹配发话  : {stats.total_unmatched}",
            "",
            f"  最小时延    : {stats.min_delay_ms:.1f} ms",
            f"  最大时延    : {stats.max_delay_ms:.1f} ms",
            f"  平均时延    : {stats.avg_delay_ms:.1f} ms",
        ]
        if stats.mode == "realtime":
            lines += [
                "",
                f"  首字上屏平均时延: {stats.first_char_avg_delay_ms:.1f} ms",
                f"  尾字上屏平均时延: {stats.last_char_avg_delay_ms:.1f} ms",
                f"  上屏间隔标准差  : {stats.gap_std_ms:.2f} ms",
                f"  连续吐字率      : {stats.instant_rate * 100:.1f}%"
                f"  （间隔 ≤ {INSTANT_THRESHOLD_MS:.0f} ms）",
                f"  识别卡顿率      : {stats.stutter_rate * 100:.1f}%"
                f"  （间隔 ≥ {STUTTER_THRESHOLD_MS:.0f} ms）",
                f"  上屏结果缺失率  : {stats.overall_missing_rate * 100:.1f}%",
            ]
        lines += ["", f"  报告已输出至: {output_path}"]
        return self.format_summary_box(f"ASR 时延分析 — {mode_name}", "\n".join(lines))


# ─── CLI Entry Point ──────────────────────────────────────────────────────────

def main():
    """
    命令行入口函数

    使用示例:
        python3 -m src.testsuite.NANO.tools.tsr.delay \\
            -ref label.txt -r callback.jsonl -t PSTTASRResultTemp -o delay.xlsx

        python3 src/testsuite/NANO/tools/tsr/delay.py \\
            -ref label.txt -r callback.jsonl -t PSTTASRResult
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="ASR 时延分析工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 实时上屏时延（type 以 Temp 结尾）
  python3 %(prog)s -ref label.txt -r callback.jsonl -t PSTTASRResultTemp -o delay.xlsx

  # 最终结果时延
  python3 %(prog)s -ref label.txt -r callback.jsonl -t PSTTASRResult

标注文件格式（卡拉OK式，每行一句发话）:
  TestAudio/1.wav   <0.3>打<0.5>开<0.8>车<1.2>窗<1.5>
  TestAudio/1.wav   <3.3>关<3.5>闭<3.8>空<4.2>调<4.5>

  规则：每个字的结束时间 = 它后面的时间标记；最后一个 <time> 是整句结束时间点。

JSONL 文件格式:
  每行一条 JSON，需包含 callback_type、data.audio、data.audiotime、
  data.asr、data.start（ms）、data.end（ms） 字段。

输出 Excel（4 个 Sheet）:
  汇总         — 总体统计指标
  时延明细     — 每条测量的详细数据
  上屏间隔分布 — 相邻实时结果的 audiotime 差（实时模式专有）
  上屏缺失明细 — 每句话的缺失步数统计（实时模式专有）
        """,
    )

    parser.add_argument(
        "-ref", "--ref", required=True,
        help="卡拉OK式标注文件路径",
    )
    parser.add_argument(
        "-r", "--result", required=True,
        help="callback.jsonl 文件路径",
    )
    parser.add_argument(
        "-t", "--type", required=True, dest="filter_type",
        help="回调类型，如 PSTTASRResultTemp（实时）或 PSTTASRResult（最终）",
    )
    parser.add_argument(
        "-o", "--output", default=None,
        help="Excel 报告输出路径（默认：当前目录/delay.xlsx）",
    )

    args = parser.parse_args()

    # -o 未传时不传入 output=，让 execute 自动落到 cwd/mango_report/ 目录
    params = [
        f"ref={args.ref}",
        f"result={args.result}",
        f"type={args.filter_type}",
    ]
    if args.output:
        params.append(f"output={args.output}")

    handler = ASRDelayHandler(config=None)
    try:
        summary = handler.execute(params)
        print(summary)
    except FileNotFoundError as e:
        print(f"❌ 文件不存在: {e}")
        exit(1)
    except ValueError as e:
        print(f"❌ 参数错误: {e}")
        exit(1)
    except Exception as e:
        print(f"❌ 执行失败: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    main()
