#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2026/03/15
# @Author  : huidong.bai
# @File    : llm.py
# @Software: PyCharm
# @Mail    : MasterBai2018@outlook.com
"""
LLM 指令实现

使用大模型（DeepSeek / OpenAI 兼容接口）对测试结果进行离线批量评测。

设计原则：
  1. Data Mapper:    pandas 读取 CSV，或按行读取 JSONL 并展平为表；SafeDict 安全渲染 Prompt 占位符
  2. 强 JSON 提取:  多级策略从大模型回复中提取合法 JSON 列表
  3. 动态列展开:    pd.concat 平行拼接，严禁硬编码列名
  4. 渲染委托:      调用 BaseTSRHandler 现有基础设施生成 HTML / Excel

使用示例（DSL）:
    [TSR]LLM result=test_result.csv prompt=TestCase/eval_prompts.txt output=eval_report.xlsx batch=10
    [TSR]LLM result=pisa_llm_result.jsonl prompt=eval_prompts.txt output=eval_report.xlsx batch=5

命令行独立运行:
    python3 src/testsuite/NANO/tools/tsr/llm.py \\
        -r test_result.csv -p eval_prompts.txt -o eval_report.xlsx -b 10

环境变量:
    DEEPSEEK_API_URL   大模型 API 地址（默认 https://api.deepseek.com/v1/chat/completions）
    DEEPSEEK_API_KEY   API 密钥（必须设置）
    DEEPSEEK_MODEL     模型名称（默认 deepseek-chat）
"""
import os
import sys
import re
import json
import time
from typing import Dict, List, Optional, Tuple, Any
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


# ── 常量 ─────────────────────────────────────────────────────────────────────
DEFAULT_API_URL  = "https://api.deepseek.com/v1/chat/completions"
DEFAULT_MODEL    = "deepseek-chat"
DEEPSEEK_API_KEY = "test_mango_id"
PASS_THRESHOLD   = 80   # score < 80 → fail


# ── 安全格式化字典 ────────────────────────────────────────────────────────────
class _SafeDict(dict):
    """
    安全格式化字典：遇到缺失的 key 时返回原始占位符而非抛出 KeyError。

    用法:
        template.format_map(_SafeDict(row_dict))
        # 若 row_dict 缺少 {intent} 列，原样保留 "{intent}" 而不报错
    """
    def __missing__(self, key: str) -> str:
        return f"{{{key}}}"


