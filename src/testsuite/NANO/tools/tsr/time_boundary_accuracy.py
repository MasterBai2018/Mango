"""
TIME_BOUNDARY_ACCURACY 指令实现

用于统计 VAD/时间段检测的时间边界误差，支持：
- 起点误差（hyp_start - ref_start）：平均值 / 绝对平均值 / 最大值
- 终点误差（hyp_end - ref_end）：平均值 / 绝对平均值 / 最大值
- 区间 IOU（交并比）
- 命中率（时间误差在给定阈值内的比例，例如 0.2s / 0.3s）

输入文件格式（ref 和 result 相同格式，空格分隔，无表头）：
    音频路径  00h_S  开始时间(s)  结束时间(s)

使用示例:
    [TSR]TIME_BOUNDARY_ACCURACY result=vad.txt ref=ref.txt [output=report.xlsx] [threshold=3]
"""

import os
import sys
from dataclasses import dataclass, field
import json
import math
from typing import Dict, List, Tuple, Optional

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


class TimeSegment:
    """时间段（用于时间边界统计）

    NOTE:
        为了支持“识别文本”一起统计，除了起止时间外，这里额外保留一份文本字段：
            audio_path  <text>  start  end
        其中 <text> 可以是标签（例如 00h_S）、参考转写或识别结果。
    """

    def __init__(
        self,
        audio_path: str,
        start: float,
        end: float,
        line_num: int = 0,
        text: str = "",
    ):
        self.audio_path = audio_path
        self.start = start
        self.end = end
        self.line_num = line_num
        self.text = text  # 行中携带的标签 / 文本内容
        self.matched = False

    def __repr__(self) -> str:
        return f"TimeSegment({self.audio_path}, {self.start:.3f}, {self.end:.3f})"


@dataclass
class TimeBoundaryPairMetrics:
    """单条配对结果的时间误差指标"""
    audio_path: str
    ref_start: float
    ref_end: float
    hyp_start: float
    hyp_end: float
    start_err: float   # hyp_start - ref_start（单位：秒）
    end_err: float     # hyp_end - ref_end（单位：秒）
    start_delta_ms: float  # |ΔStart|，毫秒
    end_delta_ms: float    # |ΔEnd|，毫秒
    distance_ms: float     # 按 sqrt(Δs^2 + Δe^2) 计算的综合时间距离（毫秒）
    hit: bool          # 是否在阈值内

    # 文本信息（可选）
    ref_text: str = ""     # 参考转写
    hyp_text: str = ""     # 实际识别结果


@dataclass
class TimeBoundaryStats:
    """时间边界统计汇总"""

    # 配对统计
    pair_metrics: List[TimeBoundaryPairMetrics] = field(default_factory=list)
    # 明细对齐行（按参考段顺序）：
    # (audio_path, ref_start, ref_end, hyp_start|None, hyp_end|None, ref_text, hyp_text|None)
    aligned_rows: List[
        Tuple[str, float, float, Optional[float], Optional[float], str, Optional[str]]
    ] = field(default_factory=list)

    # ref / result 段数量
    total_ref: int = 0
    total_result: int = 0
    matched_count: int = 0
    unmatched_ref: int = 0
    unmatched_result: int = 0

    # 起点 / 终点误差（基于所有配对）
    avg_start_err: float = 0.0
    avg_abs_start_err: float = 0.0
    max_abs_start_err: float = 0.0

    avg_end_err: float = 0.0
    avg_abs_end_err: float = 0.0
    max_abs_end_err: float = 0.0

    # 阈值
    threshold: float = 0.3

    # 参考 / 结果文件路径（用于 HTML / 报告展示）
    ref_file: str = ""
    result_file: str = ""


def _percentile(values: List[float], p: float) -> float:
    """计算百分位，values 需为非空列表，p 取值 0~1"""
    if not values:
        return 0.0
    vs = sorted(values)
    n = len(vs)
    if n == 1:
        return vs[0]
    # 使用 (n-1)*p 的位置，并四舍五入
    idx = int(round((n - 1) * p))
    idx = max(0, min(n - 1, idx))
    return vs[idx]


def _compute_delta_stats(stats: TimeBoundaryStats):
    """
    基于 pair_metrics 计算：
      - start / end 绝对误差（毫秒）的平均值、最小值、最大值
      - 90% / 70% / 50% / 30% 覆盖的误差阈值（即对应百分位）
    """
    n = len(stats.pair_metrics)
    if n == 0:
        return {
            "count": 0,
            "start": {"avg": 0.0, "min": 0.0, "max": 0.0, "p": {90: 0.0, 70: 0.0, 50: 0.0, 30: 0.0}},
            "end":   {"avg": 0.0, "min": 0.0, "max": 0.0, "p": {90: 0.0, 70: 0.0, 50: 0.0, 30: 0.0}},
        }

    start_list = [p.start_delta_ms for p in stats.pair_metrics]
    end_list   = [p.end_delta_ms for p in stats.pair_metrics]

    def _basic(vs: List[float]):
        return {
            "avg": sum(vs) / len(vs),
            "min": min(vs),
            "max": max(vs),
            "p": {
                90: _percentile(vs, 0.9),
                70: _percentile(vs, 0.7),
                50: _percentile(vs, 0.5),
                30: _percentile(vs, 0.3),
            },
        }

    return {
        "count": n,
        "start": _basic(start_list),
        "end":   _basic(end_list),
    }


def _parse_time_file(file_path: str) -> List[TimeSegment]:
    """
    解析时间边界文件（ref 和 result 使用相同格式）

    新的更通用格式约定为：
        音频路径  文本(可包含空格)  开始时间(s)  结束时间(s)

    兼容旧格式：
        音频路径  00h_S  开始时间(s)  结束时间(s)
    此时“文本”即为原来的标签（例如 00h_S）。
    """
    segments: List[TimeSegment] = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 4:
                logger.warning(f"时间文件第 {line_num} 行格式不正确，跳过：{line}")
                continue
            try:
                audio_path = parts[0]
                # 约定最后两个字段一定是起止时间，其余字段合并为“文本/标签”
                start_time = float(parts[-2])
                end_time = float(parts[-1])
                if start_time >= end_time:
                    logger.warning(f"时间文件第 {line_num} 行 start >= end，跳过")
                    continue
                text = " ".join(parts[1:-2]) if len(parts) > 3 else ""
                segments.append(TimeSegment(audio_path, start_time, end_time, line_num, text=text))
            except (ValueError, IndexError) as e:
                logger.warning(f"时间文件第 {line_num} 行解析失败，跳过：{e}")
    return segments


