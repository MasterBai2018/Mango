#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2026/04/08
# @Author  : huidong.bai
# @File    : pstt_accuracy.py
# @Software: PyCharm
# @Mail    : baihuidong@pachiratech.com
"""
PSTT_ACCURACY 指令实现

用于统计 pstt_client_qa 产生的结果文件，支持以下维度：
  - asr   : ASR 识别准确率（句准率 + 字准率）
  - lang  : 语种识别正确率
  - sex/age/emotion : 性别/年龄/情绪识别正确率（支持子维度组合）
  - gpu   : GPU 推理时延统计（P50/P90/P99/均值/标准差）

支持单测试集（局部）和多测试集目录（全局汇总）两种输入模式。

----------------------------------------------------------------------
result 文件格式（pstt_client_qa 输出的 TSV，_full.txt）：
    audio  asr  timebord  sex/age/emotion  lang  process_time  wave_time  rt  gpu_delay

ref 文件格式（用户提供的标注 TSV）：
    AUDIOPATH  [TEXT]  [LANG]  [SEX]  [AGE]  [EMOTION]
    其中 AUDIOPATH 必须存在；其余列按需提供，与 type 参数对应。

----------------------------------------------------------------------
指令格式:
    # 单文件（局部分析）
    [TSR]PSTT_ACCURACY result=path/to/C1_full.txt ref=path/to/C1_ref.tsv type=asr,lang,sex,gpu

    # 目录（全局汇总）——按 bref 前缀匹配：
    #   result 目录下：<bref>_full.txt
    #   ref    目录下：按优先级匹配
    #                  <bref>_ref.tsv / <bref>.tsv /
    #                  <bref>_ref.csv / <bref>.csv /
    #                  <bref>_ref.txt / <bref>.txt /
    #                  <bref>_ref.ref / <bref>.ref
    [TSR]PSTT_ACCURACY result=path/to/result_file/ ref=path/to/ref/ type=auto

    可选参数：
      output=<xlsx 路径>     报告输出路径（默认 suite_mango_dir/pstt_accuracy.xlsx）

----------------------------------------------------------------------
bref 匹配规则：
  result 文件名格式 ：  {bref}_full.txt
                     或 {bref}__<n>_full.txt（自动避重产物）
  ref    文件名格式 ：  {bref}_ref.tsv | {bref}.tsv | {bref}_ref.csv | {bref}.csv |
                       {bref}_ref.txt | {bref}.txt | {bref}_ref.ref | {bref}.ref
  优先按完整 bref 精确匹配，若 bref 含 __ 后缀会回退到基础 bref 匹配。
"""

import os
import re
import sys
import csv
import math
import statistics
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass, field
from loguru import logger

try:
    from . import register_tsr_command
    from .base import BaseTSRHandler, calculate_edit_distance, EditDistance
except ImportError:
    _cur = os.path.dirname(os.path.abspath(__file__))
    _root = os.path.abspath(os.path.join(_cur, '..', '..', '..', '..', '..'))
    if _root not in sys.path:
        sys.path.insert(0, _root)
    from src.testsuite.NANO.tools.tsr import register_tsr_command
    from src.testsuite.NANO.tools.tsr.base import BaseTSRHandler, calculate_edit_distance, EditDistance


# ──────────────────────────────────────────────────────────────────────────────
# 常量 / 映射
# ──────────────────────────────────────────────────────────────────────────────

VALID_TYPES: Set[str] = {"asr", "lang", "gpu", "gae", "sex", "age", "emotion", "auto"}
_DEFAULT_TYPES: List[str] = ["asr", "lang", "sex", "age", "emotion", "gpu"]
_GAE_SUB_TYPES: Set[str] = {"sex", "age", "emotion"}
_TYPE_ORDER: List[str] = ["asr", "lang", "sex", "age", "emotion", "gpu"]

# sex/age/emotion 字段在 ref 中对应的列名
REF_COL_FOR_TYPE = {
    "asr":  ["TEXT"],
    "lang": ["LANG"],
    "gae":  ["SEX", "AGE", "EMOTION"],  # 兼容旧参数，解析时会展开为 sex/age/emotion
    "sex":  ["SEX"],
    "age":  ["AGE"],
    "emotion": ["EMOTION"],
    "gpu":  [],          # gpu 无需 ref 列
}

# result TSV 列名（pstt_client_qa 输出）
RESULT_COL_AUDIO    = "audio"
RESULT_COL_ASR      = "asr"
RESULT_COL_GAE      = "sex/age/emotion"
RESULT_COL_LANG     = "lang"
RESULT_COL_GPU      = "gpu_delay"

# 语种标准化
_LANG_ALIASES: Dict[str, str] = {}
_LANG_MAP_RAW = {
    "cmn": ["cmn", "zh-cmn", "mandarin", "chinese", "zh"],
    "yue": ["yue", "zh-yue", "cantonese"],
    "eng": ["eng", "en", "en-us", "en-gb", "en-au", "english"],
    "jpn": ["jpn", "ja", "jp", "japanese"],
}
for _std, _aliases in _LANG_MAP_RAW.items():
    for _a in _aliases:
        _LANG_ALIASES[_a.lower()] = _std

# PSTTClient 里的映射（解析 result 的 sex/age/emotion 字段用）
_EMOTION_MAP = {"Sad": "sad", "Hpy": "happy", "Neu": "neutral", "Ag": "angry"}
_SEX_MAP     = {"M": "male", "F": "female"}
_AGE_MAP     = {"儿童": "child", "少年": "youth", "青年": "teenage", "中年": "middleage"}


def _safe_strip(v) -> str:
    """兼容 CSV 缺失值为 None 的情况，统一转为可安全 strip 的字符串。"""
    if v is None:
        return ""
    return str(v).strip()


# ──────────────────────────────────────────────────────────────────────────────
# 数据类
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class SingleRecord:
    """result 文件中一行已解析的数据"""
    audio:      str
    asr:        str
    lang:       str
    emotion:    str         # 原始值，已通过 _EMOTION_MAP 映射
    sex:        str         # 原始值，已通过 _SEX_MAP 映射
    age:        str         # 原始值，已通过 _AGE_MAP 映射
    gpu_delay:  float       # ms
    gae_parse_ok: bool      # sex/age/emotion 字段是否解析成功


@dataclass
class RefRecord:
    """ref 文件中一行已解析的数据"""
    audio:   str
    text:    str = ""
    lang:    str = ""
    sex:     str = ""
    age:     str = ""
    emotion: str = ""


# ── ASR ──
@dataclass
class ASRStats:
    total: int = 0
    correct: int = 0
    error: int = 0
    empty: int = 0
    missing: int = 0            # ref 中有，result 中无
    total_ref_chars: int = 0
    total_subs: int = 0
    total_ins: int = 0
    total_dels: int = 0

    @property
    def sentence_acc(self) -> float:
        return self.correct / self.total if self.total else 0.0

    @property
    def char_acc(self) -> float:
        if not self.total_ref_chars:
            return 0.0
        return max(0.0, 1.0 - (self.total_subs + self.total_ins + self.total_dels) / self.total_ref_chars)


@dataclass
class ASRDetail:
    audio: str
    ref_text: str
    hyp_text: str
    is_correct: bool
    is_empty: bool
    edit_dist: int
    char_acc: float
    subs: int = 0   # 替换操作数
    ins: int = 0    # 插入操作数
    dels: int = 0   # 删除操作数

    @property
    def error_type(self) -> str:
        """根据编辑操作数判断主要错误类型"""
        if self.is_correct:
            return ""
        if self.is_empty:
            return "删除"
        counts = [(self.dels, "删除"), (self.ins, "插入"), (self.subs, "字错")]
        dominant = max(counts, key=lambda x: x[0])
        return dominant[1] if dominant[0] > 0 else "字错"


# ── LANG ──
@dataclass
class LangStats:
    total: int = 0
    correct: int = 0
    error: int = 0
    empty: int = 0
    missing: int = 0
    distribution: Dict[str, int] = field(default_factory=dict)

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0


@dataclass
class LangDetail:
    audio: str
    detected: str
    normalized: str
    expected: str
    is_correct: bool


# ── GAE ──
@dataclass
class GAESubStats:
    """性别 / 年龄 / 情绪 中单个维度的统计"""
    total: int = 0
    correct: int = 0
    error: int = 0
    parse_fail: int = 0     # result 字段解析失败

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0


@dataclass
class GAEStats:
    sex:     GAESubStats = field(default_factory=GAESubStats)
    age:     GAESubStats = field(default_factory=GAESubStats)
    emotion: GAESubStats = field(default_factory=GAESubStats)


@dataclass
class GAEDetail:
    audio: str
    # result 解析值
    res_sex:     str
    res_age:     str
    res_emotion: str
    # ref 期望值
    ref_sex:     str
    ref_age:     str
    ref_emotion: str
    # 是否正确
    sex_ok:     bool
    age_ok:     bool
    emotion_ok: bool
    parse_ok:   bool


# ── GPU ──
@dataclass
class GPUStats:
    total: int = 0
    values: List[float] = field(default_factory=list)
    min_ms: float = 0.0
    max_ms: float = 0.0
    avg_ms: float = 0.0
    std_ms: float = 0.0
    p50_ms: float = 0.0
    p80_ms: float = 0.0
    p90_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0


# ── 单测试集完整统计 ──
@dataclass
class TestsetStats:
    bref:       str             # 测试集名称（来自文件名前缀）
    result_file: str
    ref_file:   Optional[str]
    types:      List[str]
    asr:        Optional[ASRStats]  = None
    lang:       Optional[LangStats] = None
    gae:        Optional[GAEStats]  = None
    gpu:        Optional[GPUStats]  = None
    asr_details:  List[ASRDetail]  = field(default_factory=list)
    lang_details: List[LangDetail] = field(default_factory=list)
    gae_details:  List[GAEDetail]  = field(default_factory=list)


# ── 全局汇总 ──
@dataclass
class GlobalStats:
    testsets:   List[TestsetStats]
    types:      List[str]
    asr:        Optional[ASRStats]  = None
    lang:       Optional[LangStats] = None
    gae:        Optional[GAEStats]  = None
    gpu:        Optional[GPUStats]  = None


# ──────────────────────────────────────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────────────────────────────────────

def _normalize_audio_path(p: str) -> str:
    """统一用 / 分隔的绝对路径（无法 abs 时原样返回）"""
    return os.path.normpath(p).replace('\\', '/')


def _normalize_types(raw_types: List[str]) -> List[str]:
    """
    规范化 type 列表：
    - gae 展开为 sex/age/emotion
    - 保序去重
    """
    expanded: List[str] = []
    for t in raw_types:
        if t == "gae":
            expanded.extend(["sex", "age", "emotion"])
        else:
            expanded.append(t)
    dedup: List[str] = []
    for t in expanded:
        if t not in dedup:
            dedup.append(t)
    return dedup


def _parse_type_expr(type_expr: str,
                     allow_auto: bool = False,
                     context: str = "type") -> List[str]:
    """解析 type 表达式并返回规范化后的 type 列表"""
    if not type_expr:
        raise ValueError(f"{context} 为空")
    raw_types = [t.strip().lower() for t in type_expr.split(",") if t.strip()]
    if not raw_types:
        raise ValueError(f"{context} 为空")
    invalid = [t for t in raw_types if t not in VALID_TYPES]
    if invalid:
        raise ValueError(
            f"{context} 包含无效维度: {invalid}，支持: {sorted(VALID_TYPES)}"
        )
    if not allow_auto and "auto" in raw_types:
        raise ValueError(f"{context} 不支持 auto")
    if "auto" in raw_types and len(raw_types) > 1:
        raise ValueError(f"{context} 为 auto 时不可与其他维度混用")
    if raw_types == ["auto"]:
        return ["auto"]
    return _normalize_types(raw_types)


