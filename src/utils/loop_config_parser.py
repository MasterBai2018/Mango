#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re
import json
from typing import List, Tuple


def parse_loop_config(config_str: str) -> List[Tuple[int, str]]:
    """
    解析 loop 配置字符串，返回 [(loop_index, loop_value), ...] 列表。

    LOOP_INDEX：从 0 开始的迭代计数器（始终连续）
    LOOP_VALUE：该次迭代的实际值

    支持格式：
      [0~99]            → 100次，LOOP_VALUE: "0".."99"
      [0~99:2]          → 50次，LOOP_VALUE: "0","2","4",...,"98"
      ["a","b","c"]     → 3次，LOOP_VALUE: "a","b","c"
      [1, 2, 3]         → 3次，LOOP_VALUE: "1","2","3"
    """
    config_str = config_str.strip()
    if not config_str:
        raise ValueError("loop 配置不能为空")

    # 优先匹配 range 格式：[start~end] 或 [start~end:step]
    range_match = re.match(r'^\[(-?\d+)~(-?\d+)(?::(\d+))?\]$', config_str)
    if range_match:
        start = int(range_match.group(1))
        end   = int(range_match.group(2))
        step  = int(range_match.group(3)) if range_match.group(3) else 1
        if step <= 0:
            raise ValueError(f"loop 步长必须为正整数，当前: {step}")
        if start > end:
            raise ValueError(f"loop 起始值({start})不能大于结束值({end})")
        values = list(range(start, end + 1, step))
        if not values:
            raise ValueError(f"loop 范围 [{start}~{end}:{step}] 展开后为空")
        return [(i, str(v)) for i, v in enumerate(values)]

    # 匹配 list 格式：["a","b"] 或 [1,2,3]
    if config_str.startswith('[') and config_str.endswith(']'):
        try:
            parsed = json.loads(config_str)
            if isinstance(parsed, list):
                if not parsed:
                    raise ValueError("loop list 不能为空列表")
                return [(i, str(v)) for i, v in enumerate(parsed)]
        except json.JSONDecodeError as e:
            raise ValueError(f"loop list 格式解析失败: '{config_str}'，错误: {e}") from e

    raise ValueError(
        f"无法解析 loop 配置: '{config_str}'，"
        f"支持格式: [0~99] / [0~99:2] / [\"a\",\"b\",\"c\"]"
    )
