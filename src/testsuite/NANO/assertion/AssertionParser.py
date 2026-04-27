#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2025/10/14
# @Author  : huidong.bai
# @File    : AssertionParser.py
# @Software: PyCharm  
# @Mail    : MasterBai2018@outlook.com

import re
import shlex
from loguru import logger
from dataclasses import dataclass
from typing import Dict, List, Optional
from src.testsuite.NANO.config import AssertCodeTypeList, FILE_ASSERT_COMMANDS

class CheckType:
    JSON = 0
    API = 1
    FILE = 2
    LOG = 3
    SUM = 4


class AssertionStatus:
    UNCHECKED = 0
    SUCCESS = 1
    FAILED = 2
    ERROR = 3
    NONE = 4


@dataclass
class  AssertionExpectation:
    """断言期望"""
    callback_type: Optional[str]
    check_type: Optional[CheckType]
    channel_id: Optional[str]
    expected_fields: Dict[str, str]  # 字段名 -> 期望值
    actual_infos: Optional[str]
    expect_infos: Optional[str]
    status: Optional[AssertionStatus]
    raw_assertion: Optional[str]  # 原始断言语句
    matched_data: Optional[Dict] = None
    error_message: Optional[str] = None


class AssertionParser:
    """断言语法解析器"""
    
    def __init__(self, yaml_config: Dict):
        # 匹配格式：[1]text:123;lang:cmn;start:123;end:123 或 text:123;lang:cmn;start:123;end:123
        self.exp_pattern = re.compile(
            r'(?:\[(\d+)\])?(.*?)$'
        )
        self.yaml_config = yaml_config
    
    def parse_assertion(self, assert_type: str, assertion_data: List[str]) -> Optional[AssertionExpectation]:
        """
        解析断言语句
        Args:
            assert_type: 断言类型
            assertion_data: 断言内容字符串列表
        Returns:
            AssertionExpectation对象或None
        """
        try:
            # 日志断言类型判断 [EXP]LOG ...
            if assert_type == 'LOG':
                return self._parse_log_assertion(assertion_data)
            
            if assert_type == 'SUM':
                return self._parse_sum_assertion(assertion_data)
            
            # 文件断言类型判断
            if assert_type in FILE_ASSERT_COMMANDS:
                return self._parse_file_assertion(assert_type, assertion_data)
            
            check_type = CheckType.JSON
            if assert_type in self.yaml_config:
                check_type = CheckType.JSON
            elif assert_type in AssertCodeTypeList:
                check_type = CheckType.API
            else:
                logger.error(f"断言类型不存在: {assert_type}")
                return None

            # 去除首尾空格
            assertion_line = " ".join(assertion_data).strip()
            
            # 匹配数据断言格式
            match = self.exp_pattern.match(assertion_line)
            if not match:
                logger.error(f"断言语法错误: {assertion_line}")
                return None
            
            channel_str, data_str = match.groups()
            
            # 解析channel，默认为"0"
            channel_id = channel_str if channel_str else "0"
            
            # 处理data数据，去除首尾空格
            data_str = data_str.strip() if data_str else ""
            if not data_str:
                logger.error(f"数据内容不能为空: {assertion_line}")
                return None
            
            # 解析数据字段
            expected_fields = self._parse_field_assertions(data_str)
            if not expected_fields:
                logger.error(f"数据字段解析失败: {data_str}")
                return None
            
            return AssertionExpectation(
                callback_type=assert_type,
                channel_id=channel_id,
                check_type=check_type,
                expected_fields=expected_fields,
                expect_infos=data_str,
                actual_infos="None",
                status=AssertionStatus.UNCHECKED,
                raw_assertion=f"{assert_type} {assertion_line}"
            )
            
        except Exception as e:
            logger.error(f"解析断言失败: {assertion_data}, 错误: {e}")
            return None
    
    def _parse_file_assertion(self, assert_type: str, assertion_data: List[str]) -> Optional[AssertionExpectation]:
        """
        解析文件断言语句
        Args:
            assert_type: 文件断言类型 (FILEEXIT, FILESIZE, FILEMD5, FILEDIF)
            assertion_data: 断言内容字符串列表
        Returns:
            AssertionExpectation对象或None
        """
        try:
            # 将参数列表合并为字符串
            assertion_line = " ".join(assertion_data).strip()
            
            if assert_type == 'FILEEXIT':
                # 格式: [EXP]FILEEXIT {WORKPATH}/lcs.zip 1
                # 参数: 文件路径 期望值(1存在/0不存在，默认为1)
                parts = assertion_line.split(None, 1)
                if len(parts) < 1:
                    logger.error(f"FILEEXIT断言参数错误，需要至少文件路径: {assertion_line}")
                    return None
                file_path = parts[0]
                expected_value = parts[1] if len(parts) > 1 else "1"  # 默认期望存在
                
                expected_fields = {
                    'file_path': file_path,
                    'expected_exists': expected_value
                }
                
            elif assert_type == 'FILESIZE':
                # 格式: [EXP]FILESIZE {workspace}lcs.zip > 1230
                # 参数: 文件路径 比较操作符(>,<,=) 期望大小
                # 使用正则表达式匹配: 路径 + 操作符 + 数字
                size_pattern = re.compile(r'(.+?)\s*([><=])\s*(\d+)')
                match = size_pattern.match(assertion_line)
                if not match:
                    logger.error(f"FILESIZE断言语法错误: {assertion_line}")
                    return None
                file_path = match.group(1)
                operator = match.group(2)
                expected_size = match.group(3)
                
                expected_fields = {
                    'file_path': file_path,
                    'operator': operator,
                    'expected_size': expected_size
                }
                
            elif assert_type == 'FILEMD5':
                # 格式: [EXP]FILEMD5 {workspace}lcs.zip = 1921u2u192u1921212
                # 参数: 文件路径 = MD5值
                md5_pattern = re.compile(r'(.+?)\s*=\s*(.+)')
                match = md5_pattern.match(assertion_line)
                if not match:
                    logger.error(f"FILEMD5断言语法错误: {assertion_line}")
                    return None
                file_path = match.group(1)
                expected_md5 = match.group(2)
                
                expected_fields = {
                    'file_path': file_path,
                    'expected_md5': expected_md5
                }
                
            elif assert_type == 'FILEDIF':
                # 格式: [EXP]FILEDIF JSON {workspace}/daemon_tag.json data.shsh[0].txt.status=0
                # 参数: 文件类型(JSON) 文件路径 JSON路径表达式
                parts = assertion_line.split(None, 2)
                if len(parts) < 3:
                    logger.error(f"FILEDIF断言参数错误，需要文件类型、文件路径和JSON路径: {assertion_line}")
                    return None
                file_type = parts[0].upper()
                if file_type != 'JSON':
                    logger.error(f"FILEDIF目前仅支持JSON类型: {file_type}")
                    return None
                file_path = parts[1]
                json_path_expr = parts[2]  # 如: data.shsh[0].txt.status=0
                
                expected_fields = {
                    'file_type': file_type,
                    'file_path': file_path,
                    'json_path_expr': json_path_expr
                }
            else:
                logger.error(f"不支持的文件断言类型: {assert_type}")
                return None
            
            return AssertionExpectation(
                callback_type=assert_type,
                channel_id="0",  # 文件断言不使用channel
                check_type=CheckType.FILE,
                expected_fields=expected_fields,
                expect_infos=assertion_line,
                actual_infos="None",
                status=AssertionStatus.UNCHECKED,
                raw_assertion=f"{assert_type} {assertion_line}"
            )
            
        except Exception as e:
            logger.error(f"解析文件断言失败: {assertion_line}, 错误: {e}")
            return None
    
    def _parse_field_assertions(self, field_str: str) -> Dict[str, str]:
        """
        解析字段断言部分
        
        Args:
            field_str: 字段断言字符串，如 "asr:把空调启动;lang:cmn;confidence:>90"
            
        Returns:
            字段名到期望值的映射
        """
        expected_fields = {}

        # 如果field_str是：0: int 你好小红: str [5, 5, 5, 5]: list 就直接返回
        if ";" not in field_str and ":" not in field_str:
            expected_fields["api_data"] = field_str
            return expected_fields
        
        # 如果包含;按分号分割字段
        field_pairs = field_str.split(';')
        
        for pair in field_pairs:
            pair = pair.strip()
            if ':' not in pair:
                continue
                
            field_name, expected_value = pair.split(':', 1)
            field_name = field_name.strip()
            expected_value = expected_value.strip()
            
            if field_name and expected_value:
                expected_fields[field_name] = expected_value
        
        return expected_fields


    def _parse_sum_assertion(self, assertion_data: List[str]) -> Optional[AssertionExpectation]:
        """
        解析SUM断言语句
        Args:
            assertion_data: 断言内容字符串列表
        Returns:
            AssertionExpectation对象或None
        """

        try:
            full_line = " ".join(assertion_data).strip()
            parts = shlex.split(full_line)
            if len(parts) < 3:
                logger.error(f"SUM断言参数不足: {full_line}")
                return None
            register_params = parts[0]
            if register_params.find(f'[') != -1:
                register_type =register_params.split(']')[1]
                channel_id = register_params.split(']')[0].strip('[')
            else:
                register_type = register_params
                channel_id = "-1"
            register_value = parts[1:]
            expected_fields = {
                'type': register_type,
                'value': ' '.join(register_value) if register_value else ''
            }

            count_expr = ' '.join(register_value) if register_value else ''
            expect_infos = f"{register_type} {count_expr}" if count_expr else register_type
            
            return AssertionExpectation(
                    callback_type=register_type,
                    channel_id=channel_id,
                    check_type=CheckType.SUM,
                    expected_fields=expected_fields,
                    expect_infos=expect_infos,
                    actual_infos="None",
                    status=AssertionStatus.UNCHECKED,
                    raw_assertion=f"[EXP]SUM {full_line}"
                )
        except Exception as e:
            logger.error(f"解析注册断言语句失败: {assertion_data}, 错误: {e}")
            return None

    def _parse_log_assertion(self, assertion_data: List[str]) -> Optional[AssertionExpectation]:
        """
        解析日志断言语句
        DSL 示例: 
        app.log SEARCH "TagA" EXISTS
        123.log MATCH "add Client" KV "type" == 1
        123.log DIFF "Req" "Resp" < 500ms
        """
        try:
            full_line = " ".join(assertion_data).strip()
            # 使用 shlex 智能分割，处理引号内的空格
            parts = shlex.split(full_line)
            
            if len(parts) < 3:
                logger.error(f"LOG断言参数不足: {full_line}")
                return None
            
            filename = parts[0]
            mode = parts[1].upper()
            
            expected_fields = {
                'filename': filename,
                'mode': mode,
                'args': parts[2:] # 剩余参数供引擎进一步处理
            }
            
            # 初步验证模式结构
            if mode == 'SEARCH':
                # SEARCH "keyword" [EXISTS|ABSENT|COUNT op val]
                keyword = parts[2]
                sub_op = parts[3].upper() if len(parts) > 3 else "EXISTS"
                expected_fields.update({
                    'keyword': keyword,
                    'sub_op': sub_op
                })
                if sub_op == 'COUNT':
                    if len(parts) < 6: # SEARCH key COUNT == 1
                        logger.error(f"LOG SEARCH COUNT 参数不足: {full_line}")
                        return None
                    expected_fields['operator'] = parts[4]
                    expected_fields['value'] = parts[5]
                    
            elif mode == 'MATCH':
                # MATCH "keyword" [KV|JSON|EXTRACT] ...
                if len(parts) < 5:
                    logger.error(f"LOG MATCH 参数不足: {full_line}")
                    return None
                expected_fields.update({
                    'keyword': parts[2],
                    'match_type': parts[3].upper(), # KV, JSON, EXTRACT
                    # 后续参数: key/path/regex operator value
                    'match_args': parts[4:]
                })
                
            elif mode == 'DIFF':
                # DIFF "start_key" "end_key" op time
                if len(parts) < 6:
                     logger.error(f"LOG DIFF 参数不足: {full_line}")
                     return None
                expected_fields.update({
                    'start_key': parts[2],
                    'end_key': parts[3],
                    'operator': parts[4],
                    'time_threshold': parts[5]
                })
            
            else:
                logger.error(f"不支持的LOG断言模式: {mode}")
                return None
                
            return AssertionExpectation(
                callback_type='LOG',
                channel_id="0",
                check_type=CheckType.LOG,
                expected_fields=expected_fields,
                expect_infos=full_line,
                actual_infos="None",
                status=AssertionStatus.UNCHECKED,
                raw_assertion=f"[EXP]LOG {full_line}"
            )
            
        except Exception as e:
            logger.error(f"解析LOG断言失败: {full_line}, 错误: {e}")
            return None