def _sort_types(types: List[str]) -> List[str]:
    """按固定顺序排序 type，便于稳定展示"""
    return [t for t in _TYPE_ORDER if t in types]


def _need_ref_for_types(types: List[str]) -> bool:
    """是否需要 ref 文件"""
    return any(t != "gpu" for t in types)


def _required_ref_columns(types: List[str]) -> List[str]:
    """根据 type 计算 ref 必须包含的列（不含 AUDIOPATH）"""
    required: List[str] = []
    for t in types:
        required.extend(REF_COL_FOR_TYPE.get(t, []))
    return list(dict.fromkeys(required))


def _selected_gae_sub_types(types: List[str]) -> List[str]:
    """返回当前需要展示/统计的 GAE 子维度"""
    return [k for k in ("sex", "age", "emotion") if k in types]


def _parse_ref_meta_lines(filepath: str) -> Tuple[Optional[List[str]], List[str]]:
    """
    解析 ref 文件顶部元信息：
    - 支持 @TYPE: xxx
    - 返回 (声明的 types, 去掉元信息后的数据行)
    """
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        lines = f.readlines()

    data_start = 0
    declared_types: Optional[List[str]] = None
    for idx, raw in enumerate(lines):
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        m = re.match(r'^@TYPE\s*:\s*(.+)$', stripped, flags=re.IGNORECASE)
        if m:
            declared_types = _parse_type_expr(
                m.group(1).strip(),
                allow_auto=False,
                context=f"ref 文件 @TYPE ({filepath})"
            )
            continue
        data_start = idx
        break
    else:
        data_start = len(lines)

    return declared_types, lines[data_start:]


def _normalize_lang(lang: str) -> str:
    if not lang:
        return ""
    return _LANG_ALIASES.get(lang.strip().lower(), lang.strip().lower())


def _parse_gae_field(raw: str) -> Tuple[str, str, str, bool]:
    """
    解析 sex/age/emotion 字段，支持两种格式：
      - 5 段: [Neu/65/青年/99/F]
      - 4 段: [Neu/65/青年/99]（sex 记为空）
    返回 (emotion, age, sex, parse_ok)；失败时返回 ("", "", "", False)
    """
    if not raw:
        return "", "", "", False
    m = re.match(r'^\[(.+)\]$', raw.strip())
    if not m:
        return "", "", "", False
    parts = m.group(1).split('/')
    if len(parts) < 4:
        return "", "", "", False
    try:
        emotion_raw = parts[0].strip()
        age_raw     = parts[2].strip()
        # 兼容旧数据只有 4 段的情况：sex 缺失时置空
        sex_raw     = parts[4].strip() if len(parts) >= 5 else ""
        emotion = _EMOTION_MAP.get(emotion_raw, emotion_raw.lower())
        sex     = _SEX_MAP.get(sex_raw,         sex_raw.lower())
        age     = _AGE_MAP.get(age_raw,          age_raw.lower())
        return emotion, age, sex, True
    except Exception:
        return "", "", "", False


def _percentile(data: List[float], pct: float) -> float:
    """线性插值分位数（pct 为 0-100）"""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    n = len(sorted_data)
    idx = (pct / 100.0) * (n - 1)
    lo, hi = int(idx), min(int(idx) + 1, n - 1)
    frac = idx - lo
    return sorted_data[lo] + frac * (sorted_data[hi] - sorted_data[lo])


def _detect_delimiter(filepath: str) -> str:
    with open(filepath, 'r', encoding='utf-8') as f:
        first = f.readline()
    return '\t' if first.count('\t') >= first.count(',') else ','


# ──────────────────────────────────────────────────────────────────────────────
# 文件加载
# ──────────────────────────────────────────────────────────────────────────────

def _load_result_file(filepath: str) -> List[SingleRecord]:
    """加载 pstt_client_qa 输出的 _full.txt TSV，跳过 header 行"""
    records: List[SingleRecord] = []
    delim = _detect_delimiter(filepath)
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=delim)
        for lineno, row in enumerate(reader, 2):
            audio = row.get(RESULT_COL_AUDIO, '').strip()
            if not audio:
                continue
            # gpu_delay
            try:
                gpu_delay = float(row.get(RESULT_COL_GPU, '0') or 0)
            except ValueError:
                gpu_delay = 0.0
            # sex/age/emotion
            gae_raw = row.get(RESULT_COL_GAE, '').strip()
            emotion, age, sex, gae_ok = _parse_gae_field(gae_raw)
            if not gae_ok and gae_raw:
                logger.debug(f"result 第 {lineno} 行 GAE 字段解析失败: {gae_raw!r}")

            records.append(SingleRecord(
                audio=_normalize_audio_path(audio),
                asr=row.get(RESULT_COL_ASR, '').strip(),
                lang=_normalize_lang(row.get(RESULT_COL_LANG, '').strip()),
                emotion=emotion,
                sex=sex,
                age=age,
                gpu_delay=gpu_delay,
                gae_parse_ok=gae_ok,
            ))
    logger.info(f"result 文件加载完成：{len(records)} 条 — {os.path.basename(filepath)}")
    return records


def _load_ref_file(filepath: str, required_cols: List[str]
                   ) -> Tuple[Dict[str, RefRecord], List[str], Optional[List[str]]]:
    """
    加载 ref 文件（TSV/CSV），返回 {normalized_audio_path: RefRecord}。
    required_cols 为当前 types 需要的 ref 列名列表，不满足时 raise ValueError。
    第二个返回值为实际存在的列名列表（用于错误提示）。
    """
    declared_types, content_lines = _parse_ref_meta_lines(filepath)
    if not content_lines:
        raise ValueError(f"ref 文件缺少表头与数据：{filepath}")
    header = content_lines[0]
    delim = '\t' if header.count('\t') >= header.count(',') else ','
    reader = csv.DictReader(content_lines, delimiter=delim)
    fieldnames = reader.fieldnames or []
    upper_fields = {fn.upper(): fn for fn in fieldnames}   # 大小写不敏感查找

    # 检查必要列
    if 'AUDIOPATH' not in upper_fields:
        raise ValueError(f"ref 文件缺少必要列 AUDIOPATH：{filepath}")
    for col in required_cols:
        if col.upper() not in upper_fields:
            raise ValueError(
                f"ref 文件缺少列 {col}（type 需要），文件中有：{list(fieldnames)}，路径：{filepath}"
            )

    audio_col   = upper_fields['AUDIOPATH']
    text_col    = upper_fields.get('TEXT')
    lang_col    = upper_fields.get('LANG')
    sex_col     = upper_fields.get('SEX')
    age_col     = upper_fields.get('AGE')
    emotion_col = upper_fields.get('EMOTION')

    ref_map: Dict[str, RefRecord] = {}
    for row in reader:
        audio = _safe_strip(row.get(audio_col, ''))
        if not audio:
            continue
        norm_audio = _normalize_audio_path(audio)
        ref_map[norm_audio] = RefRecord(
            audio=norm_audio,
            text=_safe_strip(row.get(text_col, '')) if text_col else '',
            lang=_normalize_lang(_safe_strip(row.get(lang_col, ''))) if lang_col else '',
            sex=_safe_strip(row.get(sex_col, '')).lower() if sex_col else '',
            age=_safe_strip(row.get(age_col, '')).lower() if age_col else '',
            emotion=_safe_strip(row.get(emotion_col, '')).lower() if emotion_col else '',
        )
    logger.info(f"ref 文件加载完成：{len(ref_map)} 条 — {os.path.basename(filepath)}")
    return ref_map, list(fieldnames), declared_types


# ──────────────────────────────────────────────────────────────────────────────
# 各维度计算
# ──────────────────────────────────────────────────────────────────────────────

def _calc_asr(result_map: Dict[str, SingleRecord],
              ref_map: Dict[str, RefRecord]) -> Tuple[ASRStats, List[ASRDetail]]:
    stats = ASRStats()
    details: List[ASRDetail] = []

    for audio, ref in ref_map.items():
        ref_text = ref.text.strip().lower()
        stats.total += 1
        stats.total_ref_chars += len(ref_text)

        if audio not in result_map:
            stats.missing += 1
            stats.empty += 1
            ed = calculate_edit_distance(ref_text, "")
            stats.total_dels += ed.deletions
            details.append(ASRDetail(
                audio=audio, ref_text=ref_text, hyp_text="",
                is_correct=False, is_empty=True,
                edit_dist=ed.distance, char_acc=0.0,
                subs=ed.substitutions, ins=ed.insertions, dels=ed.deletions,
            ))
            continue

        hyp_text = result_map[audio].asr.strip().lower()
        is_empty = not hyp_text
        if is_empty:
            stats.empty += 1

        ed = calculate_edit_distance(ref_text, hyp_text)
        stats.total_subs += ed.substitutions
        stats.total_ins  += ed.insertions
        stats.total_dels += ed.deletions

        is_correct = (ref_text == hyp_text)
        if is_correct:
            stats.correct += 1
        else:
            stats.error += 1

        char_acc = ed.accuracy
        details.append(ASRDetail(
            audio=audio, ref_text=ref_text, hyp_text=hyp_text,
            is_correct=is_correct, is_empty=is_empty,
            edit_dist=ed.distance, char_acc=char_acc,
            subs=ed.substitutions, ins=ed.insertions, dels=ed.deletions,
        ))

    return stats, details


def _calc_lang(result_map: Dict[str, SingleRecord],
               ref_map: Dict[str, RefRecord]) -> Tuple[LangStats, List[LangDetail]]:
    stats = LangStats()
    details: List[LangDetail] = []

    for audio, ref in ref_map.items():
        expected = ref.lang
        stats.total += 1

        if audio not in result_map:
            stats.missing += 1
            stats.empty += 1
            stats.distribution['(缺失)'] = stats.distribution.get('(缺失)', 0) + 1
            details.append(LangDetail(audio=audio, detected='', normalized='',
                                      expected=expected, is_correct=False))
            continue

        detected_norm = result_map[audio].lang
        if not detected_norm:
            stats.empty += 1
            stats.distribution['(空)'] = stats.distribution.get('(空)', 0) + 1
        else:
            stats.distribution[detected_norm] = stats.distribution.get(detected_norm, 0) + 1

        is_correct = bool(detected_norm) and (detected_norm == expected)
        if is_correct:
            stats.correct += 1
        else:
            stats.error += 1

        details.append(LangDetail(
            audio=audio,
            detected=result_map[audio].lang,
            normalized=detected_norm,
            expected=expected,
            is_correct=is_correct,
        ))

    return stats, details


