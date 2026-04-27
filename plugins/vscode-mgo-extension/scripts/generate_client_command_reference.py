#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
根据 nano-dsl-schema.json 生成按客户端拆分的命令参考文档。
"""

from __future__ import annotations

import json
from pathlib import Path


EXT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_JSON = EXT_ROOT / "metadata" / "nano-dsl-schema.json"
OUTPUT_MD = REPO_ROOT / "src/testsuite/NANO/doc/NANO_DSL_CLIENT_COMMAND_REFERENCE.md"


MANUAL_OVERRIDES = {
    ("TSA", "INPUTEVENT"): {
        "summary": "发送输入事件，用于注入技能执行所需的外部上下文。",
        "syntax": "[TSA]INPUTEVENT event_name",
        "params": [
            {"name": "event_name", "description": "事件名称，如 VehicleInfo、NaviLocationStatus、NavigateStatus。"}
        ],
        "example": "[TSA]INPUTEVENT VehicleInfo\n[TSA]INPUTEVENT NaviLocationStatus",
    },
    ("TSA", "CALLBACK"): {
        "summary": "主动注入回调数据，常用于多轮对话、搜索结果、事件驱动测试等场景。",
        "syntax": "[TSA]CALLBACK callback_name [field_path:value ...]",
        "params": [
            {"name": "callback_name", "description": "回调名称，常见为 default。"},
            {"name": "field_path:value", "description": "可选，按字段路径注入返回值或文件数据。"},
        ],
        "example": "[TSA]CALLBACK default\n[TSA]CALLBACK default data.result.code:0",
    },
    ("SYS", "CLEAR_ASSERT"): {
        "summary": "清空断言上下文，防止历史回调或 API 结果污染后续断言。",
        "syntax": "[SYS]CLEAR_ASSERT [type]",
        "params": [
            {"name": "type", "description": "可选。支持 ALL、CALLBACK、API 或具体断言类型名。"},
        ],
        "example": "[SYS]CLEAR_ASSERT\n[SYS]CLEAR_ASSERT CALLBACK\n[SYS]CLEAR_ASSERT cloudASRResult",
    },
    ("SYS", "BREF"): {
        "summary": "写入分段说明文本，常用于报告或日志中的步骤标记。",
        "syntax": "[SYS]BREF text",
        "params": [
            {"name": "text", "description": "分段标题或说明文本。"},
        ],
        "example": "[SYS]BREF \"1. 基础关键字搜索 (SEARCH Mode)\"",
    },
    ("EXP", "LOG"): {
        "summary": "日志断言入口，支持 SEARCH、MATCH、DIFF 三种模式。",
        "syntax": "[EXP]LOG file mode args...",
        "params": [
            {"name": "file", "description": "日志文件名或路径。"},
            {"name": "mode", "description": "SEARCH、MATCH 或 DIFF。"},
            {"name": "args", "description": "各模式对应的参数组合。"},
        ],
        "example": "[EXP]LOG app.log SEARCH \"TagA\" EXISTS\n[EXP]LOG app.log MATCH \"LoginSuccess\" KV \"user\" == \"admin\"\n[EXP]LOG app.log DIFF \"Req\" \"Resp\" < 500ms",
    },
    ("EXP", "SUM"): {
        "summary": "统计某类回调在指定通道内出现的次数，并进行数量断言。",
        "syntax": "[EXP]SUM [channel]callbackType COUNT operator value",
        "params": [
            {"name": "channel", "description": "可选，支持单通道或多通道列表。"},
            {"name": "callbackType", "description": "回调类型，如 ASRResult。"},
            {"name": "operator value", "description": "数量比较条件，如 == 1。"},
        ],
        "example": "[EXP]SUM [0]ASRResult COUNT == 1\n[EXP]SUM ASRResult COUNT == 1",
    },
}


def get_doc(schema: dict, client: str, command: str) -> dict:
    override = MANUAL_OVERRIDES.get((client, command))
    if override:
        return override

    by_client = schema.get("commandDocsByClient", {}).get(client, {})
    if command in by_client:
        return by_client[command]

    by_name = schema.get("commandDocsByName", {})
    if command in by_name:
        return by_name[command]

    if client == "EXP":
        return {
            "summary": "断言类型或特殊断言命令。",
            "syntax": f"[EXP]{command}",
            "params": [],
            "example": f"[EXP]{command}",
        }

    return {
        "summary": "文档待补充。",
        "syntax": f"[{client}]{command}",
        "params": [],
        "example": f"[{client}]{command}",
    }


def render_params(params: list[dict]) -> str:
    if not params:
        return "- 无特殊参数说明。"

    lines = []
    for item in params:
        name = item.get("name", "").strip()
        desc = item.get("description", "").strip()
        if name:
            lines.append(f"- `{name}`：{desc}")
        else:
            lines.append(f"- {desc}")
    return "\n".join(lines)


def render_client_section(schema: dict, client: str, commands: list[str]) -> str:
    lines = [f"## Client `{client}`", ""]
    for command in commands:
        doc = get_doc(schema, client, command)
        lines.append(f"### Command `{command}`")
        lines.append("")
        lines.append(f"**作用**: {doc.get('summary', '文档待补充。')}")
        lines.append("")
        lines.append(f"**语法**: `{doc.get('syntax', f'[{client}]{command}')}`")
        lines.append("")
        lines.append("**参数说明**:")
        lines.append(render_params(doc.get("params", [])))
        lines.append("")
        lines.append("**示例**:")
        lines.append("```dsl")
        lines.append(doc.get("example", f"[{client}]{command}"))
        lines.append("```")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    schema = json.loads(SCHEMA_JSON.read_text(encoding="utf-8"))
    lines = [
        "# NANO DSL 客户端命令参考",
        "",
        "本文档按客户端拆分 NANO DSL 的命令说明，用于 VSCode Hover、补全说明和人工查阅。",
        "",
        "说明：",
        "",
        "- 若同名命令在不同客户端下语义不同，这里分别写出各自说明。",
        "- 若当前项目文档缺失，则保留 `文档待补充`，后续可继续完善。",
        "",
    ]

    for client in schema["clients"]:
        if client == "EXP":
            commands = schema.get("assertions", [])
        else:
            commands = schema.get("commandsByClient", {}).get(client, [])
        lines.append(render_client_section(schema, client, commands))

    OUTPUT_MD.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"已生成: {OUTPUT_MD}")


if __name__ == "__main__":
    main()
