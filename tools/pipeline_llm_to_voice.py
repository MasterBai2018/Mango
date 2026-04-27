# -*- coding: utf-8 -*-
import os
import requests
import csv
import json
import sqlite3
from datetime import datetime
from typing import List, Optional, Iterable, Tuple


class LLMToVoiceTools:
    def __init__(self):
        self.api_url = "https://api.deepseek.com/v1/chat/completions"
        self.model = "deepseek-chat"
        # 优先从环境变量读取，避免硬编码泄露
        self.api_key = "sk-63d98415f2164aabb3984d149a77eb9e"
        self.pass_threshold = 60
        self.sqlte_path = "TestAudio/llm_asr_data/audio_data.db"
        self.default_prompt = """
## 角色定义
你是一款智能语音识别大模型（ASR），专为车载出行助手设计。

## 任务描述
你将收到用户输入的excel表，你需要理解文本的意图，并泛化生成相应的语音指令，每个生成泛化发话30条。

## 输出格式
你需要返回一个语音指令，格式为json格式，包含以下字段：
{
    "base_voice_command": "今天天气怎么样",
    "泛化语音指令": "北京今天天气怎么样？"
}
```
        """

    def set_api_key(self, api_key):
        self.api_key = api_key

    def set_model(self, model):
        self.model = model

    def set_pass_threshold(self, pass_threshold):
        self.pass_threshold = pass_threshold

    def set_api_url(self, api_url):
        self.api_url = api_url

    def _build_messages(self, user_text: str, extra_instruction: Optional[str] = None):
        system_prompt = self.default_prompt.strip()
        if extra_instruction:
            system_prompt = f"{system_prompt}\n\n{extra_instruction.strip()}"
        return [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"请根据以下原始发话，输出符合规范的语音指令：\n原始发话：{user_text}",
            },
        ]

    def _call_llm(self, messages: List[dict], temperature: float = 0.2, timeout: int = 60) -> str:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        resp = requests.post(self.api_url, headers=headers, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not content:
            raise RuntimeError(f"LLM返回为空：{data}")
        return content.strip()

    def _parse_model_output(self, content: str) -> dict:
        """
        {
            "base_voice_command": "...",
            "泛化语音指令": ["...", "..."]
        }
        """
        text = (content or "").strip()
        # 去除可能的代码围栏
        if text.startswith("```"):
            parts = text.split("```")
            if len(parts) >= 2:
                text = parts[1].strip()

        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = text[start : end + 1]
            try:
                obj = json.loads(candidate)
                # 兼容：如果模型把泛化语音指令输出成字符串，包成列表
                if isinstance(obj, dict) and "泛化语音指令" in obj and isinstance(obj["泛化语音指令"], str):
                    obj["泛化语音指令"] = [obj["泛化语音指令"]]
                return obj
            except Exception:
                pass

        # 兜底：尝试提取为字符串原样保留
        return {"raw": text}

    def generate_from_utterances(
        self,
        utterances: Iterable[str],
        output_path: str,
        output_format: str = "txt",
        extra_instruction: Optional[str] = None,
        skip_empty: bool = True,
        return_records: bool = False,
    ) -> Tuple[int, int, Optional[List[dict]]]:
        """
        根据发话列表逐条调用LLM生成case，并输出到指定格式文件。
        返回 (总条数, 成功条数)。
        - txt：原始发话\t生成指令
        - json：数组，每项 {original, result, success, error?}
        - jsonl：逐行JSON
        """
        total = 0
        success = 0
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        fmt = (output_format or "txt").lower()
        records = []

        def build_record(original_text: str, parsed_result: Optional[dict], err: Optional[str]) -> dict:
            return {
                "original": original_text,
                "result": parsed_result,
                "success": err is None,
                "error": None if err is None else str(err),
            }

        for raw in utterances:
            total += 1
            text = (raw or "").strip()
            if not text and skip_empty:
                continue
            try:
                messages = self._build_messages(text, extra_instruction)
                content = self._call_llm(messages)
                parsed = self._parse_model_output(content)
                records.append(build_record(text, parsed, None))
                success += 1
            except Exception as e:
                records.append(build_record(text, None, str(e)))

        if fmt == "txt":
            with open(output_path, "w", encoding="utf-8") as fout:
                fout.write("原始发话\t生成指令\n")
                for rec in records:
                    if rec.get("success"):
                        fout.write(f"{rec['original']}\t{json.dumps(rec['result'], ensure_ascii=False)}\n")
                    else:
                        fout.write(f"{rec['original']}\tERROR: {rec.get('error')}\n")
        elif fmt == "json":
            with open(output_path, "w", encoding="utf-8") as fout:
                json.dump(records, fout, ensure_ascii=False, indent=2)
        elif fmt == "jsonl":
            with open(output_path, "w", encoding="utf-8") as fout:
                for rec in records:
                    fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
        else:
            raise ValueError("不支持的输出格式：请使用 txt | json | jsonl")

        if return_records:
            return total, success, records
        return total, success, None

    def _ensure_db(self):
        os.makedirs(os.path.dirname(self.sqlte_path) or ".", exist_ok=True)
        conn = sqlite3.connect(self.sqlte_path)
        try:
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tts_audio'")
            exists = cur.fetchone() is not None
            if not exists:
                cur.execute(
                    """
                    CREATE TABLE tts_audio (
                        text TEXT PRIMARY KEY,
                        voice TEXT NOT NULL,
                        voice_path TEXT NOT NULL,
                        emotion TEXT NOT NULL,
                        gender TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                conn.commit()
        finally:
            conn.close()

    def _db_get_audio_path(self, text_value: str, voice: Optional[str] = None) -> Optional[str]:
        conn = sqlite3.connect(self.sqlte_path)
        try:
            cur = conn.cursor()
            if voice:
                cur.execute("SELECT voice_path FROM tts_audio WHERE text = ? AND voice = ?", (text_value, voice))
            else:
                cur.execute("SELECT voice_path FROM tts_audio WHERE text = ?", (text_value,))
            row = cur.fetchone()
            if not row:
                return None
            path = row[0]
            if not path or not os.path.exists(path):
                return None
            return path
        finally:
            conn.close()

    def _db_insert_audio(self, text_value: str, voice: str, audio_path: str, emotion: str = "neutral", gender: str = "unknown"):
        conn = sqlite3.connect(self.sqlte_path)
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT OR REPLACE INTO tts_audio(text, voice, voice_path, emotion, gender) VALUES(?,?,?,?,?)",
                (text_value, voice, audio_path, emotion, gender),
            )
            conn.commit()
        finally:
            conn.close()

    def load_utterances_from_file(
        self,
        input_path: str,
        column: Optional[str] = None,
        sheet_name: Optional[str] = None,
        limit: Optional[int] = None,
        row_start: Optional[int] = None,
        row_end: Optional[int] = None,
    ) -> List[str]:
        """
        支持CSV与Excel（.xlsx/.xls）。优先无依赖的CSV；Excel使用pandas（若不可用则报错）。
        - column 为None：CSV默认第一列；Excel默认第一列。
        - limit：仅取前N行，便于抽样。
        - row_start/row_end：仅取数据行范围（不含表头），从1开始计数；两者都为None则不截取。
        """
        path_lower = input_path.lower()
        utterances: List[str] = []
        # 将用户传入的“数据行（从1开始）”转换为 0-based 的切片区间：[start_idx, end_exclusive)
        # 例如：row_start=1,row_end=10 => 取前10条数据，即 indices [0..9]，exclusive=10
        start_idx = (row_start - 1) if row_start is not None else None
        end_exclusive = row_end if row_end is not None else None
        if start_idx is not None and end_exclusive is not None and end_exclusive < start_idx + 1:
            raise ValueError("row_end 不能小于 row_start。")

        if path_lower.endswith(".csv"):
            with open(input_path, "r", encoding="utf-8-sig") as fin:
                reader = csv.DictReader(fin)
                fieldnames = reader.fieldnames or []
                use_col = column or (fieldnames[0] if fieldnames else None)
                if use_col is None:
                    # 无表头，尝试普通读取
                    fin.seek(0)
                    raw_reader = csv.reader(fin)
                    for i, row in enumerate(raw_reader):
                        if start_idx is not None and i < start_idx:
                            continue
                        if end_exclusive is not None and i >= end_exclusive:
                            break
                        if limit is not None and len(utterances) >= limit:
                            break
                        if not row:
                            continue
                        utterances.append(row[0])
                    return utterances
                for i, row in enumerate(reader):
                    if start_idx is not None and i < start_idx:
                        continue
                    if end_exclusive is not None and i >= end_exclusive:
                        break
                    if limit is not None and len(utterances) >= limit:
                        break
                    utterances.append(str(row.get(use_col, "")).strip())
            return utterances
        elif path_lower.endswith(".xlsx") or path_lower.endswith(".xls"):
            try:
                import pandas as pd  # type: ignore
            except Exception as e:
                raise RuntimeError("读取Excel需要安装pandas与openpyxl，请先安装依赖。") from e
            df = pd.read_excel(input_path, sheet_name=sheet_name)  # type: ignore
            if start_idx is not None or end_exclusive is not None:
                # df.iloc 的 end 是 exclusive；而 end_exclusive 恰好就是用户的 row_end
                df = df.iloc[start_idx or 0 : end_exclusive]
            if column is None:
                use_col = df.columns[0]
            else:
                use_col = column
            series = df[use_col].astype(str)
            if limit is not None:
                series = series.head(limit)
            utterances = [s.strip() for s in series.tolist()]
            return utterances
        else:
            raise ValueError("仅支持CSV或Excel文件（.csv/.xlsx/.xls）。")


def _build_cli():
    import argparse

    parser = argparse.ArgumentParser(
        description="根据发话一览生成泛化语音指令并输出为TXT/JSON/JSONL"
    )
    parser.add_argument(
        "--input",
        required=True,
        help="输入文件路径，支持 .csv/.xlsx/.xls",
    )
    parser.add_argument(
        "--output",
        required=False,
        default="out.json",
        help="输出文件路径，例如 output/cases.txt 或 cases.json（默认 out.json）",
    )
    parser.add_argument(
        "--output-format",
        dest="output_format",
        choices=["txt", "json", "jsonl"],
        default="txt",
        help="输出格式：txt|json|jsonl（默认txt）",
    )
    parser.add_argument(
        "--column",
        default="中文句式",
        help="指定输入表中的列名（默认：中文句式）",
    )
    parser.add_argument(
        "--sheet",
        default="1-多媒体",
        help="Excel工作表名（默认：1-多媒体）",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="仅处理前N条，便于抽样/调试",
    )
    parser.add_argument(
        "--row",
        default=None,
        help="仅取数据行范围（不含表头，数据行从1开始，包含两端），例如：--row 8-9",
    )
    parser.add_argument(
        "--tts-output",
        default="tts_out",
        help="若不为空，则集成 RequestIndexTTS 生成 index_tts 音频（输出目录，默认 tts_out）",
    )
    parser.add_argument(
        "--tts-voice-type",
        default="random",
        help="index_tts 的参考音色参数（默认：random，对应 RequestIndexTTS --voice_type）",
    )
    parser.add_argument(
        "--tts-scp",
        action="store_true",
        help="是否生成参考 scp/text.ref（对应 RequestIndexTTS --scp）",
    )
    parser.add_argument(
        "--tts-silence",
        type=int,
        default=800,
        help="index_tts 前后静音时长（ms），对应 RequestIndexTTS --silence",
    )
    parser.add_argument(
        "--tts-threads",
        type=int,
        default=2,
        help="index_tts 线程数，对应 RequestIndexTTS read_file_list max_workers",
    )
    parser.add_argument(
        "--tts-retry",
        type=int,
        default=1,
        help="index_tts 重试次数，对应 RequestIndexTTS --retry",
    )
    parser.add_argument(
        "--tts-source",
        default="cases",
        choices=["base", "cases"],
        help="从 LLM 结果提取要合成的文本：base=base_voice_command，cases=泛化语音指令",
    )
    parser.add_argument(
        "--tts-max-per-base",
        type=int,
        default=None,
        help="每条 base_voice_command 最多合成前N条泛化语音（仅在 tts-source=cases 生效）",
    )
    parser.add_argument(
        "--tts-limit",
        type=int,
        default=None,
        help="总共最多合成前N条文本（防止太多），不传则全量",
    )
    parser.add_argument(
        "--extra-instruction",
        dest="extra_instruction",
        default=None,
        help="附加给系统prompt的补充指令",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="覆盖默认模型，例如 deepseek-chat",
    )
    parser.add_argument(
        "--api-url",
        dest="api_url",
        default=None,
        help="覆盖默认API地址，默认 https://api.deepseek.com/v1/chat/completions",
    )
    parser.add_argument(
        "--api-key",
        dest="api_key",
        default=None,
        help="覆盖API KEY",
    )
    return parser


def main():
    parser = _build_cli()
    args = parser.parse_args()

    def parse_row_range(row_str: Optional[str]) -> Tuple[Optional[int], Optional[int]]:
        if not row_str:
            return None, None
        s = str(row_str).strip()
        if "-" in s:
            left, right = s.split("-", 1)
            start = int(left.strip())
            end = int(right.strip())
            if end < start:
                raise ValueError("--row 格式错误：结束行号不能小于开始行号")
            return start, end
        start = int(s)
        return start, start

    row_start, row_end = parse_row_range(args.row)

    tool = LLMToVoiceTools()
    if args.api_key:
        tool.set_api_key(args.api_key)
    if args.model:
        tool.set_model(args.model)
    if args.api_url:
        tool.set_api_url(args.api_url)

    utterances = tool.load_utterances_from_file(
        input_path=args.input,
        column=args.column,
        sheet_name=args.sheet,
        limit=args.limit,
        row_start=row_start,
        row_end=row_end,
    )

    want_tts = args.tts_output is not None
    total, success, records = tool.generate_from_utterances(
        utterances=utterances,
        output_path=args.output,
        output_format=args.output_format,
        extra_instruction=args.extra_instruction,
        return_records=want_tts,
    )
    print(f"完成：总数={total}，成功={success}，输出文件={args.output}")

    if want_tts:
        if not args.tts_voice_type:
            raise ValueError("集成合成需要提供 --tts-voice-type（对应 RequestIndexTTS 的 voice_type 参数）。")
        if records is None:
            raise RuntimeError("内部错误：tts 模式下 records 未返回。")

        tts_texts: List[str] = []
        for rec in records:
            if not rec.get("success"):
                continue
            parsed = rec.get("result") or {}
            if args.tts_source == "base":
                base = parsed.get("base_voice_command", "")
                if base:
                    tts_texts.append(str(base).strip())
            else:
                cases = parsed.get("泛化语音指令", [])
                if isinstance(cases, str):
                    cases = [cases]
                if not isinstance(cases, list):
                    continue
                if args.tts_max_per_base is not None:
                    cases = cases[: args.tts_max_per_base]
                for c in cases:
                    c2 = str(c).strip()
                    if c2:
                        tts_texts.append(c2)
            if args.tts_limit is not None and len(tts_texts) >= args.tts_limit:
                tts_texts = tts_texts[: args.tts_limit]
                break

        if not tts_texts:
            print("tts_texts 为空：跳过音频合成。")
            return
        try:
            from RequestIndexTTS import RequestIndexTTS as IndexTTS
        except Exception as e:
            raise RuntimeError(f"导入 RequestIndexTTS 失败：{e}") from e

        tool = LLMToVoiceTools()
        tool._ensure_db()

        os.makedirs(args.tts_output, exist_ok=True)

        existing_count = 0
        missing_texts: List[str] = []
        for txt in tts_texts:
            audio_path = tool._db_get_audio_path(txt, voice=args.tts_voice_type)
            if audio_path:
                existing_count += 1
            else:
                missing_texts.append(txt)

        generated_count = 0
        if missing_texts:
            force_scp = True
            tmp_txt = os.path.join(args.tts_output, "tts_texts.missing.txt")
            with open(tmp_txt, "w", encoding="utf-8") as f:
                for t in missing_texts:
                    f.write(t + "\n")

            tts_tool = IndexTTS(args.tts_output, force_scp or args.tts_scp, args.tts_silence, args.tts_retry)
            tts_tool.set_reference(args.tts_voice_type)
            tts_tool.read_file_list(tmp_txt, max_workers=args.tts_threads)

            scp_candidates = [
                os.path.join(args.tts_output, "scp"),
                os.path.join(args.tts_output, "text.scp"),
            ]
            textref_path = os.path.join(args.tts_output, "text.ref")
            utt_to_path = {}
            path_to_text = {}
            utt_to_text = {}

            for scp_path in scp_candidates:
                if os.path.exists(scp_path):
                    with open(scp_path, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if not line:
                                continue
                            parts = line.split(None, 1)
                            if len(parts) == 2:
                                utt_to_path[parts[0]] = parts[1]
                    break
            if os.path.exists(textref_path):
                with open(textref_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.rstrip("\n")
                        if not line:
                            continue
                        if "\t" in line:
                            path_part, text_part = line.split("\t", 1)
                            path_to_text[path_part.strip()] = text_part.strip()
                        else:
                            parts = line.split(None, 1)
                            if len(parts) == 2:
                                utt_to_text[parts[0]] = parts[1].strip()

            text_to_path = {}
            if path_to_text:
                for path_val, text_val in path_to_text.items():
                    if text_val in missing_texts:
                        text_to_path[text_val] = path_val
            elif utt_to_text and utt_to_path:
                for utt, text_val in utt_to_text.items():
                    path_val = utt_to_path.get(utt)
                    if path_val and text_val in missing_texts:
                        text_to_path[text_val] = path_val

            for text_val, path_val in text_to_path.items():
                try:
                    tool._db_insert_audio(text_val, args.tts_voice_type, path_val)
                    generated_count += 1
                except Exception as e:
                    print(f"写入数据库失败：{text_val} -> {path_val}，错误：{e}")

        print(
            f"tts 合成完成：总输入条数={len(tts_texts)}，已存在复用={existing_count}，新增合成入库={generated_count}，输出目录={args.tts_output}"
        )


if __name__ == "__main__":
    main()