def _parse_jsonl_time_file(file_path: str, result_type: Optional[str]) -> List[TimeSegment]:
    """
    从 JSONL 回调日志中解析时间段

    预期示例结构（来自 TSA 回调）：
        {
          "client": "TSA",
          "status": 16,
          "callback_type": "ASRResult",
          "data": {
              "source": "TSAP",
              "type": "ASRResult",
              "data": {
                  "result": {
                      "startMts": 4690,
                      "endMts": 6240,
                      ...
                  }
              }
          },
          "audio": "TestAudio/SDK/time_boundary/0_output.wav"
        }

    Args:
        file_path: JSONL 文件路径
        result_type: 需要过滤的结果类型，如 "ASRResult"、"localASRResult"、"cloudASRResult"。
                     若为 None，则不过滤类型。
    """
    segments: List[TimeSegment] = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                logger.warning(f"JSONL 文件第 {line_num} 行解析 JSON 失败，跳过：{e}")
                continue

            cb_type = obj.get("callback_type") or obj.get("type")
            data = obj.get("data") or {}
            inner_type = data.get("type")

            # 类型过滤：优先用 data.type，其次 callback_type
            if result_type:
                if inner_type != result_type and cb_type != result_type:
                    continue

            # 提取音频路径
            audio_path = obj.get("audio") or data.get("audio")
            if not audio_path:
                # 有些结构可能把 audio 放在 data.data 里，这里保守处理
                inner_data = data.get("data") or {}
                audio_path = inner_data.get("audio")
            if not audio_path:
                logger.warning(f"JSONL 第 {line_num} 行缺少 audio 字段，跳过")
                continue

            # 提取结果中的 startMts / endMts（毫秒）以及识别文本 text
            # 常见结构：data.data.result 或 data.result
            result_block = None
            inner_data = data.get("data")
            if isinstance(inner_data, dict) and "result" in inner_data:
                result_block = inner_data.get("result")
            elif "result" in data:
                result_block = data.get("result")

            if not isinstance(result_block, dict):
                logger.warning(f"JSONL 第 {line_num} 行缺少 result 字段，跳过")
                continue

            start_ms = result_block.get("startMts")
            end_ms = result_block.get("endMts")
            if start_ms is None or end_ms is None:
                logger.warning(f"JSONL 第 {line_num} 行缺少 startMts/endMts 字段，跳过")
                continue

            # 识别文本：优先从 result.text 取
            text = ""
            try:
                raw_text = result_block.get("text")
                if isinstance(raw_text, str):
                    text = raw_text
            except Exception:
                text = ""

            try:
                start_s = float(start_ms) / 1000.0
                end_s = float(end_ms) / 1000.0
            except (TypeError, ValueError) as e:
                logger.warning(f"JSONL 第 {line_num} 行时间字段转 float 失败，跳过：{e}")
                continue

            if start_s >= end_s:
                logger.warning(f"JSONL 第 {line_num} 行 start >= end，跳过")
                continue

            segments.append(TimeSegment(audio_path, start_s, end_s, line_num, text=text))

    logger.info(
        f"从 JSONL 解析得到 {len(segments)} 个时间段"
        + (f"（类型过滤: {result_type}）" if result_type else "")
    )
    return segments


def _group_by_audio(segments: List[TimeSegment]) -> Dict[str, List[TimeSegment]]:
    """按音频路径分组并按开始时间排序"""
    grouped: Dict[str, List[TimeSegment]] = {}
    for seg in segments:
        grouped.setdefault(seg.audio_path, []).append(seg)
    for segs in grouped.values():
        segs.sort(key=lambda s: (s.start, s.end))
    return grouped


def _match_segments_for_audio(
    ref_segs: List[TimeSegment],
    result_segs: List[TimeSegment],
    max_dist_ms: Optional[float] = None,
    start_gate_ms: Optional[float] = None,
) -> List[Tuple[TimeSegment, TimeSegment]]:
    """
    最近邻 1-to-1 匹配策略（仅基于时间边界）：
      - 对每个 ref 段，在所有尚未匹配的 result 段中，找到时间边界“距离”最近的一条
      - 距离的定义与 pasr_time_boundary 一致：sqrt(Δstart_ms^2 + Δend_ms^2)
      - 不做更复杂的文本过滤，仅按时间最近邻配对
      - 匹配门限优先按“起点门距”判定：|Δstart_ms| ≤ start_gate_ms 则配上
      - 若未提供 start_gate_ms，则回退使用综合距离门限 max_dist_ms（历史行为）
    """
    # 兼容：若仅提供了 max_dist_ms（旧参数），用作起点门距
    if start_gate_ms is None and max_dist_ms is not None:
        start_gate_ms = max_dist_ms

    for seg in ref_segs:
        seg.matched = False
    for seg in result_segs:
        seg.matched = False

    pairs: List[Tuple[TimeSegment, TimeSegment]] = []
    if not ref_segs or not result_segs:
        return pairs

    for ref_seg in ref_segs:
        best_idx = None
        best_dist = None

        for idx, hyp_seg in enumerate(result_segs):
            if hyp_seg.matched:
                continue
            # 计算时间边界距离（毫秒），与 pasr_time_boundary 一致
            start_delta_ms = abs(hyp_seg.start - ref_seg.start) * 1000.0
            end_delta_ms = abs(hyp_seg.end - ref_seg.end) * 1000.0
            dist_ms = math.sqrt(start_delta_ms * start_delta_ms + end_delta_ms * end_delta_ms)

            if best_dist is None or dist_ms < best_dist:
                best_dist = dist_ms
                best_idx = idx

        if best_idx is not None:
            hyp_seg = result_segs[best_idx]
            # 门限判定：
            # 1) 若设置了起点门距，则仅按起点误差判定是否允许配对
            if start_gate_ms is not None:
                start_delta_ms = abs(hyp_seg.start - ref_seg.start) * 1000.0
                if start_delta_ms > start_gate_ms:
                    continue
            # 2) 否则回退到综合距离门限（保持兼容）
            elif max_dist_ms is not None and best_dist is not None and best_dist > max_dist_ms:
                continue
            ref_seg.matched = True
            hyp_seg.matched = True
            pairs.append((ref_seg, hyp_seg))

    return pairs