def _calc_gae(result_map: Dict[str, SingleRecord],
              ref_map: Dict[str, RefRecord]) -> Tuple[GAEStats, List[GAEDetail]]:
    stats = GAEStats()
    details: List[GAEDetail] = []

    for audio, ref in ref_map.items():
        if audio not in result_map:
            # missing：三个子维度各算一条缺失
            for sub in (stats.sex, stats.age, stats.emotion):
                sub.total += 1
                sub.error += 1
            details.append(GAEDetail(
                audio=audio,
                res_sex='', res_age='', res_emotion='',
                ref_sex=ref.sex, ref_age=ref.age, ref_emotion=ref.emotion,
                sex_ok=False, age_ok=False, emotion_ok=False, parse_ok=False,
            ))
            continue

        rec = result_map[audio]
        parse_ok = rec.gae_parse_ok

        # ── sex ──
        stats.sex.total += 1
        if not parse_ok:
            stats.sex.parse_fail += 1
            stats.sex.error += 1
        else:
            sex_ok = (rec.sex == ref.sex)
            if sex_ok:
                stats.sex.correct += 1
            else:
                stats.sex.error += 1

        # ── age ──
        stats.age.total += 1
        if not parse_ok:
            stats.age.parse_fail += 1
            stats.age.error += 1
        else:
            age_ok = (rec.age == ref.age)
            if age_ok:
                stats.age.correct += 1
            else:
                stats.age.error += 1

        # ── emotion ──
        stats.emotion.total += 1
        if not parse_ok:
            stats.emotion.parse_fail += 1
            stats.emotion.error += 1
        else:
            emotion_ok = (rec.emotion == ref.emotion)
            if emotion_ok:
                stats.emotion.correct += 1
            else:
                stats.emotion.error += 1

        sex_ok_val     = parse_ok and (rec.sex     == ref.sex)
        age_ok_val     = parse_ok and (rec.age     == ref.age)
        emotion_ok_val = parse_ok and (rec.emotion == ref.emotion)

        details.append(GAEDetail(
            audio=audio,
            res_sex=rec.sex, res_age=rec.age, res_emotion=rec.emotion,
            ref_sex=ref.sex, ref_age=ref.age, ref_emotion=ref.emotion,
            sex_ok=sex_ok_val, age_ok=age_ok_val, emotion_ok=emotion_ok_val,
            parse_ok=parse_ok,
        ))

    return stats, details


def _calc_gpu(records: List[SingleRecord]) -> GPUStats:
    values = [r.gpu_delay for r in records if r.gpu_delay > 0]
    stats = GPUStats(total=len(values), values=values)
    if not values:
        return stats
    stats.min_ms = min(values)
    stats.max_ms = max(values)
    stats.avg_ms = statistics.mean(values)
    stats.std_ms = statistics.stdev(values) if len(values) >= 2 else 0.0
    stats.p50_ms = _percentile(values, 50)
    stats.p80_ms = _percentile(values, 80)
    stats.p90_ms = _percentile(values, 90)
    stats.p95_ms = _percentile(values, 95)
    stats.p99_ms = _percentile(values, 99)
    return stats


# ──────────────────────────────────────────────────────────────────────────────
# 单测试集处理
# ──────────────────────────────────────────────────────────────────────────────

def _process_testset(bref: str, result_file: str, ref_file: Optional[str],
                     types: List[str]) -> TestsetStats:
    """处理单个测试集，返回 TestsetStats"""

    # 确定 ref 需要哪些列
    required_ref_cols = _required_ref_columns(types)

    # 加载
    result_records = _load_result_file(result_file)
    result_map: Dict[str, SingleRecord] = {r.audio: r for r in result_records}

    ref_map: Dict[str, RefRecord] = {}
    if _need_ref_for_types(types):
        if not ref_file:
            raise ValueError(f"测试集 {bref} 需要 ref 文件，但未提供")
        ref_map, _, _ = _load_ref_file(ref_file, required_ref_cols)

    ts = TestsetStats(bref=bref, result_file=result_file,
                      ref_file=ref_file, types=types)

    if "asr" in types:
        ts.asr, ts.asr_details = _calc_asr(result_map, ref_map)

    if "lang" in types:
        ts.lang, ts.lang_details = _calc_lang(result_map, ref_map)

    if _selected_gae_sub_types(types):
        ts.gae, ts.gae_details = _calc_gae(result_map, ref_map)

    if "gpu" in types:
        ts.gpu = _calc_gpu(result_records)

    return ts


# ──────────────────────────────────────────────────────────────────────────────
# 全局汇总
# ──────────────────────────────────────────────────────────────────────────────

def _merge_asr(testsets: List[TestsetStats]) -> Optional[ASRStats]:
    valid = [ts.asr for ts in testsets if ts.asr is not None]
    if not valid:
        return None
    g = ASRStats()
    for a in valid:
        g.total           += a.total
        g.correct         += a.correct
        g.error           += a.error
        g.empty           += a.empty
        g.missing         += a.missing
        g.total_ref_chars += a.total_ref_chars
        g.total_subs      += a.total_subs
        g.total_ins       += a.total_ins
        g.total_dels      += a.total_dels
    return g


def _merge_lang(testsets: List[TestsetStats]) -> Optional[LangStats]:
    valid = [ts.lang for ts in testsets if ts.lang is not None]
    if not valid:
        return None
    g = LangStats()
    for l in valid:
        g.total   += l.total
        g.correct += l.correct
        g.error   += l.error
        g.empty   += l.empty
        g.missing += l.missing
        for lang, cnt in l.distribution.items():
            g.distribution[lang] = g.distribution.get(lang, 0) + cnt
    return g


def _merge_gae(testsets: List[TestsetStats]) -> Optional[GAEStats]:
    valid = [ts.gae for ts in testsets if ts.gae is not None]
    if not valid:
        return None
    g = GAEStats()
    for gae in valid:
        for src, dst in [(gae.sex, g.sex), (gae.age, g.age), (gae.emotion, g.emotion)]:
            dst.total      += src.total
            dst.correct    += src.correct
            dst.error      += src.error
            dst.parse_fail += src.parse_fail
    return g


def _merge_gpu(testsets: List[TestsetStats]) -> Optional[GPUStats]:
    all_values: List[float] = []
    for ts in testsets:
        if ts.gpu:
            all_values.extend(ts.gpu.values)
    if not all_values:
        return None
    # 重新计算分位数
    fake_records = [SingleRecord(audio='', asr='', lang='', emotion='', sex='',
                                  age='', gpu_delay=v, gae_parse_ok=True)
                    for v in all_values]
    return _calc_gpu(fake_records)


def _build_global(testsets: List[TestsetStats], types: List[str]) -> GlobalStats:
    g = GlobalStats(testsets=testsets, types=types)
    if "asr"  in types: g.asr  = _merge_asr(testsets)
    if "lang" in types: g.lang = _merge_lang(testsets)
    if _selected_gae_sub_types(types): g.gae  = _merge_gae(testsets)
    if "gpu"  in types: g.gpu  = _merge_gpu(testsets)
    return g


# ──────────────────────────────────────────────────────────────────────────────
# 文件配对（目录模式）
# ──────────────────────────────────────────────────────────────────────────────

def _get_bref_from_result(filename: str) -> Optional[str]:
    """从 result 文件名提取 bref：<bref>_full.txt"""
    if filename.endswith('_full.txt'):
        return filename[:-len('_full.txt')]
    return None


def _iter_bref_match_keys(bref: str) -> List[str]:
    """
    生成用于 ref 匹配的 bref 候选键：
    - 先尝试完整 bref（保持一一对应）
    - 若包含避重后缀（例如 xxx__2），再回退到基础 bref
    """
    keys: List[str] = []
    b = (bref or "").strip()
    if b:
        keys.append(b)

    if "__" in b:
        base = b.split("__", 1)[0].strip()
        if base and base not in keys:
            keys.append(base)
    return keys


def _find_ref_for_bref(ref_dir: str, bref: str) -> Optional[str]:
    """在 ref_dir 中按 bref 精确匹配 ref 文件（按后缀优先级）"""
    for key in _iter_bref_match_keys(bref):
        candidates = [
            f"{key}_ref.tsv",
            f"{key}.tsv",
            f"{key}_ref.csv",
            f"{key}.csv",
            f"{key}_ref.txt",
            f"{key}.txt",
            f"{key}_ref.ref",
            f"{key}.ref",
        ]
        for name in candidates:
            path = os.path.join(ref_dir, name)
            if os.path.isfile(path):
                return path
    return None


def _pair_files(result_path: str,
                ref_path: Optional[str],
                allow_missing_ref: bool = False
                ) -> List[Tuple[str, str, Optional[str]]]:
    """
    返回 [(bref, result_file, ref_file|None), ...]。
    result_path/ref_path 可以是文件或目录。
    - 单文件模式：bref 取 result 文件名 stem
    - 目录模式：按 _full.txt 前缀 + ref 目录中同名文件配对
    """
    pairs: List[Tuple[str, str, Optional[str]]] = []
    has_ref = bool(ref_path and str(ref_path).strip().lower() != "none")

    if os.path.isfile(result_path):
        # 单文件
        bref = _get_bref_from_result(os.path.basename(result_path))
        if bref is None:
            bref = os.path.splitext(os.path.basename(result_path))[0]
        if not has_ref:
            if allow_missing_ref:
                ref_file = None
            else:
                raise FileNotFoundError("未提供 ref 文件或目录")
        elif os.path.isdir(ref_path):
            ref_file = _find_ref_for_bref(ref_path, bref)
            if ref_file is None and not allow_missing_ref:
                raise FileNotFoundError(
                    f"在 ref 目录中未找到 bref={bref!r} 对应的 ref 文件：{ref_path}"
                )
        else:
            ref_file = ref_path
        pairs.append((bref, result_path, ref_file))
        return pairs

    # 目录模式
    if not os.path.isdir(result_path):
        raise FileNotFoundError(f"result 路径不存在：{result_path}")
    if has_ref and not os.path.isdir(ref_path):
        if allow_missing_ref and os.path.isfile(ref_path):
            # 兼容传入单个 ref 文件：目录模式下不支持一对多，这里按缺失处理
            logger.warning(f"result 为目录但 ref 为文件，将按缺失处理: {ref_path}")
            has_ref = False
        elif not allow_missing_ref:
            raise FileNotFoundError(f"result 为目录时，ref 也必须是目录：{ref_path}")
        else:
            has_ref = False

    result_files = sorted(
        f for f in os.listdir(result_path)
        if f.endswith('_full.txt') and os.path.isfile(os.path.join(result_path, f))
    )
    if not result_files:
        raise FileNotFoundError(f"result 目录中未找到任何 *_full.txt 文件：{result_path}")

    for fname in result_files:
        bref = _get_bref_from_result(fname)
        ref_file = _find_ref_for_bref(ref_path, bref) if has_ref else None
        if ref_file is None and not allow_missing_ref:
            raise FileNotFoundError(
                f"在 ref 目录中未找到 bref={bref!r} 对应的 ref 文件，"
                f"请在 {ref_path} 中放置如下文件之一: "
                f"{bref}_ref.tsv / {bref}.tsv / {bref}_ref.csv / {bref}.csv / "
                f"{bref}_ref.txt / {bref}.txt / {bref}_ref.ref / {bref}.ref"
            )
        pairs.append((bref, os.path.join(result_path, fname), ref_file))
        logger.info(f"配对成功：bref={bref!r}  result={fname}  ref={'(无)' if not ref_file else os.path.basename(ref_file)}")

    return pairs


# ──────────────────────────────────────────────────────────────────────────────
# HTML 报告构建（Tab 式布局）
# ──────────────────────────────────────────────────────────────────────────────

def _pct(v: float) -> str:
    return f"{v * 100:.2f}%"


def _pct_safe(num: int, den: int) -> str:
    """安全计算百分比，分母为 0 时返回 0.00%"""
    return _pct(num / den) if den else "0.00%"


def _safe_html(s: Optional[str]) -> str:
    """转义 HTML 特殊字符"""
    if s is None:
        return ""
    s = str(s)
    return (s.replace('&', '&amp;')
             .replace('<', '&lt;')
             .replace('>', '&gt;')
             .replace('"', '&quot;'))


