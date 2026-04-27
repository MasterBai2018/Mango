#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2025/02/02
# @Author  : huidong.bai
# @File    : base.py
# @Software: PyCharm
# @Mail    : MasterBai2018@outlook.com
"""
TSR 指令基类和共享工具函数

包含:
- BaseTSRHandler: TSR 指令处理器基类
- 编辑距离计算算法
- Excel 报告生成工具
"""
import os
import re
import json
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Tuple, List, Dict, Any, Optional
from dataclasses import dataclass
from loguru import logger


# ─── 内联到子报告 HTML 中的 Allure 风格 CSS ──────────────────────────────────
ALLURE_STYLE_CSS = """
:root {
  --primary:   #3498db;
  --success:   #96ba2f;
  --failure:   #e74c3c;
  --warning:   #f39c12;
  --header-bg: #2c3e50;
  --bg:        #f5f5f5;
  --card-bg:   #ffffff;
  --text:      #333333;
  --text-muted:#666666;
  --border:    #e0e0e0;
  --radius:    4px;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Roboto', 'Segoe UI', Arial, sans-serif;
       background: var(--bg); color: var(--text); font-size: 13px; }
.report-header {
  background: var(--header-bg); color: #fff;
  padding: 14px 24px; display: flex; align-items: center;
  justify-content: space-between; flex-wrap: wrap; gap: 8px;
}
.report-header .logo { font-size: 18px; font-weight: 700; letter-spacing: 0.5px; }
.report-header .meta { font-size: 11px; opacity: 0.75; }
.report-body { padding: 20px 24px; }
.summary-cards { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 20px; }
.card {
  background: var(--card-bg); border-radius: var(--radius);
  padding: 14px 20px; min-width: 140px; flex: 1;
  box-shadow: 0 1px 4px rgba(0,0,0,0.1);
  border-top: 3px solid var(--primary); text-align: center;
}
.card.card-success { border-top-color: var(--success); }
.card.card-failure { border-top-color: var(--failure); }
.card.card-warning { border-top-color: var(--warning); }
.card .card-value { font-size: 22px; font-weight: 700; color: var(--text); line-height: 1.2; }
.card .card-label { font-size: 11px; color: var(--text-muted); margin-top: 4px; }
.section { background: var(--card-bg); border-radius: var(--radius);
           box-shadow: 0 1px 4px rgba(0,0,0,0.08); margin-bottom: 16px; overflow: hidden; }
.section-header { padding: 10px 16px; font-weight: 600; font-size: 13px;
                  border-bottom: 1px solid var(--border); background: #fafafa; }
.section-body { padding: 0; }
.inner-tabs { display: flex; border-bottom: 1px solid var(--border); background: #fafafa; }
.inner-tab { padding: 8px 16px; cursor: pointer; font-size: 12px; color: var(--text-muted);
             border-bottom: 2px solid transparent; margin-bottom: -1px; }
.inner-tab.active { color: var(--primary); border-bottom-color: var(--primary); font-weight: 600; }
.inner-pane { display: none; }
.inner-pane.active { display: block; }
.report-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.report-table th {
  background: #4a6fa5; color: #fff; padding: 7px 10px;
  text-align: left; font-weight: 600; white-space: nowrap;
}
.report-table td { padding: 5px 10px; border-bottom: 1px solid var(--border); }
.report-table tbody tr:nth-child(odd) { background: #fafafa; }
.report-table tbody tr:hover { background: #eef4fb; }
.tag-pass { background: #eaf4e2; color: #4a7c1f; padding: 1px 7px; border-radius: 10px; }
.tag-fail { background: #fde8e8; color: #c0392b; padding: 1px 7px; border-radius: 10px; }
.tag-warn { background: #fef9e2; color: #b7770d; padding: 1px 7px; border-radius: 10px; }
.pbar-wrap { display: flex; align-items: center; gap: 6px; }
.pbar { width: 80px; height: 8px; background: #e9ecef; border-radius: 4px; overflow: hidden; flex-shrink: 0; }
.pbar-fill { height: 100%; border-radius: 4px; }
.pbar-pass { background: var(--success); }
.pbar-fail { background: var(--failure); }
"""

