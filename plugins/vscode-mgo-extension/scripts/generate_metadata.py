#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 Mango 项目源码中提取 NANO DSL 元数据，供 VSCode 扩展复用。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List


REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PY = REPO_ROOT / "src/testsuite/NANO/config.py"
ASSERT_YAML = REPO_ROOT / "conf/assert_key_value.yaml"
STATUS_PY = REPO_ROOT / "src/core/Status/AIBSSessionStatus.py"
SPEECH_ENGINE_CLIENT_PY = REPO_ROOT / "src/testsuite/NANO/client/SpeechEngineClient.py"
TSS_CLIENT_PY = REPO_ROOT / "src/testsuite/NANO/client/TSSClient.py"
COMMAND_MD = REPO_ROOT / "src/testsuite/NANO/doc/COMMAND.md"
CLIENT_COMMAND_REFERENCE_MD = REPO_ROOT / "src/testsuite/NANO/doc/NANO_DSL_CLIENT_COMMAND_REFERENCE.md"
OUTPUT_JSON = Path(__file__).resolve().parents[1] / "metadata" / "nano-dsl-schema.json"


def unique_preserve_order(items: List[str]) -> List[str]:
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def extract_string_list(list_body: str) -> List[str]:
    return re.findall(r"'([^']+)'", list_body)


def normalize_inline_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def strip_markdown_wrappers(text: str) -> str:
    text = text.strip()
    wrappers = [("**`", "`**"), ("**", "**"), ("`", "`")]
    changed = True
    while changed and text:
        changed = False
        for prefix, suffix in wrappers:
            if text.startswith(prefix) and text.endswith(suffix) and len(text) > len(prefix) + len(suffix):
                text = text[len(prefix) : len(text) - len(suffix)].strip()
                changed = True
    return text


def extract_block(src: str, start_marker: str) -> str:
    start = src.index(start_marker)
    brace_start = src.index("{", start)
    depth = 0
    for idx in range(brace_start, len(src)):
        ch = src[idx]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return src[brace_start : idx + 1]
    raise ValueError(f"未找到完整代码块: {start_marker}")


def parse_environment_variables(config_src: str) -> List[str]:
    block = extract_block(config_src, "ENVIRONMENT_VARIABLES =")
    return re.findall(r"'([A-Z][A-Z0-9_]*)'\s*:", block)


def parse_assert_code_types(config_src: str) -> List[str]:
    match = re.search(r"AssertCodeTypeList\s*=\s*\[(.*?)\]\s*", config_src, re.DOTALL)
    if not match:
        raise ValueError("未找到 AssertCodeTypeList")
    return unique_preserve_order(extract_string_list(match.group(1)))


def parse_file_assertions(config_src: str) -> List[str]:
    match = re.search(r"FILE_ASSERT_COMMANDS\s*=\s*\[(.*?)\]\s*", config_src, re.DOTALL)
    if not match:
        raise ValueError("未找到 FILE_ASSERT_COMMANDS")
    return unique_preserve_order(extract_string_list(match.group(1)))


def parse_client_commands(config_src: str) -> Dict[str, List[str]]:
    block = extract_block(config_src, "CLIENT_COMMANDS =")
    client_commands: Dict[str, List[str]] = {}

    for client, list_body in re.findall(r"'([A-Z]+)'\s*:\s*\[(.*?)\]", block, re.DOTALL):
        if client == "EXP":
            continue
        client_commands[client] = unique_preserve_order(extract_string_list(list_body))

    return client_commands


def parse_assertions_from_yaml(yaml_text: str) -> List[str]:
    results: List[str] = []
    for line in yaml_text.splitlines():
        if not line or line.startswith(" ") or line.startswith("\t") or line.lstrip().startswith("#"):
            continue
        match = re.match(r"^([A-Za-z0-9_-]+):\s*$", line)
        if match:
            results.append(match.group(1))
    return unique_preserve_order(results)