def _calculate_time_boundary_stats(
    ref_file: str,
    result_file: str,
    threshold: float,
    result_type: Optional[str],
    max_dist_ms: Optional[float] = None,
) -> TimeBoundaryStats:
    """读取文件、按音频匹配，并统计时间边界指标"""
    # 参考文件：现在假定已经在外部清理掉无关段（例如 00h_N），
    #           并且第二列开始为“参考转写文本”，最后两列为起止时间
    ref_segments = _parse_time_file(ref_file)

    if result_file.endswith(".jsonl"):
        result_segments = _parse_jsonl_time_file(result_file, result_type)
    else:
        result_segments = _parse_time_file(result_file)

    logger.info(f"TIME_BOUNDARY_ACCURACY: ref 记录数={len(ref_segments)}, result 记录数={len(result_segments)}")

    ref_grouped = _group_by_audio(ref_segments)
    result_grouped = _group_by_audio(result_segments)
    all_audio_paths = set[str](ref_grouped.keys()) | set(result_grouped.keys())

    stats = TimeBoundaryStats(
        total_ref=len(ref_segments),
        total_result=len(result_segments),
        threshold=threshold,
        ref_file=ref_file,
        result_file=result_file,
    )

    # 收集所有配对样本
    for audio_path in sorted(all_audio_paths):
        ref_segs = ref_grouped.get(audio_path, [])
        hyp_segs = result_grouped.get(audio_path, [])

        # 使用“起点门距”优先的匹配规则：将 max_dist_ms 作为 start_gate_ms 使用
        pairs = _match_segments_for_audio(ref_segs, hyp_segs, max_dist_ms=max_dist_ms, start_gate_ms=max_dist_ms)
        # 为明细表构建“按参考顺序”的对齐行
        ref_to_hyp: Dict[TimeSegment, TimeSegment] = {}
        for r, h in pairs:
            ref_to_hyp[r] = h
        for r in ref_segs:
            h = ref_to_hyp.get(r)
            if h is None:
                stats.aligned_rows.append(
                    (audio_path, r.start, r.end, None, None, r.text, None)
                )
            else:
                stats.aligned_rows.append(
                    (audio_path, r.start, r.end, h.start, h.end, r.text, h.text)
                )
        for ref_seg, hyp_seg in pairs:
            start_err = hyp_seg.start - ref_seg.start
            end_err = hyp_seg.end - ref_seg.end
            # 将误差转换为毫秒，并按“距离公式”计算综合时间边界距离
            start_delta_ms = abs(start_err) * 1000.0
            end_delta_ms = abs(end_err) * 1000.0
            distance_ms = math.sqrt(start_delta_ms * start_delta_ms + end_delta_ms * end_delta_ms)

            # 命中逻辑：按 pasr_time_boundary 思路，用综合距离与阈值比较（阈值单位：秒）
            hit = distance_ms <= threshold * 1000.0
            stats.pair_metrics.append(
                TimeBoundaryPairMetrics(
                    audio_path=audio_path,
                    ref_start=ref_seg.start,
                    ref_end=ref_seg.end,
                    hyp_start=hyp_seg.start,
                    hyp_end=hyp_seg.end,
                    start_err=start_err,
                    end_err=end_err,
                    start_delta_ms=start_delta_ms,
                    end_delta_ms=end_delta_ms,
                    distance_ms=distance_ms,
                    hit=hit,
                    ref_text=ref_seg.text,
                    hyp_text=hyp_seg.text,
                )
            )

        stats.matched_count += len(pairs)
        stats.unmatched_ref += max(0, len(ref_segs) - len(pairs))
        stats.unmatched_result += max(0, len(hyp_segs) - len(pairs))

    # 统计聚合指标
    if stats.pair_metrics:
        n = len(stats.pair_metrics)
        start_errs = [p.start_err for p in stats.pair_metrics]
        end_errs = [p.end_err for p in stats.pair_metrics]
        abs_start_errs = [abs(x) for x in start_errs]
        abs_end_errs = [abs(x) for x in end_errs]

        stats.avg_start_err = sum(start_errs) / n
        stats.avg_abs_start_err = sum(abs_start_errs) / n
        stats.max_abs_start_err = max(abs_start_errs)

        stats.avg_end_err = sum(end_errs) / n
        stats.avg_abs_end_err = sum(abs_end_errs) / n
        stats.max_abs_end_err = max(abs_end_errs)

    return stats