# ── 主处理器 ──────────────────────────────────────────────────────────────────
@register_tsr_command("LLM")
class LLMEvalHandler(BaseTSRHandler):
    """
    大模型离线批量评测处理器

    指令格式:
        [TSR]LLM result=<csv|jsonl> prompt=<prompt_file> [output=<xlsx>] [batch=<n>]

    参数说明:
        result:  待评测数据文件路径（必需）。支持 .csv（Tab/逗号自动识别）或 .jsonl（每行一个 JSON 对象）
        prompt:  外部 Prompt 模板文本文件路径，内部用 {列名} 占位符（必需）。
                 JSONL 行会展平为列：嵌套 dict 用下划线连接键名（如 case.index → case_index），
                 list 整段序列化为 JSON 字符串作为单元格（如 prelude、rounds）
        output:  Excel 报告输出路径（可选，默认 suite_dir/mango_report/llm_eval.xlsx）
        batch:   每次请求大模型的数据条数（可选，默认 10）
    """

    COMMAND_NAME = "LLM"

    # ─── 参数解析 ─────────────────────────────────────────────────────────────

    def _parse_params(self, params: list,
                      default_output: str = None) -> Tuple[str, str, str, int]:
        """
        解析 DSL 参数列表

        Returns:
            (result_file, prompt_file, output_path, batch_size)
        """
        result_file = None
        prompt_file = None
        output_path = default_output
        batch_size  = 10

        for param in params:
            if param.startswith("result="):
                result_file = param[7:]
            elif param.startswith("prompt="):
                prompt_file = param[7:]
            elif param.startswith("output="):
                output_path = param[7:]
            elif param.startswith("batch="):
                try:
                    batch_size = int(param[6:])
                except ValueError:
                    logger.warning(f"batch 参数值无效: '{param[6:]}'，使用默认值 10")

        if not result_file:
            raise ValueError("缺少必需参数: result=<csv 或 jsonl>")
        if not prompt_file:
            raise ValueError("缺少必需参数: prompt=<prompt_file>")

        if not output_path:
            suite_mango_dir = self._get_suite_mango_dir()
            output_path = os.path.join(suite_mango_dir, "llm_eval.xlsx")

        return result_file, prompt_file, output_path, batch_size

    # ─── 数据与模板加载 ───────────────────────────────────────────────────────

    @staticmethod
    def _flatten_json_object_for_row(obj: Any, parent_key: str = "",
                                     sep: str = "_") -> Dict[str, str]:
        """
        将单行 JSON 对象展平为 str → str，供 Prompt 的 {列名} 占位符替换。

        - 嵌套 dict：递归，键名用 sep 连接（如 case + index → case_index）
        - list / tuple：整段 json.dumps（ensure_ascii=False），不再向下展开
        - 标量：str()，None → 空串
        """
        flat: Dict[str, str] = {}
        if not isinstance(obj, dict):
            raise TypeError(f"JSONL 每行顶层必须是 JSON 对象(dict)，实际: {type(obj).__name__}")
        for k, v in obj.items():
            key = f"{parent_key}{sep}{k}" if parent_key else str(k)
            if isinstance(v, dict):
                flat.update(
                    LLMEvalHandler._flatten_json_object_for_row(v, key, sep=sep)
                )
            elif isinstance(v, (list, tuple)):
                flat[key] = json.dumps(v, ensure_ascii=False)
            else:
                flat[key] = "" if v is None else str(v)
        return flat

    def _load_jsonl(self, filepath: str):
        """
        按行读取 JSONL，每行解析为一个 dict，展平后合并为 DataFrame。

        空行跳过；解析失败抛出 ValueError（带行号）。
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("LLM 指令需要 pandas 库：pip install pandas")

        rows: List[Dict[str, str]] = []
        with open(filepath, 'r', encoding='utf-8') as f:
            for line_no, line in enumerate(f, 1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    obj = json.loads(stripped)
                except json.JSONDecodeError as e:
                    raise ValueError(
                        f"JSONL 解析失败 {filepath}:{line_no}: {e}"
                    ) from e
                rows.append(self._flatten_json_object_for_row(obj))

        if not rows:
            raise ValueError(f"JSONL 文件无有效数据行: {filepath}")

        df = pd.DataFrame(rows).fillna('')
        for col in df.columns:
            df[col] = df[col].astype(str)
        logger.info(f"已加载 JSONL: {len(df)} 行，列: {list(df.columns)}")
        return df

    def _load_data(self, filepath: str):
        """
        加载评测输入：CSV（自动探测 Tab / 逗号）或 JSONL（扩展名 .jsonl，大小写不敏感）。

        Returns:
            pd.DataFrame，所有列均为 str 类型，缺失值填充为空字符串
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("LLM 指令需要 pandas 库：pip install pandas")

        lower = filepath.lower()
        if lower.endswith('.jsonl'):
            return self._load_jsonl(filepath)

        with open(filepath, 'r', encoding='utf-8') as f:
            first_line = f.readline()
        delimiter = '\t' if first_line.count('\t') > first_line.count(',') else ','

        df = pd.read_csv(filepath, sep=delimiter, dtype=str).fillna('')
        logger.info(f"已加载数据: {len(df)} 行，列: {list(df.columns)}")
        return df

    def _load_prompt_template(self, filepath: str) -> str:
        """读取 Prompt 模板文件内容"""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Prompt 模板文件不存在: {filepath}")
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        logger.info(f"已加载 Prompt 模板: {filepath}（{len(content)} 字符）")
        return content

    # ─── Batch 消息构造 ───────────────────────────────────────────────────────

    @staticmethod
    def _render_row(template: str, row_dict: dict) -> str:
        """
        将模板中的 {列名} 替换为行数据。
        使用 _SafeDict 确保缺失列时不抛 KeyError，原样保留占位符。
        """
        return template.format_map(_SafeDict(row_dict))

    @staticmethod
    def _extract_images_from_rounds(rounds_text: str) -> List[str]:
        """
        从 rounds 字段（JSON 字符串）中提取所有 image 路径。
        结构示例：
            [{"round":1,"images":[{"image":"xxx.png","image_text":"..."}],...}]
        """
        if not rounds_text:
            return []
        try:
            rounds_obj = json.loads(rounds_text)
        except Exception:
            return []
        if not isinstance(rounds_obj, list):
            return []

        images: List[str] = []
        for round_item in rounds_obj:
            if not isinstance(round_item, dict):
                continue
            image_items = round_item.get("images", [])
            if not isinstance(image_items, list):
                continue
            for image_item in image_items:
                if not isinstance(image_item, dict):
                    continue
                image_path = image_item.get("image", "")
                if image_path:
                    images.append(str(image_path))
        return images

    @staticmethod
    def _extract_row_images(row_dict: dict) -> List[str]:
        rounds_text = ""
        for k, v in row_dict.items():
            if str(k).lower() == "rounds":
                rounds_text = v
                break
        return LLMEvalHandler._extract_images_from_rounds(rounds_text)

    @staticmethod
    def _normalize_image_key(image_path: str) -> str:
        return str(image_path).replace("\\", "/").strip().lower()

    def _load_picture_desc_map(self, excel_path: str) -> Dict[str, str]:
        try:
            import pandas as pd
        except ImportError:
            logger.warning("未安装 pandas，跳过图片描述增强。")
            return {}

        if not os.path.exists(excel_path):
            logger.warning(f"图片描述 Excel 不存在，跳过描述增强: {excel_path}")
            return {}

        try:
            df = pd.read_excel(excel_path)
        except Exception as e:
            logger.warning(f"读取图片描述 Excel 失败，跳过描述增强: {e}")
            return {}

        required_cols = {"picture_path", "describe"}
        if not required_cols.issubset(set(df.columns)):
            logger.warning(
                f"图片描述 Excel 缺少必要列 {required_cols}，实际列: {list(df.columns)}"
            )
            return {}

        desc_map: Dict[str, str] = {}
        for _, row in df.iterrows():
            picture_path = str(row.get("picture_path", "")).strip()
            describe = str(row.get("describe", "")).strip()
            if not picture_path or not describe:
                continue
            full_key = self._normalize_image_key(picture_path)
            base_key = self._normalize_image_key(os.path.basename(picture_path))
            desc_map[full_key] = describe
            # basename 作为兜底键，兼容 rounds 里只写文件名的情况
            if base_key not in desc_map:
                desc_map[base_key] = describe
        return desc_map

    def _build_batch_messages(self, prompt_template: str, rows: List[dict]) -> list:
        """
        构造 OpenAI 格式的 messages（system + user）。

        框架统一注入：
          - system message：JSON 输出格式约束（score/result 必填）
          - user message：N 条渲染后的 prompt，用 [数据 n] 分隔

        Args:
            prompt_template: 单条 Prompt 模板（含 {列名} 占位符）
            rows:            当前 batch 的行数据列表

        Returns:
            OpenAI messages 格式列表
        """
        n = len(rows)
        system_msg = (
            f"你是一个专业的测试评测助手。你将收到 {n} 条测试数据，"
            f"请逐条进行评测，并以 JSON 数组格式返回结果。\n"
            f"\n"
            f"【强制要求】每个元素必须包含以下字段：\n"
            f"  - score:  整数，0-100，表示本条数据的质量得分\n"
            f"  - result: 字符串，\"pass\" 或 \"fail\"\n"
            f"            （score < {PASS_THRESHOLD} 时必须为 \"fail\"，否则为 \"pass\"）\n"
            f"\n"
            f"你可以自由添加其他字段（如 reason、suggestion、error_type 等）。\n"
            f"\n"
            f"【输出格式】只返回一个合法的 JSON 数组，"
            f"不要有任何多余的文字、Markdown 代码块标记或解释。\n"
            f"示例（2 条数据）：\n"
            f'[{{"score": 85, "result": "pass", "reason": "用户请求是规划一下三天的行程，要求提供具体、结构化的三日游玩安排。大模型的回复提供了三天的行程安排，每天包含2个活动，覆盖了景点参观、文化体验和美食推荐，基本满足了用户的核心需求。"}}, '
            f'{{"score": 20, "result": "fail", "reason": "用户请求是规划一下三天的行程，要求提供具体、结构化的三日游玩安排。而大模型的回复仅提及了长沙的当前天气和两个景点（橘子洲头、岳麓山）的推荐，完全没有涉及任何行程规划（如每日行程安排、时间分配、餐饮住宿建议等）。虽然回复内容与长沙游玩有一定关联，但严重偏离了用户的核心需求，属于部分相关但信息严重不足，因此给予低分。"}}]'
        )

        picture_excel = 'TestCase/nano/PISA/Images/picture.xlsx'
        if not hasattr(self, "_picture_desc_map_cache"):
            self._picture_desc_map_cache = {}
        if picture_excel not in self._picture_desc_map_cache:
            self._picture_desc_map_cache[picture_excel] = self._load_picture_desc_map(picture_excel)
        picture_desc_map = self._picture_desc_map_cache.get(picture_excel, {})

        user_parts = []
        for i, row_dict in enumerate(rows, 1):
            rendered = self._render_row(prompt_template, row_dict)
            if picture_desc_map:
                row_images = self._extract_row_images(row_dict)
                desc_lines: List[str] = []
                seen_desc = set()
                for image_path in row_images:
                    norm_full = self._normalize_image_key(image_path)
                    norm_base = self._normalize_image_key(os.path.basename(image_path))
                    desc = picture_desc_map.get(norm_full) or picture_desc_map.get(norm_base)
                    if not desc:
                        continue
                    dedup_key = f"{norm_base}::{desc}"
                    if dedup_key in seen_desc:
                        continue
                    seen_desc.add(dedup_key)
                    desc_lines.append(f"- {image_path}: {desc}")
                if desc_lines:
                    rendered = f"{rendered}\n\n[图片描述参考]\n" + "\n".join(desc_lines)
            user_parts.append(f"[数据 {i}]\n{rendered}")

        user_msg = "\n\n".join(user_parts)
        return [
            {"role": "system", "content": system_msg},
            {"role": "user",   "content": user_msg},
        ]

    # ─── LLM API 调用 ─────────────────────────────────────────────────────────

    def _call_llm_api(self, messages: list, retry: int = 2) -> str:
        """
        调用 OpenAI 兼容 API（支持 DeepSeek）。

        配置项（均从环境变量读取）：
            DEEPSEEK_API_URL   API 地址（默认 https://api.deepseek.com/v1/chat/completions）
            DEEPSEEK_API_KEY   API 密钥（必须设置，否则抛出 ValueError）
            DEEPSEEK_MODEL     模型名称（默认 deepseek-chat）

        Args:
            messages: OpenAI 格式的 messages 列表
            retry:    失败后最大重试次数（指数退避）

        Returns:
            大模型原始回复文本（choices[0].message.content）
        """
        try:
            import requests
        except ImportError:
            raise ImportError("LLM 指令需要 requests 库：pip install requests")

        api_url = os.environ.get("DEEPSEEK_API_URL", DEFAULT_API_URL)
        api_key = os.environ.get("DEEPSEEK_API_KEY", DEEPSEEK_API_KEY)
        model   = os.environ.get("DEEPSEEK_MODEL",   DEFAULT_MODEL)

        if not api_key:
            raise ValueError(
                "未设置 DEEPSEEK_API_KEY 环境变量。\n"
                "请执行: export DEEPSEEK_API_KEY=<your_key>"
            )

        headers = {
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        payload = {
            "model":       model,
            "messages":    messages,
            "temperature": 0.1,  # 低温度提升 JSON 格式稳定性
        }

        for attempt in range(retry + 1):
            try:
                resp = requests.post(
                    api_url, headers=headers,
                    json=payload, timeout=120
                )
                if resp.status_code >= 400:
                    raise RuntimeError(
                        f"HTTP {resp.status_code}: {resp.text[:800]}"
                    )
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            except Exception as e:
                if attempt < retry:
                    wait = 2 ** attempt
                    logger.warning(
                        f"LLM API 调用失败（第 {attempt + 1} 次），"
                        f"{wait}s 后重试: {e}"
                    )
                    time.sleep(wait)
                else:
                    raise

    # ─── 强 JSON 提取 ─────────────────────────────────────────────────────────

    def _extract_json_list(self, text: str, expected_count: int) -> List[Dict]:
        """
        从大模型回复中强制提取 JSON 列表，确保程序不崩溃。

        提取策略（按优先级）：
          1. 直接 json.loads(text)
          2. 正则提取最外层 [...] 块后 json.loads
          3. 逐个匹配 {...} 对象
          4. 全部失败：返回 expected_count 个错误占位字典

        后处理：
          - 强制 score 为 int，result 由 score 与 PASS_THRESHOLD 重新推导
          - 条数不足时补充错误占位；超出时截断
          - 保留大模型自由添加的其他字段（原则三：不硬编码列名）

        Args:
            text:           大模型原始回复文本
            expected_count: 本 batch 期望的条数

        Returns:
            长度恰好为 expected_count 的 dict 列表
        """
        raw = text.strip()
        result_list: Optional[List] = None

        # 策略 1：直接解析
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                result_list = parsed
            elif isinstance(parsed, dict):
                result_list = [parsed]
        except Exception:
            pass

        # 策略 2：提取最外层 [...] 块
        if result_list is None:
            m = re.search(r'\[[\s\S]*\]', raw)
            if m:
                try:
                    parsed = json.loads(m.group())
                    if isinstance(parsed, list):
                        result_list = parsed
                except Exception:
                    pass

        # 策略 3：逐个提取 {...} 对象（处理大模型换行分隔的情况）
        if result_list is None:
            items = []
            for obj_m in re.finditer(r'\{[^{}]*\}', raw, re.DOTALL):
                try:
                    items.append(json.loads(obj_m.group()))
                except Exception:
                    pass
            if items:
                result_list = items

        # 策略 4：完全失败
        if result_list is None:
            logger.warning(f"JSON 解析完全失败，原始回复片段：{raw[:300]}")
            return [self._error_item("JSON解析失败") for _ in range(expected_count)]

        # ── 标准化每一项 ──
        normalized: List[Dict] = []
        for item in result_list:
            if not isinstance(item, dict):
                normalized.append(self._error_item("返回类型非dict"))
                continue

            # 强制 score 为整数
            try:
                score = int(float(str(item.get("score", 0))))
            except (ValueError, TypeError):
                score = 0
            score = max(0, min(100, score))  # 夹到 [0, 100]

            # 由 score 强制推导 result，保证一致性
            item["score"]  = score
            item["result"] = "pass" if score >= PASS_THRESHOLD else "fail"
            normalized.append(item)

        # ── 对齐条数 ──
        if len(normalized) < expected_count:
            shortage = expected_count - len(normalized)
            logger.warning(
                f"大模型返回 {len(normalized)} 条，期望 {expected_count} 条，"
                f"补充 {shortage} 个错误占位"
            )
            normalized.extend(
                [self._error_item("大模型返回条数不足") for _ in range(shortage)]
            )
        elif len(normalized) > expected_count:
            logger.warning(
                f"大模型返回 {len(normalized)} 条，超出期望 {expected_count}，截断"
            )
            normalized = normalized[:expected_count]

        return normalized

    @staticmethod
    def _error_item(reason: str) -> Dict[str, Any]:
        """构造评测异常时的错误占位字典"""
        return {"score": 0, "result": "fail", "reason": f"[评测异常] {reason}"}

    # ─── 主评测流程 ───────────────────────────────────────────────────────────

    def _run_evaluation(self, df, prompt_template: str,
                        batch_size: int) -> List[Dict]:
        """
        分批调用大模型，逐批收集评测结果。

        Args:
            df:              原始 pandas DataFrame
            prompt_template: Prompt 模板字符串
            batch_size:      每批条数

        Returns:
            与 df 等长的 dict 列表（每个 dict 为大模型对该行的评测结果）
        """
        all_results: List[Dict] = []
        total = len(df)
        rows_dicts = df.to_dict(orient='records')
        batch_count = (total + batch_size - 1) // batch_size

        logger.info(
            f"共 {total} 条数据，分 {batch_count} 批"
            f"（每批最多 {batch_size} 条）调用大模型"
        )

        for batch_idx in range(batch_count):
            start      = batch_idx * batch_size
            end        = min(start + batch_size, total)
            batch_rows = rows_dicts[start:end]

            logger.info(
                f"  → 第 {batch_idx + 1}/{batch_count} 批"
                f"（行 {start + 1}-{end}）..."
            )

            try:
                messages     = self._build_batch_messages(prompt_template, batch_rows)
                raw_reply    = self._call_llm_api(messages)
                batch_result = self._extract_json_list(raw_reply, len(batch_rows))
            except Exception as e:
                logger.error(f"批次 {batch_idx + 1} 调用失败: {e}")
                batch_result = [self._error_item(str(e)) for _ in batch_rows]

            all_results.extend(batch_result)

        return all_results

    # ─── 结果合并 ─────────────────────────────────────────────────────────────

    @staticmethod
    def _merge_results(df_input, llm_results: List[Dict]):
        """
        将 LLM JSON 结果动态平行拼接到原始数据右侧（原则三：严禁硬编码列名）。

        大模型返回的 JSON 中有哪些 key，最终报告中就有哪些新列；
        框架不预设任何列名（score/result/reason 等均由大模型决定）。

        Args:
            df_input:    原始 DataFrame
            llm_results: 与 df_input 等长的 dict 列表

        Returns:
            合并后的 DataFrame
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("需要 pandas 库")

        df_llm    = pd.DataFrame(llm_results)
        df_merged = pd.concat(
            [df_input.reset_index(drop=True), df_llm.reset_index(drop=True)],
            axis=1
        )
        return df_merged

    # ─── 状态列识别 ───────────────────────────────────────────────────────────

    @staticmethod
    def _detect_status_col(df) -> Optional[str]:
        """
        智能识别 DataFrame 中的状态列（用于 Excel 着色和 Summary 通过率统计）。

        优先识别大模型写入的 result 列，其次扫描常见的状态列名关键字。

        Returns:
            列名字符串；若未找到返回 None
        """
        candidates = [
            'result', 'Result', 'RESULT',
            '是否通过', '状态', 'status', 'Status',
            'pass_fail', 'pass/fail', 'verdict', 'label',
        ]
        for col in candidates:
            if col in df.columns:
                return col
        return None

    # ─── Excel 报告生成 ───────────────────────────────────────────────────────

    def _generate_excel_report(self, df_merged, output_path: str,
                               total: int, pass_count: int, fail_count: int,
                               avg_score: float, status_col: Optional[str]) -> None:
        """
        生成包含 3 个 Sheet 的 Excel 报告：
          Sheet 1 — 汇总统计
          Sheet 2 — 评测详情（全量数据，状态列着色）
          Sheet 3 — 不及格详情（仅 result=fail 的行）
        """
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
            from openpyxl.utils import get_column_letter
        except ImportError:
            logger.warning("openpyxl 未安装，跳过 Excel 报告生成")
            return

        wb = openpyxl.Workbook()

        # ── 公共样式 ──
        header_font  = Font(bold=True, color="FFFFFF")
        header_fill  = PatternFill(start_color="4472C4", end_color="4472C4",
                                   fill_type="solid")
        pass_fill    = PatternFill(start_color="C6EFCE", end_color="C6EFCE",
                                   fill_type="solid")
        fail_fill    = PatternFill(start_color="FFC7CE", end_color="FFC7CE",
                                   fill_type="solid")
        fail_header_fill = PatternFill(start_color="C00000", end_color="C00000",
                                       fill_type="solid")
        center_align = Alignment(horizontal='center', vertical='center',
                                 wrap_text=True)
        thin_border  = Border(
            left=Side(style='thin'),  right=Side(style='thin'),
            top=Side(style='thin'),   bottom=Side(style='thin'),
        )

        pass_rate = (pass_count / total * 100) if total > 0 else 0.0
        model     = os.environ.get("DEEPSEEK_MODEL", DEFAULT_MODEL)

        # ── Sheet 1：汇总统计 ────────────────────────────────────────────────
        ws1 = wb.active
        ws1.title = "汇总统计"
        summary_rows = [
            ["指标",    "数值",                     "说明"],
            ["模型",    model,                      "使用的大模型"],
            ["总数",    total,                      "评测数据总条数"],
            ["通过数",  pass_count,                 f"score ≥ {PASS_THRESHOLD}"],
            ["不及格数", fail_count,                f"score < {PASS_THRESHOLD}"],
            ["通过率",  f"{pass_rate:.2f}%",        "通过数 / 总数"],
            ["平均分",  f"{avg_score:.2f}",         "所有评测结果的平均 score"],
        ]
        for r_idx, row in enumerate(summary_rows, 1):
            for c_idx, val in enumerate(row, 1):
                cell           = ws1.cell(row=r_idx, column=c_idx, value=val)
                cell.border    = thin_border
                cell.alignment = center_align
                if r_idx == 1:
                    cell.font = header_font
                    cell.fill = header_fill
        ws1.column_dimensions['A'].width = 12
        ws1.column_dimensions['B'].width = 18
        ws1.column_dimensions['C'].width = 28

        # ── Sheet 2：评测详情 ────────────────────────────────────────────────
        ws2 = wb.create_sheet("评测详情")
        cols = list(df_merged.columns)
        status_col_idx = (cols.index(status_col) + 1) if (
            status_col and status_col in cols
        ) else None

        for c_idx, col_name in enumerate(cols, 1):
            cell           = ws2.cell(row=1, column=c_idx, value=col_name)
            cell.font      = header_font
            cell.fill      = header_fill
            cell.border    = thin_border
            cell.alignment = center_align

        for r_idx, (_, row) in enumerate(df_merged.iterrows(), 2):
            is_pass = True
            if status_col and status_col in df_merged.columns:
                is_pass = str(row[status_col]).lower() == 'pass'
            for c_idx, col_name in enumerate(cols, 1):
                val            = str(row[col_name])
                cell           = ws2.cell(row=r_idx, column=c_idx, value=val)
                cell.border    = thin_border
                cell.alignment = center_align
                if c_idx == status_col_idx:
                    cell.fill = pass_fill if is_pass else fail_fill

        # 自动列宽（最大 50 字符）
        col_widths = self._calc_col_widths(df_merged, cols, max_width=50)
        for c_idx, width in enumerate(col_widths, 1):
            ws2.column_dimensions[get_column_letter(c_idx)].width = width

        # ── Sheet 3：不及格详情 ──────────────────────────────────────────────
        ws3 = wb.create_sheet("不及格详情")

        if status_col and status_col in df_merged.columns:
            df_fail = df_merged[df_merged[status_col].str.lower() == 'fail']
        else:
            df_fail = df_merged

        for c_idx, col_name in enumerate(cols, 1):
            cell           = ws3.cell(row=1, column=c_idx, value=col_name)
            cell.font      = header_font
            cell.fill      = fail_header_fill
            cell.border    = thin_border
            cell.alignment = center_align

        for r_idx, (_, row) in enumerate(df_fail.iterrows(), 2):
            for c_idx, col_name in enumerate(cols, 1):
                val            = str(row[col_name])
                cell           = ws3.cell(row=r_idx, column=c_idx, value=val)
                cell.border    = thin_border
                cell.alignment = center_align
                cell.fill      = fail_fill

        for c_idx, width in enumerate(col_widths, 1):
            ws3.column_dimensions[get_column_letter(c_idx)].width = width

        # ── 保存 ──
        parent = os.path.dirname(output_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        wb.save(output_path)
        logger.info(f"Excel 报告已生成: {output_path}")

    @staticmethod
    def _calc_col_widths(df, cols: List[str], max_width: int = 50) -> List[int]:
        """计算每列合适的显示宽度（表头长度与数据长度的最大值，上限 max_width）"""
        widths = []
        for col in cols:
            header_len = len(str(col))
            data_len = df[col].astype(str).str.len().max() if len(df) > 0 else 0
            widths.append(min(max(header_len, int(data_len)) + 2, max_width))
        return widths

    # ─── HTML 报告生成 ────────────────────────────────────────────────────────

    def generate_html_report(self, *args, **kwargs) -> Optional[str]:
        """
        实现基类抽象方法。

        调用签名:
            generate_html_report(df_merged, stats_dict)

        Returns:
            保存后的 HTML 绝对路径，或 None
        """
        df_merged  = args[0] if args else kwargs.get('df_merged')
        stats_dict = args[1] if len(args) > 1 else kwargs.get('stats_dict', {})
        if df_merged is None:
            return None
        html = self._build_eval_html(df_merged, stats_dict)
        return self.save_html_report(
            html, "llm_eval.html", "LLM 智能评测报告", "llm_eval"
        )

    def _build_eval_html(self, df_merged, stats_dict: dict) -> str:
        """构建完整的评测 HTML 报告（使用基类 build_html_page 统一风格）"""
        total      = stats_dict.get('total', len(df_merged))
        pass_count = stats_dict.get('pass_count', 0)
        fail_count = stats_dict.get('fail_count', 0)
        avg_score  = stats_dict.get('avg_score', 0.0)
        pass_rate  = (pass_count / total * 100) if total > 0 else 0.0
        status_col = stats_dict.get('status_col')

        # ── 汇总卡片 ──
        rate_cls = (
            'card-success'  if pass_rate >= 90 else
            'card-warning'  if pass_rate >= 80 else
            'card-failure'
        )

        def _card(value: str, label: str, css_cls: str = '') -> str:
            return (
                f'<div class="card {css_cls}">'
                f'<div class="card-value">{value}</div>'
                f'<div class="card-label">{label}</div></div>'
            )

        cards_html = (
            '<div class="summary-cards">'
            + _card(str(total),            '总数')
            + _card(str(pass_count),       '通过数',   'card-success')
            + _card(str(fail_count),       '不及格数', 'card-failure')
            + _card(f'{pass_rate:.2f}%',   '通过率',   rate_cls)
            + _card(f'{avg_score:.2f}',    '平均分',   'card-warning')
            + '</div>'
        )

        # ── 通用表格生成器 ──
        def _make_table(df_sub) -> str:
            if len(df_sub) == 0:
                return '<p style="padding:16px;color:#666">暂无数据</p>'
            sub_cols   = list(df_sub.columns)
            status_idx = (
                sub_cols.index(status_col)
                if status_col and status_col in sub_cols
                else None
            )
            thead = '<tr>' + ''.join(
                (
                    f'<th style="max-width:520px;width:520px;">{c}</th>'
                    if str(c).lower() == 'rounds'
                    else f'<th>{c}</th>'
                )
                for c in sub_cols
            ) + '</tr>'
            body_rows = []
            for _, row in df_sub.iterrows():
                tds = []
                for i, col in enumerate(sub_cols):
                    val = str(row[col])
                    if i == status_idx:
                        tag_cls = 'tag-pass' if val.lower() == 'pass' else 'tag-fail'
                        tds.append(f'<td><span class="{tag_cls}">{val}</span></td>')
                    elif str(col).lower() == 'rounds':
                        # rounds 列通常是长 JSON，限制列宽并允许换行，避免撑破表格布局
                        tds.append(
                            '<td style="max-width:520px;width:520px;white-space:pre-wrap;'
                            'word-break:break-all;overflow-wrap:anywhere;">'
                            f'{val}</td>'
                        )
                    else:
                        tds.append(f'<td>{val}</td>')
                body_rows.append('<tr>' + ''.join(tds) + '</tr>')
            return (
                f'<table class="report-table">'
                f'<thead>{thead}</thead>'
                f'<tbody>{"".join(body_rows)}</tbody>'
                f'</table>'
            )

        # ── 不及格子集 ──
        if status_col and status_col in df_merged.columns:
            df_fail = df_merged[df_merged[status_col].str.lower() == 'fail']
        else:
            df_fail = df_merged

        tab1_html = _make_table(df_merged)
        tab2_html = _make_table(df_fail)

        section_html = (
            '<div class="section">'
            '<div class="section-header">📋 评测详情</div>'
            '<div class="section-body">'
            '<div class="inner-tabs">'
            '<div class="inner-tab active" onclick="switchTab(this,\'lp1\')">全部结果</div>'
            '<div class="inner-tab" onclick="switchTab(this,\'lp2\')">不及格详情</div>'
            '</div>'
            f'<div id="lp1" class="inner-pane active">{tab1_html}</div>'
            f'<div id="lp2" class="inner-pane">{tab2_html}</div>'
            '</div></div>'
        )

        return self.build_html_page("LLM 智能评测报告", cards_html + section_html)

    # ─── 终端 Summary ─────────────────────────────────────────────────────────

    def _generate_summary(self, stats_dict: dict, output_path: str) -> str:
        """生成打印到终端的 Summary Box"""
        total      = stats_dict['total']
        pass_count = stats_dict['pass_count']
        fail_count = stats_dict['fail_count']
        avg_score  = stats_dict['avg_score']
        pass_rate  = (pass_count / total * 100) if total > 0 else 0.0
        model      = os.environ.get("DEEPSEEK_MODEL", DEFAULT_MODEL)

        lines = [
            f"*  模型:      {model}",
            f"*  总数:      {total}",
            f"*  通过数:    {pass_count}  (score ≥ {PASS_THRESHOLD})",
            f"*  不及格数:  {fail_count}  (score < {PASS_THRESHOLD})",
            f"*  通过率:    {pass_rate:.2f}%  ({pass_count}/{total})",
            f"*  平均分:    {avg_score:.2f}",
            f"*  详细报告:  {output_path}",
        ]
        return self.format_summary_box("LLM", "\n".join(lines), width=90)

    # ─── 主入口 ───────────────────────────────────────────────────────────────

    def execute(self, params: list, output_report: str = None) -> str:
        """
        执行 LLM 批量评测。

        完整流程：
          1. 解析 DSL 参数
          2. 加载数据 CSV 和 Prompt 模板
          3. 分批调用大模型
          4. 提取 JSON → 平行拼接到原始数据右侧
          5. 统计通过率/平均分
          6. 生成 Excel + HTML 报告（allure_result/mango_report/ + 本地副本）
          7. 返回终端 Summary 字符串

        Args:
            params:        DSL 参数列表（如 ["result=x.csv", "prompt=p.txt", "batch=10"]）
            output_report: 外部传入的默认报告路径（可被 params 中 output= 覆盖）

        Returns:
            str: 终端 Summary 字符串
        """
        result_file, prompt_file, xlsx_path, batch_size = self._parse_params(
            params, output_report
        )

        if not os.path.exists(result_file):
            raise FileNotFoundError(f"数据文件不存在: {result_file}")

        df_input        = self._load_data(result_file)
        prompt_template = self._load_prompt_template(prompt_file)

        # ── 批量评测 ──
        llm_results = self._run_evaluation(df_input, prompt_template, batch_size)

        # ── 动态列展开拼接（原则三） ──
        df_merged = self._merge_results(df_input, llm_results)

        # ── 统计 ──
        status_col = self._detect_status_col(df_merged)
        score_col  = 'score' if 'score' in df_merged.columns else None

        if status_col:
            pass_count = int((df_merged[status_col].str.lower() == 'pass').sum())
            fail_count = int((df_merged[status_col].str.lower() == 'fail').sum())
        else:
            pass_count = fail_count = 0

        avg_score = 0.0
        if score_col:
            try:
                avg_score = float(df_merged[score_col].astype(float).mean())
            except Exception:
                pass

        total = len(df_merged)
        stats_dict = {
            'total':      total,
            'pass_count': pass_count,
            'fail_count': fail_count,
            'avg_score':  avg_score,
            'status_col': status_col,
        }

        # ── 生成 Excel 报告 ──
        self._generate_excel_report(
            df_merged, xlsx_path,
            total, pass_count, fail_count, avg_score, status_col
        )

        # ── 生成 HTML 报告（写入 allure_result/mango_report/...） ──
        html_content = self._build_eval_html(df_merged, stats_dict)
        self.save_html_report(
            html_content, "llm_eval.html", "LLM 智能评测报告", "llm_eval"
        )

        # ── 本地 HTML 副本（与 xlsx 同目录，方便直接查看） ──
        local_html = os.path.splitext(xlsx_path)[0] + '.html'
        html_parent = os.path.dirname(local_html)
        if html_parent:
            os.makedirs(html_parent, exist_ok=True)
        with open(local_html, 'w', encoding='utf-8') as f:
            f.write(html_content)
        logger.info(f"本地 HTML 报告已生成: {local_html}")

        return self._generate_summary(stats_dict, xlsx_path)


# ── 命令行独立运行入口 ────────────────────────────────────────────────────────

def main():
    """
    命令行独立运行入口。

    使用示例:
        python3 src/testsuite/NANO/tools/tsr/llm.py \\
            -r test_result.csv -p eval_prompts.txt

        python3 src/testsuite/NANO/tools/tsr/llm.py \\
            -r test_result.csv -p eval_prompts.txt -o /tmp/report.xlsx -b 5
    """
    import argparse

    parser = argparse.ArgumentParser(
        description='LLM 离线批量评测工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 %(prog)s -r test_result.csv -p eval_prompts.txt
  python3 %(prog)s -r test_result.csv -p eval_prompts.txt -o report.xlsx -b 5

环境变量:
  DEEPSEEK_API_KEY   API 密钥（必须）
  DEEPSEEK_API_URL   API 地址（可选，默认 DeepSeek 官方地址）
  DEEPSEEK_MODEL     模型名称（可选，默认 deepseek-chat）

Prompt 模板示例（eval_prompts.txt）:
  请评测以下语音识别结果是否正确：
  用户说：{asr_text}
  参考答案：{ref_text}
  NLU 意图：{intent}
        """
    )
    parser.add_argument('-r',  '--result', required=True,
                        help='待评测数据文件路径（.csv 或 .jsonl）')
    parser.add_argument('-p',  '--prompt', required=True,
                        help='Prompt 模板文件路径')
    parser.add_argument('-o',  '--output', default=None,
                        help='Excel 报告输出路径（默认：当前目录/mango_report/llm_eval.xlsx）')
    parser.add_argument('-b',  '--batch',  type=int, default=10,
                        help='每批数据条数（默认 10）')
    args = parser.parse_args()

    params = [
        f"result={args.result}",
        f"prompt={args.prompt}",
        f"batch={args.batch}",
    ]
    if args.output:
        params.append(f"output={args.output}")

    handler = LLMEvalHandler(config=None)
    try:
        summary = handler.execute(params)
        print(summary)
    except FileNotFoundError as e:
        print(f"错误: {e}")
        raise SystemExit(1)
    except ValueError as e:
        print(f"参数错误: {e}")
        raise SystemExit(1)
    except Exception as e:
        print(f"执行失败: {e}")
        import traceback
        traceback.print_exc()
        raise SystemExit(1)


if __name__ == "__main__":
    main()
