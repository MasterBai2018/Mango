#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2025/10/14
# @Author  : huidong.bai
# @File    : AssertionEngine.py
# @Software: PyCharm  
# @Mail    : MasterBai2018@outlook.com
import os
import re
import time
import json
import allure
import hashlib
import threading
from datetime import datetime
from loguru import logger
from typing import Dict, Any, Optional, List
from src.utils.jsonUtil import JsonUtil
from src.testsuite.NANO.dsl_engine import DSLCommand, Status
from src.testsuite.NANO.assertion.AssertionParser import AssertionParser
from src.testsuite.NANO.assertion.AssertionParser import CheckType, AssertionStatus, AssertionExpectation
from src.testsuite.NANO.assertion.AssertionDataManager import AssertionDataManager
from src.testsuite.NANO.assertion.ValueMatcher import ValueMatcher, match_value
from src.utils.common import embeddedType


class AssertionEngine:
    """断言引擎 - 核心类"""
    
    def __init__(self, assert_data: AssertionDataManager, yaml_config: Dict):
        self.yaml_config = yaml_config
        self.parser = AssertionParser(yaml_config)
        self.lock = threading.Lock()
        self.assert_data = assert_data
        self.assertion_results = []
        
        # 统一值匹配器
        self.value_matcher = ValueMatcher()

        # 1. 永久指针：记录上一个Case结束时的文件位置 (Case之间隔离)
        self.log_file_pointers = {} 
        # 2. 临时指针：记录当前Case执行过程中读到的最大位置 (Case内部共享)
        self.temp_log_pointers = {}
        # 3. 报告器：由 NANORunner 注入，可选
        self.reporter = None
    
    def commit_log_pointers(self):
        """
        提交日志指针 (在Case结束时调用)
        将当前Case读取到的最大位置更新为永久指针，供下一个Case使用
        """
        if self.temp_log_pointers:
            self.log_file_pointers.update(self.temp_log_pointers)
            self.temp_log_pointers.clear()
            logger.debug("日志断言指针已提交(Commit)，窗口后移")
    
    def do_assertion(self, command: DSLCommand):
        """
        执行断言
        
        Args:
            command: DSL断言指令，包含超时时间
        Returns:
            是否断言成功
        """
        expectation = self.parser.parse_assertion(command.command, command.params)
        if not expectation:
            command.status = Status.ERROR
            command.message = f'[Running Error] 断言参数解析失败: {command.command} {command.params}'
            return False
        
        # 获取超时时间（秒）
        # timeout=0: 立即断言，不等待
        # timeout>0: 等待指定秒数
        # timeout=-1: 无限等待
        timeout = command.timeout if command.timeout != 0 else None
        # 根据断言类型执行不同的断言逻辑
        if expectation.check_type == CheckType.JSON:
            self._do_json_assertion(expectation, timeout)
        elif expectation.check_type == CheckType.API:
            self._do_api_assertion(expectation, timeout)
        elif expectation.check_type == CheckType.FILE:
            self._do_file_assertion(expectation, timeout)
        elif expectation.check_type == CheckType.LOG:
            self._do_log_assertion(expectation, timeout)
        elif expectation.check_type == CheckType.SUM:
            self._do_sum_assertion(expectation, timeout)
        else:
            expectation.status = AssertionStatus.ERROR
            expectation.error_message = f"不支持的断言类型"
        
        # 终端打印信息
        self._print_test_result(expectation)
        
        # 收集断言结果
        assertion_passed = expectation.status == AssertionStatus.SUCCESS
        with self.lock:
            self.assertion_results.append(assertion_passed)
        
        # 记录每个断言的详细信息到Allure
        self._record_assertion_to_allure(expectation, assertion_passed)

        # 记录到本地result.txt中
        if self.reporter:
            self.reporter.record(expectation)
        
        return assertion_passed

    def _absent_callback_satisfies_expectation(self, expectation: AssertionExpectation) -> bool:
        """
        判断「整条回调未到达」时是否仍应判为通过。
        与 _check_field_assert 一致，用 ValueMatcher 以 actual=None 做匹配，使 None、None|ignore、!None 等语义与有回调时一致。
        单独一个 * 表示「有回调时任意值」，不视为允许无回调。
        """
        if not expectation.expected_fields:
            return False
        cfg = self.yaml_config.get(expectation.callback_type) or {}
        for key, exp in expectation.expected_fields.items():
            if not cfg.get(key, ""):
                return False
            if exp.strip() == "*":
                return False
            case_sensitive = key != "asr"
            if not self.value_matcher.match(exp, None, case_sensitive).success:
                return False
        return True
    
    def _do_json_assertion(self, expectation: AssertionExpectation, timeout: Optional[float]):
        """
        执行JSON回调断言，支持超时等待
        
        Args:
            expectation: 断言期望
            timeout: 超时时间（秒）
                    - None 或 0: 立即断言，不等待
                    - 正数: 等待指定秒数
                    - -1: 无限等待，直到信号触发
        """
        callback_record = None
        if timeout is None or timeout == 0:
            # 立即断言，不等待
            with self.assert_data.condition:
                callback_record = self.assert_data.find_callback_match(
                    expectation.callback_type, 
                    expectation.channel_id, 
                    wait=False
                )
        elif timeout == -1:
            # 无限等待，直到找到匹配的回调
            with self.assert_data.condition:
                while True:
                    # 检查是否有匹配的回调
                    callback_record = self.assert_data.find_callback_match(
                        expectation.callback_type,
                        expectation.channel_id,
                        wait=True  # 仅查找，不消费
                    )
                    
                    if callback_record:
                        # 找到匹配的回调，标记为已消费
                        callback_record.is_consumed = True
                        logger.info(f"无限等待模式：找到匹配的回调 {expectation.callback_type}")
                        break
                    
                    # 无限等待回调数据到达（不设置超时）
                    self.assert_data.condition.wait()
        else:
            # 带超时的等待断言
            start_time = time.time()
            with self.assert_data.condition:
                while True:
                    # 检查是否有匹配的回调
                    callback_record = self.assert_data.find_callback_match(
                        expectation.callback_type,
                        expectation.channel_id,
                        wait=True  # 仅查找，不消费
                    )
                    
                    if callback_record:
                        # 找到匹配的回调，标记为已消费
                        callback_record.is_consumed = True
                        break
                    
                    # 计算剩余超时时间
                    elapsed = time.time() - start_time
                    remaining = timeout - elapsed
                    
                    if remaining <= 0:
                        # 超时
                        logger.warning(f"等待回调超时: {expectation.callback_type}, 超时时间: {timeout}秒")
                        break
                    
                    # 等待回调数据到达，最长等待remaining秒
                    self.assert_data.condition.wait(timeout=remaining)
        
        # 执行断言
        if callback_record:
            if self._check_field_assert(expectation, callback_record.data):
                pass  # 匹配成功
            else:
                # 字段值不匹配
                expectation.status = AssertionStatus.FAILED
                if not expectation.error_message:
                    expectation.error_message = "回调数据字段值不匹配"
        else:
            # 检查「未收到回调」是否与期望一致：不能仅用 v=='none'，否则 skill:None|ignore
            # 等写法在 OR 首分支为 None 时无法识别；改为与字段断言一致，用 ValueMatcher 对 actual=None 判定。
            is_expecting_none = self._absent_callback_satisfies_expectation(expectation)
            if is_expecting_none:
                msg = []
                for k,v in expectation.expected_fields.items():
                    msg.append(f"{k}:{v}")
                expectation.status = AssertionStatus.SUCCESS
                expectation.actual_infos = ";".join(msg)
                expectation.expect_infos = ";".join(msg)
                logger.info(f"断言通过: 未收到回调 {expectation.callback_type}, 符合 'None' 预期。")
            else:
                # 没有找到对应类型的回调记录
                expectation.status = AssertionStatus.FAILED
                if timeout and timeout > 0:
                    expectation.error_message = f"等待 {timeout}秒 后仍未找到 {expectation.callback_type} 类型的回调记录"
                else:
                    expectation.error_message = f"没有找到 {expectation.callback_type} 类型的回调记录"
    
    def _do_api_assertion(self, expectation: AssertionExpectation, timeout: Optional[float]):
        """
        执行API断言，支持超时等待
        
        Args:
            expectation: 断言期望
            timeout: 超时时间（秒）
                    - None 或 0: 立即断言，不等待
                    - 正数: 等待指定秒数
                    - -1: 无限等待，直到信号触发
        """
        api_record = None
        
        if timeout is None or timeout == 0:
            # 立即断言，不等待
            with self.assert_data.condition:
                api_record = self.assert_data.find_api_call_match(
                    expectation.callback_type,
                    wait=False
                )
        elif timeout == -1:
            # 无限等待，直到找到匹配的API调用
            with self.assert_data.condition:
                while True:
                    # 检查是否有匹配的API调用
                    api_record = self.assert_data.find_api_call_match(
                        expectation.callback_type,
                        wait=True  # 仅查找，不消费
                    )
                    
                    if api_record:
                        # 找到匹配的API调用，标记为已消费
                        api_record.is_consumed = True
                        logger.info(f"无限等待模式：找到匹配的API调用 {expectation.callback_type}")
                        break
                    
                    # 无限等待API调用数据到达（不设置超时）
                    self.assert_data.condition.wait()
        else:
            # 带超时的等待断言
            start_time = time.time()
            with self.assert_data.condition:
                while True:
                    # 检查是否有匹配的API调用
                    api_record = self.assert_data.find_api_call_match(
                        expectation.callback_type,
                        wait=True  # 仅查找，不消费
                    )
                    
                    if api_record:
                        # 找到匹配的API调用，标记为已消费
                        api_record.is_consumed = True
                        break
                    
                    # 计算剩余超时时间
                    elapsed = time.time() - start_time
                    remaining = timeout - elapsed
                    
                    if remaining <= 0:
                        # 超时
                        logger.warning(f"等待API调用超时: {expectation.callback_type}, 超时时间: {timeout}秒")
                        break
                    
                    # 等待API调用数据到达，最长等待remaining秒
                    self.assert_data.condition.wait(timeout=remaining)
        
        # 执行断言
        if api_record:
            # 对API返回值进行断言
            expected_value = list(expectation.expected_fields.values())[0]  # API断言通常只有一个期望值
            actual_value = str(api_record.return_value)
            
            if actual_value == expected_value:
                expectation.status = AssertionStatus.SUCCESS
            else:
                expectation.status = AssertionStatus.FAILED
            
            expectation.actual_infos = f"api_data:{actual_value}"
            expectation.expect_infos = f"api_data:{expected_value}"
        else:
            # 没有找到对应类型的API调用记录
            expectation.status = AssertionStatus.FAILED
            if timeout and timeout > 0:
                expectation.error_message = f"等待 {timeout}秒 后仍未找到 {expectation.callback_type} 类型的API调用记录"
            else:
                expectation.error_message = f"没有找到 {expectation.callback_type} 类型的API调用记录"
    

    # ================= LOG ASSERTION LOGIC START =================
    def _do_log_assertion(self, expectation: AssertionExpectation, timeout: Optional[float]):
        """执行日志断言，支持超时等待"""
        # 默认重试间隔
        interval = 0.5
        
        if timeout is None or timeout == 0:
            self._execute_log_assertion(expectation)
        else:
            start_time = time.time()
            while True:
                # 每次循环都尝试执行断言
                self._execute_log_assertion(expectation)
                
                # 如果成功，直接跳出
                if expectation.status == AssertionStatus.SUCCESS:
                    break
                
                # 检查超时
                elapsed = time.time() - start_time
                if timeout != -1 and elapsed >= timeout:
                    if expectation.error_message:
                         expectation.error_message = f"超时({timeout}s): {expectation.error_message}"
                    break
                
                # 等待下一次轮询，对于LOG来说，可能需要等待文件写入
                time.sleep(interval)
        
    def _do_sum_assertion(self, expectation: AssertionExpectation, timeout: Optional[float]):
        """
        执行注册断言，支持COUNT等统计操作
        
        断言格式示例：
        [EXP]SUM [0,1,2,3]localASRResult COUNT == 1
        [EXP]SUM ASRResult COUNT >= 0
        """
        try:
            assert_value = expectation.expected_fields.get('value', '').strip()
            if not assert_value:
                expectation.status = AssertionStatus.ERROR
                expectation.error_message = "SUM断言表达式为空"
                return
            
            # 查找匹配的回调记录
            matched_records = self._find_sum_records(expectation, timeout)
            if matched_records is None:
                return

            success = self._evaluate_sum_assertion(assert_value, matched_records)
            
            # 设置断言结果
            callback_type = expectation.callback_type or "SUM"
            dedup_count = len(matched_records)

            if success:
                expectation.status = AssertionStatus.SUCCESS
                expectation.actual_infos = f"{callback_type} COUNT == {dedup_count}"
                # 只消费去重后的记录
                with self.assert_data.condition:
                    for record in matched_records:
                        record.is_consumed = True
            else:
                expectation.status = AssertionStatus.FAILED
                expectation.error_message = (
                    f"断言失败: {assert_value}, "
                    f"原始匹配 {dedup_count} 条"
                )
                expectation.actual_infos = (
                    f"{callback_type} COUNT == {dedup_count} "
                )
        
        except Exception as e:
            logger.error(f"执行注册断言失败: {e}")
            expectation.status = AssertionStatus.ERROR
            expectation.error_message = f"执行注册断言异常: {str(e)}"
    
    def _find_sum_records(self, expectation: AssertionExpectation, timeout: Optional[float]) -> Optional[List]:
        """
        查找SUM的回调记录，支持超时等待
        
        Returns:
            匹配的记录列表，如果超时返回None
        """
        if timeout is None or timeout == 0:
            with self.assert_data.condition:
                return self.assert_data.find_callback_all_match(
                    expectation.callback_type, 
                    expectation.channel_id, 
                )
        
        start_time = time.time()
        with self.assert_data.condition:
            while True:
                matched_records = self.assert_data.find_callback_all_match(
                    expectation.callback_type,
                    expectation.channel_id,
                )
                if matched_records:
                    return matched_records

                elapsed = time.time() - start_time
                if timeout != -1 and elapsed >= timeout:
                    expectation.status = AssertionStatus.FAILED
                    expectation.error_message = f"超时({timeout}s): 未找到满足条件的记录"
                    return None

                if timeout == -1:
                    self.assert_data.condition.wait()
                else:
                    remaining_time = timeout - elapsed
                    if remaining_time > 0:
                        self.assert_data.condition.wait(remaining_time)


    def _evaluate_sum_assertion(self, assert_value: str, matched_records: List) -> bool:
        """
        评估注册断言表达式
        
        Args:
            assert_value: 断言表达式，如 "COUNT == 1", "COUNT > 0"
            matched_records: 匹配的记录列表（已过滤冲突）
        
        Returns:
            断言是否通过
        """
        try:
            assert_value = assert_value.strip()
            count_match = re.match(r'COUNT\s*(.*)', assert_value, re.IGNORECASE)
            if not count_match:
                logger.warning(f"不支持的SUM断言表达式: {assert_value}")
                return False
            
            compare_expr = count_match.group(1).strip()
            actual_count = len(matched_records)
            operator = compare_expr.split(' ')[0]
            value = compare_expr.split(' ')[1]
            match_result = self._compare_values(str(actual_count), operator, value)
            return match_result
        
        except Exception as e:
            logger.error(f"评估注册断言表达式失败: {assert_value}, 错误: {e}")
            return False
    
    
    def _execute_log_assertion(self, expectation: AssertionExpectation):
        """执行具体的日志断言逻辑"""
        try:
            fields = expectation.expected_fields
            filename = fields.get('filename')
            mode = fields.get('mode')
            
            # 1. 确定文件路径 (支持环境变量替换，此处假设已处理或路径相对)
            # 如果是相对路径，默认在当前工作目录
            file_path = os.path.abspath(filename)
            
            if not os.path.exists(file_path):
                expectation.status = AssertionStatus.FAILED
                expectation.error_message = f"日志文件不存在: {file_path}"
                return

            # 2. 读取窗口内的日志 始终使用 log_file_pointers (Case起始锚点) 作为读取起点
            current_offset = self.log_file_pointers.get(file_path, 0)
            file_size = os.path.getsize(file_path)
            
            # 如果文件被截断（变小了），重置指针
            if file_size < current_offset:
                current_offset = 0
            
            # 读取新内容
            new_lines = []
            with open(file_path, 'rb') as f:
                f.seek(current_offset)
                # 使用errors='ignore'防止编码错误中断
                content = f.read().decode('utf-8', errors='ignore')
                if content:
                    new_lines = content.splitlines()
                
                # 记录当前读到的位置到 临时指针 只有当当前位置大于已有记录时才更新（防止某些逻辑回退，虽然一般不会）
                current_pos = f.tell()
                if current_pos > self.temp_log_pointers.get(file_path, 0):
                    self.temp_log_pointers[file_path] = current_pos

            # 3. 分支处理
            if mode == 'SEARCH':
                self._handle_log_search(expectation, new_lines)
            elif mode == 'MATCH':
                self._handle_log_match(expectation, new_lines)
            elif mode == 'DIFF':
                self._handle_log_diff(expectation, new_lines)
            else:
                expectation.status = AssertionStatus.ERROR
                expectation.error_message = f"未知LOG模式: {mode}"

        except Exception as e:
            expectation.status = AssertionStatus.ERROR
            expectation.error_message = f"日志断言异常: {str(e)}"
            logger.error(f"日志断言执行失败: {e}")

    def _handle_log_search(self, expectation: AssertionExpectation, lines: List[str]):
        """处理 SEARCH 模式"""
        fields = expectation.expected_fields
        keyword = fields.get('keyword')
        sub_op = fields.get('sub_op') # EXISTS, ABSENT, COUNT
        log_tag = "AND"
        if keyword and "&&" in keyword:
            sub_keywords = [k.strip() for k in keyword.split("&&") if k.strip()]
            log_tag = "AND"
        elif keyword and "||" in keyword:
            sub_keywords = [k.strip() for k in keyword.split("||") if k.strip()]
            log_tag = "OR"
        else:
            sub_keywords = [keyword] if keyword else []
            log_tag = "AND"

        count = 0
        for line in lines:
            if not sub_keywords:
                continue
            
            if log_tag == "AND":
                if all(sub in line for sub in sub_keywords):
                    count += 1
            else:
                if any(sub in line for sub in sub_keywords):
                    count += 1

        
        result = False
        actual_msg = f"Count={count}"
        expect_msg = ""
        
        if sub_op == 'EXISTS':
            result = count > 0
            expect_msg = f"'{keyword}' Exists"
        elif sub_op == 'ABSENT':
            result = count == 0
            expect_msg = f"'{keyword}' Absent"
        elif sub_op == 'COUNT':
            op = fields.get('operator')
            val = int(fields.get('value', 0))
            expect_msg = f"'{keyword}' Count {op} {val}"
            
            if op == '==': result = count == val
            elif op == '!=': result = count != val
            elif op == '>': result = count > val
            elif op == '<': result = count < val
            elif op == '>=': result = count >= val
            elif op == '<=': result = count <= val
        
        expectation.status = AssertionStatus.SUCCESS if result else AssertionStatus.FAILED
        expectation.actual_infos = actual_msg
        expectation.expect_infos = expect_msg

    def _handle_log_match(self, expectation: AssertionExpectation, lines: List[str]):
        """处理 MATCH 模式 (查找最后一行匹配)"""
        fields = expectation.expected_fields
        keyword = fields.get('keyword')
        match_type = fields.get('match_type') # KV, JSON, EXTRACT
        args = fields.get('match_args', [])
        
        # 倒序查找包含keyword的行
        target_line = None
        for line in reversed(lines):
            if keyword in line:
                target_line = line
                break
        
        if not target_line:
            expectation.status = AssertionStatus.FAILED
            expectation.error_message = f"未找到包含关键字 '{keyword}' 的日志"
            expectation.actual_infos = "Keyword not found"
            expectation.expect_infos = f"Log with '{keyword}'"
            return

        # 提取并验证
        extracted_value = None
        key_or_path = args[0]
        operator = args[1]
        expect_val = args[2] # 此时是字符串，可能需要类型转换
        
        try:
            if match_type == 'KV':
                # 智能KV提取
                extracted_value = self._smart_kv_extract(target_line, key_or_path)
            elif match_type == 'JSON':
                # JSON提取: 尝试在行里找到JSON子串并解析
                extracted_value = self._json_extract(target_line, key_or_path)
            elif match_type == 'EXTRACT':
                # 正则提取: key_or_path 当作 regex
                match = re.search(key_or_path.strip(), target_line)
                if match:
                    # 优先取第一个捕获组，否则取整个匹配
                    extracted_value = match.group(1) if match.lastindex and match.lastindex >= 1 else match.group(0)
            
            if extracted_value is None:
                expectation.status = AssertionStatus.FAILED
                expectation.error_message = f"无法从日志行提取到值. Type={match_type}, Key={key_or_path}"
                expectation.actual_infos = f"Line: {target_line.strip()}"
                return

            # 执行比较
            if self._compare_values(extracted_value, operator, expect_val):
                expectation.status = AssertionStatus.SUCCESS
            else:
                expectation.status = AssertionStatus.FAILED
                expectation.error_message = f"值不匹配: {key_or_path}"
            
            expectation.actual_infos = f"{extracted_value}"
            expectation.expect_infos = f"{operator} {expect_val}"
            
        except Exception as e:
            expectation.status = AssertionStatus.ERROR
            expectation.error_message = f"MATCH处理异常: {e}"

    def _handle_log_diff(self, expectation: AssertionExpectation, lines: List[str]):
        """处理 DIFF 模式 (时间差)"""
        fields = expectation.expected_fields
        start_key = fields.get('start_key')
        end_key = fields.get('end_key')
        operator = fields.get('operator')
        time_threshold_str = fields.get('time_threshold')
        
        # 解析阈值 (e.g., 500ms, 1s) -> seconds float
        threshold_sec = self._parse_time_duration(time_threshold_str)
        
        # 1. 找 End Log (最新的)
        end_time = None
        end_line_content = ""
        reversed_lines = list(reversed(lines))
        
        end_idx = -1
        for i, line in enumerate(reversed_lines):
            if end_key in line:
                t = self._extract_timestamp(line)
                if t:
                    end_time = t
                    end_idx = i
                    end_line_content = line
                    break
        
        if end_time is None:
            expectation.status = AssertionStatus.FAILED
            expectation.error_message = f"未找到结束日志或无法解析时间: '{end_key}'"
            return
            
        # 2. 找 Start Log (在 End Log 之前的)
        # 继续遍历 reversed_lines，从 end_idx + 1 开始
        start_time = None
        start_line_content = ""
        
        for i in range(end_idx + 1, len(reversed_lines)):
            line = reversed_lines[i]
            if start_key in line:
                t = self._extract_timestamp(line)
                if t:
                    start_time = t
                    start_line_content = line
                    break
        
        if start_time is None:
            expectation.status = AssertionStatus.FAILED
            expectation.error_message = f"找到结束日志 '{end_key}'，但在其之前未找到开始日志 '{start_key}'"
            return
            
        # 3. 计算差值并比较
        diff_sec = (end_time - start_time).total_seconds()
        
        if self._compare_values(diff_sec, operator, threshold_sec):
            expectation.status = AssertionStatus.SUCCESS
        else:
            expectation.status = AssertionStatus.FAILED
            expectation.error_message = f"时间差校验失败: {diff_sec}s {operator} {threshold_sec}s"
            
        expectation.actual_infos = f"Diff: {diff_sec:.3f}s ({start_key} -> {end_key})"
        expectation.expect_infos = f"{operator} {time_threshold_str}"

    # --- Log Assert Helpers ---
    def _smart_kv_extract(self, line: str, key: str) -> Optional[str]:
        """
        从行中提取 key 对应的值
        支持: key:value, key=value, key value
        """
        # 构造正则: key 后跟可选的 : 或 =，然后是可选空格，然后是值(非空字符 或 引号包围的串)
        # 这里的 regex 比较宽泛，匹配 Key 后面紧跟的内容
        escaped_key = re.escape(key)
        # 模式解释:
        # 1. key
        # 2. \s*[:=]?\s* : 分隔符 (冒号/等号/空格)
        # 3. ("[^"]*"|\S+) : 值 (双引号包围的内容 OR 连续非空字符)
        pattern = re.compile(rf'{escaped_key}\s*[:=]?\s*(?:"([^"]*)"|(\S+))')
        match = pattern.search(line)
        if match:
            # group(1) 是带引号的，group(2) 是不带引号的
            return match.group(1) if match.group(1) is not None else match.group(2)
        return None

    def _json_extract(self, line: str, json_path: str) -> Optional[Any]:
        """
        在行中查找 JSON 对象并提取路径
        """
        # 简单策略：查找行里的第一个 '{' 和最后一个 '}'
        start = line.find('{')
        end = line.rfind('}')
        if start != -1 and end != -1 and end > start:
            json_str = line[start:end+1]
            try:
                data = json.loads(json_str)
                # 使用 JsonUtil (假设支持 data.field 格式，如果路径以 $. 开头需要转换)
                # 简单处理 $.data.text -> data.text
                if json_path.startswith('$.'):
                    json_path = json_path[2:]
                return JsonUtil.parse(data, json_path)
            except:
                pass
        return None

    def _extract_timestamp(self, line: str) -> Optional[datetime]:
        """
        尝试从日志行提取时间戳
        支持格式: 
        2025-10-14 10:00:00.123
        2025/10/14 10:00:00
        10:00:00.123 (补全当前日期)
        """
        # 正则匹配常见时间格式
        # YYYY-MM-DD HH:MM:SS(.mmm)
        patterns = [
            r'(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}(?:\.\d+)?)',
            r'(\d{4}/\d{2}/\d{2}\s\d{2}:\d{2}:\d{2}(?:\.\d+)?)',
            r'(\d{2}:\d{2}:\d{2}\.\d+)' # 仅时间，一般日志会有日期，这里作为兜底
        ]
        
        for pat in patterns:
            match = re.search(pat, line)
            if match:
                ts_str = match.group(1)
                # 尝试解析
                formats = [
                    '%Y-%m-%d %H:%M:%S.%f',
                    '%Y-%m-%d %H:%M:%S',
                    '%Y/%m/%d %H:%M:%S.%f',
                    '%Y/%m/%d %H:%M:%S'
                ]
                for fmt in formats:
                    try:
                        return datetime.strptime(ts_str, fmt)
                    except ValueError:
                        continue
                
                # 处理仅有时分秒的情况，假设是当天
                if len(ts_str) < 15: # 简单长度判断
                     try:
                         t = datetime.strptime(ts_str, '%H:%M:%S.%f')
                         now = datetime.now()
                         return t.replace(year=now.year, month=now.month, day=now.day)
                     except:
                         pass
        return None

    def _parse_time_duration(self, duration_str: str) -> float:
        """解析时间字符串 500ms -> 0.5, 1s -> 1.0"""
        s = duration_str.lower().strip()
        if s.endswith('ms'):
            return float(s[:-2]) / 1000.0
        elif s.endswith('s'):
            return float(s[:-1])
        try:
            return float(s)
        except:
            return 0.0

    def _compare_values(self, actual: Any, operator: str, expected: str) -> bool:
        """
        通用值比较
        
        支持两种模式:
        1. 传统操作符模式: operator 为 '==', '!=', '>', '<', '>=', '<='
        2. 表达式模式: operator 为 '==' 且 expected 为表达式（如 '*', '>80', '~天气' 等）
        """
        # 如果是等值比较且expected包含特殊字符，尝试用ValueMatcher
        if operator == '==' and any(c in expected for c in ['*', '|', '&', '~', '@', '!', '(', ')', '[', ']', '>', '<']):
            result = self.value_matcher.match(expected, actual)
            return result.success
        
        # 传统操作符比较
        try:
            actual_num = float(actual)
            expect_num = float(expected)
            if operator == '==': return abs(actual_num - expect_num) < 1e-9
            if operator == '!=': return abs(actual_num - expect_num) > 1e-9
            if operator == '>': return actual_num > expect_num
            if operator == '<': return actual_num < expect_num
            if operator == '>=': return actual_num >= expect_num
            if operator == '<=': return actual_num <= expect_num
        except (ValueError, TypeError):
            # 字符串比较
            actual_str = str(actual) if actual is not None else ''
            expect_str = str(expected)
            if operator == '==': return actual_str == expect_str
            if operator == '!=': return actual_str != expect_str
            # 字符串大小比较通常不常用，但也支持
            if operator == '>': return actual_str > expect_str
            if operator == '<': return actual_str < expect_str
        return False

    def _do_file_assertion(self, expectation: AssertionExpectation, timeout: Optional[float]):
        """
        执行文件断言，支持超时等待
        
        Args:
            expectation: 断言期望
            timeout: 超时时间（秒）
                    - None 或 0: 立即断言，不等待
                    - 正数: 等待指定秒数
                    - -1: 无限等待，直到成功
        """
        if timeout is None or timeout == 0:
            # 立即断言，不等待
            self._execute_file_assertion(expectation)
        elif timeout == -1:
            # 无限等待，直到断言成功
            while True:
                self._execute_file_assertion(expectation)
                
                # 如果断言成功，直接返回
                if expectation.status == AssertionStatus.SUCCESS:
                    logger.info(f"无限等待模式：文件断言成功 {expectation.callback_type}")
                    break
                
                # 短暂休眠后重试，避免CPU占用过高
                time.sleep(0.2)
        else:
            # 带超时的等待断言，轮询检查文件状态
            start_time = time.time()
            while True:
                self._execute_file_assertion(expectation)
                
                # 如果断言成功，直接返回
                if expectation.status == AssertionStatus.SUCCESS:
                    break
                
                # 计算剩余超时时间
                elapsed = time.time() - start_time
                remaining = timeout - elapsed
                
                if remaining <= 0:
                    # 超时
                    logger.warning(f"文件断言等待超时: {expectation.callback_type}, 超时时间: {timeout}秒")
                    # 更新错误信息，添加超时提示
                    if expectation.error_message:
                        expectation.error_message = f"等待 {timeout}秒 后仍然失败: {expectation.error_message}"
                    break
                
                # 短暂休眠后重试，避免CPU占用过高
                time.sleep(min(0.1, remaining))
    
    def _execute_file_assertion(self, expectation: AssertionExpectation):
        """执行具体的文件断言检查"""
        if expectation.callback_type == 'FILEEXIT':
            self._check_file_exit(expectation)
        elif expectation.callback_type == 'FILESIZE':
            self._check_file_size(expectation)
        elif expectation.callback_type == 'FILEMD5':
            self._check_file_md5(expectation)
        elif expectation.callback_type == 'FILEDIF':
            self._check_file_diff(expectation)
        else:
            expectation.status = AssertionStatus.ERROR
            expectation.error_message = f"不支持的文件断言类型: {expectation.callback_type}"
    
    def _check_field_assert(self, expectation: AssertionExpectation, callback_data: Dict[str, Any]) -> bool:
        """
        尝试匹配回调数据
        
        使用 ValueMatcher 进行统一的值匹配，支持多种断言语法：
        - 精确匹配: value
        - 模糊匹配: *
        - 通配符: *pattern*
        - 或断言: v1|v2
        - 且断言: v1&v2
        - 非断言: !value
        - 空值/非空: None / !None
        - 数值比较: >N, <N, >=N, <=N
        - 范围断言: (N~M)
        - 包含/不包含: ~value / !~value
        - IN/NOT IN: @in(val) / @notin(val)
        - 忽略大小写: @i(expr)
        """
        try:
            exp_list = []
            acl_list = []
            assert_list = []
            match_messages = []
            
            for key, exp in expectation.expected_fields.items():
                field_path = self.yaml_config[expectation.callback_type].get(key, "")
                if not field_path:
                    # 字段在yaml配置中未定义，记录为失败但继续检查其余字段
                    logger.error(f"匹配异常: {key} not in {expectation.callback_type}.")
                    exp_list.append(f"{key}:{exp}")
                    acl_list.append(f"{key}:N/A(未配置)")
                    assert_list.append(False)
                    match_messages.append(f"{key}: 字段未在yaml配置中定义({expectation.callback_type})")
                    continue
                
                acl = JsonUtil.parse(callback_data, field_path)
                if "embeddedType" in key:
                    index_type = "embeddedType_" + str(acl)
                    acl = getattr(embeddedType, index_type, embeddedType.embeddedType_0)
                    
                exp_list.append(f"{key}:{exp}")
                acl_list.append(f"{key}:{acl}")
                
                # 使用统一值匹配器进行匹配
                # asr字段默认忽略大小写
                case_sensitive = (key != 'asr')
                match_result = self.value_matcher.match(exp, acl, case_sensitive)
                
                assert_list.append(match_result.success)
                match_messages.append(f"{key}: {match_result.message}")

            assert_result = all(assert_list)
            
            expectation.matched_data = callback_data
            expectation.status = AssertionStatus.SUCCESS if assert_result else AssertionStatus.FAILED
            expectation.actual_infos = ";".join(acl_list)
            expectation.expect_infos = ";".join(exp_list)
            
            # 如果匹配失败，记录详细的匹配信息
            if not assert_result:
                failed_fields = [msg for msg, success in zip(match_messages, assert_list) if not success]
                expectation.error_message = f"字段匹配失败: {'; '.join(failed_fields)}"
            
            return True

        except Exception as e:
            expectation.error_message = f"匹配异常: {e}"
            logger.error(f"断言匹配异常: {e}")
            return False

    def _print_test_result(self, expectation: AssertionExpectation, width=80):
        # 颜色代码
        GREEN = '\033[92m'
        RED = '\033[91m'
        RESET = '\033[0m'
        separator = "-" * width

        if expectation.status == AssertionStatus.ERROR:
            print(f"{RED}{separator}\n{expectation.error_message}\n{separator}{RESET}")
            return
        
        # 根据结果选择颜色和标记
        if expectation.status == AssertionStatus.SUCCESS:
            color = GREEN
            mark = "PASS"
        else:
            color = RED
            mark = "FAIL"

        # 构建显示内容
        expected_line = f"[预期][{expectation.callback_type}] [{expectation.channel_id}]{expectation.expect_infos}"
        actual_line = f"[实际][{expectation.callback_type}] [{expectation.channel_id}]{expectation.actual_infos}"

        # 构建带标记的实际行
        actual_with_mark = f"{actual_line}{' ' * 10} [{mark}]"

        # 打印结果
        logger.success(f"{separator}\n{expected_line}{RESET}\n{color}{actual_with_mark}{RESET}\n{separator}")
    
    def _record_assertion_to_allure(self, expectation: AssertionExpectation, assertion_passed: bool):
        """记录单个断言的详细信息到Allure报告"""
        try:
            # 构建断言状态标识
            status_icon = "✅" if assertion_passed else "❌"
            status_text = "PASS" if assertion_passed else "FAIL"
            
            # 构建步骤标题
            step_title = f"{status_icon} [EXP]   [{expectation.callback_type}] - {status_text}"

            try:
                with allure.step(f"[预期][{expectation.callback_type}] [{expectation.channel_id}]{expectation.expect_infos}"):
                    # 创建详细的断言信息
                    assertion_detail = {
                        "断言类型": expectation.callback_type,
                        "检查类型": "回调断言" if expectation.check_type == CheckType.JSON else "API断言",
                        "通道ID": expectation.channel_id,
                        "断言状态": status_text,
                        "原始断言": expectation.raw_assertion,
                        "预期结果": expectation.expect_infos,
                        "实际结果": expectation.actual_infos
                    }
                    
                    # 如果有错误信息，添加到详情中
                    if expectation.error_message:
                        assertion_detail["错误信息"] = expectation.error_message
                    
                    # 如果有匹配的数据，添加到详情中
                    if expectation.matched_data:
                        assertion_detail["匹配数据"] = expectation.matched_data
                    
                    # 将断言详情作为JSON附件添加到Allure
                    allure.attach(
                        json.dumps(assertion_detail, ensure_ascii=False, indent=2),
                        name=f"断言详情_{expectation.callback_type}",
                        attachment_type=allure.attachment_type.JSON
                    )
                with allure.step(f"[实际][{expectation.callback_type}] [{expectation.channel_id}]{expectation.actual_infos}"):
                    if not assertion_passed:
                        error_summary = f"断言失败: {expectation.callback_type}"
                        if expectation.error_message:
                            error_summary += f" - {expectation.error_message}"
                        
                        allure.attach(
                            error_summary,
                            name="断言失败原因",
                            attachment_type=allure.attachment_type.TEXT
                        )
                        
                        # 记录到日志
                        logger.debug(f"断言失败: {expectation.callback_type} - "
                                    f"预期: {expectation.expect_infos}, "
                                    f"实际: {expectation.actual_infos}")
                        raise AssertionError
                    else:
                        # 记录成功到日志
                        logger.info(f"断言通过: {expectation.callback_type} - "
                                f"{expectation.expect_infos}")
            except Exception as e:
                pass
                    
        except Exception as e:
            logger.error(f"记录断言到Allure失败: {e}")
    
    def get_assertion_stats(self) -> Dict[str, Any]:
        """获取断言统计信息"""
        with self.lock:
            total = len(self.assertion_results)
            passed = sum(self.assertion_results)
            failed = total - passed
            
            return {
                'total': total,
                'passed': passed, 
                'failed': failed,
                'all_passed': all(self.assertion_results)
            }
    
    def clear_assertion_results(self):
        """清理断言结果列表（在每个case执行前调用）"""
        with self.lock:
            self.assertion_results.clear()
            logger.debug("已清理断言结果列表")
    
    def _check_file_exit(self, expectation: AssertionExpectation):
        """
        检查文件是否存在
        格式: [EXP]FILEEXIT {WORKPATH}/lcs.zip 1
        """
        try:
            file_path = expectation.expected_fields.get('file_path', '')
            expected_exists = expectation.expected_fields.get('expected_exists', '1')
            
            # 检查文件是否存在
            file_exists = os.path.exists(file_path) and os.path.isfile(file_path)
            expected_bool = str(expected_exists).strip() == '1'
            
            if file_exists == expected_bool:
                expectation.status = AssertionStatus.SUCCESS
                expectation.actual_infos = f"{file_path} 文件存在: {file_exists}"
                expectation.expect_infos = f"{file_path} 期望存在: {expected_bool}"
            else:
                expectation.status = AssertionStatus.FAILED
                expectation.actual_infos = f"{file_path} 文件存在: {file_exists}"
                expectation.expect_infos = f"{file_path} 期望存在: {expected_bool}"
                expectation.error_message = f"文件存在性不匹配: 文件{file_path} {'存在' if file_exists else '不存在'}, 但期望{'存在' if expected_bool else '不存在'}"
                
        except Exception as e:
            expectation.status = AssertionStatus.ERROR
            expectation.error_message = f"检查文件存在性失败: {e}"
            logger.error(f"FILEEXIT断言失败: {e}")
    
    def _check_file_size(self, expectation: AssertionExpectation):
        """
        检查文件大小
        格式: [EXP]FILESIZE {workspace}lcs.zip > 1230
        """
        try:
            file_path = expectation.expected_fields.get('file_path', '')
            operator = expectation.expected_fields.get('operator', '=')
            expected_size = int(expectation.expected_fields.get('expected_size', '0'))
            
            # 检查文件是否存在
            if not os.path.exists(file_path) or not os.path.isfile(file_path):
                expectation.status = AssertionStatus.FAILED
                expectation.error_message = f"文件不存在: {file_path}"
                expectation.actual_infos = f"文件不存在"
                expectation.expect_infos = f"文件大小 {operator} {expected_size} 字节"
                return
            
            # 获取文件大小
            actual_size = os.path.getsize(file_path)
            
            # 执行比较
            result = False
            if operator == '>':
                result = actual_size > expected_size
            elif operator == '<':
                result = actual_size < expected_size
            elif operator == '=':
                result = actual_size == expected_size
            else:
                expectation.status = AssertionStatus.ERROR
                expectation.error_message = f"不支持的操作符: {operator}"
                return
            
            if result:
                expectation.status = AssertionStatus.SUCCESS
                expectation.actual_infos = f"{file_path} 文件大小: {actual_size} 字节"
                expectation.expect_infos = f"{file_path} 期望大小: {operator} {expected_size} 字节"
            else:
                expectation.status = AssertionStatus.FAILED
                expectation.actual_infos = f"{file_path} 文件大小: {actual_size} 字节"
                expectation.expect_infos = f"{file_path} 期望大小: {operator} {expected_size} 字节"
                expectation.error_message = f"文件大小不匹配: {actual_size} {operator} {expected_size} 不成立"
                
        except Exception as e:
            expectation.status = AssertionStatus.ERROR
            expectation.error_message = f"检查文件大小失败: {e}"
            logger.error(f"FILESIZE断言失败: {e}")
    
    def _check_file_md5(self, expectation: AssertionExpectation):
        """
        检查文件MD5值
        格式: [EXP]FILEMD5 {workspace}lcs.zip = 1921u2u192u1921212
        """
        try:
            file_path = expectation.expected_fields.get('file_path', '')
            expected_md5 = expectation.expected_fields.get('expected_md5', '').strip()
            
            # 检查文件是否存在
            if not os.path.exists(file_path) or not os.path.isfile(file_path):
                expectation.status = AssertionStatus.FAILED
                expectation.error_message = f"文件不存在: {file_path}"
                expectation.actual_infos = f"文件不存在"
                expectation.expect_infos = f"期望MD5: {expected_md5}"
                return
            
            # 计算文件MD5
            md5_hash = hashlib.md5()
            with open(file_path, 'rb') as f:
                # 分块读取大文件
                for chunk in iter(lambda: f.read(4096), b''):
                    md5_hash.update(chunk)
            actual_md5 = md5_hash.hexdigest()
            
            # 比较MD5值（不区分大小写）
            if actual_md5.lower() == expected_md5.lower():
                expectation.status = AssertionStatus.SUCCESS
                expectation.actual_infos = f"{file_path} 文件MD5: {actual_md5}"
                expectation.expect_infos = f"{file_path} 期望MD5: {expected_md5}"
            else:
                expectation.status = AssertionStatus.FAILED
                expectation.actual_infos = f"{file_path} 文件MD5: {actual_md5}"
                expectation.expect_infos = f"{file_path} 期望MD5: {expected_md5}"
                expectation.error_message = f"MD5值不匹配: 实际={actual_md5}, 期望={expected_md5}"
                
        except Exception as e:
            expectation.status = AssertionStatus.ERROR
            expectation.error_message = f"检查文件MD5失败: {e}"
            logger.error(f"FILEMD5断言失败: {e}")
    
    def _check_file_diff(self, expectation: AssertionExpectation):
        """
        检查文件内容差异（目前仅支持JSON）
        格式: [EXP]FILEDIF JSON {workspace}/daemon_tag.json data.shsh[0].txt.status=0
        """
        try:
            file_type = expectation.expected_fields.get('file_type', '').upper()
            file_path = expectation.expected_fields.get('file_path', '')
            json_path_expr = expectation.expected_fields.get('json_path_expr', '')  # 如: data.shsh[0].txt.status=0
            
            # 检查文件是否存在
            if not os.path.exists(file_path) or not os.path.isfile(file_path):
                expectation.status = AssertionStatus.FAILED
                expectation.error_message = f"文件不存在: {file_path}"
                expectation.actual_infos = f"文件不存在"
                expectation.expect_infos = f"{file_type}路径: {json_path_expr}"
                return
            
            if file_type == 'JSON':
                # 解析JSON文件
                with open(file_path, 'r', encoding='utf-8') as f:
                    json_data = json.load(f)
                
                # 解析JSON路径表达式，格式: data.shsh[0].txt.status=0
                # 分离路径和期望值
                if '=' not in json_path_expr:
                    expectation.status = AssertionStatus.ERROR
                    expectation.error_message = f"JSON路径表达式格式错误，需要包含=号: {json_path_expr}"
                    return
                
                # 分离路径和值
                path_part, expected_value = json_path_expr.rsplit('=', 1)
                path_part = path_part.strip()
                expected_value = expected_value.strip()
                
                # 解析JSON路径（支持数组索引，如 data.shsh[0].txt.status）
                # 将路径分割为部分，处理数组索引
                path_parts = []
                current_part = ""
                i = 0
                while i < len(path_part):
                    if path_part[i] == '.':
                        if current_part:
                            path_parts.append(current_part)
                            current_part = ""
                    elif path_part[i] == '[':
                        if current_part:
                            path_parts.append(current_part)
                            current_part = ""
                        # 查找]的位置
                        end_bracket = path_part.find(']', i)
                        if end_bracket == -1:
                            expectation.status = AssertionStatus.ERROR
                            expectation.error_message = f"JSON路径表达式格式错误，缺少]: {json_path_expr}"
                            return
                        index_str = path_part[i+1:end_bracket]
                        try:
                            index = int(index_str)
                            path_parts.append(index)
                        except ValueError:
                            expectation.status = AssertionStatus.ERROR
                            expectation.error_message = f"数组索引必须是整数: {index_str}"
                            return
                        i = end_bracket
                    else:
                        current_part += path_part[i]
                    i += 1
                
                if current_part:
                    path_parts.append(current_part)
                
                # 根据路径获取值
                actual_value = json_data
                for part in path_parts:
                    if isinstance(part, int):
                        # 数组索引
                        if isinstance(actual_value, list) and 0 <= part < len(actual_value):
                            actual_value = actual_value[part]
                        else:
                            expectation.status = AssertionStatus.FAILED
                            expectation.error_message = f"无法访问数组索引 {part}，路径: {path_part}"
                            expectation.actual_infos = f"{path_part} 路径无效"
                            expectation.expect_infos = f"{path_part} = {expected_value}"
                            return
                    else:
                        # 对象键
                        if isinstance(actual_value, dict) and part in actual_value:
                            actual_value = actual_value[part]
                        else:
                            expectation.status = AssertionStatus.FAILED
                            expectation.error_message = f"无法访问键 '{part}'，路径: {path_part}"
                            expectation.actual_infos = f"{path_part} 路径无效"
                            expectation.expect_infos = f"{path_part} = {expected_value}"
                            return
                
                # 比较值
                actual_str = str(actual_value)
                expected_str = expected_value
                
                # 尝试数值比较
                try:
                    if '.' in actual_str or '.' in expected_str:
                        # 浮点数比较
                        actual_float = float(actual_str)
                        expected_float = float(expected_str)
                        if abs(actual_float - expected_float) < 0.0001:  # 浮点数精度容忍
                            result = True
                        else:
                            result = False
                    else:
                        # 整数比较
                        actual_int = int(actual_str)
                        expected_int = int(expected_str)
                        result = (actual_int == expected_int)
                except ValueError:
                    # 字符串比较
                    result = (actual_str == expected_str)
                
                if result:
                    expectation.status = AssertionStatus.SUCCESS
                    expectation.actual_infos = f"{file_path} {path_part} = {actual_str}"
                    expectation.expect_infos = f"{file_path} {path_part} = {expected_value}"
                else:
                    expectation.status = AssertionStatus.FAILED
                    expectation.actual_infos = f"{file_path} {path_part} = {actual_str}"
                    expectation.expect_infos = f"{file_path} {path_part} = {expected_value}"
                    expectation.error_message = f"JSON值不匹配: {path_part} 实际={actual_str}, 期望={expected_value}"
            else:
                expectation.status = AssertionStatus.ERROR
                expectation.error_message = f"不支持的文件类型: {file_type}，目前仅支持JSON"
                
        except json.JSONDecodeError as e:
            expectation.status = AssertionStatus.ERROR
            expectation.error_message = f"JSON解析失败: {e}"
            logger.error(f"FILEDIF断言JSON解析失败: {e}")
        except Exception as e:
            expectation.status = AssertionStatus.ERROR
            expectation.error_message = f"检查文件内容差异失败: {e}"
            logger.error(f"FILEDIF断言失败: {e}")