@register_tsr_command("TIME_BOUNDARY_ACCURACY")
class TimeBoundaryAccuracyHandler(BaseTSRHandler):
    """
    时间边界误差统计处理器

    指令格式:
        [TSR]TIME_BOUNDARY_ACCURACY result=<result_txt> ref=<ref_txt> [output=<report_xlsx>] [threshold=<秒>]

    参数说明:
        result   : 检测结果文件路径（必需）
        ref      : 参考时间文件路径（必需）
        output   : Excel 报告输出路径（可选）
        threshold: 命中阈值（单位：秒，默认 0.3）

    输入文件格式（ref/result 相同）：
        音频路径  00h_S  开始时间(s)  结束时间(s)
    """

    COMMAND_NAME = "TIME_BOUNDARY_ACCURACY"

    def execute(self, params: List[str], output_report: str = None) -> str:
        """执行时间边界误差统计"""
        result_file, ref_file, xlsx_path, threshold, result_type, max_dist_ms = self._parse_params(params, output_report)

        if not os.path.exists(result_file):
            raise FileNotFoundError(f"结果文件不存在: {result_file}")
        if not os.path.exists(ref_file):
            raise FileNotFoundError(f"参考文件不存在: {ref_file}")

        if result_type == "both":
            logger.info(
                f"TIME_BOUNDARY_ACCURACY[localASRResult/cloudASRResult]: result={result_file}, ref={ref_file}, "
                f"threshold={threshold}s, output={xlsx_path}"
            )

            stats_local = _calculate_time_boundary_stats(ref_file, result_file, threshold, "localASRResult", max_dist_ms)
            stats_cloud = _calculate_time_boundary_stats(ref_file, result_file, threshold, "cloudASRResult", max_dist_ms)

            self._generate_excel_report_both(stats_local, stats_cloud, ref_file, result_file, xlsx_path)

            html_content = self._build_html_both(stats_local, stats_cloud)
            html_filename = "time_boundary_accuracy.html"
            self.save_html_report(html_content, html_filename, "时间边界误差报告（本地 & 端云）", "time_boundary_accuracy")

            local_html = os.path.splitext(xlsx_path)[0] + ".html"
            os.makedirs(os.path.dirname(local_html) or ".", exist_ok=True)
            with open(local_html, "w", encoding="utf-8") as f:
                f.write(html_content)
            logger.info(f"本地 HTML 报告已生成: {local_html}")

            summary_local = self._generate_summary(stats_local, xlsx_path, "localASRResult")
            summary_cloud = self._generate_summary(stats_cloud, xlsx_path, "cloudASRResult")
            return f"{summary_local}\n\n{summary_cloud}"

        logger.info(
            f"TIME_BOUNDARY_ACCURACY: result={result_file}, ref={ref_file}, "
            f"threshold={threshold}s, type={result_type}, output={xlsx_path}"
        )

        stats = _calculate_time_boundary_stats(ref_file, result_file, threshold, result_type, max_dist_ms)

        # 生成 Excel 报告
        self._generate_excel_report(stats, ref_file, result_file, xlsx_path, result_type)

        # 生成 HTML 报告（保存到 allure_result/mango_report/{define}/{suite}/）
        html_content = self._build_html(stats)
        html_filename = "time_boundary_accuracy.html"
        self.save_html_report(html_content, html_filename, "时间边界误差报告", "time_boundary_accuracy")

        # 本地副本
        local_html = os.path.splitext(xlsx_path)[0] + ".html"
        os.makedirs(os.path.dirname(local_html) or ".", exist_ok=True)
        with open(local_html, "w", encoding="utf-8") as f:
            f.write(html_content)
        logger.info(f"本地 HTML 报告已生成: {local_html}")

        return self._generate_summary(stats, xlsx_path, result_type)

    # ── 参数解析 ──────────────────────────────────────────────────────────────

    def _parse_params(
        self,
        params: List[str],
        default_output: str = None,
    ) -> Tuple[str, str, str, float, Optional[str], Optional[float]]:
        result_file: Optional[str] = None
        ref_file: Optional[str] = None
        output_path: Optional[str] = default_output
        threshold: float = 0.3
        result_type: Optional[str] = None
        max_dist_ms: Optional[float] = 1200.0

        for param in params:
            if param.startswith("result="):
                result_file = param[7:]
            elif param.startswith("ref="):
                ref_file = param[4:]
            elif param.startswith("output="):
                output_path = param[7:]
            elif param.startswith("threshold="):
                try:
                    threshold = float(param[len("threshold=") :])
                except ValueError:
                    raise ValueError(f"threshold 参数非法: {param}")
            elif param.startswith("type="):
                result_type = param[5:]
            elif param.startswith("maxdist_ms="):
                # 直接使用毫秒门限
                try:
                    max_dist_ms = float(param[len("maxdist_ms=") :])
                except ValueError:
                    raise ValueError(f"maxdist_ms 参数非法: {param}")
            elif param.startswith("maxdist="):
                # 以秒为单位的门限
                try:
                    max_dist_ms = float(param[len("maxdist=") :]) * 1000.0
                except ValueError:
                    raise ValueError(f"maxdist 参数非法: {param}")

        if not result_file:
            raise ValueError("缺少必需参数: result=<result_txt>")
        if not ref_file:
            raise ValueError("缺少必需参数: ref=<ref_txt>")

        if output_path is None:
            suite_mango_dir = self._get_suite_mango_dir()
            output_path = os.path.join(suite_mango_dir, "time_boundary_accuracy.xlsx")

        return result_file, ref_file, output_path, threshold, result_type, max_dist_ms

    # ── HTML 报告 ─────────────────────────────────────────────────────────────

    def generate_html_report(self, *args, **kwargs) -> Optional[str]:
        """实现抽象方法"""
        stats = args[0] if args else kwargs.get("stats")
        if stats is None:
            return None
        html = self._build_html(stats)
        return self.save_html_report(
            html,
            "time_boundary_accuracy.html",
            "时间边界误差报告",
            "time_boundary_accuracy",
        )

    def _build_html(self, stats: TimeBoundaryStats) -> str:
        """构建自包含 HTML 报告"""
        delta_stats = _compute_delta_stats(stats)

        cards_html = (
            '<div class="summary-cards">'
            f'<div class="card"><div class="card-value">{stats.ref_file}</div>'
            f'<div class="card-label">参考文件</div></div>'
            f'<div class="card"><div class="card-value">{stats.result_file}</div>'
            f'<div class="card-label">结果文件</div></div>'
            f'<div class="card"><div class="card-value">{stats.total_ref}</div>'
            f'<div class="card-label">样本数量</div></div>'
            "</div>"
        )

        # 详细数据表（全部以毫秒为单位输出）
        threshold_ms = stats.threshold * 1000.0
        detail_rows = "".join(
            f"<tr>"
            f"<td>{i}</td>"
            f"<td>{p.audio_path}</td>"
            f"<td>{p.ref_start * 1000:.1f}</td><td>{p.ref_end * 1000:.1f}</td>"
            f"<td>{p.ref_text}</td>"
            f"<td>{p.hyp_text}</td>"
            f"<td>{p.hyp_start * 1000:.1f}</td><td>{p.hyp_end * 1000:.1f}</td>"
            f"<td>{p.start_err * 1000:.1f}</td>"
            f"<td>{p.end_err * 1000:.1f}</td>"
            f"<td><span style=\"color:{'red' if p.start_delta_ms > threshold_ms else '#333'}\">{p.start_delta_ms:.1f}</span></td>"
            f"<td><span style=\"color:{'red' if p.end_delta_ms > threshold_ms else '#333'}\">{p.end_delta_ms:.1f}</span></td>"
            f"</tr>"
            for i, p in enumerate(stats.pair_metrics, 1)
        )

        detail_table = (
            '<table class="report-table"><thead>'
            "<tr>"
            "<th>#</th><th>音频路径</th>"
            "<th>Ref 起点(ms)</th><th>Ref 终点(ms)</th>"
            "<th>Ref 文本</th>"
            "<th>Hyp 文本</th>"
            "<th>Hyp 起点(ms)</th><th>Hyp 终点(ms)</th>"
            "<th>ΔStart(ms)</th><th>ΔEnd(ms)</th>"
            "<th>|ΔStart|(ms)</th><th>|ΔEnd|(ms)</th>"
            "</tr>"
            f"</thead><tbody>{detail_rows}</tbody></table>"
        )

        # 汇总统计表（平均值 / 最大值 / 最小值 + 百分位）
        ds = delta_stats
        summary_tables = (
            "<table class=\"report-table\"><thead>"
            "<tr><th>指标</th><th>起点误差 ΔStart (ms)</th><th>终点误差 ΔEnd (ms)</th></tr>"
            "</thead><tbody>"
            f"<tr><td>样本数量</td><td colspan=\"2\">{ds['count']}</td></tr>"
            f"<tr><td>平均值</td>"
            f"<td>{ds['start']['avg']:.1f}</td>"
            f"<td>{ds['end']['avg']:.1f}</td></tr>"
            f"<tr><td>最大值</td>"
            f"<td>{ds['start']['max']:.1f}</td>"
            f"<td>{ds['end']['max']:.1f}</td></tr>"
            f"<tr><td>最小值</td>"
            f"<td>{ds['start']['min']:.1f}</td>"
            f"<td>{ds['end']['min']:.1f}</td></tr>"
            "</tbody></table>"
            "<br/>"
            "<table class=\"report-table\"><thead>"
            "<tr><th>覆盖比例</th><th>ΔStart 阈值 (ms)</th><th>ΔEnd 阈值 (ms)</th></tr>"
            "</thead><tbody>"
            f"<tr><td>90%</td><td>{ds['start']['p'][90]:.0f}</td><td>{ds['end']['p'][90]:.0f}</td></tr>"
            f"<tr><td>70%</td><td>{ds['start']['p'][70]:.0f}</td><td>{ds['end']['p'][70]:.0f}</td></tr>"
            f"<tr><td>50%</td><td>{ds['start']['p'][50]:.0f}</td><td>{ds['end']['p'][50]:.0f}</td></tr>"
            f"<tr><td>30%</td><td>{ds['start']['p'][30]:.0f}</td><td>{ds['end']['p'][30]:.0f}</td></tr>"
            "</tbody></table>"
        )

        section_html = (
            '<div class="section">'
            '<div class="section-header">⏱ 时间边界误差详情</div>'
            '<div class="section-body">'
            f"{detail_table}"
            "<br/>"
            f"{summary_tables}"
            "</div></div>"
        )

        return self.build_html_page("时间边界误差报告", cards_html + section_html)

    def _build_html_both(
        self,
        stats_local: TimeBoundaryStats,
        stats_cloud: TimeBoundaryStats,
    ) -> str:
        """type=both 时，构建 Tab 页面：汇总统计 / 本地&云端结果 / 端云边界误差"""

        # 顶部摘要卡片：只渲染一次，显示参考/结果文件及样本数量（与 Excel 汇总一致）
        ds_local = _compute_delta_stats(stats_local)
        cards_html = (
            '<div class="summary-cards">'
            f'<div class="card"><div class="card-value">{stats_local.ref_file}</div>'
            f'<div class="card-label">参考文件</div></div>'
            f'<div class="card"><div class="card-value">{stats_local.result_file}</div>'
            f'<div class="card-label">结果文件</div></div>'
            f'<div class="card"><div class="card-value">{ds_local["count"]}</div>'
            f'<div class="card-label">样本数量</div></div>'
            "</div>"
        )

        # ── Tab1：汇总统计（本地 + 云端） ─────────────────────────────
        ds_cloud = _compute_delta_stats(stats_cloud)

        def _summary_block(title: str, ds) -> str:
            return (
                f"<h3>{title}</h3>"
                "<table class=\"report-table\"><thead>"
                "<tr><th>指标</th><th>起点误差 ΔStart (ms)</th><th>终点误差 ΔEnd (ms)</th></tr>"
                "</thead><tbody>"
                f"<tr><td>平均值</td><td>{ds['start']['avg']:.1f}</td><td>{ds['end']['avg']:.1f}</td></tr>"
                f"<tr><td>最大值</td><td>{ds['start']['max']:.1f}</td><td>{ds['end']['max']:.1f}</td></tr>"
                f"<tr><td>最小值</td><td>{ds['start']['min']:.1f}</td><td>{ds['end']['min']:.1f}</td></tr>"
                "</tbody></table>"
                "<br/>"
                "<table class=\"report-table\"><thead>"
                "<tr><th>覆盖比例</th><th>ΔStart 阈值 (ms)</th><th>ΔEnd 阈值 (ms)</th></tr>"
                "</thead><tbody>"
                f"<tr><td>90%</td><td>{ds['start']['p'][90]:.0f}</td><td>{ds['end']['p'][90]:.0f}</td></tr>"
                f"<tr><td>70%</td><td>{ds['start']['p'][70]:.0f}</td><td>{ds['end']['p'][70]:.0f}</td></tr>"
                f"<tr><td>50%</td><td>{ds['start']['p'][50]:.0f}</td><td>{ds['end']['p'][50]:.0f}</td></tr>"
                f"<tr><td>30%</td><td>{ds['start']['p'][30]:.0f}</td><td>{ds['end']['p'][30]:.0f}</td></tr>"
                "</tbody></table>"
            )

        summary_tab_html = (
            "<div class=\"section-body\">"
            f"{_summary_block('本地边界结果 (localASRResult)', ds_local)}"
            "<br/>"
            f"{_summary_block('云端边界结果 (cloudASRResult)', ds_cloud)}"
            "</div>"
        )

        # ── Tab2：本地 / 云端 明细结果 ───────────────────────────────
        def _detail_table(title: str, stats: TimeBoundaryStats) -> str:
            threshold_ms = stats.threshold * 1000.0
            detail_rows = "".join(
                f"<tr>"
                f"<td>{i}</td>"
                f"<td>{p.audio_path}</td>"
                f"<td>{p.ref_start * 1000:.1f}</td><td>{p.ref_end * 1000:.1f}</td>"
                f"<td>{p.ref_text}</td>"
                f"<td>{p.hyp_text}</td>"
                f"<td>{p.hyp_start * 1000:.1f}</td><td>{p.hyp_end * 1000:.1f}</td>"
                f"<td>{p.start_err * 1000:.1f}</td>"
                f"<td>{p.end_err * 1000:.1f}</td>"
                f"<td><span style=\"color:{'red' if p.start_delta_ms > threshold_ms else '#333'}\">{p.start_delta_ms:.1f}</span></td>"
                f"<td><span style=\"color:{'red' if p.end_delta_ms > threshold_ms else '#333'}\">{p.end_delta_ms:.1f}</span></td>"
                f"</tr>"
                for i, p in enumerate(stats.pair_metrics, 1)
            )

            return (
                f"<h3>{title}</h3>"
                "<table class=\"report-table\"><thead>"
                "<tr>"
                "<th>#</th><th>音频路径</th>"
                "<th>Ref 起点(ms)</th><th>Ref 终点(ms)</th>"
                "<th>Ref 文本</th>"
                "<th>Hyp 文本</th>"
                "<th>Hyp 起点(ms)</th><th>Hyp 终点(ms)</th>"
                "<th>ΔStart(ms)</th><th>ΔEnd(ms)</th>"
                "<th>|ΔStart|(ms)</th><th>|ΔEnd|(ms)</th>"
                "</tr>"
                f"</thead><tbody>{detail_rows}</tbody></table>"
            )

        local_detail_tab_html = (
            "<div class=\"section-body\">"
            f"{_detail_table('本地边界结果 (localASRResult)', stats_local)}"
            "</div>"
        )
        cloud_detail_tab_html = (
            "<div class=\"section-body\">"
            f"{_detail_table('云端边界结果 (cloudASRResult)', stats_cloud)}"
            "</div>"
        )

        def _diff_section(stats_local: TimeBoundaryStats, stats_cloud: TimeBoundaryStats) -> str:
            """端云边界误差对比表：按参考段顺序对齐，未匹配填 'unknow'"""
            n = max(len(stats_local.aligned_rows), len(stats_cloud.aligned_rows))
            if n == 0:
                rows = "<tr><td colspan=\"8\">无可比对样本</td></tr>"
            else:
                tr_list = []
                for i in range(n):
                    al = stats_local.aligned_rows[i] if i < len(stats_local.aligned_rows) else None
                    ac = stats_cloud.aligned_rows[i] if i < len(stats_cloud.aligned_rows) else None
                    # 公共参考信息（以本地优先，否则云端）
                    if al is not None:
                        audio_path, ref_s, ref_e, lh_s, lh_e, _, _ = al
                    elif ac is not None:
                        audio_path, ref_s, ref_e, lh_s, lh_e, _, _ = ac[0], ac[1], ac[2], None, None, "", None
                    else:
                        continue
                    ch_s = ac[3] if ac is not None else None
                    ch_e = ac[4] if ac is not None else None
                    # 数值或 unknow
                    def _fmt(v):
                        return f"{v*1000:.1f}" if isinstance(v, (int, float)) else "unknow"
                    def _diff(a, b):
                        return f"{abs((b - a)*1000):.1f}" if isinstance(a, (int,float)) and isinstance(b, (int,float)) else "unknow"
                    tr_list.append(
                        "<tr>"
                        f"<td>{i+1}</td>"
                        f"<td>{audio_path}</td>"
                        f"<td>{_fmt(lh_s)}</td>"
                        f"<td>{_fmt(ch_s)}</td>"
                        f"<td>{_diff(lh_s, ch_s)}</td>"
                        f"<td>{_fmt(lh_e)}</td>"
                        f"<td>{_fmt(ch_e)}</td>"
                        f"<td>{_diff(lh_e, ch_e)}</td>"
                        "</tr>"
                    )
                rows = "".join(tr_list)

            table = (
                "<table class=\"report-table\"><thead>"
                "<tr>"
                "<th>#</th><th>音频路径</th>"
                "<th>本地 Start(ms)</th><th>云端 Start(ms)</th><th>差值 (cloud-local,ms)</th>"
                "<th>本地 End(ms)</th><th>云端 End(ms)</th><th>差值 (cloud-local,ms)</th>"
                "</tr>"
                f"</thead><tbody>{rows}</tbody></table>"
            )

            return "<div class=\"section-body\">" + table + "</div>"

        diff_tab_html = _diff_section(stats_local, stats_cloud)

        # 外层 Section + Tabs（4 个 Tab：汇总 / 本地 / 云端 / 端云误差）
        tabs_html = (
            '<div class="section">'
            '<div class="section-header">时间边界误差详情（本地 & 云端）</div>'
            '<div class="section-body">'
            '<div class="inner-tabs">'
            '<div class="inner-tab active" onclick="switchTab(this,\'tb_sum\')">汇总统计</div>'
            '<div class="inner-tab" onclick="switchTab(this,\'tb_local\')">本地边界结果</div>'
            '<div class="inner-tab" onclick="switchTab(this,\'tb_cloud\')">云端边界结果</div>'
            '<div class="inner-tab" onclick="switchTab(this,\'tb_diff\')">端云边界误差</div>'
            "</div>"
            f'<div id="tb_sum" class="inner-pane active">{summary_tab_html}</div>'
            f'<div id="tb_local" class="inner-pane">{local_detail_tab_html}</div>'
            f'<div id="tb_cloud" class="inner-pane">{cloud_detail_tab_html}</div>'
            f'<div id="tb_diff" class="inner-pane">{diff_tab_html}</div>'
            "</div></div>"
        )

        return self.build_html_page("时间边界误差报告（本地 & 云端）", cards_html + tabs_html)

    # ── Excel 报告 ─────────────────────────────────────────────────────────────

    def _generate_excel_report(
        self,
        stats: TimeBoundaryStats,
        ref_file: str,
        result_file: str,
        output_path: str,
        result_type: Optional[str] = None,
    ) -> None:
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment
            from openpyxl.utils import get_column_letter
        except ImportError:
            raise ImportError("生成 Excel 报告需要安装 openpyxl：pip install openpyxl")

        wb = openpyxl.Workbook()
        if "Sheet" in wb.sheetnames:
            wb.remove(wb["Sheet"])

        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF", size=11)
        title_font = Font(bold=True, size=12)
        center_align = Alignment(horizontal="center", vertical="center")
        left_align = Alignment(horizontal="left", vertical="center")
        warn_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
        warn_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
        warn_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
        warn_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
        blue_fill = PatternFill(start_color="DDEBF7", end_color="DDEBF7", fill_type="solid")
        green_fill = PatternFill(start_color="C5E0B4", end_color="C5E0B4", fill_type="solid")
        red_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")

        def _write_header(ws, row: int, headers: list) -> None:
            for c, h in enumerate(headers, 1):
                cell = ws.cell(row=row, column=c, value=h)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = center_align

        # Sheet1：汇总信息
        ws_sum = wb.create_sheet("汇总信息", 0)
        ws_sum["A1"] = "时间边界误差分析结果（单位：毫秒）"
        ws_sum["A1"].font = Font(bold=True, size=14)
        ws_sum.merge_cells("A1:B1")

        r = 3
        for label, value in [("参考文件：", ref_file), ("结果文件：", result_file)]:
            ws_sum.cell(row=r, column=1, value=label)
            ws_sum.cell(row=r, column=2, value=value)
            r += 1

        r += 1

        ws_sum.cell(row=r, column=1, value="样本数量").font = title_font
        ws_sum.cell(row=r, column=2, value=stats.total_ref)
        ws_sum.merge_cells(f"B{r}:C{r}")
        r += 1

        ws_sum.cell(row=r, column=1, value="汇总统计").font = title_font
        ws_sum.merge_cells(f"A{r}:B{r}")
        r += 1

        delta_stats = _compute_delta_stats(stats)
        ds = delta_stats
        headers = ["指标", "ΔStart (ms)", "ΔEnd (ms)"]
        _write_header(ws_sum, r, headers)
        r += 1
        for name, ds in [("平均值", ds), ("最大值", ds), ("最小值", ds)]:
            if name == "平均值":
                ws_sum.cell(row=r, column=1, value="平均值")
                ws_sum.cell(row=r, column=2, value=round(ds["start"]["avg"], 2))
                ws_sum.cell(row=r, column=3, value=round(ds["end"]["avg"], 2))
            elif name == "最大值":
                ws_sum.cell(row=r, column=1, value="最大值")
                ws_sum.cell(row=r, column=2, value=round(ds["start"]["max"], 2))
                ws_sum.cell(row=r, column=3, value=round(ds["end"]["max"], 2))
            elif name == "最小值":
                ws_sum.cell(row=r, column=1, value="最小值")
                ws_sum.cell(row=r, column=2, value=round(ds["start"]["min"], 2))
                ws_sum.cell(row=r, column=3, value=round(ds["end"]["min"], 2))
            r += 1


        # 百分位统计表
        r += 1
        ws_sum.cell(row=r, column=1, value="误差覆盖分布").font = title_font
        ws_sum.merge_cells(f"A{r}:B{r}")
        r += 1

        pct_headers = ["覆盖比例", "ΔStart 阈值(ms)", "ΔEnd 阈值(ms)"]
        for c, h in enumerate(pct_headers, 1):
            cell = ws_sum.cell(row=r, column=c, value=h)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = center_align
        r += 1

        for pct in (90, 70, 50, 30):
            ws_sum.cell(row=r, column=1, value=f"{pct}%")
            ws_sum.cell(row=r, column=2, value=round(ds["start"]["p"][pct], 2))
            ws_sum.cell(row=r, column=3, value=round(ds["end"]["p"][pct], 2))
            r += 1

        ws_sum.column_dimensions["A"].width = 22
        ws_sum.column_dimensions["B"].width = 24
        ws_sum.column_dimensions["C"].width = 24

        # Sheet2：配对明细
        # 按你的命名约定：
        #   - 本地结果：  本地边界结果   （localASRResult）
        #   - 端云结果：  端云边界误差   （cloudASRResult）
        #   - 其它/未指定：本地边界结果（默认）
        if result_type == "cloudASRResult":
            detail_sheet_name = "端云边界误差"
        else:
            detail_sheet_name = "本地边界结果"
        ws_detail = wb.create_sheet(detail_sheet_name, 1)
        headers = [
            "序号",
            "音频路径",
            "Ref 文本",
            "Ref 起点(ms)",
            "Ref 终点(ms)",
            "Hyp 文本",
            "Hyp 起点(ms)",
            "Hyp 终点(ms)",
            "ΔStart(ms)",
            "ΔEnd(ms)",
            "|ΔStart|(ms)",
            "|ΔEnd|(ms)"
        ]
        _write_header(ws_detail, 1, headers)

        threshold_ms = stats.threshold * 1000.0
        # 明细：按参考顺序输出；未匹配的 Hyp 列与误差列填 "unknow"
        for idx, row in enumerate(stats.aligned_rows, 2):
            audio_path, ref_s, ref_e, hyp_s, hyp_e, ref_text, hyp_text = row
            if hyp_s is None or hyp_e is None:
                values = [
                    idx - 1,
                    audio_path,
                    ref_text or "",
                    ref_s * 1000,
                    ref_e * 1000,
                    hyp_text or "",
                    "unknow",
                    "unknow",
                    "unknow",
                    "unknow",
                    "unknow",
                    "unknow",
                ]
                for col, v in enumerate(values, 1):
                    cell = ws_detail.cell(row=idx, column=col, value=v)
                    cell.alignment = left_align if col == 2 else center_align
            else:
                start_err_ms = (hyp_s - ref_s) * 1000.0
                end_err_ms = (hyp_e - ref_e) * 1000.0
                abs_start_ms = abs(start_err_ms)
                abs_end_ms = abs(end_err_ms)
                values = [
                    idx - 1,
                    audio_path,
                    ref_text or "",
                    ref_s * 1000,
                    ref_e * 1000,
                    hyp_text or "",
                    hyp_s * 1000,
                    hyp_e * 1000,
                    start_err_ms,
                    end_err_ms,
                    abs_start_ms,
                    abs_end_ms,
                ]
                for col, v in enumerate(values, 1):
                    cell = ws_detail.cell(row=idx, column=col, value=v)
                    cell.alignment = left_align if col == 2 else center_align
                # 阈值着色仅对绝对列
                abs_start_cell = ws_detail.cell(row=idx, column=9)
                abs_end_cell = ws_detail.cell(row=idx, column=10)
                warn_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
                if abs_start_ms > threshold_ms:
                    abs_start_cell.fill = warn_fill
                if abs_end_ms > threshold_ms:
                    abs_end_cell.fill = warn_fill

        widths = [8, 50, 26, 14, 14, 14, 26, 14, 14, 14, 16, 16, 14, 10, 10]
        for ci, w in enumerate(widths, 1):
            ws_detail.column_dimensions[get_column_letter(ci)].width = w
        ws_detail.freeze_panes = "A2"
        parent = os.path.dirname(output_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        wb.save(output_path)
        logger.info(f"Excel 报告已生成: {output_path}")

    def _generate_excel_report_both(
        self,
        stats_local: TimeBoundaryStats,
        stats_cloud: TimeBoundaryStats,
        ref_file: str,
        result_file: str,
        output_path: str,
    ) -> None:
        """type=both 时，在一个 xlsx 里生成三个 Sheet：汇总信息 / 本地边界结果 / 端云边界误差"""
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment
            from openpyxl.utils import get_column_letter
        except ImportError:
            raise ImportError("生成 Excel 报告需要安装 openpyxl：pip install openpyxl")

        wb = openpyxl.Workbook()
        if "Sheet" in wb.sheetnames:
            wb.remove(wb["Sheet"])

        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF", size=11)
        title_font = Font(bold=True, size=12)
        center_align = Alignment(horizontal="center", vertical="center")
        left_align = Alignment(horizontal="left", vertical="center")

        def _write_header(ws, row: int, headers: list) -> None:
            for c, h in enumerate(headers, 1):
                cell = ws.cell(row=row, column=c, value=h)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = center_align

        # Sheet1：汇总信息
        ws_sum = wb.create_sheet("汇总信息", 0)
        ws_sum["A1"] = "时间边界误差分析结果（本地 & 端云）"
        ws_sum["A1"].font = Font(bold=True, size=14)
        ws_sum.merge_cells("A1:C1")

        r = 3
        # 参考 / 结果文件信息
        for label, value in [("参考文件：", ref_file), ("结果文件：", result_file)]:
            ws_sum.cell(row=r, column=1, value=label)
            ws_sum.cell(row=r, column=2, value=value)
            r += 1

        # 汇总两套统计
        ds_local = _compute_delta_stats(stats_local)
        ds_cloud = _compute_delta_stats(stats_cloud)

        # 样本数量（使用本地样本数量，通常与云端相同）
        ws_sum.cell(row=r, column=1, value="样本数量")
        ws_sum.cell(row=r, column=2, value=ds_local["count"])
        ws_sum.merge_cells(f"B{r}:C{r}")
        r += 1

        # 本地边界结果统计 + 百分位
        r += 1
        ws_sum.cell(row=r, column=1, value="本地边界结果 (localASRResult)").font = title_font
        ws_sum.merge_cells(f"A{r}:C{r}")
        r += 1

        headers = ["指标", "ΔStart (ms)", "ΔEnd (ms)"]
        _write_header(ws_sum, r, headers)
        r += 1
        for name, ds in [("平均值", ds_local), ("最大值", ds_local), ("最小值", ds_local)]:
            if name == "平均值":
                ws_sum.cell(row=r, column=1, value="平均值")
                ws_sum.cell(row=r, column=2, value=round(ds["start"]["avg"], 2))
                ws_sum.cell(row=r, column=3, value=round(ds["end"]["avg"], 2))
            elif name == "最大值":
                ws_sum.cell(row=r, column=1, value="最大值")
                ws_sum.cell(row=r, column=2, value=round(ds["start"]["max"], 2))
                ws_sum.cell(row=r, column=3, value=round(ds["end"]["max"], 2))
            elif name == "最小值":
                ws_sum.cell(row=r, column=1, value="最小值")
                ws_sum.cell(row=r, column=2, value=round(ds["start"]["min"], 2))
                ws_sum.cell(row=r, column=3, value=round(ds["end"]["min"], 2))
            r += 1

        # 本地百分位统计表
        r += 1
        ws_sum.cell(row=r, column=1, value="本地误差覆盖分布").font = title_font
        ws_sum.merge_cells(f"A{r}:C{r}")
        r += 1
        pct_headers = ["覆盖比例", "ΔStart 阈值(ms)", "ΔEnd 阈值(ms)"]
        for c, h in enumerate(pct_headers, 1):
            cell = ws_sum.cell(row=r, column=c, value=h)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = center_align
        r += 1
        for pct in (90, 70, 50, 30):
            ws_sum.cell(row=r, column=1, value=f"{pct}%")
            ws_sum.cell(row=r, column=2, value=round(ds_local["start"]["p"][pct], 2))
            ws_sum.cell(row=r, column=3, value=round(ds_local["end"]["p"][pct], 2))
            r += 1

        # 云端边界误差统计 + 百分位
        r += 1
        ws_sum.cell(row=r, column=1, value="云端边界误差 (cloudASRResult)").font = title_font
        ws_sum.merge_cells(f"A{r}:C{r}")
        r += 1
        _write_header(ws_sum, r, headers)
        r += 1
        for name, ds in [("平均值", ds_cloud), ("最大值", ds_cloud), ("最小值", ds_cloud)]:
            if name == "平均值":
                ws_sum.cell(row=r, column=1, value="平均值")
                ws_sum.cell(row=r, column=2, value=round(ds["start"]["avg"], 2))
                ws_sum.cell(row=r, column=3, value=round(ds["end"]["avg"], 2))
            elif name == "最大值":
                ws_sum.cell(row=r, column=1, value="最大值")
                ws_sum.cell(row=r, column=2, value=round(ds["start"]["max"], 2))
                ws_sum.cell(row=r, column=3, value=round(ds["end"]["max"], 2))
            elif name == "最小值":
                ws_sum.cell(row=r, column=1, value="最小值")
                ws_sum.cell(row=r, column=2, value=round(ds["start"]["min"], 2))
                ws_sum.cell(row=r, column=3, value=round(ds["end"]["min"], 2))
            r += 1

        r += 1
        ws_sum.cell(row=r, column=1, value="云端误差覆盖分布").font = title_font
        ws_sum.merge_cells(f"A{r}:C{r}")
        r += 1
        for c, h in enumerate(pct_headers, 1):
            cell = ws_sum.cell(row=r, column=c, value=h)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = center_align
        r += 1
        for pct in (90, 70, 50, 30):
            ws_sum.cell(row=r, column=1, value=f"{pct}%")
            ws_sum.cell(row=r, column=2, value=round(ds_cloud["start"]["p"][pct], 2))
            ws_sum.cell(row=r, column=3, value=round(ds_cloud["end"]["p"][pct], 2))
            r += 1

        ws_sum.column_dimensions["A"].width = 18
        ws_sum.column_dimensions["B"].width = 18
        ws_sum.column_dimensions["C"].width = 18

        # Sheet2 / Sheet3：本地 / 云端 边界结果明细
        def _write_detail_sheet(name: str, stats: TimeBoundaryStats, index: int):
            ws_detail = wb.create_sheet(name, index)
            headers = [
                "序号",
                "音频路径",
                "Ref 文本",
                "Ref 起点(ms)",
                "Ref 终点(ms)",
                "Hyp 文本",
                "Hyp 起点(ms)",
                "Hyp 终点(ms)",
                "ΔStart(ms)",
                "ΔEnd(ms)",
                "|ΔStart|(ms)",
                "|ΔEnd|(ms)"
            ]
            _write_header(ws_detail, 1, headers)
            threshold_ms = stats.threshold * 1000.0
            for idx, row in enumerate(stats.aligned_rows, 2):
                audio_path, ref_s, ref_e, hyp_s, hyp_e, ref_text, hyp_text = row
                if hyp_s is None or hyp_e is None:
                    values = [
                        idx - 1,
                        audio_path,
                        ref_text or "",
                        ref_s * 1000,
                        ref_e * 1000,
                        hyp_text or "",
                        "unknow",
                        "unknow",
                        "unknow",
                        "unknow",
                        "unknow",
                        "unknow",
                    ]
                    for col, v in enumerate(values, 1):
                        cell = ws_detail.cell(row=idx, column=col, value=v)
                        cell.alignment = left_align if col == 2 else center_align
                else:
                    start_err_ms = (hyp_s - ref_s) * 1000.0
                    end_err_ms = (hyp_e - ref_e) * 1000.0
                    abs_start_ms = abs(start_err_ms)
                    abs_end_ms = abs(end_err_ms)
                    values = [
                        idx - 1,
                        audio_path,
                        ref_text or "",
                        ref_s * 1000,
                        ref_e * 1000,
                        hyp_text or "",
                        hyp_s * 1000,
                        hyp_e * 1000,
                        start_err_ms,
                        end_err_ms,
                        abs_start_ms,
                        abs_end_ms,
                    ]
                    for col, v in enumerate(values, 1):
                        cell = ws_detail.cell(row=idx, column=col, value=v)
                        cell.alignment = left_align if col == 2 else center_align
                    abs_start_cell = ws_detail.cell(row=idx, column=9)
                    abs_end_cell = ws_detail.cell(row=idx, column=10)
                    warn_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
                    if abs_start_ms > threshold_ms:
                        abs_start_cell.fill = warn_fill
                    if abs_end_ms > threshold_ms:
                        abs_end_cell.fill = warn_fill
            widths = [8, 50, 26, 14, 14, 14, 26, 14, 14, 14, 16, 16, 14, 10, 10]
            for ci, w in enumerate(widths, 1):
                ws_detail.column_dimensions[get_column_letter(ci)].width = w
            ws_detail.freeze_panes = "A2"

        _write_detail_sheet("本地边界结果", stats_local, 1)
        _write_detail_sheet("云端边界结果", stats_cloud, 2)

        # Sheet4：端云边界误差（云端与本地的差异）
        ws_diff = wb.create_sheet("端云边界误差", 3)
        diff_headers = [
            "序号",
            "音频路径",
            "本地 Start(ms)",
            "云端 Start(ms)",
            "差值 (cloud-local,ms)",
            "本地 End(ms)",
            "云端 End(ms)",
            "差值 (cloud-local,ms)",
        ]
        _write_header(ws_diff, 1, diff_headers)

        # 基于“参考段顺序”的 aligned_rows 对齐，未匹配写入 "unknow"
        n_diff = max(len(stats_local.aligned_rows), len(stats_cloud.aligned_rows))
        for i in range(n_diff):
            al = stats_local.aligned_rows[i] if i < len(stats_local.aligned_rows) else None
            ac = stats_cloud.aligned_rows[i] if i < len(stats_cloud.aligned_rows) else None
            if al is not None:
                audio_path, ref_s, ref_e, lh_s, lh_e, _, _ = al
            elif ac is not None:
                audio_path, ref_s, ref_e, lh_s, lh_e, _, _ = ac[0], ac[1], ac[2], None, None, "", None
            else:
                continue
            ch_s = ac[3] if ac is not None else None
            ch_e = ac[4] if ac is not None else None

            def _fmt_ms(v):
                return v * 1000 if isinstance(v, (int, float)) else "unknow"
            def _diff_ms(a, b):
                return abs((b - a) * 1000) if isinstance(a, (int, float)) and isinstance(b, (int, float)) else "unknow"

            row_vals = [
                i + 1,
                audio_path,
                _fmt_ms(lh_s),
                _fmt_ms(ch_s),
                _diff_ms(lh_s, ch_s),
                _fmt_ms(lh_e),
                _fmt_ms(ch_e),
                _diff_ms(lh_e, ch_e),
            ]
            for col, v in enumerate(row_vals, 1):
                cell = ws_diff.cell(row=i + 2, column=col, value=v)
                cell.alignment = left_align if col == 2 else center_align

        for ci, w in enumerate([8, 50, 14, 14, 16, 16, 20, 16, 16, 20], 1):
            ws_diff.column_dimensions[get_column_letter(ci)].width = w
        ws_diff.freeze_panes = "A2"

        parent = os.path.dirname(output_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        wb.save(output_path)
        logger.info(f"Excel 报告已生成: {output_path}")

    # ── Summary 文本 ──────────────────────────────────────────────────────────

    def _generate_summary(self, stats: TimeBoundaryStats, output_path: str, result_type: Optional[str] = None) -> str:
        ds = _compute_delta_stats(stats)
        title = (
            "TIME_BOUNDARY_ACCURACY"
            if not result_type
            else f"TIME_BOUNDARY_ACCURACY[{result_type}]"
        )
        content_lines = [
            f"*  总样本数:       {ds['count']}  |  Ref 段总数: {stats.total_ref}  |  Result 段总数: {stats.total_result}",
            "",
            f"*  起点误差 ΔStart: 平均 {ds['start']['avg']:6.2f} ms  |  最大 {ds['start']['max']:6.2f} ms  |  最小 {ds['start']['min']:6.2f} ms",
            f"*  终点误差 ΔEnd:   平均 {ds['end']['avg']:6.2f} ms  |  最大 {ds['end']['max']:6.2f} ms  |  最小 {ds['end']['min']:6.2f} ms",
            "",
            f"*  详细报告: {output_path}",
        ]
        return self.format_summary_box(title, "\n".join(content_lines), width=90)


def main() -> None:
    """
    命令行入口函数

    使用示例:
        python3 -m src.testsuite.NANO.tools.tsr.time_boundary_accuracy -r result.txt -ref ref.txt
        python3 -m src.testsuite.NANO.tools.tsr.time_boundary_accuracy -r result.txt -ref ref.txt -o report.xlsx -t 0.3
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="时间边界误差统计工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 %(prog)s -r result.txt -ref ref.txt
  python3 %(prog)s -r result.txt -ref ref.txt -o report.xlsx -t 0.3 --rtype ASRResult

输入文件格式（ref/result 相同格式，空格分隔，无表头）：
  音频路径  00h_S  开始时间(s)  结束时间(s)

输出:
  - 终端打印 Summary 统计报告
  - 生成 Excel 详细报告（概要 / 配对明细 / 按音频统计）
  - 生成同路径下的 HTML 报告
        """,
    )

    parser.add_argument("-r", "--result", required=True, help="结果文件路径")
    parser.add_argument("-ref", "--reference", required=True, help="参考文件路径")
    parser.add_argument("-o", "--output", default=None, help="Excel 报告输出路径")
    parser.add_argument(
        "-t",
        "--threshold",
        type=float,
        default=0.3,
        help="命中阈值（秒），默认 0.3",
    )
    parser.add_argument(
        "--rtype",
        dest="rtype",
        default=None,
        help="结果类型（用于 JSONL 日志解析过滤），如 ASRResult/localASRResult/cloudASRResult",
    )

    args = parser.parse_args()

    params = [
        f"result={args.result}",
        f"ref={args.reference}",
        f"threshold={args.threshold}",
    ]
    if args.rtype:
        params.append(f"type={args.rtype}")
    if args.output:
        params.append(f"output={args.output}")

    handler = TimeBoundaryAccuracyHandler(config=None)
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


if __name__ == "__main__":
    main()