def parse_vr_configs(status_src: str) -> List[str]:
    items = re.findall(r"AIBS_SETTING_([A-Z0-9_]+)\s*=", status_src)
    return unique_preserve_order(items)


def parse_command_docs(command_md: str, client_commands: Dict[str, List[str]]) -> Dict[str, Dict[str, dict]]:
    command_docs_by_client: Dict[str, Dict[str, dict]] = {client: {} for client in client_commands.keys()}
    command_docs_by_name: Dict[str, dict] = {}

    heading_matches = list(re.finditer(r"^### ([A-Z_]+) - (.+)$", command_md, re.MULTILINE))
    all_clients = list(client_commands.keys()) + ["EXP"]

    def infer_clients(command: str, syntax: str) -> List[str]:
        explicit_clients = []
        for client in all_clients:
            if f"[{client}]" in syntax:
                explicit_clients.append(client)
        if explicit_clients:
            return explicit_clients
        if "[VOI客户端]" in syntax:
            return ["VOI"]
        if "[客户端]" in syntax:
            return [client for client, commands in client_commands.items() if command in commands]
        return [client for client, commands in client_commands.items() if command in commands]

    for idx, match in enumerate(heading_matches):
        command = match.group(1)
        summary = match.group(2).strip()
        start = match.end()
        end = heading_matches[idx + 1].start() if idx + 1 < len(heading_matches) else len(command_md)
        body = command_md[start:end]

        syntax_match = re.search(r"\*\*语法\*\*:\s*`([^`]+)`", body)
        syntax = syntax_match.group(1).strip() if syntax_match else ""

        params_block_match = re.search(r"\*\*参数说明\*\*:\s*(.*?)(?:\n\*\*|\n### |\Z)", body, re.DOTALL)
        params = []
        if params_block_match:
            for line in params_block_match.group(1).splitlines():
                line = line.strip()
                if not line.startswith("-"):
                    continue
                param_match = re.match(r"-\s+`?([^`：:]+)`?\s*[：:]\s*(.+)", line)
                if param_match:
                    params.append({
                        "name": param_match.group(1).strip(),
                        "description": param_match.group(2).strip(),
                    })
                else:
                    params.append({
                        "name": "",
                        "description": line[1:].strip(),
                    })

        example_match = re.search(r"\*\*使用示例\*\*:\s*```(?:dsl|text)?\n(.*?)\n```", body, re.DOTALL)
        example = ""
        if example_match:
            example_lines = [line.rstrip() for line in example_match.group(1).splitlines() if line.strip()]
            example = "\n".join(example_lines[:4])

        doc = {
            "summary": summary,
            "syntax": syntax,
            "params": params,
            "example": example,
        }

        if command not in command_docs_by_name:
            command_docs_by_name[command] = doc

        for client in infer_clients(command, syntax):
            command_docs_by_client.setdefault(client, {})
            if command not in command_docs_by_client[client]:
                command_docs_by_client[client][command] = doc

    return {
        "byClient": command_docs_by_client,
        "byName": command_docs_by_name,
    }


def extract_markdown_section(body: str, title: str) -> str:
    match = re.search(
        rf"^\*\*{re.escape(title)}\*\*:\s*(.*?)(?=^\*\*[^*]+\*\*:\s*|\Z)",
        body,
        re.MULTILINE | re.DOTALL,
    )
    return match.group(1).strip() if match else ""


def parse_param_item(content: str) -> dict:
    normalized = normalize_inline_whitespace(content)
    match = re.match(r"^(?P<name>.+?)\s*[：:]\s*(?P<desc>.+)$", normalized)
    if match:
        return {
            "name": strip_markdown_wrappers(match.group("name")),
            "description": normalize_inline_whitespace(match.group("desc")),
        }

    name_only = strip_markdown_wrappers(normalized)
    if name_only != normalized or re.fullmatch(r"[A-Za-z0-9_.-]+", name_only):
        return {"name": name_only, "description": ""}

    return {"name": "", "description": normalized}


