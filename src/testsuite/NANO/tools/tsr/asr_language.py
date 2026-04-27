#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2025/02/02
# @Author  : huidong.bai
# @File    : asr_language.py
# @Software: PyCharm
# @Mail    : MasterBai2018@outlook.com
"""
ASR_LANGUAGE 指令实现

用于计算 ASR 识别结果中语种识别的正确率。

使用示例:
    [TSR]ASR_LANGUAGE result=asr.csv ref=cmn [output=report.xlsx]
"""
import os
import sys
import csv
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from loguru import logger

# 支持独立运行和作为模块导入两种方式
try:
    from . import register_tsr_command
    from .base import BaseTSRHandler
except ImportError:
    # 独立运行时，添加项目根目录到 sys.path
    _current_dir = os.path.dirname(os.path.abspath(__file__))
    _project_root = os.path.abspath(os.path.join(_current_dir, '..', '..', '..', '..', '..'))
    if _project_root not in sys.path:
        sys.path.insert(0, _project_root)
    
    from src.testsuite.NANO.tools.tsr import register_tsr_command
    from src.testsuite.NANO.tools.tsr.base import BaseTSRHandler


@dataclass
class LanguageResult:
    """单条语种识别结果"""
    audio_path: str         # 音频路径
    detected_lang: str      # 检测到的语种（原始值）
    normalized_lang: str    # 标准化后的语种
    expected_lang: str      # 期望的语种
    is_correct: bool        # 是否正确
    confidence: float = 0.0 # 置信度


@dataclass
class LanguageStats:
    """语种识别统计结果"""
    total_count: int = 0            # 总数
    correct_count: int = 0          # 正确数
    error_count: int = 0            # 错误数
    empty_count: int = 0            # 空结果数（无语种信息）
    
    # 按语种分类统计
    lang_distribution: Dict[str, int] = field(default_factory=dict)
    
    results: List[LanguageResult] = field(default_factory=list)
    
    @property
    def accuracy(self) -> float:
        """语种识别准确率"""
        if self.total_count == 0:
            return 0.0
        return self.correct_count / self.total_count
    
    @property
    def empty_rate(self) -> float:
        """空结果率"""
        if self.total_count == 0:
            return 0.0
        return self.empty_count / self.total_count