# ── 全局 CSS ──

_PSTT_EXTRA_CSS: str = """<style>
/* KPI 指标卡片 */
.kpi-row{display:flex;gap:12px;flex-wrap:wrap;margin:16px 0 24px}
.kpi-card{flex:1;min-width:110px;background:#fff;border:1px solid var(--border);
  border-radius:8px;padding:14px 12px;text-align:center;
  box-shadow:0 2px 6px rgba(0,0,0,.06)}
.kpi-value{font-size:22px;font-weight:700;color:var(--primary);line-height:1.2}
.kpi-label{font-size:11px;color:var(--text-muted);margin-top:4px}
/* 主 Tab */
.main-tabs{display:flex;flex-wrap:wrap;border-bottom:2px solid var(--primary)}
.main-tab{padding:9px 16px;cursor:pointer;font-size:13px;font-weight:500;
  color:#555;border:1px solid transparent;border-bottom:none;
  border-radius:4px 4px 0 0;transition:background .15s;user-select:none}
.main-tab.active{background:var(--primary);color:#fff;border-color:var(--primary)}
.main-tab:hover:not(.active){background:#eef4fb;color:var(--primary)}
/* Tab 面板 */
.tab-panes{border:1px solid var(--border);border-top:none;border-radius:0 0 8px 8px;
  padding:20px 16px;background:#fff}
.tab-pane{display:none}.tab-pane.active{display:block}
/* 汇总 Section */
.summary-section{margin-bottom:28px}
.summary-section-title{font-size:14px;font-weight:600;color:var(--primary);
  padding:6px 0 6px 10px;border-left:3px solid var(--primary);margin-bottom:10px}
/* 表格容器（横向滚动） */
.table-wrap{overflow-x:auto}
/* 报告表格 */
.report-table{border-collapse:collapse;width:100%;min-width:300px;font-size:13px}
.report-table th{background:#4a6fa5;color:#fff;padding:8px 10px;
  text-align:center;white-space:nowrap;font-weight:600}
.report-table td{padding:6px 10px;border:1px solid var(--border);
  text-align:center;vertical-align:middle;word-break:break-all}
.report-table tbody tr:nth-child(even) td{background:#fafafa}
.report-table tbody tr:hover td{background:#eef4fb}
.total-row td{background:#dde9f8!important;font-weight:600}
.overview-table td{word-break:break-all}
.overview-table td:nth-child(2),.overview-table td:nth-child(3){
  text-align:left;white-space:normal}
.path-cell{text-align:left!important;white-space:normal;word-break:break-all}
/* 详情面板 */
.detail-panel{margin-top:16px;border:1px solid var(--border);
  border-radius:8px;overflow:hidden}
.detail-panel-hdr{background:#f0f4ff;padding:10px 14px;font-size:13px;
  font-weight:600;color:var(--primary);border-bottom:1px solid var(--border);
  display:flex;align-items:center;justify-content:space-between}
.detail-panel-body{padding:10px}
/* 筛选栏 */
.filter-bar{display:flex;gap:16px;align-items:center;flex-wrap:wrap;
  padding:7px 12px;background:#f8f9fc;border-radius:4px;
  margin-bottom:8px;font-size:12px;color:#555}
.filter-bar label{display:flex;align-items:center;gap:5px}
.filter-select{padding:2px 6px;border:1px solid #ccc;border-radius:3px;
  font-size:12px;color:#333}
/* 纵横可滚动表格 */
.scrollable-table{overflow-x:auto;overflow-y:auto;max-height:500px}
.scrollable-table thead th{position:sticky;top:0;z-index:1}
/* 状态标签 */
.tag-pass{display:inline-block;padding:1px 8px;border-radius:10px;
  font-size:11px;background:#d4edda;color:#155724;white-space:nowrap}
.tag-fail{display:inline-block;padding:1px 8px;border-radius:10px;
  font-size:11px;background:#fce4e4;color:#721c24;white-space:nowrap}
/* 详情/收起按钮 */
.btn-detail{padding:3px 12px;border:1px solid var(--primary);border-radius:4px;
  background:#fff;color:var(--primary);font-size:12px;cursor:pointer;white-space:nowrap}
.btn-detail:hover{background:#eef4fb}
.btn-close{padding:2px 10px;border:1px solid #ccc;border-radius:4px;
  background:#fff;color:#666;font-size:12px;cursor:pointer}
.btn-close:hover{background:#f5f5f5}
/* GPU 统计卡片 */
.gpu-stat-cards{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px}
.gpu-stat-card{flex:1;min-width:80px;border:1px solid var(--border);
  border-radius:6px;padding:8px 10px;text-align:center}
.gpu-stat-card .sv{font-size:15px;font-weight:600;color:#333}
.gpu-stat-card .sl{font-size:11px;color:var(--text-muted);margin-top:2px}
</style>"""


# ── 全局 JS ──

_PSTT_JS: str = """<script>
function switchMainTab(el,tabId){
  document.querySelectorAll('.main-tab').forEach(function(t){t.classList.remove('active')});
  document.querySelectorAll('.tab-pane').forEach(function(p){p.classList.remove('active')});
  el.classList.add('active');
  var pane=document.getElementById(tabId);if(pane)pane.classList.add('active');
}
function goDetail(tabId,detailId){
  document.querySelectorAll('.main-tab').forEach(function(t){
    if(t.dataset.tab===tabId){switchMainTab(t,tabId);}
  });
  setTimeout(function(){showPanelInTab(tabId,detailId);},60);
}
function showPanelInTab(tabId,detailId){
  var pane=document.getElementById(tabId);if(!pane)return;
  pane.querySelectorAll('.detail-panel').forEach(function(p){p.style.display='none';});
  var target=document.getElementById(detailId);
  if(target){target.style.display='block';
    target.scrollIntoView({behavior:'smooth',block:'start'});}
}
function closePanel(id){var p=document.getElementById(id);if(p)p.style.display='none';}
function filterRows(tbodyId,barId){
  var bar=document.getElementById(barId);
  var selects=bar.querySelectorAll('.filter-select');
  document.getElementById(tbodyId).querySelectorAll('tr').forEach(function(row){
    var show=true;
    selects.forEach(function(sel){
      if(sel.value==='__all__')return;
      var col=parseInt(sel.dataset.col);
      var cell=row.cells[col];
      if(!cell){show=false;return;}
      if(cell.textContent.trim()!==sel.value)show=false;
    });
    row.style.display=show?'':'none';
  });
}
</script>"""


# ── 顶部 KPI 卡片 ──

def _build_kpi_cards(g: 'GlobalStats') -> str:
    """根据 types 动态生成顶部 KPI 指标卡片"""
    gae_sub_types = _selected_gae_sub_types(g.types)
    cards = []
    if g.asr:
        cards.append(
            f'<div class="kpi-card"><div class="kpi-value">{_pct(g.asr.char_acc)}</div>'
            f'<div class="kpi-label">ASR字准率</div></div>'
        )
        cards.append(
            f'<div class="kpi-card"><div class="kpi-value">{_pct(g.asr.sentence_acc)}</div>'
            f'<div class="kpi-label">ASR句准率</div></div>'
        )
    if g.lang:
        cards.append(
            f'<div class="kpi-card"><div class="kpi-value">{_pct(g.lang.accuracy)}</div>'
            f'<div class="kpi-label">语种准确率</div></div>'
        )
    if g.gae and "sex" in gae_sub_types:
        cards.append(
            f'<div class="kpi-card"><div class="kpi-value">{_pct(g.gae.sex.accuracy)}</div>'
            f'<div class="kpi-label">性别准确率</div></div>'
        )
    if g.gae and "age" in gae_sub_types:
        cards.append(
            f'<div class="kpi-card"><div class="kpi-value">{_pct(g.gae.age.accuracy)}</div>'
            f'<div class="kpi-label">年龄准确率</div></div>'
        )
    if g.gae and "emotion" in gae_sub_types:
        cards.append(
            f'<div class="kpi-card"><div class="kpi-value">{_pct(g.gae.emotion.accuracy)}</div>'
            f'<div class="kpi-label">情绪准确率</div></div>'
        )
    if g.gpu:
        cards.append(
            f'<div class="kpi-card"><div class="kpi-value">{g.gpu.p90_ms:.0f}ms</div>'
            f'<div class="kpi-label">GPU时延P90指标</div></div>'
        )
    if not cards:
        return ''
    return '<div class="kpi-row">' + ''.join(cards) + '</div>'


# ── 主 Tab 导航 ──

def _build_main_tab_nav(types: List[str]) -> str:
    """根据 types 动态生成主 Tab 导航"""
    tabs = [
        '<div class="main-tab active" data-tab="tab-summary" '
        'onclick="switchMainTab(this,\'tab-summary\')">汇总信息</div>'
    ]
    if 'asr' in types:
        tabs.append(
            '<div class="main-tab" data-tab="tab-asr" '
            'onclick="switchMainTab(this,\'tab-asr\')">ASR准确率</div>'
        )
    if 'lang' in types:
        tabs.append(
            '<div class="main-tab" data-tab="tab-lang" '
            'onclick="switchMainTab(this,\'tab-lang\')">语种准确率</div>'
        )
    if 'sex' in types:
        tabs.append(
            '<div class="main-tab" data-tab="tab-sex" '
            'onclick="switchMainTab(this,\'tab-sex\')">性别准确率</div>'
        )
    if 'age' in types:
        tabs.append(
            '<div class="main-tab" data-tab="tab-age" '
            'onclick="switchMainTab(this,\'tab-age\')">年龄准确率</div>'
        )
    if 'emotion' in types:
        tabs.append(
            '<div class="main-tab" data-tab="tab-emotion" '
            'onclick="switchMainTab(this,\'tab-emotion\')">情绪准确率</div>'
        )
    if 'gpu' in types:
        tabs.append(
            '<div class="main-tab" data-tab="tab-gpu" '
            'onclick="switchMainTab(this,\'tab-gpu\')">GPU时延</div>'
        )
    return '<div class="main-tabs">' + ''.join(tabs) + '</div>'


# ── 汇总信息 Tab ──