def append_param_description(param: dict, extra: str) -> None:
    extra = normalize_inline_whitespace(extra)
    if not extra:
        return
    if param["description"]:
        param["description"] = f"{param['description']}；{extra}"
    else:
        param["description"] = extra


def parse_markdown_params(section: str) -> List[dict]:
    params: List[dict] = []
    current = None

    for raw_line in section.splitlines():
        if not raw_line.strip():
            continue

        indent = len(raw_line) - len(raw_line.lstrip(" "))
        stripped = raw_line.strip()

        if not stripped.startswith("-"):
            if current is not None:
                append_param_description(current, stripped)
            continue

        content = stripped[1:].strip()
        if indent == 0:
            if current is not None:
                params.append(current)
            current = parse_param_item(content)
        elif current is not None:
            append_param_description(current, content)
        else:
            current = parse_param_item(content)

    if current is not None:
        params.append(current)

    return [param for param in params if param["name"] or param["description"]]


def parse_markdown_example(section: str) -> str:
    match = re.search(r"```(?:\w+)?\n(.*?)\n```", section, re.DOTALL)
    if not match:
        return ""
    return "\n".join(line.rstrip() for line in match.group(1).splitlines()).strip()


def parse_client_command_reference(reference_md: str) -> Dict[str, Dict[str, dict]]:
    docs_by_client: Dict[str, Dict[str, dict]] = {}
    docs_by_name: Dict[str, dict] = {}
    current_client = None
    lines = reference_md.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i]
        client_match = re.match(r"^## Client `([^`]+)`\s*$", line)
        if client_match:
            current_client = client_match.group(1).strip()
            docs_by_client.setdefault(current_client, {})
            i += 1
            continue

        command_match = re.match(r"^### Command `([^`]+)`\s*$", line)
        if command_match and current_client:
            current_command = command_match.group(1).strip()
            start = i + 1
            end = start
            while end < len(lines):
                if lines[end].startswith("### Command `") or lines[end].startswith("## Client `"):
                    break
                end += 1

            body = "\n".join(lines[start:end]).strip()
            summary = normalize_inline_whitespace(extract_markdown_section(body, "作用"))
            syntax_section = extract_markdown_section(body, "语法")
            syntax_match = re.search(r"`([^`]+)`", syntax_section)
            syntax = syntax_match.group(1).strip() if syntax_match else normalize_inline_whitespace(syntax_section)
            params = parse_markdown_params(extract_markdown_section(body, "参数说明"))
            example = parse_markdown_example(extract_markdown_section(body, "示例"))

            doc = {
                "summary": summary,
                "syntax": syntax,
                "params": params,
                "example": example,
            }

            docs_by_client[current_client][current_command] = doc
            docs_by_name.setdefault(current_command, doc)
            i = end
            continue

        i += 1

    return {"byClient": docs_by_client, "byName": docs_by_name}


def parse_class_constants(src: str, class_name: str, prefix: str) -> List[str]:
    match = re.search(rf"class\s+{class_name}\s*:\s*(.*?)(?:\nclass\s+\w+\s*:|\Z)", src, re.DOTALL)
    if not match:
        return []
    block = match.group(1)
    items = re.findall(rf"\b({prefix}[A-Z0-9_]+)\s*=", block)
    return unique_preserve_order(items)