@register_tsr_command("ASR_LANGUAGE")
class ASRLanguageHandler(BaseTSRHandler):
    """
    ASR 语种识别正确率计算处理器
    
    指令格式:
        [TSR]ASR_LANGUAGE result=<result_csv> ref=<expected_lang> [output=<report_xlsx>]
    
    参数说明:
        result: 识别结果 CSV 文件路径（必需）
        ref: 期望的语种代码（必需），如 cmn, en, yue 等
        output: Excel 报告输出路径（可选，默认在 suite_dir 下生成）
    
    语种匹配规则:
        - zh-cmn 和 cmn 都视为 cmn
        - zh-yue 和 yue 都视为 yue
        - 不区分大小写
    """
    
    COMMAND_NAME = "ASR_LANGUAGE"
    
    def execute(self, params: list, output_report: str = None) -> str:
        """
        执行语种识别正确率计算

        Args:
            params: 参数列表，格式为 ["result=xxx.csv", "ref=cmn", "output=xxx.xlsx"]
            output_report: 报告输出路径（可选，会被 params 中的 output 覆盖）

        Returns:
            str: Summary 报告字符串
        """
        result_file, expected_lang, xlsx_path, output_was_specified = self._parse_params(
            params, output_report
        )

        if not os.path.exists(result_file):
            raise FileNotFoundError(f"识别结果文件不存在: {result_file}")

        logger.info(f"ASR_LANGUAGE: 开始计算语种识别正确率")
        logger.info(f"  识别结果: {result_file}")
        logger.info(f"  期望语种: {expected_lang}")
        logger.info(f"  输出报告: {xlsx_path}")

        stats = self._calculate_language_accuracy(result_file, expected_lang)

        logger.info(f"  总数: {stats.total_count}, 正确: {stats.correct_count}, 错误: {stats.error_count}")

        # 生成 Excel 报告
        self._generate_excel_report(stats, expected_lang, xlsx_path)

        # 生成 HTML 报告（allure_result/mango_report/{define}/{suite}/）
        html_content = self._build_language_html(stats, expected_lang)
        self.save_html_report(html_content, "asr_language.html", "ASR 语种识别报告", "asr_language")

        # 本地副本（与 xlsx 同目录）
        local_html = os.path.splitext(xlsx_path)[0] + '.html'
        parent = os.path.dirname(local_html)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(local_html, 'w', encoding='utf-8') as f:
            f.write(html_content)
        logger.info(f"本地 HTML 报告已生成: {local_html}")

        return self._generate_summary(stats, expected_lang, xlsx_path)

    def _parse_params(self, params: list, default_output: str = None) -> Tuple[str, str, str, bool]:
        """
        解析参数

        Returns:
            Tuple[result_file, expected_lang, xlsx_path, output_was_specified]
        """
        result_file   = None
        expected_lang = None
        output_path   = default_output

        for param in params:
            if   param.startswith("result="):
                result_file   = param[7:]
            elif param.startswith("ref="):
                expected_lang = param[4:]
            elif param.startswith("output="):
                output_path   = param[7:]

        if not result_file:
            raise ValueError("缺少必需参数: result=<result_csv>")
        if not expected_lang:
            raise ValueError("缺少必需参数: ref=<expected_lang>")

        output_was_specified = output_path is not None
        if not output_path:
            suite_mango_dir = self._get_suite_mango_dir()
            output_path     = os.path.join(suite_mango_dir, "asr_language.xlsx")

        return result_file, expected_lang.lower(), output_path, output_was_specified

    # ── HTML report ──

    def generate_html_report(self, *args, **kwargs) -> Optional[str]:
        """实现抽象方法：generate_html_report(stats, expected_lang) → Optional[str]"""
        stats         = args[0] if args else kwargs.get('stats')
        expected_lang = args[1] if len(args) > 1 else kwargs.get('expected_lang', '')
        if stats is None:
            return None
        html = self._build_language_html(stats, expected_lang)
        return self.save_html_report(html, "asr_language.html", "ASR 语种识别报告", "asr_language")

    def _build_language_html(self, stats: 'LanguageStats', expected_lang: str) -> str:
        """根据 LanguageStats 构建自包含 HTML"""

        # ── 汇总卡片 ────────────────────────────────────────────────────────
        acc_cls = 'card-success' if stats.accuracy >= 0.9 else (
            'card-warning' if stats.accuracy >= 0.7 else 'card-failure')
        cards_html = (
            '<div class="summary-cards">'
            f'<div class="card"><div class="card-value">{expected_lang.upper()}</div>'
            f'<div class="card-label">期望语种</div></div>'
            f'<div class="card"><div class="card-value">{stats.total_count}</div>'
            f'<div class="card-label">总数</div></div>'
            f'<div class="card card-success"><div class="card-value">{stats.correct_count}</div>'
            f'<div class="card-label">正确数</div></div>'
            f'<div class="card card-failure"><div class="card-value">{stats.error_count}</div>'
            f'<div class="card-label">错误数</div></div>'
            f'<div class="card card-warning"><div class="card-value">{stats.empty_count}</div>'
            f'<div class="card-label">空结果数</div></div>'
            f'<div class="card {acc_cls}"><div class="card-value">{stats.accuracy * 100:.2f}%</div>'
            f'<div class="card-label">语种正确率</div></div>'
            f'</div>'
        )

        # ── 语种分布（CSS 进度条）───────────────────────────────────────────
        dist_rows = ''
        for lang, cnt in sorted(stats.lang_distribution.items(), key=lambda x: -x[1]):
            pct = cnt / stats.total_count * 100 if stats.total_count else 0
            is_correct_lang = lang == expected_lang
            bar_cls = 'pbar-pass' if is_correct_lang else 'pbar-fail'
            dist_rows += (
                f'<tr><td>{lang}</td><td>{cnt}</td>'
                f'<td><div class="pbar-wrap">'
                f'<div class="pbar"><div class="pbar-fill {bar_cls}" style="width:{min(pct,100):.1f}%"></div></div>'
                f'{pct:.1f}%</div></td></tr>'
            )
        dist_section = (
            '<div class="section">'
            '<div class="section-header">🌐 语种分布</div>'
            '<div class="section-body">'
            '<table class="report-table"><thead>'
            '<tr><th>语种</th><th>数量</th><th>占比</th></tr>'
            f'</thead><tbody>{dist_rows}</tbody></table>'
            '</div></div>'
        )

        # ── 详细结果 Tab ─────────────────────────────────────────────────────
        detail_rows = ''.join(
            f'<tr><td>{i}</td>'
            f'<td>{os.path.basename(r.audio_path)}</td>'
            f'<td>{r.detected_lang}</td>'
            f'<td>{r.normalized_lang}</td>'
            f'<td>{r.expected_lang.upper()}</td>'
            f'<td><span class="tag-{"pass" if r.is_correct else "fail"}">'
            f'{"正确" if r.is_correct else "错误"}</span></td>'
            f'<td>{r.confidence:.0f}</td></tr>'
            for i, r in enumerate(stats.results, 1)
        )
        detail_table = (
            '<table class="report-table"><thead>'
            '<tr><th>#</th><th>音频</th><th>检测语种</th><th>标准化</th>'
            '<th>期望语种</th><th>状态</th><th>置信度</th></tr>'
            f'</thead><tbody>{detail_rows}</tbody></table>'
        )

        # ── 错误详情 Tab ─────────────────────────────────────────────────────
        error_rows = ''.join(
            f'<tr><td>{i}</td>'
            f'<td>{os.path.basename(r.audio_path)}</td>'
            f'<td>{r.detected_lang or "(空)"}</td>'
            f'<td>{r.expected_lang.upper()}</td></tr>'
            for i, r in enumerate((x for x in stats.results if not x.is_correct), 1)
        )
        error_table = (
            '<table class="report-table"><thead>'
            '<tr><th>#</th><th>音频</th><th>检测语种</th><th>期望语种</th></tr>'
            f'</thead><tbody>{error_rows}</tbody></table>'
        )

        detail_section = (
            '<div class="section">'
            '<div class="section-header">📋 识别明细</div>'
            '<div class="section-body">'
            '<div class="inner-tabs">'
            '<div class="inner-tab active" onclick="switchTab(this,\'lg1\')">详细结果</div>'
            '<div class="inner-tab" onclick="switchTab(this,\'lg2\')">错误详情</div>'
            '</div>'
            f'<div id="lg1" class="inner-pane active">{detail_table}</div>'
            f'<div id="lg2" class="inner-pane">{error_table}</div>'
            '</div></div>'
        )

        return self.build_html_page("ASR 语种识别报告", cards_html + dist_section + detail_section)
    
    # 语种标准化映射配置
    # key: 标准语种代码, value: 该语种的所有别名列表
    LANGUAGE_ALIASES = {
        'cmn': ['cmn', 'zh-cmn', 'mandarin', 'chinese'],
        'yue': ['yue', 'zh-yue', 'cantonese'],
        'eng': ['eng', 'en', 'en-us', 'en-gb', 'en-au', 'english'],
        'jpn': ['jpn', 'ja', 'jp', 'japanese']
    }
    
    # 建立反向索引（类级别缓存，只构建一次）
    _LANG_REVERSE_INDEX = None
    
    @classmethod
    def _get_lang_reverse_index(cls) -> Dict[str, str]:
        """获取语种反向索引（懒加载，O(1)查找）"""
        if cls._LANG_REVERSE_INDEX is None:
            cls._LANG_REVERSE_INDEX = {}
            for standard_code, aliases in cls.LANGUAGE_ALIASES.items():
                for alias in aliases:
                    cls._LANG_REVERSE_INDEX[alias] = standard_code
        return cls._LANG_REVERSE_INDEX
    
    def _normalize_language(self, lang: str) -> str:
        """
        标准化语种代码（O(1) 查找）
        """
        if not lang:
            return ""
        
        lang = lang.strip().lower()
        
        # 使用反向索引直接查找
        reverse_index = self._get_lang_reverse_index()
        return reverse_index.get(lang, lang)
    
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
                return '\t'
    
    def _is_final_asr_result(self, result_type: str) -> bool:
        """
        判断是否为最终 ASR 结果（过滤中间结果）
        
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
    
    def _calculate_language_accuracy(self, result_file: str, expected_lang: str) -> LanguageStats:
        """
        计算语种识别正确率
        
        Args:
            result_file: 识别结果 CSV 文件路径
            expected_lang: 期望的语种（已标准化）
        
        Returns:
            LanguageStats: 统计结果
        """
        stats = LanguageStats()
        
        # 检测分隔符
        delimiter = self._detect_delimiter(result_file)
        
        # 用于去重（同一音频只取最后一条最终结果）
        audio_results: Dict[str, Tuple[str, str, float]] = {}
        
        with open(result_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            
            for row in reader:
                # 只保留最终结果
                result_type = row.get('type', '')
                if not self._is_final_asr_result(result_type):
                    continue
                
                audio_path = row.get('voice', '').strip()
                detected_lang = row.get('lang', '').strip()
                confidence = float(row.get('confidence', 0) or 0)
                
                if audio_path:
                    # 同一音频保留最后一条
                    audio_results[audio_path] = (detected_lang, result_type, confidence)
        
        # 统计结果
        for audio_path, (detected_lang, result_type, confidence) in audio_results.items():
            stats.total_count += 1
            
            # 标准化语种
            normalized_lang = self._normalize_language(detected_lang)
            
            # 统计语种分布
            if normalized_lang:
                stats.lang_distribution[normalized_lang] = stats.lang_distribution.get(normalized_lang, 0) + 1
            else:
                stats.empty_count += 1
                stats.lang_distribution["(空)"] = stats.lang_distribution.get("(空)", 0) + 1
            
            # 判断是否正确
            is_correct = (normalized_lang == expected_lang) if normalized_lang else False
            
            if is_correct:
                stats.correct_count += 1
            else:
                stats.error_count += 1
            
            # 记录详情
            result = LanguageResult(
                audio_path=audio_path,
                detected_lang=detected_lang,
                normalized_lang=normalized_lang,
                expected_lang=expected_lang,
                is_correct=is_correct,
                confidence=confidence
            )
            stats.results.append(result)
        
        return stats
    
    def _generate_excel_report(self, stats: LanguageStats, expected_lang: str, output_path: str):
        """
        生成 Excel 详细报告
        
        Args:
            stats: 统计结果
            expected_lang: 期望语种
            output_path: 输出路径
        """
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
            from openpyxl.utils import get_column_letter
        except ImportError:
            logger.warning("openpyxl 未安装，将生成 CSV 格式报告")
            self._generate_csv_report(stats, expected_lang, output_path.replace('.xlsx', '.csv'))
            return
        
        # 创建工作簿
        wb = openpyxl.Workbook()
        
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
        
        # ========== Sheet 1: 汇总统计 ==========
        ws_summary = wb.active
        ws_summary.title = "汇总统计"
        
        summary_data = [
            ["指标", "数值", "说明"],
            ["期望语种", expected_lang, "测试用例期望的语种"],
            ["总数", stats.total_count, "识别结果总条数"],
            ["正确数", stats.correct_count, "语种识别正确的条数"],
            ["错误数", stats.error_count, "语种识别错误的条数"],
            ["空结果数", stats.empty_count, "无语种信息的条数"],
            ["", "", ""],
            ["语种正确率", f"{stats.accuracy * 100:.2f}%", "语种识别正确的比例"],
            ["空结果率", f"{stats.empty_rate * 100:.2f}%", "无语种信息的比例"],
            ["", "", ""],
            ["=== 语种分布 ===", "", ""],
        ]
        
        # 添加语种分布
        for lang, count in sorted(stats.lang_distribution.items(), key=lambda x: -x[1]):
            percentage = count / stats.total_count * 100 if stats.total_count > 0 else 0
            summary_data.append([lang, count, f"{percentage:.2f}%"])
        
        for row_idx, row_data in enumerate(summary_data, 1):
            for col_idx, value in enumerate(row_data, 1):
                cell = ws_summary.cell(row=row_idx, column=col_idx, value=value)
                cell.border = border
                cell.alignment = Alignment(horizontal='center', vertical='center')
                if row_idx == 1:
                    cell.font = header_font
                    cell.fill = header_fill
        
        # 调整列宽
        ws_summary.column_dimensions['A'].width = 20
        ws_summary.column_dimensions['B'].width = 20
        ws_summary.column_dimensions['C'].width = 30
        
        # ========== Sheet 2: 详细结果 ==========
        ws_detail = wb.create_sheet(title="详细结果")
        
        detail_headers = ["序号", "音频路径", "检测语种", "标准化语种", "期望语种", "状态", "置信度"]
        
        for col_idx, header in enumerate(detail_headers, 1):
            cell = ws_detail.cell(row=1, column=col_idx, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.border = border
            cell.alignment = Alignment(horizontal='center', vertical='center')
        
        for row_idx, result in enumerate(stats.results, 2):
            row_data = [
                row_idx - 1,
                os.path.basename(result.audio_path),
                result.detected_lang,
                result.normalized_lang,
                result.expected_lang,
                "正确" if result.is_correct else "错误",
                f"{result.confidence:.0f}"
            ]
            
            for col_idx, value in enumerate(row_data, 1):
                cell = ws_detail.cell(row=row_idx, column=col_idx, value=value)
                cell.border = border
                cell.alignment = Alignment(horizontal='center', vertical='center')
                
                # 状态列着色
                if col_idx == 6:
                    if result.is_correct:
                        cell.fill = correct_fill
                    else:
                        cell.fill = error_fill
        
        # 调整列宽
        column_widths = [8, 50, 15, 15, 15, 10, 10]
        for col_idx, width in enumerate(column_widths, 1):
            ws_detail.column_dimensions[get_column_letter(col_idx)].width = width
        
        # ========== Sheet 3: 错误详情 ==========
        ws_errors = wb.create_sheet(title="错误详情")
        
        error_headers = ["序号", "音频路径", "检测语种", "期望语种"]
        
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
            
            row_data = [
                error_row - 1,
                os.path.basename(result.audio_path),
                result.detected_lang or "(空)",
                result.expected_lang
            ]
            
            for col_idx, value in enumerate(row_data, 1):
                cell = ws_errors.cell(row=error_row, column=col_idx, value=value)
                cell.border = border
                cell.alignment = Alignment(horizontal='center', vertical='center')
                cell.fill = error_fill
            
            error_row += 1
        
        # 调整列宽
        error_widths = [8, 50, 15, 15]
        for col_idx, width in enumerate(error_widths, 1):
            ws_errors.column_dimensions[get_column_letter(col_idx)].width = width
        
        # 保存文件（dirname 为空时使用当前目录）
        parent = os.path.dirname(output_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        wb.save(output_path)
        logger.info(f"Excel 报告已生成: {output_path}")
    
    def _generate_csv_report(self, stats: LanguageStats, expected_lang: str, output_path: str):
        """
        生成 CSV 格式报告（openpyxl 不可用时的备选方案）
        """
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            
            writer.writerow(["=== 汇总统计 ==="])
            writer.writerow(["期望语种", expected_lang])
            writer.writerow(["总数", stats.total_count])
            writer.writerow(["正确数", stats.correct_count])
            writer.writerow(["错误数", stats.error_count])
            writer.writerow(["语种正确率", f"{stats.accuracy * 100:.2f}%"])
            writer.writerow([])
            
            writer.writerow(["=== 详细结果 ==="])
            writer.writerow(["音频路径", "检测语种", "期望语种", "状态"])
            
            for result in stats.results:
                writer.writerow([
                    result.audio_path,
                    result.detected_lang,
                    result.expected_lang,
                    "正确" if result.is_correct else "错误"
                ])
        
        logger.info(f"CSV 报告已生成: {output_path}")
    
    def _generate_summary(self, stats: LanguageStats, expected_lang: str, output_path: str) -> str:
        """
        生成终端输出的 Summary 报告
        
        Args:
            stats: 统计结果
            expected_lang: 期望语种
            output_path: 报告文件路径
        
        Returns:
            str: Summary 字符串
        """
        # 语种分布字符串
        lang_dist_str = ", ".join([f"{lang}:{count}" for lang, count in 
                                   sorted(stats.lang_distribution.items(), key=lambda x: -x[1])])
        
        content_lines = [
            f"*  期望语种: {expected_lang}",
            f"*  总数: {stats.total_count}  |  正确: {stats.correct_count}  |  错误: {stats.error_count}  |  空结果: {stats.empty_count}",
            f"*  语种正确率:  {stats.accuracy * 100:6.2f}% ({stats.correct_count}/{stats.total_count})\t(语种识别正确的比例)",
            f"*  空结果率:    {stats.empty_rate * 100:6.2f}% ({stats.empty_count}/{stats.total_count})\t(无语种信息的比例)",
            f"*  语种分布: {lang_dist_str}",
            f"*  详细报告: {output_path}"
        ]
        content = "\n".join(content_lines)
        
        return self.format_summary_box("ASR_LANGUAGE", content, width=90)


def main():
    """
    命令行入口函数
    
    使用示例:
        python3 -m src.testsuite.NANO.tools.tsr.asr_language -r asr.csv -ref cmn
        python3 src/testsuite/NANO/tools/tsr/asr_language.py -r asr.csv -ref cmn -o report.xlsx
    """
    import argparse
    
    parser = argparse.ArgumentParser(
        description='ASR 语种识别正确率计算工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python3 %(prog)s -r result.csv -ref cmn
  python3 %(prog)s -r result.csv -ref cmn -o report.xlsx

语种匹配规则:
  - zh-cmn 和 cmn 都视为 cmn
  - zh-yue 和 yue 都视为 yue
  - 不区分大小写

输出:
  - 终端打印 Summary 统计报告
  - 生成 Excel 详细报告（包含汇总统计、详细结果、错误详情三个 Sheet）
        '''
    )
    
    parser.add_argument('-r', '--result', required=True, 
                        help='识别结果 CSV 文件路径')
    parser.add_argument('-ref', '--reference', required=True, 
                        help='期望的语种代码（如 cmn, en, yue）')
    parser.add_argument('-o', '--output', default=None, 
                        help='Excel 报告输出路径（默认: 当前目录/asr_language.xlsx）')
    
    args = parser.parse_args()
    
    # -o 未传时不带 output= 参数，execute 自动落到 cwd/mango_report/
    params = [
        f"result={args.result}",
        f"ref={args.reference}",
    ]
    if args.output:
        params.append(f"output={args.output}")

    handler = ASRLanguageHandler(config=None)

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