def _build_summary_tab(g: 'GlobalStats') -> str:
    """汇总信息 Tab：按 type 分小节，各测试集汇总数据 + 查看按钮"""
    sections: List[str] = []
    gae_sub_types = _selected_gae_sub_types(g.types)

    # ── ASR 汇总 ──
    if g.asr:
        rows = []
        for i, ts in enumerate(g.testsets):
            if not ts.asr:
                continue
            a = ts.asr
            rows.append(
                f'<tr>'
                f'<td>{_safe_html(ts.bref)}</td>'
                f'<td>{_pct(a.char_acc)}</td>'
                f'<td>{_pct_safe(a.total_ins,  a.total_ref_chars)}</td>'
                f'<td>{_pct_safe(a.total_dels, a.total_ref_chars)}</td>'
                f'<td>{_pct_safe(a.empty,      a.total)}</td>'
                f'<td>{_pct(a.sentence_acc)}</td>'
                f'<td>{a.correct}</td>'
                f'<td>{a.total}</td>'
                f'<td><button class="btn-detail" '
                f'onclick="goDetail(\'tab-asr\',\'asr-detail-{i}\')">查看</button></td>'
                f'</tr>'
            )
        ga = g.asr
        rows.append(
            f'<tr class="total-row"><td>总计</td>'
            f'<td>{_pct(ga.char_acc)}</td>'
            f'<td>{_pct_safe(ga.total_ins,  ga.total_ref_chars)}</td>'
            f'<td>{_pct_safe(ga.total_dels, ga.total_ref_chars)}</td>'
            f'<td>{_pct_safe(ga.empty,      ga.total)}</td>'
            f'<td>{_pct(ga.sentence_acc)}</td>'
            f'<td>{ga.correct}</td><td>{ga.total}</td><td></td>'
            f'</tr>'
        )
        sections.append(
            '<div class="summary-section">'
            '<div class="summary-section-title">ASR准确率</div>'
            '<div class="table-wrap"><table class="report-table"><thead><tr>'
            '<th>测试集</th><th>字准率</th><th>插入率</th><th>删除率</th>'
            '<th>空结果率</th><th>句准率</th><th>句子通过数</th><th>句子总数</th><th>详情</th>'
            '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div></div>'
        )

    # ── 语种汇总 ──
    if g.lang:
        rows = []
        for i, ts in enumerate(g.testsets):
            if not ts.lang:
                continue
            l = ts.lang
            rows.append(
                f'<tr><td>{_safe_html(ts.bref)}</td>'
                f'<td>{l.total}</td><td>{l.correct}</td>'
                f'<td>{l.error}</td><td>{l.missing}</td>'
                f'<td>{_pct(l.accuracy)}</td>'
                f'<td><button class="btn-detail" '
                f'onclick="goDetail(\'tab-lang\',\'lang-detail-{i}\')">查看</button></td>'
                f'</tr>'
            )
        gl = g.lang
        rows.append(
            f'<tr class="total-row"><td>总数</td>'
            f'<td>{gl.total}</td><td>{gl.correct}</td>'
            f'<td>{gl.error}</td><td>{gl.missing}</td>'
            f'<td>{_pct(gl.accuracy)}</td><td></td></tr>'
        )
        sections.append(
            '<div class="summary-section">'
            '<div class="summary-section-title">语种准确率</div>'
            '<div class="table-wrap"><table class="report-table"><thead><tr>'
            '<th>测试集</th><th>总数</th><th>正确数</th><th>错误数</th>'
            '<th>未知数</th><th>总通过率</th><th>详情</th>'
            '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div></div>'
        )

    # ── GAE 汇总（性别/年龄/情绪分别展示）──
    if g.gae and gae_sub_types:
        _gae_cfg = []
        if "sex" in gae_sub_types:
            _gae_cfg.append(('sex', '性别准确率', 'tab-sex', 'sex'))
        if "age" in gae_sub_types:
            _gae_cfg.append(('age', '年龄准确率', 'tab-age', 'age'))
        if "emotion" in gae_sub_types:
            _gae_cfg.append(('emotion', '情绪准确率', 'tab-emotion', 'emotion'))
        for sub_key, sub_label, tab_id, det_pfx in _gae_cfg:
            rows = []
            for i, ts in enumerate(g.testsets):
                if not ts.gae:
                    continue
                sub = getattr(ts.gae, sub_key)
                rows.append(
                    f'<tr><td>{_safe_html(ts.bref)}</td>'
                    f'<td>{sub.total}</td><td>{sub.correct}</td>'
                    f'<td>{sub.error}</td><td>{sub.parse_fail}</td>'
                    f'<td>{_pct(sub.accuracy)}</td>'
                    f'<td><button class="btn-detail" '
                    f'onclick="goDetail(\'{tab_id}\',\'{det_pfx}-detail-{i}\')">查看</button></td>'
                    f'</tr>'
                )
            g_sub = getattr(g.gae, sub_key)
            rows.append(
                f'<tr class="total-row"><td>总数</td>'
                f'<td>{g_sub.total}</td><td>{g_sub.correct}</td>'
                f'<td>{g_sub.error}</td><td>{g_sub.parse_fail}</td>'
                f'<td>{_pct(g_sub.accuracy)}</td><td></td></tr>'
            )
            sections.append(
                f'<div class="summary-section">'
                f'<div class="summary-section-title">{sub_label}</div>'
                f'<div class="table-wrap"><table class="report-table"><thead><tr>'
                f'<th>测试集</th><th>总数</th><th>正确数</th><th>错误数</th>'
                f'<th>未知数</th><th>总通过率</th><th>详情</th>'
                f'</tr></thead><tbody>' + ''.join(rows) + f'</tbody></table></div></div>'
            )

    # ── GPU 汇总 ──
    if g.gpu:
        rows = []
        for i, ts in enumerate(g.testsets):
            if not ts.gpu:
                continue
            gpu = ts.gpu
            rows.append(
                f'<tr><td>{_safe_html(ts.bref)}</td>'
                f'<td>{gpu.total}</td>'
                f'<td>{gpu.avg_ms:.1f}</td><td>{gpu.max_ms:.1f}</td>'
                f'<td>{gpu.min_ms:.1f}</td><td>{gpu.p90_ms:.1f}</td>'
                f'<td>{gpu.p80_ms:.1f}</td>'
                f'<td><button class="btn-detail" '
                f'onclick="goDetail(\'tab-gpu\',\'gpu-detail-{i}\')">查看</button></td>'
                f'</tr>'
            )
        gg = g.gpu
        rows.append(
            f'<tr class="total-row"><td>总数</td>'
            f'<td>{gg.total}</td>'
            f'<td>{gg.avg_ms:.1f}</td><td>{gg.max_ms:.1f}</td>'
            f'<td>{gg.min_ms:.1f}</td><td>{gg.p90_ms:.1f}</td>'
            f'<td>{gg.p80_ms:.1f}</td><td></td></tr>'
        )
        sections.append(
            '<div class="summary-section">'
            '<div class="summary-section-title">时延</div>'
            '<div class="table-wrap"><table class="report-table"><thead><tr>'
            '<th>测试集</th><th>总数</th><th>平均时延(ms)</th><th>最大时延(ms)</th>'
            '<th>最小时延(ms)</th><th>P90指标(ms)</th><th>P80指标(ms)</th><th>详情</th>'
            '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div></div>'
        )

    return '<div id="tab-summary" class="tab-pane active">' + ''.join(sections) + '</div>'


# ── ASR 详情 Tab ──

def _build_asr_tab(g: 'GlobalStats') -> str:
    """ASR准确率详情 Tab：顶部概览表 + 各测试集可展开详情面板"""
    # 概览表
    ov_rows = []
    for i, ts in enumerate(g.testsets):
        if not ts.asr:
            continue
        a = ts.asr
        ov_rows.append(
            f'<tr>'
            f'<td>{_safe_html(ts.bref)}</td>'
            f'<td class="path-cell" title="{_safe_html(ts.result_file)}">'
            f'{_safe_html(ts.result_file)}</td>'
            f'<td class="path-cell" title="{_safe_html(ts.ref_file)}">'
            f'{_safe_html(ts.ref_file)}</td>'
            f'<td>{_pct(a.char_acc)}</td>'
            f'<td>{_pct_safe(a.total_ins,  a.total_ref_chars)}</td>'
            f'<td>{_pct_safe(a.total_dels, a.total_ref_chars)}</td>'
            f'<td>{_pct_safe(a.empty,      a.total)}</td>'
            f'<td>{_pct(a.sentence_acc)}</td>'
            f'<td>{a.correct}</td><td>{a.total}</td>'
            f'<td><button class="btn-detail" '
            f'onclick="showPanelInTab(\'tab-asr\',\'asr-detail-{i}\')">查看</button></td>'
            f'</tr>'
        )
    overview = (
        '<div class="table-wrap">'
        '<table class="report-table overview-table"><thead><tr>'
        '<th>测试集</th><th>测试路径</th><th>ref参考文件</th>'
        '<th>字准率</th><th>插入率</th><th>删除率</th><th>空结果率</th>'
        '<th>句准率</th><th>句子通过数</th><th>句子总数</th><th>详情</th>'
        '</tr></thead><tbody>' + ''.join(ov_rows) + '</tbody></table></div>'
    )

    # 各测试集详情面板
    panels: List[str] = []
    for i, ts in enumerate(g.testsets):
        if not ts.asr or not ts.asr_details:
            continue
        panel_id = f'asr-detail-{i}'
        tbody_id = f'asr-tbody-{i}'
        bar_id   = f'asr-bar-{i}'
        err_types = sorted({d.error_type for d in ts.asr_details if d.error_type})
        err_opts  = '<option value="__all__">全部</option>' + ''.join(
            f'<option value="{_safe_html(et)}">{_safe_html(et)}</option>'
            for et in err_types
        )
        filter_bar = (
            f'<div class="filter-bar" id="{bar_id}">'
            f'<label>是否通过: <select class="filter-select" data-col="4" '
            f'onchange="filterRows(\'{tbody_id}\',\'{bar_id}\')">'
            f'<option value="__all__">全部</option>'
            f'<option value="Pass">Pass</option>'
            f'<option value="Fail">Fail</option>'
            f'</select></label>'
            f'<label>错误类型: <select class="filter-select" data-col="5" '
            f'onchange="filterRows(\'{tbody_id}\',\'{bar_id}\')">'
            f'{err_opts}</select></label>'
            f'</div>'
        )
        rows = []
        for j, d in enumerate(ts.asr_details, 1):
            p_tag = ('<span class="tag-pass">Pass</span>' if d.is_correct
                     else '<span class="tag-fail">Fail</span>')
            rows.append(
                f'<tr>'
                f'<td>{j}</td>'
                f'<td class="path-cell" title="{_safe_html(d.audio)}">'
                f'{_safe_html(d.audio)}</td>'
                f'<td>{_safe_html(d.ref_text)}</td>'
                f'<td>{_safe_html(d.hyp_text) or "(空)"}</td>'
                f'<td>{p_tag}</td>'
                f'<td>{_safe_html(d.error_type)}</td>'
                f'</tr>'
            )
        panels.append(
            f'<div class="detail-panel" id="{panel_id}" style="display:none">'
            f'<div class="detail-panel-hdr">'
            f'{_safe_html(ts.bref)} — 测试详细数据'
            f'<button class="btn-close" onclick="closePanel(\'{panel_id}\')">收起</button>'
            f'</div>'
            f'<div class="detail-panel-body">'
            f'{filter_bar}'
            f'<div class="scrollable-table">'
            f'<table class="report-table"><thead><tr>'
            f'<th>#</th><th>音频路径</th><th>预期结果</th>'
            f'<th>实际结果</th><th>是否通过</th><th>错误类型</th>'
            f'</tr></thead><tbody id="{tbody_id}">'
            + ''.join(rows)
            + f'</tbody></table></div>'
            f'</div></div>'
        )
    return '<div id="tab-asr" class="tab-pane">' + overview + ''.join(panels) + '</div>'


# ── 语种详情 Tab ──

