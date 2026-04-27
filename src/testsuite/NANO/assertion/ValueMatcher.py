#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2025/01/08
# @Author  : huidong.bai
# @File    : ValueMatcher.py
# @Software: PyCharm  
# @Mail    : MasterBai2018@outlook.com
"""
统一值匹配器 - 支持多种断言语法

语法汇总:
    精确匹配:   value           完全等于
    列表匹配:   [v1,v2,v3]      列表元素 multiset 相等（顺序无关）；项内含逗号时写 \\,
    模糊匹配:   *               任意值皆可
    通配符:     *pattern*       通配符模式匹配
    或断言:     v1|v2           满足其一即可
    分组:       (expr)          明确优先级
    非断言:     !value          不等于
    空值:       None            期望为空
    非空:       !None           期望非空
    大于:       >N              数值大于
    大于等于:   >=N             数值大于等于
    小于:       <N              数值小于
    小于等于:   <=N             数值小于等于
    范围断言:   (N~M)           开区间 N < x < M
    包含:       ~value          包含子串
    不包含:     !~value         不包含子串
    IN断言:     @in(val)        值存在于数组/字符串中
    NOT IN:     @notin(val)     值不存在于数组/字符串中
    忽略大小写: @i(expr)        表达式匹配时忽略大小写
    转义:       \\字符           转义特殊字符 | ~ ! @ ( ) [ ]
"""
import re
import fnmatch
from collections import Counter
from enum import Enum
from loguru import logger
from typing import Any, Optional, List, Tuple
from dataclasses import dataclass


class MatchType(Enum):
    """匹配类型枚举"""
    EXACT = "exact"              # 精确匹配
    LIST = "list"                # 列表匹配
    WILDCARD = "wildcard"        # 通配符匹配
    ANY = "any"                  # 任意值 (*)
    OR = "or"                    # 或断言
    NOT = "not"                  # 非断言
    NONE = "none"                # 空值断言
    NOT_NONE = "not_none"        # 非空断言
    GREATER = "greater"          # 大于
    GREATER_EQ = "greater_eq"    # 大于等于
    LESS = "less"                # 小于
    LESS_EQ = "less_eq"          # 小于等于
    RANGE = "range"              # 范围断言
    CONTAINS = "contains"        # 包含
    NOT_CONTAINS = "not_contains"  # 不包含
    IN = "in"                    # IN断言
    NOT_IN = "not_in"            # NOT IN断言
    CASE_INSENSITIVE = "case_insensitive"  # 忽略大小写


@dataclass
class MatchResult:
    """匹配结果"""
    success: bool               # 是否匹配成功
    expected: str               # 预期值（原始表达式）
    actual: Any                 # 实际值
    match_type: MatchType       # 匹配类型
    message: str = ""           # 结果描述
    
    def __bool__(self):
        return self.success


