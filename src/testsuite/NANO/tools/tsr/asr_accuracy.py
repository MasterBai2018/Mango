#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2025/02/02
# @Author  : huidong.bai
# @File    : asr_accuracy.py
# @Software: PyCharm
# @Mail    : MasterBai2018@outlook.com
"""
ASR_ACCURACY 指令实现

用于计算 ASR 识别准确率，支持：
- 字准率 (Character Accuracy Rate)
- 句准率 (Sentence Accuracy Rate)
- 插入率 (Insertion Rate)
- 删除率 (Deletion Rate)
- 替换率 (Substitution Rate)
- 空结果率 (Empty Result Rate)

使用示例:
    [TSR]ASR_ACCURACY result=asr.csv ref=ref.csv [output=report.xlsx]
"""
import os
import sys
import re
import csv
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from loguru import logger

# 支持独立运行和作为模块导入两种方式
try:
    from . import register_tsr_command
    from .base import (
        BaseTSRHandler, 
        ASRComparisonResult, 
        EditDistance,
        calculate_edit_distance
    )
except ImportError:
    # 独立运行时，添加项目根目录到 sys.path
    _current_dir = os.path.dirname(os.path.abspath(__file__))
    _project_root = os.path.abspath(os.path.join(_current_dir, '..', '..', '..', '..', '..'))
    if _project_root not in sys.path:
        sys.path.insert(0, _project_root)
    
    from src.testsuite.NANO.tools.tsr import register_tsr_command
    from src.testsuite.NANO.tools.tsr.base import (
        BaseTSRHandler, 
        ASRComparisonResult, 
        EditDistance,
        calculate_edit_distance
    )

# ASR 最终结果类型（过滤中间结果 *Temp）
ASR_RESULT_TYPES = [
    "ASRResult",
    "cloudASRResult", 
    "localASRResult",
    "SpeechASRResult",
    "PSTTASRResult",
    "TiTanASRResult"
]


@dataclass
class ASRAccuracyStats:
    """ASR 准确率统计结果"""
    total_count: int = 0                # 总数
    correct_count: int = 0              # 正确数
    error_count: int = 0                # 错误数
    empty_count: int = 0                # 空结果数
    missing_count: int = 0              # 参考文件中有但结果中没有的数量
    
    total_ref_chars: int = 0            # 参考文本总字符数
    total_hyp_chars: int = 0            # 识别文本总字符数
    total_substitutions: int = 0        # 总替换数
    total_insertions: int = 0           # 总插入数
    total_deletions: int = 0            # 总删除数
    
    results: List[ASRComparisonResult] = field(default_factory=list)
    
    @property
    def sentence_accuracy(self) -> float:
        """句准率"""
        if self.total_count == 0:
            return 0.0
        return self.correct_count / self.total_count
    
    @property
    def character_accuracy(self) -> float:
        """字准率"""
        if self.total_ref_chars == 0:
            return 0.0
        errors = self.total_substitutions + self.total_insertions + self.total_deletions
        return max(0.0, 1.0 - errors / self.total_ref_chars)
    
    @property
    def insertion_rate(self) -> float:
        """插入率"""
        if self.total_ref_chars == 0:
            return 0.0
        return self.total_insertions / self.total_ref_chars
    
    @property
    def deletion_rate(self) -> float:
        """删除率"""
        if self.total_ref_chars == 0:
            return 0.0
        return self.total_deletions / self.total_ref_chars
    
    @property
    def substitution_rate(self) -> float:
        """替换率"""
        if self.total_ref_chars == 0:
            return 0.0
        return self.total_substitutions / self.total_ref_chars
    
    @property
    def empty_rate(self) -> float:
        """空结果率"""
        if self.total_count == 0:
            return 0.0
        return self.empty_count / self.total_count