def _build_lang_tab(g: 'GlobalStats') -> str:
    """语种准确率详情 Tab"""
    ov_rows = []
    for i, ts in enumerate(g.testsets):
        if not ts.lang:
            continue
        l = ts.lang
        ov_rows.append(
            f'<tr>'
            f'<td>{_safe_html(ts.bref)}</td>'
            f'<td class="path-cell" title="{_safe_html(ts.result_file)}">'
            f'{_safe_html(ts.result_file)}</td>'
            f'<td class="path-cell" title="{_safe_html(ts.ref_file)}">'
            f'{_safe_html(ts.ref_file)}</td>'
            f'<td>{l.total}</td><td>{l.correct}</td>'
            f'<td>{l.error}</td><td>{l.missing}</td>'
            f'<td>{_pct(l.accuracy)}</td>'
            f'<td><button class="btn-detail" '
            f'onclick="showPanelInTab(\'tab-lang\',\'lang-detail-{i}\')">查看</button></td>'
            f'</tr>'
        )
    overview = (
        '<div class="table-wrap">'
        '<table class="report-table overview-table"><thead><tr>'
        '<th>测试集</th><th>测试路径</th><th>ref参考文件</th>'
        '<th>总数</th><th>正确数</th><th>错误数</th><th>未知数</th>'
        '<th>准确率</th><th>详情</th>'
        '</tr></thead><tbody>' + ''.join(ov_rows) + '</tbody></table></div>'
    )

    panels: List[str] = []
    for i, ts in enumerate(g.testsets):
        if not ts.lang or not ts.lang_details:
            continue
        panel_id = f'lang-detail-{i}'
        tbody_id = f'lang-tbody-{i}'
        bar_id   = f'lang-bar-{i}'
        filter_bar = (
            f'<div class="filter-bar" id="{bar_id}">'
            f'<label>是否通过: <select class="filter-select" data-col="4" '
            f'onchange="filterRows(\'{tbody_id}\',\'{bar_id}\')">'
            f'<option value="__all__">全部</option>'
            f'<option value="Pass">Pass</option>'
            f'<option value="Fail">Fail</option>'
            f'</select></label></div>'
        )
        rows = []
        for j, d in enumerate(ts.lang_details, 1):
            p_tag = ('<span class="tag-pass">Pass</span>' if d.is_correct
                     else '<span class="tag-fail">Fail</span>')
            rows.append(
                f'<tr>'
                f'<td>{j}</td>'
                f'<td class="path-cell" title="{_safe_html(d.audio)}">'
                f'{_safe_html(d.audio)}</td>'
                f'<td>{_safe_html(d.expected)}</td>'
                f'<td>{_safe_html(d.detected) or "(空)"}</td>'
                f'<td>{p_tag}</td>'
                f'</tr>'
            )
        panels.append(
            f'<div class="detail-panel" id="{panel_id}" style="display:none">'
            f'<div class="detail-panel-hdr">'
            f'{_safe_html(ts.bref)} — 测试详细数据'
            f'<button class="btn-close" onclick="closePanel(\'{panel_id}\')">收起</button>'
            f'</div>'
            f'<div class="detail-panel-body">'
            f'{filter_bar}'
            f'<div class="scrollable-table">'
            f'<table class="report-table"><thead><tr>'
            f'<th>#</th><th>音频路径</th><th>预期语种</th>'
            f'<th>实际语种</th><th>是否通过</th>'
            f'</tr></thead><tbody id="{tbody_id}">'
            + ''.join(rows)
            + f'</tbody></table></div>'
            f'</div></div>'
        )
    return '<div id="tab-lang" class="tab-pane">' + overview + ''.join(panels) + '</div>'


# ── GAE 子维度详情 Tab（性别/年龄/情绪共用同一模板）──

def _build_gae_sub_tab(g: 'GlobalStats', sub_key: str,
                       tab_id: str, col_labels: Tuple[str, str]) -> str:
    """
    构建 GAE 某一子维度（性别/年龄/情绪）的详情 Tab。
    sub_key    : 'sex' | 'age' | 'emotion'
    tab_id     : 'tab-sex' | 'tab-age' | 'tab-emotion'
    col_labels : (期望列标签, 实际列标签)
    """
    ref_label, res_label = col_labels
    det_pfx = sub_key

    ov_rows = []
    for i, ts in enumerate(g.testsets):
        if not ts.gae:
            continue
        sub = getattr(ts.gae, sub_key)
        ov_rows.append(
            f'<tr>'
            f'<td>{_safe_html(ts.bref)}</td>'
            f'<td class="path-cell" title="{_safe_html(ts.result_file)}">'
            f'{_safe_html(ts.result_file)}</td>'
            f'<td class="path-cell" title="{_safe_html(ts.ref_file)}">'
            f'{_safe_html(ts.ref_file)}</td>'
            f'<td>{sub.total}</td><td>{sub.correct}</td>'
            f'<td>{sub.error}</td><td>{sub.parse_fail}</td>'
            f'<td>{_pct(sub.accuracy)}</td>'
            f'<td><button class="btn-detail" '
            f'onclick="showPanelInTab(\'{tab_id}\',\'{det_pfx}-detail-{i}\')">查看</button></td>'
            f'</tr>'
        )
    overview = (
        f'<div class="table-wrap">'
        f'<table class="report-table overview-table"><thead><tr>'
        f'<th>测试集</th><th>测试路径</th><th>ref参考文件</th>'
        f'<th>总数</th><th>正确数</th><th>错误数</th><th>解析失败</th>'
        f'<th>准确率</th><th>详情</th>'
        f'</tr></thead><tbody>' + ''.join(ov_rows) + f'</tbody></table></div>'
    )

    panels: List[str] = []
    for i, ts in enumerate(g.testsets):
        if not ts.gae or not ts.gae_details:
            continue
        panel_id = f'{det_pfx}-detail-{i}'
        tbody_id = f'{det_pfx}-tbody-{i}'
        bar_id   = f'{det_pfx}-bar-{i}'
        filter_bar = (
            f'<div class="filter-bar" id="{bar_id}">'
            f'<label>是否通过: <select class="filter-select" data-col="4" '
            f'onchange="filterRows(\'{tbody_id}\',\'{bar_id}\')">'
            f'<option value="__all__">全部</option>'
            f'<option value="Pass">Pass</option>'
            f'<option value="Fail">Fail</option>'
            f'</select></label></div>'
        )
        rows = []
        for j, d in enumerate(ts.gae_details, 1):
            if sub_key == 'sex':
                ref_v, res_v, is_ok = d.ref_sex, d.res_sex, d.sex_ok
            elif sub_key == 'age':
                ref_v, res_v, is_ok = d.ref_age, d.res_age, d.age_ok
            else:
                ref_v, res_v, is_ok = d.ref_emotion, d.res_emotion, d.emotion_ok
            p_tag = ('<span class="tag-pass">Pass</span>' if is_ok
                     else '<span class="tag-fail">Fail</span>')
            rows.append(
                f'<tr>'
                f'<td>{j}</td>'
                f'<td class="path-cell" title="{_safe_html(d.audio)}">'
                f'{_safe_html(d.audio)}</td>'
                f'<td>{_safe_html(ref_v)}</td>'
                f'<td>{_safe_html(res_v) or "(空)"}</td>'
                f'<td>{p_tag}</td>'
                f'</tr>'
            )
        panels.append(
            f'<div class="detail-panel" id="{panel_id}" style="display:none">'
            f'<div class="detail-panel-hdr">'
            f'{_safe_html(ts.bref)} — 测试详细数据'
            f'<button class="btn-close" onclick="closePanel(\'{panel_id}\')">收起</button>'
            f'</div>'
            f'<div class="detail-panel-body">'
            f'{filter_bar}'
            f'<div class="scrollable-table">'
            f'<table class="report-table"><thead><tr>'
            f'<th>#</th><th>音频路径</th><th>{ref_label}</th>'
            f'<th>{res_label}</th><th>是否通过</th>'
            f'</tr></thead><tbody id="{tbody_id}">'
            + ''.join(rows)
            + f'</tbody></table></div>'
            f'</div></div>'
        )
    return (
        f'<div id="{tab_id}" class="tab-pane">'
        + overview + ''.join(panels)
        + '</div>'
    )


# ── GPU 时延详情 Tab ──

def _build_gpu_tab(g: 'GlobalStats') -> str:
    """GPU 时延详情 Tab：顶部概览表 + 各测试集可展开详情面板（含统计卡片）"""
    ov_rows = []
    for i, ts in enumerate(g.testsets):
        if not ts.gpu:
            continue
        gpu = ts.gpu
        ov_rows.append(
            f'<tr>'
            f'<td>{_safe_html(ts.bref)}</td>'
            f'<td class="path-cell" title="{_safe_html(ts.result_file)}">'
            f'{_safe_html(ts.result_file)}</td>'
            f'<td>{gpu.total}</td>'
            f'<td>{gpu.avg_ms:.1f}</td><td>{gpu.max_ms:.1f}</td>'
            f'<td>{gpu.min_ms:.1f}</td>'
            f'<td>{gpu.p50_ms:.1f}</td><td>{gpu.p80_ms:.1f}</td>'
            f'<td>{gpu.p90_ms:.1f}</td><td>{gpu.p95_ms:.1f}</td>'
            f'<td>{gpu.p99_ms:.1f}</td><td>{gpu.std_ms:.1f}</td>'
            f'<td><button class="btn-detail" '
            f'onclick="showPanelInTab(\'tab-gpu\',\'gpu-detail-{i}\')">查看</button></td>'
            f'</tr>'
        )
    overview = (
        '<div class="table-wrap">'
        '<table class="report-table overview-table"><thead><tr>'
        '<th>测试集</th><th>测试路径</th><th>样本数</th>'
        '<th>均值(ms)</th><th>最大(ms)</th><th>最小(ms)</th>'
        '<th>P50(ms)</th><th>P80(ms)</th><th>P90(ms)</th>'
        '<th>P95(ms)</th><th>P99(ms)</th><th>标准差</th><th>详情</th>'
        '</tr></thead><tbody>' + ''.join(ov_rows) + '</tbody></table></div>'
    )

    panels: List[str] = []
    for i, ts in enumerate(g.testsets):
        if not ts.gpu or not ts.gpu.values:
            continue
        panel_id = f'gpu-detail-{i}'
        tbody_id = f'gpu-tbody-{i}'
        gpu = ts.gpu
        p90 = gpu.p90_ms
        stat_cards = (
            '<div class="gpu-stat-cards">'
            + f'<div class="gpu-stat-card"><div class="sv">{gpu.total}</div><div class="sl">样本数</div></div>'
            + f'<div class="gpu-stat-card"><div class="sv">{gpu.avg_ms:.1f}ms</div><div class="sl">均值</div></div>'
            + f'<div class="gpu-stat-card"><div class="sv">{gpu.p50_ms:.1f}ms</div><div class="sl">P50</div></div>'
            + f'<div class="gpu-stat-card"><div class="sv">{gpu.p80_ms:.1f}ms</div><div class="sl">P80</div></div>'
            + f'<div class="gpu-stat-card"><div class="sv">{gpu.p90_ms:.1f}ms</div><div class="sl">P90</div></div>'
            + f'<div class="gpu-stat-card"><div class="sv">{gpu.p95_ms:.1f}ms</div><div class="sl">P95</div></div>'
            + f'<div class="gpu-stat-card"><div class="sv">{gpu.p99_ms:.1f}ms</div><div class="sl">P99</div></div>'
            + f'<div class="gpu-stat-card"><div class="sv">{gpu.min_ms:.1f}ms</div><div class="sl">最小值</div></div>'
            + f'<div class="gpu-stat-card"><div class="sv">{gpu.max_ms:.1f}ms</div><div class="sl">最大值</div></div>'
            + f'<div class="gpu-stat-card"><div class="sv">{gpu.std_ms:.1f}ms</div><div class="sl">标准差</div></div>'
            + '</div>'
        )
        rows = []
        for j, v in enumerate(ts.gpu.values, 1):
            ok = (v <= p90)
            t_tag = ('<span class="tag-pass">正常</span>' if ok
                     else '<span class="tag-fail">超P90</span>')
            rows.append(f'<tr><td>{j}</td><td>{v:.3f}</td><td>{t_tag}</td></tr>')
        panels.append(
            f'<div class="detail-panel" id="{panel_id}" style="display:none">'
            f'<div class="detail-panel-hdr">'
            f'{_safe_html(ts.bref)} — GPU时延详情'
            f'<button class="btn-close" onclick="closePanel(\'{panel_id}\')">收起</button>'
            f'</div>'
            f'<div class="detail-panel-body">'
            f'{stat_cards}'
            f'<div class="scrollable-table">'
            f'<table class="report-table"><thead><tr>'
            f'<th>#</th><th>GPU时延(ms)</th><th>状态(≤P90)</th>'
            f'</tr></thead><tbody id="{tbody_id}">'
            + ''.join(rows)
            + f'</tbody></table></div>'
            f'</div></div>'
        )
    return '<div id="tab-gpu" class="tab-pane">' + overview + ''.join(panels) + '</div>'