# ─── 报告 HTML 骨架（用 <<<KEY>>> 做占位符，规避 CSS/JS 花括号与 str.format 冲突）──
# build_html_page() 用 str.replace() 注入，不调用 .format()
HTML_PAGE_TEMPLATE = (
    '<!DOCTYPE html>\n'
    '<html lang="zh-CN">\n'
    '<head>\n'
    '  <meta charset="UTF-8">\n'
    '  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
    '  <title><<<TITLE>>></title>\n'
    '  <style><<<CSS>>></style>\n'
    '  <script>\n'
    '    function switchTab(el, paneId) {\n'
    '      var tabs = el.closest(\'.inner-tabs\').querySelectorAll(\'.inner-tab\');\n'
    '      var panes = el.closest(\'.section-body\').querySelectorAll(\'.inner-pane\');\n'
    '      tabs.forEach(function(t){ t.classList.remove(\'active\'); });\n'
    '      panes.forEach(function(p){ p.classList.remove(\'active\'); });\n'
    '      el.classList.add(\'active\');\n'
    '      document.getElementById(paneId).classList.add(\'active\');\n'
    '    }\n'
    '  </script>\n'
    '</head>\n'
    '<body>\n'
    '  <div class="report-header">\n'
    '    <div class="logo"><<<TITLE>>></div>\n'
    '    <div class="meta"><<<DEFINE>>> / <<<SUITE>>> &nbsp;|&nbsp; <<<GENERATED_AT>>></div>\n'
    '  </div>\n'
    '  <div class="report-body">\n'
    '    <<<BODY>>>\n'
    '  </div>\n'
    '</body>\n'
    '</html>\n'
)


@dataclass
class EditDistance:
    """编辑距离计算结果"""
    distance: int           # 总编辑距离
    substitutions: int      # 替换次数
    insertions: int         # 插入次数
    deletions: int          # 删除次数
    ref_length: int         # 参考文本长度
    hyp_length: int         # 假设文本长度
    
    @property
    def cer(self) -> float:
        """字符错误率 (Character Error Rate)"""
        if self.ref_length == 0:
            return 0.0 if self.hyp_length == 0 else 1.0
        return (self.substitutions + self.insertions + self.deletions) / self.ref_length
    
    @property
    def accuracy(self) -> float:
        """字符准确率 (Character Accuracy Rate)"""
        return max(0.0, 1.0 - self.cer)
    
    @property
    def insertion_rate(self) -> float:
        """插入率"""
        if self.ref_length == 0:
            return 0.0
        return self.insertions / self.ref_length
    
    @property
    def deletion_rate(self) -> float:
        """删除率"""
        if self.ref_length == 0:
            return 0.0
        return self.deletions / self.ref_length
    
    @property
    def substitution_rate(self) -> float:
        """替换率"""
        if self.ref_length == 0:
            return 0.0
        return self.substitutions / self.ref_length


# 尝试导入高性能库
_USE_RAPIDFUZZ = False
try:
    from rapidfuzz.distance import Levenshtein
    _USE_RAPIDFUZZ = True
except ImportError:
    pass