class ValueMatcher:
    """
    统一值匹配器
    
    用于解析断言表达式并与实际值进行匹配
    支持多种匹配语法，可用于JSON断言、LOG断言、FILE断言等场景
    """
    
    # 特殊字符（需要转义）
    SPECIAL_CHARS = {'|', '&', '~', '!', '@', '(', ')', '[', ']'}
    
    # 转义字符
    ESCAPE_CHAR = '\\'
    
    # 占位符（用于临时替换转义字符）
    ESCAPE_PLACEHOLDER_PREFIX = '\x00ESC_'
    
    def __init__(self):
        """初始化匹配器"""
        pass
    
    def match(self, expected: str, actual: Any, case_sensitive: bool = True) -> MatchResult:
        """
        根据预期表达式匹配实际值
        
        Args:
            expected: 预期表达式，如 "NAVI", "*", ">80", "~天气"
            actual: 实际值，可以是 str, int, float, list, None 等
            case_sensitive: 是否大小写敏感，默认敏感
        
        Returns:
            MatchResult 对象
        """
        try:
            # 处理转义字符，将转义序列替换为占位符
            expected_processed, escape_map = self._process_escapes(expected)
            
            # 解析并执行匹配
            result = self._match_expression(expected_processed, actual, case_sensitive, escape_map)
            
            # 恢复原始表达式用于显示
            result.expected = expected
            return result
            
        except Exception as e:
            logger.error(f"值匹配异常: expected={expected}, actual={actual}, error={e}")
            return MatchResult(
                success=False,
                expected=expected,
                actual=actual,
                match_type=MatchType.EXACT,
                message=f"匹配异常: {str(e)}"
            )
    
    def _process_escapes(self, expr: str) -> Tuple[str, dict]:
        """
        处理转义字符
        
        将 \\| 等转义序列替换为占位符，避免被当作操作符解析
        
        Returns:
            (处理后的表达式, 转义映射表)
        """
        escape_map = {}
        result = []
        i = 0
        escape_count = 0
        
        while i < len(expr):
            if expr[i] == self.ESCAPE_CHAR and i + 1 < len(expr):
                next_char = expr[i + 1]
                if next_char in self.SPECIAL_CHARS or next_char == self.ESCAPE_CHAR:
                    # 创建占位符
                    placeholder = f"{self.ESCAPE_PLACEHOLDER_PREFIX}{escape_count}\x00"
                    escape_map[placeholder] = next_char
                    result.append(placeholder)
                    escape_count += 1
                    i += 2
                    continue
            result.append(expr[i])
            i += 1
        
        return ''.join(result), escape_map
    
    def _restore_escapes(self, text: str, escape_map: dict) -> str:
        """恢复转义字符"""
        for placeholder, char in escape_map.items():
            text = text.replace(placeholder, char)
        return text
    
    def _match_expression(self, expr: str, actual: Any, case_sensitive: bool, escape_map: dict) -> MatchResult:
        """
        解析并匹配表达式（递归处理）
        
        解析优先级（从低到高）:
        1. | (或)
        2. 前缀运算符 ! ~
        3. 函数式 @in() @notin() @i()
        4. 范围 (N~M)
        5. 比较 > < >= <=
        6. 特殊值 None *
        7. 列表 [...]
        8. 精确匹配
        """
        expr = expr.strip()
        
        if not expr:
            return MatchResult(False, expr, actual, MatchType.EXACT, "空表达式")
        
        # 1. 检查忽略大小写函数 @i(...)
        if expr.startswith('@i(') and expr.endswith(')'):
            inner = expr[3:-1]
            return self._match_expression(inner, actual, case_sensitive=False, escape_map=escape_map)
        
        # 2. 解析或表达式 (最低优先级)
        or_parts = self._split_by_operator(expr, '|')
        if len(or_parts) > 1:
            return self._match_or(or_parts, actual, case_sensitive, escape_map)
        
        # 3. 处理括号分组
        if expr.startswith('(') and expr.endswith(')') and self._is_balanced_parens(expr[1:-1]):
            # 检查是否是范围表达式 (N~M)
            inner = expr[1:-1]
            if '~' in inner and not inner.startswith('~') and not inner.startswith('!~'):
                range_match = re.match(r'^(-?[\d.]+)~(-?[\d.]+)$', inner)
                if range_match:
                    return self._match_range(range_match.group(1), range_match.group(2), actual)
            # 普通分组，递归解析内部
            return self._match_expression(inner, actual, case_sensitive, escape_map)
        
        # 4. 处理非断言 !
        if expr.startswith('!'):
            return self._match_not(expr, actual, case_sensitive, escape_map)
        
        # 5. 处理包含断言 ~
        if expr.startswith('~'):
            return self._match_contains(expr[1:], actual, case_sensitive, escape_map)
        
        # 6. 处理 @in() 和 @notin()
        if expr.startswith('@in(') and expr.endswith(')'):
            return self._match_in(expr[4:-1], actual, case_sensitive, escape_map)
        if expr.startswith('@notin(') and expr.endswith(')'):
            return self._match_notin(expr[7:-1], actual, case_sensitive, escape_map)
        
        # 7. 处理比较运算符
        if expr.startswith('>='):
            return self._match_compare(expr[2:], actual, '>=')
        if expr.startswith('<='):
            return self._match_compare(expr[2:], actual, '<=')
        if expr.startswith('>'):
            return self._match_compare(expr[1:], actual, '>')
        if expr.startswith('<'):
            return self._match_compare(expr[1:], actual, '<')
        
        # 8. 处理特殊值
        if expr == '*':
            return MatchResult(True, expr, actual, MatchType.ANY, "任意值匹配")
        
        if expr == 'None':
            return self._match_none(actual)
        
        # 9. 处理列表匹配 [...]
        if expr.startswith('[') and expr.endswith(']'):
            return self._match_list(expr, actual, case_sensitive, escape_map)
        
        # 10. 处理通配符匹配 (包含 *)
        if '*' in expr:
            return self._match_wildcard(expr, actual, case_sensitive, escape_map)
        
        # 11. 精确匹配（兜底）
        return self._match_exact(expr, actual, case_sensitive, escape_map)
    
    def _split_by_operator(self, expr: str, op: str) -> List[str]:
        """
        按操作符分割表达式，考虑括号和函数嵌套
        
        Args:
            expr: 表达式
            op: 操作符 '|'
        
        Returns:
            分割后的部分列表
        """
        parts = []
        current = []
        depth = 0  # 括号深度
        i = 0
        
        while i < len(expr):
            char = expr[i]
            
            # 跳过占位符
            if char == '\x00' and expr[i:].startswith(self.ESCAPE_PLACEHOLDER_PREFIX):
                end = expr.find('\x00', i + 1)
                if end != -1:
                    current.append(expr[i:end + 1])
                    i = end + 1
                    continue
            
            if char in '([':
                depth += 1
                current.append(char)
            elif char in ')]':
                depth -= 1
                current.append(char)
            elif char == op and depth == 0:
                # 找到顶层操作符
                parts.append(''.join(current).strip())
                current = []
            else:
                current.append(char)
            i += 1
        
        # 添加最后一部分
        if current:
            parts.append(''.join(current).strip())
        
        return parts
    
    def _is_balanced_parens(self, expr: str) -> bool:
        """检查括号是否平衡"""
        depth = 0
        for char in expr:
            if char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
            if depth < 0:
                return False
        return depth == 0
    
    def _match_or(self, parts: List[str], actual: Any, case_sensitive: bool, escape_map: dict) -> MatchResult:
        """或断言：任一条件满足即可"""
        messages = []
        for part in parts:
            result = self._match_expression(part, actual, case_sensitive, escape_map)
            if result.success:
                return MatchResult(
                    success=True,
                    expected='|'.join(parts),
                    actual=actual,
                    match_type=MatchType.OR,
                    message=f"或断言通过: {part}"
                )
            messages.append(f"{part}={result.message}")
        
        return MatchResult(
            success=False,
            expected='|'.join(parts),
            actual=actual,
            match_type=MatchType.OR,
            message=f"或断言失败: 所有条件均不满足 [{', '.join(messages)}]"
        )
    
    def _match_not(self, expr: str, actual: Any, case_sensitive: bool, escape_map: dict) -> MatchResult:
        """非断言"""
        inner = expr[1:]  # 去掉 !
        # 特殊处理 !None
        if inner == 'None':
            actual_is_none = actual is None or str(actual).lower() == 'none' or str(actual) == ''
            return MatchResult(
                success=not actual_is_none,
                expected=expr,
                actual=actual,
                match_type=MatchType.NOT_NONE,
                message="非空断言通过" if not actual_is_none else "非空断言失败: 实际值为空"
            )
        
        # 特殊处理 !~ (不包含)
        if inner.startswith('~'):
            return self._match_not_contains(inner[1:], actual, case_sensitive, escape_map)
        
        # 普通非断言
        inner_result = self._match_expression(inner, actual, case_sensitive, escape_map)
        return MatchResult(
            success=not inner_result.success,
            expected=expr,
            actual=actual,
            match_type=MatchType.NOT,
            message=f"非断言{'通过' if not inner_result.success else '失败'}"
        )
    
    def _match_none(self, actual: Any) -> MatchResult:
        """空值断言"""
        actual_is_none = actual is None or str(actual).lower() == 'none' or str(actual) == ''
        return MatchResult(
            success=actual_is_none,
            expected='None',
            actual=actual,
            match_type=MatchType.NONE,
            message="空值断言通过" if actual_is_none else f"空值断言失败: 实际值={actual}"
        )
    
    def _match_contains(self, value: str, actual: Any, case_sensitive: bool, escape_map: dict) -> MatchResult:
        """包含断言"""
        value = self._restore_escapes(value, escape_map)
        actual_str = str(actual) if actual is not None else ''
        
        if not case_sensitive:
            match = value.lower() in actual_str.lower()
        else:
            match = value in actual_str
        
        return MatchResult(
            success=match,
            expected=f'~{value}',
            actual=actual,
            match_type=MatchType.CONTAINS,
            message=f"包含断言{'通过' if match else '失败'}: '{value}' {'在' if match else '不在'} '{actual_str}' 中"
        )
    
    def _match_not_contains(self, value: str, actual: Any, case_sensitive: bool, escape_map: dict) -> MatchResult:
        """不包含断言"""
        value = self._restore_escapes(value, escape_map)
        actual_str = str(actual) if actual is not None else ''
        
        if not case_sensitive:
            match = value.lower() not in actual_str.lower()
        else:
            match = value not in actual_str
        
        return MatchResult(
            success=match,
            expected=f'!~{value}',
            actual=actual,
            match_type=MatchType.NOT_CONTAINS,
            message=f"不包含断言{'通过' if match else '失败'}"
        )
    
    def _match_in(self, value: str, actual: Any, case_sensitive: bool, escape_map: dict) -> MatchResult:
        """IN断言：检查值是否存在于实际结果中"""
        value = self._restore_escapes(value, escape_map)
        
        # 实际值是列表
        if isinstance(actual, (list, tuple)):
            if case_sensitive:
                match = value in [str(item) for item in actual]
            else:
                match = value.lower() in [str(item).lower() for item in actual]
        # 实际值是字符串
        elif isinstance(actual, str):
            if case_sensitive:
                match = value in actual
            else:
                match = value.lower() in actual.lower()
        else:
            actual_str = str(actual) if actual is not None else ''
            match = value in actual_str
        
        return MatchResult(
            success=match,
            expected=f'@in({value})',
            actual=actual,
            match_type=MatchType.IN,
            message=f"IN断言{'通过' if match else '失败'}: '{value}' {'存在于' if match else '不存在于'} {actual}"
        )
    
    def _match_notin(self, value: str, actual: Any, case_sensitive: bool, escape_map: dict) -> MatchResult:
        """NOT IN断言：检查值是否不存在于实际结果中"""
        in_result = self._match_in(value, actual, case_sensitive, escape_map)
        return MatchResult(
            success=not in_result.success,
            expected=f'@notin({value})',
            actual=actual,
            match_type=MatchType.NOT_IN,
            message=f"NOT IN断言{'通过' if not in_result.success else '失败'}"
        )
    
    def _match_compare(self, value: str, actual: Any, operator: str) -> MatchResult:
        """数值比较断言"""
        try:
            expected_num = float(value.strip())
            
            # 尝试将实际值转为数字
            if actual is None or str(actual).lower() == 'none':
                return MatchResult(
                    success=False,
                    expected=f'{operator}{value}',
                    actual=actual,
                    match_type=MatchType.GREATER if operator == '>' else MatchType.LESS,
                    message=f"比较断言失败: 实际值为None，无法比较"
                )
            
            actual_num = float(actual)
            
            if operator == '>':
                match = actual_num > expected_num
                match_type = MatchType.GREATER
            elif operator == '>=':
                match = actual_num >= expected_num
                match_type = MatchType.GREATER_EQ
            elif operator == '<':
                match = actual_num < expected_num
                match_type = MatchType.LESS
            elif operator == '<=':
                match = actual_num <= expected_num
                match_type = MatchType.LESS_EQ
            else:
                match = False
                match_type = MatchType.EXACT
            
            return MatchResult(
                success=match,
                expected=f'{operator}{value}',
                actual=actual,
                match_type=match_type,
                message=f"比较断言{'通过' if match else '失败'}: {actual_num} {operator} {expected_num}"
            )
            
        except (ValueError, TypeError) as e:
            return MatchResult(
                success=False,
                expected=f'{operator}{value}',
                actual=actual,
                match_type=MatchType.GREATER,
                message=f"比较断言失败: 无法将值转换为数字 ({e})"
            )
    
    def _match_range(self, min_val: str, max_val: str, actual: Any) -> MatchResult:
        """范围断言（开区间）: min < actual < max"""
        try:
            min_num = float(min_val.strip())
            max_num = float(max_val.strip())
            
            if actual is None or str(actual).lower() == 'none':
                return MatchResult(
                    success=False,
                    expected=f'({min_val}~{max_val})',
                    actual=actual,
                    match_type=MatchType.RANGE,
                    message=f"范围断言失败: 实际值为None"
                )
            
            actual_num = float(actual)
            match = min_num < actual_num < max_num
            
            return MatchResult(
                success=match,
                expected=f'({min_val}~{max_val})',
                actual=actual,
                match_type=MatchType.RANGE,
                message=f"范围断言{'通过' if match else '失败'}: {min_num} < {actual_num} < {max_num}"
            )
            
        except (ValueError, TypeError) as e:
            return MatchResult(
                success=False,
                expected=f'({min_val}~{max_val})',
                actual=actual,
                match_type=MatchType.RANGE,
                message=f"范围断言失败: 无法转换为数字 ({e})"
            )
    
    def _split_list_items(self, inner: str) -> List[str]:
        """按逗号切分列表字面量，\\, 表示项内的字面量逗号"""
        items: List[str] = []
        buf: List[str] = []
        i, n = 0, len(inner)
        while i < n:
            if inner[i] == "\\" and i + 1 < n and inner[i + 1] == ",":
                buf.append(",")
                i += 2
                continue
            if inner[i] == ",":
                items.append("".join(buf).strip())
                buf = []
                i += 1
                continue
            buf.append(inner[i])
            i += 1
        items.append("".join(buf).strip())
        return items

    def _match_list(self, expr: str, actual: Any, case_sensitive: bool, escape_map: dict) -> MatchResult:
        """列表匹配：元素 multiset 相等（顺序无关，重复次数需一致）"""
        # 解析预期列表
        inner = expr[1:-1]  # 去掉 [ ]
        inner = self._restore_escapes(inner, escape_map)
        inner = inner.strip()
        if inner == "":
            expected_items = []
        else:
            expected_items = self._split_list_items(inner)
        # 处理实际值
        if isinstance(actual, (list, tuple)):
            actual_items = [str(item) for item in actual]
        elif isinstance(actual, str):
            # 尝试解析字符串形式的列表
            actual_str = actual.strip()
            if actual_str.startswith('[') and actual_str.endswith(']'):
                try:
                    import ast
                    parsed = ast.literal_eval(actual_str)
                    if isinstance(parsed, (list, tuple)):
                        actual_items = [str(item) for item in parsed]
                    else:
                        actual_items = [actual_str]
                except:
                    actual_items = [actual_str]
            else:
                actual_items = [actual_str]
        else:
            actual_items = [str(actual)]
        
        # 无序 multiset 比较（顺序不影响结果，重复项按出现次数比较）
        if case_sensitive:
            match = Counter(expected_items) == Counter(actual_items)
        else:
            match = Counter(x.lower() for x in expected_items) == Counter(x.lower() for x in actual_items)
        
        return MatchResult(
            success=match,
            expected=expr,
            actual=actual,
            match_type=MatchType.LIST,
            message=f"列表匹配{'通过' if match else '失败'}: 预期{expected_items}, 实际{actual_items}"
        )
    
    def _match_wildcard(self, pattern: str, actual: Any, case_sensitive: bool, escape_map: dict) -> MatchResult:
        """通配符匹配"""
        pattern = self._restore_escapes(pattern, escape_map)
        actual_str = str(actual) if actual is not None else ''
        
        if not case_sensitive:
            match = fnmatch.fnmatch(actual_str.lower(), pattern.lower())
        else:
            match = fnmatch.fnmatch(actual_str, pattern)
        
        return MatchResult(
            success=match,
            expected=pattern,
            actual=actual,
            match_type=MatchType.WILDCARD,
            message=f"通配符匹配{'通过' if match else '失败'}: '{actual_str}' {'匹配' if match else '不匹配'} '{pattern}'"
        )
    
    # 布尔值归一化映射表（统一为小写形式）
    _BOOLEAN_NORMALIZE = {
        'true': 'true', 'false': 'false',
        'True': 'true', 'False': 'false',
        'TRUE': 'true', 'FALSE': 'false',
    }

    def _match_exact(self, expected: str, actual: Any, case_sensitive: bool, escape_map: dict) -> MatchResult:
        """精确匹配"""
        expected = self._restore_escapes(expected, escape_map)
        actual_str = str(actual) if actual is not None else 'None'
        
        if not case_sensitive:
            match = expected.lower() == actual_str.lower()
        else:
            # 布尔值兼容：True/true/TRUE 和 False/false/FALSE 视为相同
            exp_norm = self._BOOLEAN_NORMALIZE.get(expected)
            act_norm = self._BOOLEAN_NORMALIZE.get(actual_str)
            if exp_norm is not None and act_norm is not None:
                match = (exp_norm == act_norm)
            else:
                match = expected == actual_str
        
        return MatchResult(
            success=match,
            expected=expected,
            actual=actual,
            match_type=MatchType.EXACT,
            message=f"精确匹配{'通过' if match else '失败'}: 预期'{expected}', 实际'{actual_str}'"
        )


# 全局单例（方便直接使用）
_matcher_instance: Optional[ValueMatcher] = None


def get_matcher() -> ValueMatcher:
    """获取全局匹配器实例"""
    global _matcher_instance
    if _matcher_instance is None:
        _matcher_instance = ValueMatcher()
    return _matcher_instance


def match_value(expected: str, actual: Any, case_sensitive: bool = True) -> MatchResult:
    """
    便捷函数：匹配值
    
    Args:
        expected: 预期表达式
        actual: 实际值
        case_sensitive: 是否大小写敏感
    
    Returns:
        MatchResult
    """
    return get_matcher().match(expected, actual, case_sensitive)