# ──────────────────────────────────────────────────────────────────────────────
# Excel 报告
# ──────────────────────────────────────────────────────────────────────────────

def _write_excel(global_stats: GlobalStats, output_path: str) -> None:
    """
    生成 Excel 报告，结构与 HTML 对应：
      Sheet1: 汇总信息（按 type 分小节，各测试集汇总 + 总计）
      后续 Sheet: 各测试集按 type 分开的明细数据
    """
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter
    except ImportError:
        logger.warning("openpyxl 未安装，跳过 Excel 报告生成")
        return

    wb = openpyxl.Workbook()

    # ── 样式常量 ──
    HDR_FONT  = Font(bold=True, color="FFFFFF")
    HDR_FILL  = PatternFill(start_color="1A73E8", end_color="1A73E8", fill_type="solid")
    TTL_FILL  = PatternFill(start_color="DDE9F8", end_color="DDE9F8", fill_type="solid")
    TTL_FONT  = Font(bold=True)
    SEC_FONT  = Font(bold=True, color="1A73E8", size=12)
    PASS_FILL = PatternFill(start_color="D4EDDA", end_color="D4EDDA", fill_type="solid")
    FAIL_FILL = PatternFill(start_color="FCE4E4", end_color="FCE4E4", fill_type="solid")
    CENTER    = Alignment(horizontal='center', vertical='center', wrap_text=True)
    LEFT      = Alignment(horizontal='left',   vertical='center', wrap_text=True)

    def _hrow(ws, row: int, headers: list, widths: list = None):
        """写蓝色表头行，可选同时设置列宽"""
        for c, h in enumerate(headers, 1):
            cell = ws.cell(row=row, column=c, value=h)
            cell.font      = HDR_FONT
            cell.fill      = HDR_FILL
            cell.alignment = CENTER
        if widths:
            for i, w in enumerate(widths, 1):
                ws.column_dimensions[get_column_letter(i)].width = w

    def _trow(ws, row: int, values: list):
        """写蓝底总计行"""
        for c, v in enumerate(values, 1):
            cell = ws.cell(row=row, column=c, value=v)
            cell.font      = TTL_FONT
            cell.fill      = TTL_FILL
            cell.alignment = CENTER

    def _sec(ws, row: int, title: str, col_span: int = 10) -> int:
        """写小节标题行，返回下一行号"""
        cell = ws.cell(row=row, column=1, value=title)
        cell.font = SEC_FONT
        return row + 1

    def _cval(ws, row: int, col: int, value, align=None):
        """写单元格值"""
        cell = ws.cell(row=row, column=col, value=value)
        cell.alignment = align or CENTER
        return cell

    g = global_stats
    gae_sub_types = _selected_gae_sub_types(g.types)

    # ════════════════════════════════════════════════════════════
    # Sheet 1：汇总信息
    # ════════════════════════════════════════════════════════════
    ws = wb.active
    ws.title = "汇总信息"
    r = 1

    # ── ASR 汇总 ──
    if g.asr:
        r = _sec(ws, r, "ASR准确率")
        _hrow(ws, r,
              ["测试集", "字准率", "插入率", "删除率", "空结果率",
               "句准率", "句子通过数", "句子总数"],
              [28, 10, 10, 10, 10, 10, 12, 12])
        r += 1
        for ts in g.testsets:
            if not ts.asr:
                continue
            a = ts.asr
            for c, v in enumerate([
                ts.bref,
                _pct(a.char_acc),
                _pct_safe(a.total_ins,  a.total_ref_chars),
                _pct_safe(a.total_dels, a.total_ref_chars),
                _pct_safe(a.empty,      a.total),
                _pct(a.sentence_acc),
                a.correct,
                a.total,
            ], 1):
                ws.cell(r, c, v).alignment = CENTER
            r += 1
        ga = g.asr
        _trow(ws, r, [
            "总计",
            _pct(ga.char_acc),
            _pct_safe(ga.total_ins,  ga.total_ref_chars),
            _pct_safe(ga.total_dels, ga.total_ref_chars),
            _pct_safe(ga.empty,      ga.total),
            _pct(ga.sentence_acc),
            ga.correct,
            ga.total,
        ])
        r += 2  # 空一行

    # ── 语种汇总 ──
    if g.lang:
        r = _sec(ws, r, "语种准确率")
        _hrow(ws, r, ["测试集", "总数", "正确数", "错误数", "未知数", "总通过率"])
        r += 1
        for ts in g.testsets:
            if not ts.lang:
                continue
            l = ts.lang
            for c, v in enumerate(
                [ts.bref, l.total, l.correct, l.error, l.missing, _pct(l.accuracy)], 1
            ):
                ws.cell(r, c, v).alignment = CENTER
            r += 1
        gl = g.lang
        _trow(ws, r, ["总数", gl.total, gl.correct, gl.error, gl.missing, _pct(gl.accuracy)])
        r += 2

    # ── GAE 汇总（性别/年龄/情绪分别写小节）──
    if g.gae and gae_sub_types:
        cfg = []
        if "sex" in gae_sub_types:
            cfg.append(('sex', '性别准确率'))
        if "age" in gae_sub_types:
            cfg.append(('age', '年龄准确率'))
        if "emotion" in gae_sub_types:
            cfg.append(('emotion', '情绪准确率'))
        for sub_key, sub_label in cfg:
            r = _sec(ws, r, sub_label)
            _hrow(ws, r, ["测试集", "总数", "正确数", "错误数", "解析失败", "准确率"])
            r += 1
            for ts in g.testsets:
                if not ts.gae:
                    continue
                sub = getattr(ts.gae, sub_key)
                for c, v in enumerate(
                    [ts.bref, sub.total, sub.correct, sub.error,
                     sub.parse_fail, _pct(sub.accuracy)], 1
                ):
                    ws.cell(r, c, v).alignment = CENTER
                r += 1
            g_sub = getattr(g.gae, sub_key)
            _trow(ws, r, [
                "总数", g_sub.total, g_sub.correct,
                g_sub.error, g_sub.parse_fail, _pct(g_sub.accuracy),
            ])
            r += 2

    # ── GPU 汇总 ──
    if g.gpu:
        r = _sec(ws, r, "时延")
        _hrow(ws, r,
              ["测试集", "总数", "均值(ms)", "最大(ms)", "最小(ms)",
               "P50(ms)", "P80(ms)", "P90(ms)", "P95(ms)", "P99(ms)", "标准差"])
        r += 1
        for ts in g.testsets:
            if not ts.gpu:
                continue
            gpu = ts.gpu
            for c, v in enumerate([
                ts.bref, gpu.total,
                round(gpu.avg_ms, 1), round(gpu.max_ms, 1), round(gpu.min_ms, 1),
                round(gpu.p50_ms, 1), round(gpu.p80_ms, 1), round(gpu.p90_ms, 1),
                round(gpu.p95_ms, 1), round(gpu.p99_ms, 1), round(gpu.std_ms, 1),
            ], 1):
                ws.cell(r, c, v).alignment = CENTER
            r += 1
        gg = g.gpu
        _trow(ws, r, [
            "总数", gg.total,
            round(gg.avg_ms, 1), round(gg.max_ms, 1), round(gg.min_ms, 1),
            round(gg.p50_ms, 1), round(gg.p80_ms, 1), round(gg.p90_ms, 1),
            round(gg.p95_ms, 1), round(gg.p99_ms, 1), round(gg.std_ms, 1),
        ])

    # ════════════════════════════════════════════════════════════
    # 各测试集明细 Sheet（每个 type 独立一个 Sheet）
    # ════════════════════════════════════════════════════════════
    for ts in global_stats.testsets:
        # Sheet 名最长 31 字符，去掉非法字符
        tag = re.sub(r'[\\/:*?"<>|]', '_', ts.bref)[:26]

        # ── ASR 明细 ──
        if ts.asr and ts.asr_details:
            ws2 = wb.create_sheet(f"{tag}_ASR")
            _hrow(ws2, 1,
                  ["#", "音频路径", "预期结果", "实际结果",
                   "是否通过", "错误类型", "字准率"],
                  [6, 42, 26, 26, 8, 8, 10])
            for i, d in enumerate(ts.asr_details, 2):
                _cval(ws2, i, 1, i - 1)
                _cval(ws2, i, 2, d.audio, LEFT)
                _cval(ws2, i, 3, d.ref_text, LEFT)
                _cval(ws2, i, 4, d.hyp_text, LEFT)
                sc = ws2.cell(i, 5, "Pass" if d.is_correct else "Fail")
                sc.fill      = PASS_FILL if d.is_correct else FAIL_FILL
                sc.alignment = CENTER
                _cval(ws2, i, 6, d.error_type)
                _cval(ws2, i, 7, _pct(d.char_acc))

        # ── 语种明细 ──
        if ts.lang and ts.lang_details:
            ws2 = wb.create_sheet(f"{tag}_语种")
            _hrow(ws2, 1,
                  ["#", "音频路径", "预期语种", "实际语种", "是否通过"],
                  [6, 42, 12, 12, 8])
            for i, d in enumerate(ts.lang_details, 2):
                _cval(ws2, i, 1, i - 1)
                _cval(ws2, i, 2, d.audio, LEFT)
                _cval(ws2, i, 3, d.expected)
                _cval(ws2, i, 4, d.detected)
                sc = ws2.cell(i, 5, "Pass" if d.is_correct else "Fail")
                sc.fill      = PASS_FILL if d.is_correct else FAIL_FILL
                sc.alignment = CENTER

        # ── GAE 明细（性别/年龄/情绪各独立 Sheet）──
        if ts.gae and ts.gae_details:
            _gae_sheet_cfg = []
            if "sex" in ts.types:
                _gae_sheet_cfg.append(('sex', '性别', 'ref_sex', 'res_sex', 'sex_ok'))
            if "age" in ts.types:
                _gae_sheet_cfg.append(('age', '年龄', 'ref_age', 'res_age', 'age_ok'))
            if "emotion" in ts.types:
                _gae_sheet_cfg.append(('emotion', '情绪', 'ref_emotion', 'res_emotion', 'emotion_ok'))
            for sub_key, sub_label, ref_attr, res_attr, ok_attr in _gae_sheet_cfg:
                ws2 = wb.create_sheet(f"{tag}_{sub_label}")
                _hrow(ws2, 1,
                      ["#", "音频路径", f"预期{sub_label}", f"实际{sub_label}", "是否通过"],
                      [6, 42, 12, 12, 8])
                for i, d in enumerate(ts.gae_details, 2):
                    is_ok = getattr(d, ok_attr)
                    _cval(ws2, i, 1, i - 1)
                    _cval(ws2, i, 2, d.audio, LEFT)
                    _cval(ws2, i, 3, getattr(d, ref_attr))
                    _cval(ws2, i, 4, getattr(d, res_attr))
                    sc = ws2.cell(i, 5, "Pass" if is_ok else "Fail")
                    sc.fill      = PASS_FILL if is_ok else FAIL_FILL
                    sc.alignment = CENTER

        # ── GPU 明细 ──
        if ts.gpu and ts.gpu.values:
            ws2 = wb.create_sheet(f"{tag}_GPU")
            p90 = ts.gpu.p90_ms
            _hrow(ws2, 1,
                  ["#", "GPU时延(ms)", "状态(≤P90)"],
                  [6, 18, 12])
            for i, v in enumerate(ts.gpu.values, 2):
                ok = (v <= p90)
                _cval(ws2, i, 1, i - 1)
                _cval(ws2, i, 2, round(v, 3))
                sc = ws2.cell(i, 3, "正常" if ok else "超P90")
                sc.fill      = PASS_FILL if ok else FAIL_FILL
                sc.alignment = CENTER

    parent = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(parent, exist_ok=True)
    wb.save(output_path)
    logger.info(f"Excel 报告已保存：{output_path}")