def calculate_edit_distance(reference: str, hypothesis: str) -> EditDistance:
    """
    计算两个字符串之间的编辑距离（Levenshtein Distance）
    
    优先使用 rapidfuzz 库（C实现，速度快10-100倍），
    如果不可用则使用优化后的纯 Python 实现。
    
    Args:
        reference: 参考文本（标准答案）
        hypothesis: 假设文本（识别结果）
    
    Returns:
        EditDistance: 包含详细统计信息的编辑距离结果
    """
    m, n = len(reference), len(hypothesis)
    
    # 快速路径：相同字符串
    if reference == hypothesis:
        return EditDistance(
            distance=0, substitutions=0, insertions=0, deletions=0,
            ref_length=m, hyp_length=n
        )
    
    # 快速路径：空字符串
    if m == 0:
        return EditDistance(
            distance=n, substitutions=0, insertions=n, deletions=0,
            ref_length=0, hyp_length=n
        )
    if n == 0:
        return EditDistance(
            distance=m, substitutions=0, insertions=0, deletions=m,
            ref_length=m, hyp_length=0
        )
    
    if _USE_RAPIDFUZZ:
        return _calculate_edit_distance_rapidfuzz(reference, hypothesis, m, n)
    else:
        return _calculate_edit_distance_optimized(reference, hypothesis, m, n)


def _calculate_edit_distance_rapidfuzz(ref: str, hyp: str, m: int, n: int) -> EditDistance:
    """使用 rapidfuzz 库计算编辑距离（高性能）"""
    # rapidfuzz 提供的操作码
    opcodes = Levenshtein.opcodes(ref, hyp)
    
    subs = ins = dels = 0
    for tag, i1, i2, j1, j2 in opcodes:
        if tag == 'replace':
            # 替换操作
            ref_len = i2 - i1
            hyp_len = j2 - j1
            min_len = min(ref_len, hyp_len)
            subs += min_len
            if ref_len > hyp_len:
                dels += ref_len - hyp_len
            else:
                ins += hyp_len - ref_len
        elif tag == 'delete':
            dels += i2 - i1
        elif tag == 'insert':
            ins += j2 - j1
    
    return EditDistance(
        distance=subs + ins + dels,
        substitutions=subs,
        insertions=ins,
        deletions=dels,
        ref_length=m,
        hyp_length=n
    )


def _calculate_edit_distance_optimized(ref: str, hyp: str, m: int, n: int) -> EditDistance:
    """
    优化后的纯 Python 编辑距离计算
    
    空间复杂度优化：O(m*n) -> O(min(m,n))
    使用两行滚动数组代替完整矩阵
    """
    # 确保 hyp 是较短的字符串（减少空间）
    if m < n:
        ref, hyp = hyp, ref
        m, n = n, m
        swapped = True
    else:
        swapped = False
    
    # 使用滚动数组，只保留两行
    # 每个元素: (distance, substitutions, insertions, deletions)
    prev_row = [(j, 0, j, 0) for j in range(n + 1)]
    curr_row = [(0, 0, 0, 0)] * (n + 1)
    
    for i in range(1, m + 1):
        curr_row[0] = (i, 0, 0, i)
        
        for j in range(1, n + 1):
            if ref[i - 1] == hyp[j - 1]:
                curr_row[j] = prev_row[j - 1]
            else:
                # 替换
                sub = prev_row[j - 1]
                sub_total = (sub[0] + 1, sub[1] + 1, sub[2], sub[3])
                
                # 插入
                ins = curr_row[j - 1]
                ins_total = (ins[0] + 1, ins[1], ins[2] + 1, ins[3])
                
                # 删除
                del_ = prev_row[j]
                del_total = (del_[0] + 1, del_[1], del_[2], del_[3] + 1)
                
                # 选择代价最小的
                curr_row[j] = min(sub_total, ins_total, del_total, key=lambda x: x[0])
        
        # 交换行
        prev_row, curr_row = curr_row, prev_row
    
    dist, subs, ins, dels = prev_row[n]
    
    # 如果交换过，需要交换 insertions 和 deletions
    if swapped:
        ins, dels = dels, ins
    
    return EditDistance(
        distance=dist,
        substitutions=subs,
        insertions=ins,
        deletions=dels,
        ref_length=m if not swapped else n,
        hyp_length=n if not swapped else m
    )


