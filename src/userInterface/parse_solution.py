#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import os
import re
import sys
import yaml

from src.utils.common import mango_config


def _normalize_loop_config(loop_raw) -> str:
    """
    将 YAML 解析后的 loop 值规范化为 parse_loop_config 可识别的字符串。

    YAML 原生写法与解析结果：
      loop: [0~99]       → list ["0~99"]   → "[0~99]"    (range 格式)
      loop: [0~99:2]     → list ["0~99:2"] → "[0~99:2]"  (range+step 格式)
      loop: ["1", "2"]   → list ["1","2"]  → '["1","2"]' (JSON list)
      loop: [1, 2]       → list [1, 2]     → '["1","2"]' (JSON list)
    """
    if isinstance(loop_raw, list):
        # 单元素列表且包含 ~ 时视为 range 格式：["0~99"] → "[0~99]"
        if len(loop_raw) == 1 and isinstance(loop_raw[0], str) and '~' in loop_raw[0]:
            return f"[{loop_raw[0]}]"
        # 其余情况视为值列表，序列化为 JSON 字符串
        return json.dumps([str(v) for v in loop_raw])
    # 已是字符串（理论上 YAML 不会走到这里，保留作为兜底）
    return str(loop_raw).strip()


class Suite:
    """YAML solution 解析后的最小 Suite 对象。"""

    def __init__(
        self,
        suite_id,
        name,
        conf,
        tag,
        case_list,
        scenario_conf=None,
        parameterized_data=None,
        steps_data=None,
        abstract=None,
        retry=0,
        xdist_workers=0,
    ):
        self.suiteID = suite_id
        self.name = name
        self.conf = conf
        self.tag = tag
        self.caseList = case_list
        self.parameterized_data = parameterized_data
        self.steps_data = steps_data
        self.scenario_conf = scenario_conf
        self.abstract = abstract
        self.retry = retry
        self.xdist_workers = xdist_workers
        self.main_tag = None
        self.loop = None  # loop 配置字符串，如 "[0~99]" / "[0~99:2]" / '["a","b"]'

    def set_scenarioConfig(self, config):
        self.scenario_conf = config


class Scenario:
    """YAML solution 解析后的最小 Scenario 对象。"""

    scenarioCounter = 0

    def __init__(self, name, owner=None):
        Scenario.scenarioCounter += 1
        self.scenarioID = Scenario.scenarioCounter
        self.name = name
        self.owner = owner
        self.suiteInfo = []
        self.useValgrind = False
        self.repeatNum = 1
        # 新 YAML 中 environment 不支持继承，这里固定为空，避免覆盖 global.environment
        self.project = None