# ──────────────────────────────────────────────────────────────────────────────
# Handler
# ──────────────────────────────────────────────────────────────────────────────

@register_tsr_command("PSTT_ACCURACY")
class PSTTAccuracyHandler(BaseTSRHandler):
    """
    PSTT 测试集结果统计处理器

    指令格式:
        [TSR]PSTT_ACCURACY result=<path> [ref=<path|None>] type=<asr,lang,sex,age,emotion,gpu,auto> [output=<xlsx>]

    参数:
        result  : result _full.txt 文件 或 包含多个 *_full.txt 的目录（必填）
        ref     : ref 标注文件 或 ref 目录（可选，gpu-only 时可省略）
        type    : 统计维度，逗号分隔，支持 asr/lang/sex/age/emotion/gpu，或 auto（默认全部）
        output  : Excel 报告输出路径（可选）
    """

    COMMAND_NAME = "PSTT_ACCURACY"

    def execute(self, params: list, output_report: str = None) -> str:
        result_path, ref_path, types, type_auto, xlsx_path = self._parse_params(params, output_report)

        # 配对文件
        allow_missing_ref = type_auto or (types == ["gpu"])
        pairs = _pair_files(result_path, ref_path, allow_missing_ref=allow_missing_ref)
        logger.info(f"共找到 {len(pairs)} 对测试集文件")

        # 逐测试集处理
        testsets: List[TestsetStats] = []
        union_types: List[str] = []
        for bref, rf, ref_f in pairs:
            logger.info(f"处理测试集: {bref}")
            if type_auto:
                if ref_f:
                    declared_types, _ = _parse_ref_meta_lines(ref_f)
                    if not declared_types:
                        raise ValueError(
                            f"type=auto 时，ref 文件必须声明 @TYPE 头：{ref_f}"
                        )
                    test_types = declared_types
                else:
                    # auto + 无 ref：按 gpu-only 处理
                    test_types = ["gpu"]
            else:
                test_types = types
                if ref_f:
                    declared_types, _ = _parse_ref_meta_lines(ref_f)
                    if declared_types and set(declared_types) != set(types):
                        raise ValueError(
                            f"type 与 ref @TYPE 不一致：bref={bref}，"
                            f"命令行 type={types}，ref @TYPE={declared_types}，ref={ref_f}"
                        )

            ts = _process_testset(bref, rf, ref_f, test_types)
            testsets.append(ts)
            for t in test_types:
                if t not in union_types:
                    union_types.append(t)

        # 全局汇总
        global_types = _sort_types(union_types if type_auto else types)
        global_stats = _build_global(testsets, global_types)

        # 生成 Excel
        _write_excel(global_stats, xlsx_path)

        # 生成 HTML 报告
        html_content = self._build_full_html(global_stats)
        html_filename = "pstt_accuracy.html"
        self.save_html_report(html_content, html_filename,
                              "PSTT 测试集统计报告", "pstt_accuracy")

        # 本地副本
        local_html = os.path.splitext(xlsx_path)[0] + '.html'
        os.makedirs(os.path.dirname(os.path.abspath(local_html)), exist_ok=True)
        with open(local_html, 'w', encoding='utf-8') as f:
            f.write(html_content)
        logger.info(f"本地 HTML 报告已生成: {local_html}")

        return self._build_summary(global_stats, xlsx_path)

    # ── 参数解析 ──

    def _parse_params(self, params: list,
                      default_output: str = None) -> Tuple[str, Optional[str], List[str], bool, str]:
        result_path = None
        ref_path    = None
        types_raw   = None
        output_path = default_output

        for param in params:
            if '=' not in param:
                raise ValueError(f"PSTT_ACCURACY 参数格式错误（需 key=value）: {param!r}")
            key, val = param.split('=', 1)
            key = key.strip().lower()
            val = val.strip()
            if key == 'result':
                result_path = val
            elif key == 'ref':
                ref_path = val
            elif key == 'type':
                types_raw = val
            elif key == 'output':
                output_path = val
            else:
                raise ValueError(f"PSTT_ACCURACY 不支持的参数: {key!r}")

        if not result_path:
            raise ValueError("PSTT_ACCURACY 缺少必填参数: result=<path>")
        if ref_path and ref_path.strip().lower() == "none":
            ref_path = None

        # 解析 type
        if types_raw:
            parsed_types = _parse_type_expr(types_raw, allow_auto=True, context="PSTT_ACCURACY type")
        else:
            parsed_types = list(_DEFAULT_TYPES)   # 默认全部

        type_auto = (parsed_types == ["auto"])
        types = [] if type_auto else _sort_types(parsed_types)
        if not type_auto and _need_ref_for_types(types) and not ref_path:
            raise ValueError(
                f"PSTT_ACCURACY 当前 type={types} 需要 ref，请传 ref=<path>。"
                f"若仅统计 GPU，可传 type=gpu 且 ref=None。"
            )

        # 输出路径
        if not output_path:
            suite_mango_dir = self._get_suite_mango_dir()
            output_path = os.path.join(suite_mango_dir, "pstt_accuracy.xlsx")

        return result_path, ref_path, types, type_auto, output_path

    # ── HTML ──

    def generate_html_report(self, *args, **kwargs) -> Optional[str]:
        global_stats = args[0] if args else kwargs.get('global_stats')
        if global_stats is None:
            return None
        html = self._build_full_html(global_stats)
        return self.save_html_report(html, "pstt_accuracy.html",
                                     "PSTT 测试集统计报告", "pstt_accuracy")

    def _build_full_html(self, g: GlobalStats) -> str:
        """构建完整 HTML 报告（Tab 式布局）"""
        types = g.types
        gae_sub_types = _selected_gae_sub_types(types)
        parts: List[str] = [_PSTT_EXTRA_CSS, _PSTT_JS]

        # 顶部 KPI 指标卡片
        parts.append(_build_kpi_cards(g))

        # 主 Tab 导航
        parts.append(_build_main_tab_nav(types))

        # 各 Tab 面板
        panes: List[str] = [_build_summary_tab(g)]
        if 'asr'  in types:
            panes.append(_build_asr_tab(g))
        if 'lang' in types:
            panes.append(_build_lang_tab(g))
        if "sex" in gae_sub_types:
            panes.append(_build_gae_sub_tab(g, 'sex',     'tab-sex',
                                             ('预期性别', '实际性别')))
        if "age" in gae_sub_types:
            panes.append(_build_gae_sub_tab(g, 'age',     'tab-age',
                                             ('预期年龄', '实际年龄')))
        if "emotion" in gae_sub_types:
            panes.append(_build_gae_sub_tab(g, 'emotion', 'tab-emotion',
                                             ('预期情绪', '实际情绪')))
        if 'gpu'  in types:
            panes.append(_build_gpu_tab(g))

        parts.append('<div class="tab-panes">' + ''.join(panes) + '</div>')
        return self.build_html_page("PSTT 测试集统计报告", ''.join(parts))

    # ── Summary 文本 ──

    def _build_summary(self, g: GlobalStats, xlsx_path: str) -> str:
        lines = []
        testset_names = ', '.join(ts.bref for ts in g.testsets)
        lines.append(f"  测试集({len(g.testsets)}个): {testset_names}")
        lines.append(f"  统计维度: {', '.join(g.types)}")
        lines.append("")

        if g.asr:
            lines.append(f"  [ASR]  句准率: {_pct(g.asr.sentence_acc)}"
                         f"  ({g.asr.correct}/{g.asr.total})"
                         f"  | 字准率: {_pct(g.asr.char_acc)}"
                         f"  | 空结果: {g.asr.empty}")
        if g.lang:
            lines.append(f"  [LANG] 语种正确率: {_pct(g.lang.accuracy)}"
                         f"  ({g.lang.correct}/{g.lang.total})")
        if g.gae:
            gae_parts = []
            if "sex" in g.types:
                gae_parts.append(f"性别: {_pct(g.gae.sex.accuracy)}")
            if "age" in g.types:
                gae_parts.append(f"年龄: {_pct(g.gae.age.accuracy)}")
            if "emotion" in g.types:
                gae_parts.append(f"情绪: {_pct(g.gae.emotion.accuracy)}")
            if gae_parts:
                lines.append("  [GAE]  " + "  ".join(gae_parts))
        if g.gpu:
            lines.append(f"  [GPU]  均值: {g.gpu.avg_ms:.1f}ms"
                         f"  P50: {g.gpu.p50_ms:.1f}ms"
                         f"  P90: {g.gpu.p90_ms:.1f}ms"
                         f"  P99: {g.gpu.p99_ms:.1f}ms"
                         f"  样本: {g.gpu.total}")

        lines.append("")
        lines.append(f"  报告: {xlsx_path}")

        return self.format_summary_box("PSTT_ACCURACY", "\n".join(lines), width=95)


# ──────────────────────────────────────────────────────────────────────────────
# CLI 入口
# ──────────────────────────────────────────────────────────────────────────────

def main():
    """
    命令行入口

    示例（单文件）:
        python3 pstt_accuracy.py \\
            -result workspace/.../C1_full.txt \\
            -ref    testset/C1_ref.tsv \\
            -type   asr,lang,sex,gpu

    示例（目录）:
        python3 pstt_accuracy.py \\
            -result workspace/solution_filter/FILTER/1/result_file/ \\
            -ref    testset/ref/ \\
            -type   auto \\
            -o      report.xlsx
    """
    import argparse
    parser = argparse.ArgumentParser(description="PSTT 测试集结果统计工具")
    parser.add_argument('-result', '--result', required=True,
                        help='result _full.txt 文件或包含多个 *_full.txt 的目录')
    parser.add_argument('-ref',    '--ref',    required=False, default=None,
                        help='ref 标注文件或 ref 目录，gpu-only 时可不传/传 None')
    parser.add_argument('-type',   '--type',   default=None,
                        help='统计维度，逗号分隔（asr/lang/sex/age/emotion/gpu）或 auto，默认全部')
    parser.add_argument('-o',      '--output', default=None,
                        help='Excel 报告输出路径')
    args = parser.parse_args()

    p = [f"result={args.result}"]
    if args.ref is not None:
        p.append(f"ref={args.ref}")
    if args.type:
        p.append(f"type={args.type}")
    if args.output:
        p.append(f"output={args.output}")

    handler = PSTTAccuracyHandler(config=None)
    try:
        summary = handler.execute(p)
        print(summary)
    except (FileNotFoundError, ValueError) as e:
        print(f"❌ {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 执行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