@dataclass
class ASRComparisonResult:
    """单条 ASR 对比结果"""
    audio_path: str                 # 音频路径
    reference: str                  # 参考文本（标准答案）
    hypothesis: str                 # 识别结果
    is_correct: bool                # 是否完全正确
    is_empty: bool                  # 识别结果是否为空
    edit_distance: EditDistance     # 编辑距离详情
    confidence: float = 0.0         # 置信度
    
    @property
    def status(self) -> str:
        """状态描述"""
        if self.is_empty:
            return "空结果"
        return "正确" if self.is_correct else "错误"


class BaseTSRHandler(ABC):
    """
    TSR 指令处理器基类
    
    所有 TSR 指令处理器都应继承此类，并实现 execute 方法。
    """
    
    # 指令名称（子类应覆盖）
    COMMAND_NAME: str = "BASE"
    
    def __init__(self, config=None):
        """
        初始化处理器
        
        Args:
            config: pytest config 对象（用于环境变量替换）
        """
        self.config = config
    
    @abstractmethod
    def execute(self, params: list, output_report: str = None) -> str:
        """
        执行指令
        
        Args:
            params: 参数列表
            output_report: 报告输出路径（可选）
        
        Returns:
            str: 执行结果的 Summary 字符串
        """
        pass
    
    @abstractmethod
    def generate_html_report(self, *args, **kwargs) -> Optional[str]:
        """
        生成 HTML 报告并保存，子类必须实现。

        典型实现步骤：
          1. 用数据构建 HTML 内容字符串；
          2. 调用 self.save_html_report() 保存到 allure_result/mango_report/{define}/{suite}/；
          3. 返回保存后的绝对路径，失败时返回 None。
        """
        pass

    # ─── HTML 报告路径基础设施 ─────────────────────────────────────────────────

    @staticmethod
    def _clean_dirname(name: str) -> str:
        """清理目录名：将空格及文件系统不安全字符替换为下划线，并合并连续下划线"""
        if not name:
            return 'unknown'
        name = name.strip()
        # 文件系统不安全字符统一替换为下划线
        name = re.sub(r'[\s/\\:*?"<>|]+', '_', name)
        name = re.sub(r'_+', '_', name).strip('_')
        return name or 'unknown'

    def _get_define_dirname(self) -> str:
        """获取 define 目录名（取自 --mongo_scene_name）"""
        if not self.config:
            return 'unknown_define'
        try:
            scene_name = self.config.getoption('--mongo_scene_name') or 'unknown_define'
            return self._clean_dirname(scene_name)
        except Exception:
            return 'unknown_define'

    def _get_suite_dirname(self) -> str:
        """获取 suite 目录名（suite_id + _ + abstract）"""
        if not self.config:
            return 'unknown_suite'
        try:
            suite_id = str(self.config.getoption('--mongo_suite_id') or '')
            abstract = str(self.config.getoption('--mongo_suite_abstract') or '')
            raw = f"{suite_id}_{abstract}" if abstract else suite_id
            return self._clean_dirname(raw) or 'unknown_suite'
        except Exception:
            return 'unknown_suite'

    def _get_allure_result_dir(self) -> Optional[str]:
        """获取 allure result 目录（pytest 运行时才有值）"""
        if not self.config:
            return None
        try:
            return self.config.getoption('allure_report_dir')
        except Exception:
            return None

    def _get_mango_html_dir(self) -> Optional[str]:
        """返回 allure_result/mango_report/{define}/{suite}/ 的绝对路径，失败返回 None"""
        allure_dir = self._get_allure_result_dir()
        if not allure_dir:
            return None
        define = self._get_define_dirname()
        suite  = self._get_suite_dirname()
        return os.path.join(allure_dir, 'mango_report', define, suite)

    def _get_suite_mango_dir(self) -> str:
        """返回 suite_dir/mango_report/ 目录（CLI 时回退到 cwd/mango_report/）"""
        if self.config and hasattr(self.config, 'suite_dir') and self.config.suite_dir:
            return os.path.join(self.config.suite_dir, 'mango_report')
        return os.path.join(os.getcwd(), 'mango_report')

    def _update_manifest(self, define: str, suite: str, title: str,
                         report_type: str, filename: str) -> None:
        """在 allure_result/mango_report/manifest.json 中新增或更新一条记录"""
        allure_dir = self._get_allure_result_dir()
        if not allure_dir:
            return
        manifest_path = os.path.join(allure_dir, 'mango_report', 'manifest.json')

        # 读取已有 manifest
        manifest: Dict[str, Any] = {'generated_at': '', 'reports': []}
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)
            except Exception:
                pass

        rel_path = f"{define}/{suite}/{filename}"
        now_str  = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        entry = {
            'define':       define,
            'suite':        suite,
            'title':        title,
            'type':         report_type,
            'file':         rel_path,
            'generated_at': now_str,
        }

        # 已存在相同 file 则更新，否则追加
        reports: list = manifest.setdefault('reports', [])
        for i, r in enumerate(reports):
            if r.get('file') == rel_path:
                reports[i] = entry
                break
        else:
            reports.append(entry)

        manifest['generated_at'] = now_str
        os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
        logger.debug(f"manifest.json 已更新: {rel_path}")

    def save_html_report(self, html_content: str, report_filename: str,
                         report_title: str, report_type: str) -> Optional[str]:
        """
        将 HTML 内容保存到 allure_result/mango_report/{define}/{suite}/{report_filename}，
        同时更新 manifest.json。

        Returns:
            保存后的绝对路径，无法获取 allure_result 时返回 None。
        """
        html_dir = self._get_mango_html_dir()
        if not html_dir:
            logger.warning("无法获取 allure_result 目录，跳过 Allure HTML 报告保存")
            return None

        os.makedirs(html_dir, exist_ok=True)
        html_path = os.path.join(html_dir, report_filename)
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        logger.info(f"Allure HTML 报告已生成: {html_path}")

        define = self._get_define_dirname()
        suite  = self._get_suite_dirname()
        self._update_manifest(define, suite, report_title, report_type, report_filename)
        return html_path

    def build_html_page(self, title: str, body_html: str) -> str:
        """
        用统一的 Allure 风格骨架包裹 body 内容，生成完整 HTML 字符串。

        Args:
            title:     报告标题
            body_html: <body> 内部 HTML 片段

        Returns:
            完整的自包含 HTML 字符串
        """
        # 使用 str.replace() 而非 .format()，避免 CSS/JS 花括号被误认为格式占位符
        return (
            HTML_PAGE_TEMPLATE
            .replace('<<<TITLE>>>', title)
            .replace('<<<CSS>>>', ALLURE_STYLE_CSS)
            .replace('<<<DEFINE>>>', self._get_define_dirname())
            .replace('<<<SUITE>>>', self._get_suite_dirname())
            .replace('<<<GENERATED_AT>>>', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            .replace('<<<BODY>>>', body_html)
        )

    # ─── 原有通用方法 ──────────────────────────────────────────────────────────

    def get_default_output_path(self, filename: str) -> str:
        """
        获取默认输出路径
        
        优先使用 config 中的 suite_dir，否则使用当前目录
        
        Args:
            filename: 文件名
        
        Returns:
            str: 完整的输出路径
        """
        if self.config and hasattr(self.config, 'suite_dir'):
            base_dir = self.config.suite_dir
        else:
            base_dir = os.getcwd()
        
        return os.path.join(base_dir, filename)
    
    def format_summary_box(self, title: str, content: str, width: int = 80) -> str:
        """
        格式化 Summary 输出框
        
        Args:
            title: 标题
            content: 内容
            width: 宽度
        
        Returns:
            str: 格式化后的字符串
        """
        border = "*" * width
        title_line = f" {title} ".center(width, "*")
        
        lines = [
            "",
            title_line,
            content,
            border
        ]
        return "\n".join(lines)