class Parse:
    """面向 YAML solution 的轻量解析器，仅兼容 run_test.py 主执行链路。"""

    MAIN_TAGS = {"ONLINE", "OFFLINE", "CP"}
    DEFAULT_SUITE_NAME = "NANO"

    def __init__(self, cfgFile, _tag, _enable, work):
        self.config = cfgFile
        self.workspace = work
        self.project = None
        self.enable = []
        self.disable = []
        self.sceneList = []
        self.requested_tags = self._parse_requested_tags(_tag)
        self.scheduler_limits = {
            "GLOBAL_MAX_WORKERS": None,
            "ONLINE_MAX_WORKERS": None,
            "CP_MAX_WORKERS": None,
            "OFFLINE_MAX_WORKERS": None,
        }
        self._cli_enable = _enable
        self.parse()

    def get_scheduler_limits(self):
        return self.scheduler_limits

    def get_project(self):
        return self.project

    def get_tasks(self):
        return self.sceneList

    def get_enable(self):
        return self.enable

    def get_disable(self):
        return self.disable

    def _parse_requested_tags(self, raw_tag):
        result = {
            "required": set(),
            "optional": set(),
            "excluded": set(),
        }
        if not raw_tag:
            return result
        tokens = [t.strip() for t in re.findall(r"\[([^\[\]]+)\]", str(raw_tag)) if t.strip()]
        for token in tokens:
            if token.startswith("+") and len(token) > 1:
                result["required"].add(token[1:].upper())
            elif token.startswith("-") and len(token) > 1:
                result["excluded"].add(token[1:].upper())
            else:
                result["optional"].add(token.upper())
        return result

    def _normalize_list(self, value):
        if value is None:
            return []
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        if isinstance(value, str):
            return [v.strip() for v in value.split(",") if v.strip()]
        return [str(value).strip()]

    def _validate_environment(self, value):
        if value is None:
            print(f"ERROR : File '{self.config}'\n\tMissing required global.environment.")
            sys.exit(0)
        project_name = str(value).strip().lower()
        if project_name not in mango_config.get_all_project_names():
            print(f"ERROR : File '{self.config}'\n\tThe project name is not valid. Please check: {value}")
            sys.exit(0)
        return project_name

    def _parse_non_negative_int(self, value, field_name, minimum=0):
        try:
            parsed = int(value)
        except Exception:
            print(f"ERROR : File '{self.config}'\n\tThe field '{field_name}' must be an integer.")
            sys.exit(0)
        if parsed < minimum:
            print(f"ERROR : File '{self.config}'\n\tThe field '{field_name}' must be >= {minimum}.")
            sys.exit(0)
        return parsed

    def _parse_scheduler_limits(self, global_cfg):
        self.scheduler_limits["GLOBAL_MAX_WORKERS"] = self._parse_non_negative_int(
            global_cfg.get("global_max_workers"), "global.global_max_workers", minimum=1
        )
        self.scheduler_limits["ONLINE_MAX_WORKERS"] = self._parse_non_negative_int(
            global_cfg.get("online_max_workers"), "global.online_max_workers", minimum=0
        )
        self.scheduler_limits["CP_MAX_WORKERS"] = self._parse_non_negative_int(
            global_cfg.get("cp_max_workers"), "global.cp_max_workers", minimum=0
        )

        offline_value = global_cfg.get("offline_max_workers")
        if isinstance(offline_value, str) and offline_value.lower() == "auto":
            self.scheduler_limits["OFFLINE_MAX_WORKERS"] = "auto"
        else:
            self.scheduler_limits["OFFLINE_MAX_WORKERS"] = self._parse_non_negative_int(
                offline_value, "global.offline_max_workers", minimum=0
            )

    def _validate_xdist_workers(self):
        """
        校验所有 suite 的 xdist_workers 不能超过其 main_tag 对应的 *_MAX_WORKERS 上限。

        规则：
        - xdist_workers=0 或 1：占 1 个槽位，不受上限约束（1 个槽位一定能被容纳）。
        - xdist_workers >= 2：占 N 个槽位，不能超过对应 tag 的最大槽位数。
        - OFFLINE_MAX_WORKERS=auto 时，无法在解析阶段确定上限，跳过校验。

        注意：xdist_workers 不允许配置为字符串（如 "auto"），只能是非负整数，
              _parse_non_negative_int 已在解析时强制保证这一点。
        """
        tag_limit_map = {
            "ONLINE":  self.scheduler_limits["ONLINE_MAX_WORKERS"],
            "CP":      self.scheduler_limits["CP_MAX_WORKERS"],
            "OFFLINE": self.scheduler_limits["OFFLINE_MAX_WORKERS"],
        }
        for scenario in self.sceneList:
            for suite in scenario.suiteInfo:
                workers = suite.xdist_workers  # 已是 int，由 _parse_non_negative_int 保证
                if workers <= 1:
                    # 占 1 个槽位，任何合法配置都能容纳，无需校验
                    continue
                tag = suite.main_tag  # "ONLINE" / "OFFLINE" / "CP"
                limit = tag_limit_map.get(tag)
                if limit == "auto":
                    # OFFLINE=auto 时运行时动态决定，解析阶段无法判断上限，跳过
                    continue
                if workers > limit:
                    print(
                        f"ERROR : File '{self.config}'\n"
                        f"\tScenario '{scenario.name}' suite '{suite.name}': "
                        f"xdist_workers={workers} exceeds {tag}_MAX_WORKERS={limit}. "
                        f"A single suite cannot request more slots than the tag's total capacity."
                    )
                    sys.exit(1)

    def _extract_suite_tags(self, suite_tag):
        if suite_tag is None:
            return []
        if isinstance(suite_tag, list):
            return [str(t).strip().upper() for t in suite_tag if str(t).strip()]
        return [str(t).strip().upper() for t in re.findall(r"\[([^\[\]]+)\]", str(suite_tag))]

    def _validate_main_tag(self, suite_tag, suite_name, case_path):
        tags = self._extract_suite_tags(suite_tag)
        if not tags:
            print(
                f"ERROR : File '{self.config}'\n\tSuite '{suite_name}' case '{case_path}' must include one main tag in [ONLINE]/[OFFLINE]/[CP]."
            )
            sys.exit(0)
        if len(tags) != len(set(tags)):
            print(
                f"ERROR : File '{self.config}'\n\tSuite '{suite_name}' case '{case_path}' contains duplicated tags."
            )
            sys.exit(0)
        main_tags = [tag for tag in tags if tag in self.MAIN_TAGS]
        if len(main_tags) != 1:
            print(
                f"ERROR : File '{self.config}'\n\tSuite '{suite_name}' case '{case_path}' must contain exactly one main tag in [ONLINE]/[OFFLINE]/[CP]."
            )
            sys.exit(0)
        return main_tags[0]

    def _match_requested_tags(self, suite_tag):
        requested = self.requested_tags
        if not any(requested.values()):
            return True

        suite_tags = set(self._extract_suite_tags(suite_tag))
        if requested["excluded"] & suite_tags:
            return False
        if requested["required"] and not requested["required"].issubset(suite_tags):
            return False
        if requested["optional"] and not (requested["optional"] & suite_tags):
            return False
        return True

    def _resolve_inherited_value(self, global_cfg, scenario_cfg, suite_cfg, key, default):
        if key in suite_cfg and suite_cfg[key] is not None:
            return suite_cfg[key]
        if key in scenario_cfg and scenario_cfg[key] is not None:
            return scenario_cfg[key]
        if key in global_cfg and global_cfg[key] is not None:
            return global_cfg[key]
        return default

    def parse(self):
        if not os.path.exists(self.config):
            print(f"ERROR : File '{self.config}' does not exist.")
            sys.exit(0)

        try:
            with open(self.config, "r", encoding="utf-8") as fp:
                yaml_data = yaml.safe_load(fp) or {}
        except Exception as exc:
            print(f"ERROR : File '{self.config}'\n\tFailed to load YAML: {exc}")
            sys.exit(0)

        global_cfg = yaml_data.get("global") or {}
        scenarios = yaml_data.get("scenarios") or []

        if not isinstance(global_cfg, dict):
            print(f"ERROR : File '{self.config}'\n\tThe root field 'global' must be a mapping.")
            sys.exit(0)
        if not isinstance(scenarios, list):
            print(f"ERROR : File '{self.config}'\n\tThe root field 'scenarios' must be a list.")
            sys.exit(0)

        self.project = self._validate_environment(global_cfg.get("environment"))
        self._parse_scheduler_limits(global_cfg)

        if self._cli_enable:
            self.enable = self._normalize_list(self._cli_enable)
        else:
            self.enable = self._normalize_list(global_cfg.get("enable")) or ["ALL"]
        self.disable = self._normalize_list(global_cfg.get("disable"))

        for scenario_cfg in scenarios:
            if not isinstance(scenario_cfg, dict):
                print(f"ERROR : File '{self.config}'\n\tEach scenario item must be a mapping.")
                sys.exit(0)

            scenario_name = scenario_cfg.get("name")
            if not scenario_name:
                print(f"ERROR : File '{self.config}'\n\tScenario name is required.")
                sys.exit(0)

            owner = scenario_cfg.get("owner")
            if isinstance(owner, str):
                owner = self._normalize_list(owner)
            elif owner is not None and not isinstance(owner, list):
                owner = [str(owner)]

            scenario = Scenario(scenario_name, owner=owner)
            suites = scenario_cfg.get("suites") or []
            if not isinstance(suites, list):
                print(f"ERROR : File '{self.config}'\n\tScenario '{scenario_name}' field 'suites' must be a list.")
                sys.exit(0)

            for idx, suite_cfg in enumerate(suites, start=1):
                if not isinstance(suite_cfg, dict):
                    print(f"ERROR : File '{self.config}'\n\tScenario '{scenario_name}' contains a non-mapping suite item.")
                    sys.exit(0)

                suite_tag = suite_cfg.get("tag")
                main_tag = self._validate_main_tag(
                    suite_tag,
                    suite_cfg.get("name", self.DEFAULT_SUITE_NAME),
                    suite_cfg.get("case"),
                )
                if not self._match_requested_tags(suite_tag):
                    continue

                suite_name = str(suite_cfg.get("name") or self.DEFAULT_SUITE_NAME).strip()
                suite_conf = suite_cfg.get("config")
                suite_case = suite_cfg.get("case")
                if not suite_conf or not suite_case:
                    print(
                        f"ERROR : File '{self.config}'\n\tScenario '{scenario_name}' suite '{suite_name}' must define both 'config' and 'case'."
                    )
                    sys.exit(0)

                resolved_project_config = self._resolve_inherited_value(
                    global_cfg, scenario_cfg, suite_cfg, "project_config", None
                )
                resolved_retry = self._parse_non_negative_int(
                    self._resolve_inherited_value(global_cfg, scenario_cfg, suite_cfg, "retry", 0),
                    f"{scenario_name}.retry",
                    minimum=0,
                )
                resolved_xdist = self._parse_non_negative_int(
                    self._resolve_inherited_value(global_cfg, scenario_cfg, suite_cfg, "xdist_workers", 0),
                    f"{scenario_name}.xdist_workers",
                    minimum=0,
                )

                suite = Suite(
                    suite_id=idx,
                    name=suite_name,
                    conf=suite_conf,
                    tag=suite_tag,
                    case_list=suite_case,
                    scenario_conf=resolved_project_config,
                    parameterized_data=suite_cfg.get("parameter", suite_cfg.get("parameterized_data")),
                    steps_data=suite_cfg.get("steps", suite_cfg.get("steps_data")),
                    abstract=suite_cfg.get("abstract"),
                    retry=resolved_retry,
                    xdist_workers=resolved_xdist,
                )
                suite.main_tag = main_tag
                # 解析 loop 配置，规范化为 parse_loop_config 可识别的字符串
                loop_raw = suite_cfg.get("loop")
                if loop_raw is not None:
                    suite.loop = _normalize_loop_config(loop_raw)
                scenario.suiteInfo.append(suite)

            self.sceneList.append(scenario)

        # 所有 suite 解析完毕后，集中校验 xdist_workers 不超过对应 tag 的槽位上限
        self._validate_xdist_workers()

        print(f"parse the yaml solution file: '{self.config}'  complete.")