@register_tsr_command("ASR_ACCURACY")
class ASRAccuracyHandler(BaseTSRHandler):
    """
    ASR 准确率计算处理器
    
    指令格式:
        [TSR]ASR_ACCURACY result=<result_csv> ref=<ref_csv> [output=<report_xlsx>]
    
    参数说明:
        result: 识别结果 CSV 文件路径（必需）
        ref: 参考答案 CSV 文件路径（必需）
        output: Excel 报告输出路径（可选，默认在 suite_dir 下生成）
    """
    
    COMMAND_NAME = "ASR_ACCURACY"
    
    def execute(self, params: list, output_report: str = None) -> str:
        """
        执行 ASR 准确率计算

        Args:
            params: 参数列表，格式为 ["result=xxx.csv", "ref=xxx.csv", "output=xxx.xlsx"]
            output_report: 报告输出路径（可选，会被 params 中的 output 覆盖）

        Returns:
            str: Summary 报告字符串
        """
        result_file, ref_file, xlsx_path, output_was_specified = self._parse_params(
            params, output_report
        )

        if not os.path.exists(result_file):
            raise FileNotFoundError(f"识别结果文件不存在: {result_file}")
        if not os.path.exists(ref_file):
            raise FileNotFoundError(f"参考答案文件不存在: {ref_file}")

        result_data = self._load_result_csv(result_file)
        ref_data    = self._load_ref_csv(ref_file)
        stats       = self._calculate_accuracy(result_data, ref_data)

        # 生成 Excel 报告
        self._generate_excel_report(stats, xlsx_path)

        # 生成 HTML 报告（allure_result/mango_report/{define}/{suite}/）
        html_content  = self._build_accuracy_html(stats)
        html_filename = "asr_accuracy.html"
        html_content_built = self._build_accuracy_html(stats)
        self.save_html_report(html_content_built, html_filename, "ASR 准确率报告", "asr_accuracy")

        # 本地副本（与 xlsx 同目录，仅扩展名不同）
        local_html = os.path.splitext(xlsx_path)[0] + '.html'
        os.makedirs(os.path.dirname(local_html), exist_ok=True)
        with open(local_html, 'w', encoding='utf-8') as f:
            f.write(html_content_built)
        logger.info(f"本地 HTML 报告已生成: {local_html}")

        return self._generate_summary(stats, xlsx_path)

    def _parse_params(self, params: list, default_output: str = None) -> Tuple[str, str, str, bool]:
        """
        解析参数

        Returns:
            Tuple[result_file, ref_file, xlsx_path, output_was_specified]
        """
        result_file = None
        ref_file    = None
        output_path = default_output

        for param in params:
            if   param.startswith("result="):
                result_file = param[7:]
            elif param.startswith("ref="):
                ref_file = param[4:]
            elif param.startswith("output="):
                output_path = param[7:]

        if not result_file:
            raise ValueError("缺少必需参数: result=<result_csv>")
        if not ref_file:
            raise ValueError("缺少必需参数: ref=<ref_csv>")

        output_was_specified = output_path is not None
        if not output_path:
            suite_mango_dir = self._get_suite_mango_dir()
            output_path     = os.path.join(suite_mango_dir, "asr_accuracy.xlsx")

        return result_file, ref_file, output_path, output_was_specified

    # ── HTML report ──

    def generate_html_report(self, *args, **kwargs) -> Optional[str]:
        """实现抽象方法：generate_html_report(stats) → Optional[str]"""
        stats = args[0] if args else kwargs.get('stats')
        if stats is None:
            return None
        html = self._build_accuracy_html(stats)
        return self.save_html_report(html, "asr_accuracy.html", "ASR 准确率报告", "asr_accuracy")

    def _build_accuracy_html(self, stats: 'ASRAccuracyStats') -> str:
        """根据 ASRAccuracyStats 构建自包含 HTML"""
        total_errors  = stats.total_substitutions + stats.total_insertions + stats.total_deletions
        correct_chars = stats.total_ref_chars - total_errors

        # ── 汇总卡片 ────────────────────────────────────────────────────────
        def pct_card(value: float, label: str, css: str = '') -> str:
            color_cls = 'card-success' if value >= 0.9 else ('card-warning' if value >= 0.7 else 'card-failure')
            return (f'<div class="card {color_cls} {css}">'
                    f'<div class="card-value">{value * 100:.2f}%</div>'
                    f'<div class="card-label">{label}</div></div>')

        cards_html = (
            '<div class="summary-cards">'
            f'<div class="card"><div class="card-value">{stats.total_count}</div>'
            f'<div class="card-label">总数</div></div>'
            f'<div class="card card-success"><div class="card-value">{stats.correct_count}</div>'
            f'<div class="card-label">正确数</div></div>'
            f'<div class="card card-failure"><div class="card-value">{stats.error_count}</div>'
            f'<div class="card-label">错误数</div></div>'
            f'<div class="card card-warning"><div class="card-value">{stats.empty_count}</div>'
            f'<div class="card-label">空结果数</div></div>'
            + pct_card(stats.sentence_accuracy, '句准率')
            + pct_card(stats.character_accuracy, '字准率')
            + pct_card(stats.empty_rate, '空结果率', 'card-warning')
            + '</div>'
        )

        # ── 内嵌 Tab ─────────────────────────────────────────────────────────
        # Tab1: 详细结果
        detail_rows = ''.join(
            f'<tr><td>{i}</td>'
            f'<td>{os.path.basename(r.audio_path)}</td>'
            f'<td>{r.reference}</td>'
            f'<td>{r.hypothesis}</td>'
            f'<td><span class="tag-{"pass" if r.is_correct else ("warn" if r.is_empty else "fail")}">'
            f'{r.status}</span></td>'
            f'<td>{r.confidence:.0f}</td>'
            f'<td>{r.edit_distance.distance}</td>'
            f'<td>{r.edit_distance.accuracy * 100:.2f}%</td></tr>'
            for i, r in enumerate(stats.results, 1)
        )
        tab1_html = (
            '<table class="report-table"><thead>'
            '<tr><th>#</th><th>音频</th><th>参考文本</th><th>识别结果</th>'
            '<th>状态</th><th>置信度</th><th>编辑距离</th><th>字准率</th></tr>'
            f'</thead><tbody>{detail_rows}</tbody></table>'
        )

        # Tab2: 错误详情
        error_rows = ''.join(
            f'<tr><td>{i}</td>'
            f'<td>{os.path.basename(r.audio_path)}</td>'
            f'<td>{r.reference}</td>'
            f'<td>{r.hypothesis or "(空)"}</td>'
            f'<td><span class="tag-fail">{"空结果" if r.is_empty else "识别错误"}</span></td>'
            f'<td>{r.edit_distance.distance}</td></tr>'
            for i, r in enumerate((x for x in stats.results if not x.is_correct), 1)
        )
        tab2_html = (
            '<table class="report-table"><thead>'
            '<tr><th>#</th><th>音频</th><th>参考文本</th><th>识别结果</th>'
            '<th>错误类型</th><th>编辑距离</th></tr>'
            f'</thead><tbody>{error_rows}</tbody></table>'
        )

        section_html = (
            '<div class="section">'
            '<div class="section-header">📋 识别对比明细</div>'
            '<div class="section-body">'
            '<div class="inner-tabs">'
            '<div class="inner-tab active" onclick="switchTab(this,\'ac1\')">详细结果</div>'
            '<div class="inner-tab" onclick="switchTab(this,\'ac2\')">错误详情</div>'
            '</div>'
            f'<div id="ac1" class="inner-pane active">{tab1_html}</div>'
            f'<div id="ac2" class="inner-pane">{tab2_html}</div>'
            '</div></div>'
        )

        return self.build_html_page("ASR 准确率报告", cards_html + section_html)
    
    def _detect_delimiter(self, filepath: str) -> str:
        """
        检测 CSV 文件的分隔符
        
        Args:
            filepath: CSV 文件路径
        
        Returns:
            str: 分隔符字符
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            first_line = f.readline()
            
            # 统计各分隔符出现次数
            tab_count = first_line.count('\t')
            comma_count = first_line.count(',')
            
            # 选择出现次数更多的作为分隔符
            if tab_count > comma_count:
                return '\t'
            elif comma_count > 0:
                return ','
            else:
                # 默认使用 Tab
                return '\t'
    
    def _load_result_csv(self, filepath: str) -> Dict[str, Tuple[str, float]]:
        """
        加载识别结果 CSV 文件
        
        只保留最终结果（*ASRResult），过滤中间结果（*ASRResultTemp）
        
        Args:
            filepath: CSV 文件路径
        
        Returns:
            Dict[audio_path, (result_text, confidence)]
        """
        result_data = {}
        
        # 检测分隔符
        delimiter = self._detect_delimiter(filepath)
        
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            
            for row in reader:
                # 获取类型字段
                result_type = row.get('type', '')
                
                # 只保留最终结果（匹配 *ASRResult，但不匹配 *ASRResultTemp）
                if not self._is_final_asr_result(result_type):
                    continue
                
                audio_path = row.get('voice', '').strip()
                result_text = row.get('result', '').strip()
                confidence = float(row.get('confidence', 0) or 0)
                
                if audio_path:
                    # 如果同一音频有多条最终结果，保留最后一条
                    result_data[audio_path] = (result_text, confidence)
        
        return result_data
    
    def _is_final_asr_result(self, result_type: str) -> bool:
        """
        判断是否为最终 ASR 结果（过滤中间结果）
        
        匹配规则: 以 ASRResult 结尾，但不以 ASRResultTemp 结尾
        
        Args:
            result_type: 结果类型字符串
        
        Returns:
            bool: 是否为最终结果
        """
        if not result_type:
            return False
        
        # 排除中间结果（*Temp）
        if result_type.endswith('Temp'):
            return False
        
        # 匹配最终结果（*ASRResult）
        return result_type.endswith('ASRResult')
    
    def _load_ref_csv(self, filepath: str) -> Dict[str, str]:
        """
        加载参考答案 CSV 文件
        
        Args:
            filepath: CSV 文件路径
        
        Returns:
            Dict[audio_path, reference_text]
        """
        ref_data = {}
        
        # 检测分隔符
        delimiter = self._detect_delimiter(filepath)
        
        with open(filepath, 'r', encoding='utf-8') as f:
            # 过滤空行和以 @ 开头的行（元数据行）
            lines = []
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith('@') or stripped.startswith('#') or stripped.startswith('//'):
                    continue
                lines.append(line)
            
            if not lines:
                raise ValueError(f"参考答案文件为空或没有有效数据行")
            
            # 使用过滤后的行创建 DictReader
            import io
            filtered_content = io.StringIO(''.join(lines))
            reader = csv.DictReader(filtered_content, delimiter=delimiter)
            
            # 获取字段名（支持多种命名）
            fieldnames = reader.fieldnames
            
            # 音频路径字段（优先级：AUDIOPATH > voice > audio）
            audio_field = None
            for field in ['AUDIOPATH', 'audiopath', 'voice', 'audio', 'wav', 'path']:
                if field in fieldnames:
                    audio_field = field
                    break
            
            # 文本字段（优先级：TEXT > text > ref > reference）
            text_field = None
            for field in ['TEXT', 'text', 'ref', 'reference', 'answer']:
                if field in fieldnames:
                    text_field = field
                    break
            
            if not audio_field or not text_field:
                raise ValueError(f"参考答案文件格式错误，需要包含音频路径和文本字段。当前字段: {fieldnames}")
            
            for row in reader:
                try:
                    audio_path = row.get(audio_field, '').strip()
                    ref_text = row.get(text_field, '').strip()
                except Exception as e:
                    logger.error(f"参考答案文件格式错误，跳过：{row}")
                    continue

                if audio_path:
                    ref_data[audio_path] = ref_text
        
        return ref_data
    
    def _normalize_text(self, text: str) -> str:
        """
        标准化文本用于比较
        
        - 去除前后空格
        - 转换为小写
        
        Args:
            text: 原始文本
        
        Returns:
            str: 标准化后的文本
        """
        return text.strip().lower()
    
    def _calculate_accuracy(self, result_data: Dict[str, Tuple[str, float]], 
                           ref_data: Dict[str, str]) -> ASRAccuracyStats:
        """
        计算 ASR 准确率
        
        比较时忽略大小写和前后空格
        
        Args:
            result_data: 识别结果 {audio_path: (text, confidence)}
            ref_data: 参考答案 {audio_path: text}
        
        Returns:
            ASRAccuracyStats: 统计结果
        """
        stats = ASRAccuracyStats()
        
        # 以参考答案为基准进行比对
        for audio_path, ref_text_raw in ref_data.items():
            # 标准化参考文本
            ref_text = self._normalize_text(ref_text_raw)
            
            stats.total_count += 1
            stats.total_ref_chars += len(ref_text)
            
            # 查找对应的识别结果
            if audio_path not in result_data:
                # 参考文件中有但结果中没有
                stats.missing_count += 1
                stats.empty_count += 1
                
                # 创建空结果的对比记录
                edit_dist = calculate_edit_distance(ref_text, "")
                stats.total_deletions += edit_dist.deletions
                
                result = ASRComparisonResult(
                    audio_path=audio_path,
                    reference=ref_text,
                    hypothesis="",
                    is_correct=False,
                    is_empty=True,
                    edit_distance=edit_dist,
                    confidence=0.0
                )
                stats.results.append(result)
                continue
            
            hyp_text_raw, confidence = result_data[audio_path]
            # 标准化识别文本
            hyp_text = self._normalize_text(hyp_text_raw)
            
            stats.total_hyp_chars += len(hyp_text)
            
            # 判断是否为空结果
            is_empty = len(hyp_text) == 0
            if is_empty:
                stats.empty_count += 1
            
            # 计算编辑距离（使用标准化后的文本）
            edit_dist = calculate_edit_distance(ref_text, hyp_text)
            
            # 累计统计
            stats.total_substitutions += edit_dist.substitutions
            stats.total_insertions += edit_dist.insertions
            stats.total_deletions += edit_dist.deletions
            
            # 判断是否完全正确（使用标准化后的文本比较）
            is_correct = (ref_text == hyp_text)
            if is_correct:
                stats.correct_count += 1
            else:
                stats.error_count += 1
            
            # 创建对比记录（保存标准化后的文本，便于查看）
            result = ASRComparisonResult(
                audio_path=audio_path,
                reference=ref_text,
                hypothesis=hyp_text,
                is_correct=is_correct,
                is_empty=is_empty,
                edit_distance=edit_dist,
                confidence=confidence
            )
            stats.results.append(result)
        
        return stats
    
    def _generate_excel_report(self, stats: ASRAccuracyStats, output_path: str):
        """
        生成 Excel 详细报告
        
        Args:
            stats: 统计结果
            output_path: 输出路径
        """
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
            from openpyxl.utils import get_column_letter
        except ImportError:
            logger.warning("openpyxl 未安装，将生成 CSV 格式报告")
            self._generate_csv_report(stats, output_path.replace('.xlsx', '.csv'))
            return
        
        # 创建工作簿
        wb = openpyxl.Workbook()
        
        # ========== Sheet 1: 汇总统计 ==========
        ws_summary = wb.active
        ws_summary.title = "汇总统计"
        
        # 样式定义
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        correct_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
        error_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
        border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        # 汇总数据
        summary_data = [
            ["指标", "数值", "说明"],
            ["总数", stats.total_count, "参考答案总条数"],
            ["正确数", stats.correct_count, "完全匹配的条数"],
            ["错误数", stats.error_count, "不匹配的条数"],
            ["空结果数", stats.empty_count, "识别结果为空的条数"],
            ["缺失数", stats.missing_count, "参考文件中有但识别结果中没有的条数"],
            ["", "", ""],
            ["句准率", f"{stats.sentence_accuracy * 100:.2f}%", "完全匹配的比例"],
            ["字准率", f"{stats.character_accuracy * 100:.2f}%", "字符级准确率 (1 - CER)"],
            ["插入率", f"{stats.insertion_rate * 100:.2f}%", "插入错误占参考文本的比例"],
            ["删除率", f"{stats.deletion_rate * 100:.2f}%", "删除错误占参考文本的比例"],
            ["替换率", f"{stats.substitution_rate * 100:.2f}%", "替换错误占参考文本的比例"],
            ["空结果率", f"{stats.empty_rate * 100:.2f}%", "空结果占总数的比例"],
            ["", "", ""],
            ["参考文本总字数", stats.total_ref_chars, "所有参考文本的字符总数"],
            ["识别文本总字数", stats.total_hyp_chars, "所有识别结果的字符总数"],
            ["总替换数", stats.total_substitutions, "所有替换操作的次数"],
            ["总插入数", stats.total_insertions, "所有插入操作的次数"],
            ["总删除数", stats.total_deletions, "所有删除操作的次数"],
        ]
        
        for row_idx, row_data in enumerate(summary_data, 1):
            for col_idx, value in enumerate(row_data, 1):
                cell = ws_summary.cell(row=row_idx, column=col_idx, value=value)
                cell.border = border
                cell.alignment = Alignment(horizontal='center', vertical='center')
                if row_idx == 1:
                    cell.font = header_font
                    cell.fill = header_fill
        
        # 调整列宽
        ws_summary.column_dimensions['A'].width = 15
        ws_summary.column_dimensions['B'].width = 20
        ws_summary.column_dimensions['C'].width = 40
        
        # ========== Sheet 2: 详细结果 ==========
        ws_detail = wb.create_sheet(title="详细结果")
        
        detail_headers = ["序号", "音频路径", "参考文本", "识别结果", "状态", "置信度", 
                         "编辑距离", "替换", "插入", "删除", "字准率"]
        
        # 预创建对齐样式（避免重复创建）
        center_align = Alignment(horizontal='center', vertical='center')
        wrap_align = Alignment(horizontal='center', vertical='center', wrap_text=True)
        
        for col_idx, header in enumerate(detail_headers, 1):
            cell = ws_detail.cell(row=1, column=col_idx, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.border = border
            cell.alignment = center_align
        
        # 批量准备数据
        detail_rows = []
        for idx, result in enumerate(stats.results):
            detail_rows.append((
                idx + 1,
                os.path.basename(result.audio_path),
                result.reference,
                result.hypothesis,
                result.status,
                f"{result.confidence:.0f}",
                result.edit_distance.distance,
                result.edit_distance.substitutions,
                result.edit_distance.insertions,
                result.edit_distance.deletions,
                f"{result.edit_distance.accuracy * 100:.2f}%",
                result.is_correct
            ))
        
        # 批量写入
        for row_idx, row_data in enumerate(detail_rows, 2):
            is_correct = row_data[-1]
            for col_idx, value in enumerate(row_data[:-1], 1):
                cell = ws_detail.cell(row=row_idx, column=col_idx, value=value)
                cell.border = border
                cell.alignment = wrap_align
                
                # 状态列着色
                if col_idx == 5:
                    cell.fill = correct_fill if is_correct else error_fill
        
        # 调整列宽
        column_widths = [8, 50, 30, 30, 10, 10, 10, 8, 8, 8, 10]
        for col_idx, width in enumerate(column_widths, 1):
            ws_detail.column_dimensions[get_column_letter(col_idx)].width = width
        
        # ========== Sheet 3: 错误详情 ==========
        ws_errors = wb.create_sheet(title="错误详情")
        
        error_headers = ["序号", "音频路径", "参考文本", "识别结果", "错误类型", "编辑距离"]
        
        for col_idx, header in enumerate(error_headers, 1):
            cell = ws_errors.cell(row=1, column=col_idx, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.border = border
            cell.alignment = Alignment(horizontal='center', vertical='center')
        
        error_row = 2
        for result in stats.results:
            if result.is_correct:
                continue
            
            error_type = "空结果" if result.is_empty else "识别错误"
            row_data = [
                error_row - 1,
                os.path.basename(result.audio_path),
                result.reference,
                result.hypothesis,
                error_type,
                result.edit_distance.distance
            ]
            
            for col_idx, value in enumerate(row_data, 1):
                cell = ws_errors.cell(row=error_row, column=col_idx, value=value)
                cell.border = border
                cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
                cell.fill = error_fill
            
            error_row += 1
        
        # 调整列宽
        error_widths = [8, 50, 30, 30, 15, 10]
        for col_idx, width in enumerate(error_widths, 1):
            ws_errors.column_dimensions[get_column_letter(col_idx)].width = width
        
        # 保存文件（dirname 为空时使用当前目录）
        parent = os.path.dirname(output_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        wb.save(output_path)

    def _generate_csv_report(self, stats: ASRAccuracyStats, output_path: str):
        """
        生成 CSV 格式报告（openpyxl 不可用时的备选方案）
        
        Args:
            stats: 统计结果
            output_path: 输出路径
        """
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            
            # 写入汇总
            writer.writerow(["=== 汇总统计 ==="])
            writer.writerow(["总数", stats.total_count])
            writer.writerow(["正确数", stats.correct_count])
            writer.writerow(["错误数", stats.error_count])
            writer.writerow(["空结果数", stats.empty_count])
            writer.writerow(["句准率", f"{stats.sentence_accuracy * 100:.2f}%"])
            writer.writerow(["字准率", f"{stats.character_accuracy * 100:.2f}%"])
            writer.writerow(["插入率", f"{stats.insertion_rate * 100:.2f}%"])
            writer.writerow(["删除率", f"{stats.deletion_rate * 100:.2f}%"])
            writer.writerow(["空结果率", f"{stats.empty_rate * 100:.2f}%"])
            writer.writerow([])
            
            # 写入详情
            writer.writerow(["=== 详细结果 ==="])
            writer.writerow(["音频路径", "参考文本", "识别结果", "状态", "编辑距离", "字准率"])
            
            for result in stats.results:
                writer.writerow([
                    result.audio_path,
                    result.reference,
                    result.hypothesis,
                    result.status,
                    result.edit_distance.distance,
                    f"{result.edit_distance.accuracy * 100:.2f}%"
                ])
        
        logger.info(f"CSV 报告已生成: {output_path}")
    
    def _generate_summary(self, stats: ASRAccuracyStats, output_path: str) -> str:
        """
        生成终端输出的 Summary 报告
        
        Args:
            stats: 统计结果
            output_path: 报告文件路径
        
        Returns:
            str: Summary 字符串
        """
        # 计算字准率的分子（正确字符数 = 参考总字数 - 错误数）
        total_errors = stats.total_substitutions + stats.total_insertions + stats.total_deletions
        correct_chars = stats.total_ref_chars - total_errors
        
        content_lines = [
            f"*  总数: {stats.total_count}  |  正确: {stats.correct_count}  |  错误: {stats.error_count}  |  空结果: {stats.empty_count}",
            f"*  句准率:    {stats.sentence_accuracy * 100:6.2f}% ({stats.correct_count}/{stats.total_count})\t(完全匹配的比例)",
            f"*  字准率:    {stats.character_accuracy * 100:6.2f}% ({correct_chars}/{stats.total_ref_chars})\t(字符级准确率)",
            f"*  插入率:    {stats.insertion_rate * 100:6.2f}% ({stats.total_insertions}/{stats.total_ref_chars})\t(插入错误比例)",
            f"*  删除率:    {stats.deletion_rate * 100:6.2f}% ({stats.total_deletions}/{stats.total_ref_chars})\t(删除错误比例)",
            f"*  替换率:    {stats.substitution_rate * 100:6.2f}% ({stats.total_substitutions}/{stats.total_ref_chars})\t(替换错误比例)",
            f"*  空结果率:  {stats.empty_rate * 100:6.2f}% ({stats.empty_count}/{stats.total_count})\t(空结果比例)",
            f"*  详细报告: {output_path}"
        ]
        content = "\n".join(content_lines)
        
        return self.format_summary_box("ASR_ACCURACY", content, width=90)


def main():
    """
    命令行入口函数
    
    使用示例:
        python3 -m src.testsuite.NANO.tools.tsr.asr_accuracy -r asr.csv -ref ref.csv -o report.xlsx
        python3 src/testsuite/NANO/tools/tsr/asr_accuracy.py -r asr.csv -ref ref.csv
    """
    import argparse
    
    parser = argparse.ArgumentParser(
        description='ASR 准确率计算工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python3 %(prog)s -r result.csv -ref reference.csv
  python3 %(prog)s -r result.csv -ref reference.csv -o report.xlsx

输入文件格式:
  result.csv: 识别结果文件，需包含 voice, result, type 字段
              type 字段用于过滤最终结果（*ASRResult，不含 *ASRResultTemp）
  
  reference.csv: 参考答案文件，需包含音频路径和文本字段
                 支持字段名: AUDIOPATH/voice/audio + TEXT/text/ref

输出:
  - 终端打印 Summary 统计报告
  - 生成 Excel 详细报告（包含汇总统计、详细结果、错误详情三个 Sheet）
        '''
    )
    
    parser.add_argument('-r', '--result', required=True, 
                        help='识别结果 CSV 文件路径')
    parser.add_argument('-ref', '--reference', required=True, 
                        help='参考答案 CSV 文件路径')
    parser.add_argument('-o', '--output', default=None, 
                        help='Excel 报告输出路径（默认: 当前目录/asr_accuracy.xlsx）')
    
    args = parser.parse_args()
    
    # -o 未传时不带 output= 参数，execute 自动落到 cwd/mango_report/
    params = [
        f"result={args.result}",
        f"ref={args.reference}",
    ]
    if args.output:
        params.append(f"output={args.output}")

    handler = ASRAccuracyHandler(config=None)

    try:
        summary = handler.execute(params)
        print(summary)
    except FileNotFoundError as e:
        print(f"❌ 错误: {e}")
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