def build_schema() -> dict:
    config_src = CONFIG_PY.read_text(encoding="utf-8")
    yaml_text = ASSERT_YAML.read_text(encoding="utf-8")
    status_src = STATUS_PY.read_text(encoding="utf-8")
    speech_engine_src = SPEECH_ENGINE_CLIENT_PY.read_text(encoding="utf-8")
    tss_client_src = TSS_CLIENT_PY.read_text(encoding="utf-8")
    command_md = COMMAND_MD.read_text(encoding="utf-8")

    env_variables = parse_environment_variables(config_src)
    assert_code_types = parse_assert_code_types(config_src)
    file_assertions = parse_file_assertions(config_src)
    client_commands = parse_client_commands(config_src)
    yaml_assertions = parse_assertions_from_yaml(yaml_text)
    vr_configs = parse_vr_configs(status_src)
    aibs_params = parse_class_constants(status_src, "AIBSParam", "AIBS_PARAM_")
    speech_engine_params = parse_class_constants(speech_engine_src, "SpeechEngineParam", "SPEECH_ENGINE_PARAM_")
    tss_engine_params = parse_class_constants(tss_client_src, "AIBSEngineParam", "ENGINE_PARAM_")

    assertions = unique_preserve_order(
        assert_code_types + yaml_assertions + file_assertions + ["LOG", "SUM"]
    )

    special_keywords = ["SEARCH", "MATCH", "DIFF", "KV", "JSON", "EXTRACT", "EXISTS", "ABSENT", "COUNT"]
    block_keywords = ["SETUP", "TEARDOWN", "SUITE_TEARDOWN", "CASE_SETUP", "CASE_TEARDOWN", "PARAMETER"]
    mode_keywords = ["cmn", "eng", "yue", "JSON", "LINE", "REPLACE", "DELETE", "TEXT", "CSV", "default"]
    set_params_by_client = {
        "TSA": aibs_params,
        "NIS": aibs_params,
        "HWK": speech_engine_params,
        "TSS": tss_engine_params,
    }
    command_docs = parse_command_docs(command_md, client_commands)
    if CLIENT_COMMAND_REFERENCE_MD.exists():
        reference_docs = parse_client_command_reference(CLIENT_COMMAND_REFERENCE_MD.read_text(encoding="utf-8"))
        for client, docs in reference_docs["byClient"].items():
            command_docs["byClient"].setdefault(client, {})
            command_docs["byClient"][client].update(docs)
        command_docs["byName"].update(reference_docs["byName"])

    client_command_summaries = {
        client: {
            command: doc.get("summary", "")
            for command, doc in docs.items()
        }
        for client, docs in command_docs["byClient"].items()
    }
    exp_docs_by_type = command_docs["byClient"].get("EXP", {})

    return {
        "languageId": "nano-mgo",
        "displayName": "Mango NANO DSL",
        "extensions": [".mgo"],
        "blockKeywords": block_keywords,
        "clients": list(client_commands.keys()) + ["EXP"],
        "commandsByClient": client_commands,
        "expCommands": assertions,
        "assertions": assertions,
        "assertionCategories": {
            "apiRet": assert_code_types,
            "yamlCallbacks": yaml_assertions,
            "fileAssertions": file_assertions,
            "special": ["LOG", "SUM"],
        },
        "environmentVariables": env_variables,
        "specialKeywords": special_keywords,
        "modeKeywords": mode_keywords,
        "vrConfigs": vr_configs,
        "setParamsByClient": set_params_by_client,
        "commandDocsByClient": command_docs["byClient"],
        "commandDocsByName": command_docs["byName"],
        "clientCommandSummaries": client_command_summaries,
        "expDocsByType": exp_docs_by_type,
        "parameterPlaceholders": ["NANO_STEPS"],
        "commentPrefixes": ["#"],
        "foldingMarkers": {"start": r"^\s*>>>", "end": r"^\s*<<<"},
        "notes": {
            "sourceFiles": [
                str(CONFIG_PY.relative_to(REPO_ROOT)),
                str(ASSERT_YAML.relative_to(REPO_ROOT)),
                str(STATUS_PY.relative_to(REPO_ROOT)),
                str(SPEECH_ENGINE_CLIENT_PY.relative_to(REPO_ROOT)),
                str(TSS_CLIENT_PY.relative_to(REPO_ROOT)),
                str(COMMAND_MD.relative_to(REPO_ROOT)),
                str(CLIENT_COMMAND_REFERENCE_MD.relative_to(REPO_ROOT)),
            ],
            "generatedBy": "plugins/vscode-mgo-extension/scripts/generate_metadata.py",
        },
    }


def main() -> None:
    schema = build_schema()
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已生成: {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
