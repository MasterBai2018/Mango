#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2025/09/28
# @Author  : Claude Code
# @File    : dsl_engine.py
# @Software: PyCharm
# @Mail    : noreply@anthropic.com

import re
import json
import os
import io
from loguru import logger
from typing import List, Dict, Any, Tuple
from src.utils.common import check_line_filter, tts_info_to_except, timer
from .config import CLIENT_COMMANDS, ENVIRONMENT_VARIABLES
from enum import Enum


class Status(Enum):
    NOT_RUN = 0
    PASSED = 1
    FAILED = 2
    ERROR = 3

class DSLCommand:
    """DSL指令类"""

    def __init__(self, client_type: str, command: str, params: List[str], timeout: float = 0):
        self.client_type = client_type  # TSA, SET, VOI, OMS, SYS, TTS, EXP, TIA, PST, ENR
        self.command = command          # CREATE, START, DATA, EVENT, CMD等
        self.params = params            # 参数列表
        self.timeout = timeout          # 超时时间（秒），用于断言等待或指令延时
        self.message = ""               # 运行信息
        self.status: Status = Status.NOT_RUN  # 当前指令运行状态
        self.return_code = None         # 指令返回状态码

    def __repr__(self):
        timeout_str = f" <{self.timeout}>" if self.timeout > 0 else ""
        return f"[{self.client_type}]{self.command} {' '.join(self.params)}{timeout_str}"
    
    def to_dict(self) -> Dict[str, Any]:
        """将 DSLCommand 对象转换为可 JSON 序列化的字典"""
        return {
            'client_type': self.client_type,
            'command': self.command,
            'params': self.params,
            'timeout': self.timeout,
            'message': self.message,
            'status': self.status.value,  # 枚举转换为整数值
            'return_code': self.return_code
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DSLCommand':
        """从字典恢复 DSLCommand 对象"""
        cmd = cls(
            client_type=data['client_type'],
            command=data['command'],
            params=data['params'],
            timeout=data.get('timeout', 0)
        )
        cmd.message = data.get('message', '')
        cmd.status = Status(data.get('status', Status.NOT_RUN.value))  # 从整数值恢复枚举
        cmd.return_code = data.get('return_code')
        return cmd


class DSLCase:
    """DSL测试用例类"""

    def __init__(self, casefile: str, case_content: str, index: int, repeat_count: int = 1, case_type: str = "TEST"):
        self.unique_id = None
        self.casefile = casefile
        self.case_content = case_content.strip()
        self.repeat_count = repeat_count
        self.index = index
        self.case_type = case_type  # "TEST", "SETUP", "TEARDOWN", "SUITE_TEARDOWN"
        self.commands: List[DSLCommand] = []
        self.comment = ""
        
        # 参数化相关属性
        self.param_row = None      # 参数化数据行（字典）
        self.param_index = None    # 参数化索引（第几行）
        self.case_csv_file = None  # Case级CSV文件路径（None=未指定，使用全局CSV；"default"=显式使用全局CSV；文件路径=使用指定CSV）
        
        # Case行范围信息（用于生成执行指令）
        self.case_line_range = None  # Case在mgo文件中的行号范围，格式："start-end"（从1开始）
        self.param_line_range = None  # 参数化Case在CSV文件中的行号范围，格式："start-end"（从1开始，CSV文件行号）

    def __repr__(self):
        return f"DSLCase({self.unique_id})"

    def is_setup(self) -> bool:
        """判断是否是SETUP case"""
        return self.case_type == "SETUP"
    
    def is_teardown(self) -> bool:
        """判断是否是TEARDOWN case"""
        return self.case_type == "TEARDOWN"
    
    def is_case_setup(self) -> bool:
        """判断是否是CASE_SETUP case"""
        return self.case_type == "CASE_SETUP"
    
    def is_case_teardown(self) -> bool:
        """判断是否是CASE_TEARDOWN case"""
        return self.case_type == "CASE_TEARDOWN"
    
    def is_suite_teardown(self) -> bool:
        """判断是否是SUITE_TEARDOWN case（Suite级别后置，只在主进程执行一次）"""
        return self.case_type == "SUITE_TEARDOWN"
    
    def is_test(self) -> bool:
        """判断是否是普通测试case"""
        return self.case_type == "TEST"
    
    def to_dict(self) -> Dict[str, Any]:
        """将 DSLCase 对象转换为可 JSON 序列化的字典"""
        return {
            'casefile': self.casefile,
            'case_content': self.case_content,
            'index': self.index,
            'repeat_count': self.repeat_count,
            'case_type': self.case_type,
            'commands': [cmd.to_dict() for cmd in self.commands],
            'comment': self.comment,
            'param_row': self.param_row,
            'param_index': self.param_index,
            'case_csv_file': self.case_csv_file,
            'case_line_range': self.case_line_range,
            'param_line_range': self.param_line_range
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DSLCase':
        """从字典恢复 DSLCase 对象"""
        case = cls(
            casefile=data['casefile'],
            case_content=data['case_content'],
            index=data['index'],
            repeat_count=data.get('repeat_count', 1),
            case_type=data.get('case_type', 'TEST')
        )
        case.commands = [DSLCommand.from_dict(cmd_data) for cmd_data in data.get('commands', [])]
        case.comment = data.get('comment', '')
        case.param_row = data.get('param_row')
        case.param_index = data.get('param_index')
        case.case_csv_file = data.get('case_csv_file')
        case.case_line_range = data.get('case_line_range')
        case.param_line_range = data.get('param_line_range')
        return case


class DSLEngine:
    """DSL解析引擎"""
    # PARAMETERS 特殊列名（保留字）
    PARAMETERS_COLUMN = "PARAMETERS"

    def __init__(self, parameterized_data_file: str = None, parameterized_data_filter: str = None, steps_data_file: str = None, project: str = "24mm"):
        # 支持的客户端类型
        self.supported_clients = list(CLIENT_COMMANDS.keys())
        self.case_file = None
        self.project = project
        # 传统参数化数据文件（-P参数）
        self.parameterized_data_file = parameterized_data_file
        self.parameterized_data_filter = parameterized_data_filter  # 参数化数据行过滤（-PF参数，格式：10-20）
        self.parameterized_data = None  # CSV数据，解析后存储为字典列表（包含头部@参数展开）
        self.parameterized_header_params: Dict[str, str] = {}  # CSV头部@参数（每行共享的默认参数）
        
        # Case级CSV文件缓存（key: CSV文件路径，value: 解析后的数据列表）
        self._case_csv_cache: Dict[str, List[Dict[str, str]]] = {}
        # Case级CSV行号映射缓存（key: CSV文件路径，value: 数据行索引到文件行号的映射）
        self._case_csv_line_mapping: Dict[str, Dict[int, int]] = {}
        # Case级CSV表头行号缓存（key: CSV文件路径，value: 表头行号）
        self._case_csv_header_line: Dict[str, int] = {}
        # 全局CSV行号映射（数据行索引到文件行号的映射）
        self._global_csv_line_mapping: Dict[int, int] = {}
        self._global_csv_header_line: int = None  # 全局CSV表头行号
        
        # 动态步骤参数化数据文件（-S参数）
        self.steps_data_file = steps_data_file
        self.steps_data = None  # 步骤CSV数据，按CaseID分组存储
        
        # 支持的环境变量列表（从config导入）
        self.supported_env_variables = set(ENVIRONMENT_VARIABLES.keys())
        logger.info(f"DSL解析引擎初始化完成，支持 {len(self.supported_env_variables)} 个环境变量")
        
        # 加载参数化数据
        if self.parameterized_data_file:
            self._load_parameterized_data()
        
        # 加载动态步骤数据
        if self.steps_data_file:
            self._load_steps_data()
    
    def _parse_parameters_column(self, value: str) -> Dict[str, str]:
        """
        解析 PARAMETERS 特殊列的值。
        格式：key1:value1;key2:value2;key3:value3
        支持转义：; : 表示值中的字面量分号
        优先级：普通列 > PARAMETERS 列 > @头部参数
        """
        result = {}
        if not value or not value.strip():
            return result
        
        # 先把转义的 \; 替换为占位符，防止被误切
        ESCAPED_SEMICOLON = "\x00SEMI\x00"
        value = value.replace('\\;', ESCAPED_SEMICOLON)
        
        pairs = value.split(';')
        for pair in pairs:
            pair = pair.strip()
            if not pair:
                continue
            if ':' not in pair:
                logger.warning(f"PARAMETERS列中格式错误的键值对（缺少冒号）: '{pair}'，已跳过")
                continue
            key, val = pair.split(':', 1)  # 只切第一个 :，值里的 : 不受影响
            key = key.strip()
            val = val.strip().replace(ESCAPED_SEMICOLON, ';')  # 还原转义
            if not key:
                logger.warning(f"PARAMETERS列中键名为空的键值对: '{pair}'，已跳过")
                continue
            result[key] = val
        
        return result

    def _apply_parameters_column(self, rows: List[Dict[str, str]]) -> None:
        """
        原地处理所有行中的 PARAMETERS 特殊列：
        解析其 key:value;... 内容，将结果合并到行字典中。
        
        合并规则（优先级高→低）：
        普通列（显式列）> PARAMETERS 中的 key > @头部参数（已在调用前合并）
        
        处理完后，不删除原始 PARAMETERS 列（保留原始值，便于调试）。
        """
        for row in rows:
            raw_params = row.get(self.PARAMETERS_COLUMN)
            if not raw_params or not raw_params.strip():
                continue
            
            extra = self._parse_parameters_column(raw_params)
            if not extra:
                continue
            
            merged_count = 0
            for k, v in extra.items():
                # 只有当普通列中该 key 不存在，或值为空时才填充
                if k not in row or row[k] in (None, ''):
                    row[k] = v
                    merged_count += 1
            
            if merged_count > 0:
                logger.debug(f"PARAMETERS列解析：合并了 {merged_count} 个额外参数: {list(extra.keys())}")

    def _is_valid_csv_line(self, line: str) -> bool:
        """
        判断CSV行是否有效
        无效行包括：
        1. 空行
        2. 全是空格的行（strip之后是空的）
        3. 以"#"开头的行
        4. 以"//"开头的行
        """
        stripped_line = line.strip()
        if not line.strip() or stripped_line.startswith('#') or stripped_line.startswith('//'):
            return False
        return True

    def _parse_row_filter(self, filter_str: str, header_line_num: int, total_file_lines: int) -> Tuple[int, int]:
        """
        解析并验证行过滤参数（行号从文件第一行开始计数，包括@参数行、表头行、数据行）
        :param filter_str: 过滤字符串，格式如 "10-20" 或 "10-10"
        :param header_line_num: 表头行在文件中的行号（从1开始）
        :param total_file_lines: 文件总行数（从1开始）
        :return: (start_row, end_row) 文件行号（从1开始）
        :raises ValueError: 如果参数格式错误或无效
        """
        if not filter_str:
            raise ValueError("过滤参数不能为空")
        
        # 解析格式 "start-end"
        parts = filter_str.strip().split('-')
        if len(parts) != 2:
            raise ValueError(f"过滤参数格式错误，应为 'start-end' 格式，例如 '10-20'，实际输入: {filter_str}")
        
        try:
            start_str = parts[0].strip()
            end_str = parts[1].strip()
            
            # 检查是否为小数
            if '.' in start_str or '.' in end_str:
                raise ValueError(f"过滤参数不能包含小数，实际输入: {filter_str}")
            
            start_row = int(start_str)
            end_row = int(end_str)
            
            # 验证行号不能小于1
            if start_row < 1:
                raise ValueError(f"起始行号不能小于1，实际输入: {start_row}")
            if end_row < 1:
                raise ValueError(f"结束行号不能小于1，实际输入: {end_row}")
            
            # 验证开始行号不能大于结束行号
            if start_row > end_row:
                raise ValueError(f"起始行号({start_row})不能大于结束行号({end_row})")
            
            # 验证行号不能超过文件总行数
            if start_row > total_file_lines:
                raise ValueError(f"起始行号({start_row})超过文件总行数({total_file_lines})")
            if end_row > total_file_lines:
                raise ValueError(f"结束行号({end_row})超过文件总行数({total_file_lines})")
            
            # 验证：如果指定的行号范围包含表头行，应该报错
            if start_row <= header_line_num <= end_row:
                raise ValueError(f"过滤行号范围({start_row}-{end_row})包含表头行(第{header_line_num}行)，不能过滤表头行")
            
            return start_row, end_row
            
        except ValueError as e:
            # 如果是我们抛出的ValueError，直接重新抛出
            if "过滤参数" in str(e) or "行号" in str(e) or "不能" in str(e) or "超过" in str(e) or "包含" in str(e):
                raise
            # 否则是int转换失败
            raise ValueError(f"过滤参数必须为整数，实际输入: {filter_str}") from e

    def _load_parameterized_data(self):
        """加载参数化数据CSV文件，支持自动检测分隔符（逗号或Tab）"""
        import csv
        try:
            # 支持相对路径和绝对路径
            csv_path = self.parameterized_data_file
            if not os.path.isabs(csv_path):
                # 相对路径：相对于.mgo文件所在目录
                if self.case_file:
                    mgo_dir = os.path.dirname(self.case_file)
                    csv_path = os.path.join(mgo_dir, csv_path)
            
            # 检查文件是否存在
            if not os.path.exists(csv_path):
                raise FileNotFoundError(f"参数化数据文件不存在: {csv_path}")
            
            # 读取CSV文件 - 解析头部@参数，并对正文自动检测分隔符与过滤无效行
            with open(csv_path, 'r', encoding='utf-8') as f:
                # 读取所有行
                all_lines = f.readlines()
                
                header_params: Dict[str, str] = {}   # 头部@参数
                valid_lines = []                     # CSV正文有效行
                header_line_num = None               # 表头行在文件中的行号（从1开始）
                data_line_mapping = {}               # 数据行索引到文件行号的映射 {data_index: file_line_num}
                
                file_line_num = 0  # 文件行号计数器（从1开始）
                
                for raw_line in all_lines:
                    file_line_num += 1
                    stripped = raw_line.strip()
                    
                    # 解析以 @ 开头的头部参数行，例如：@DELAY: 0
                    if stripped.startswith('@'):
                        # 去掉前缀 @，按第一个冒号分割为 key:value
                        header_body = stripped[1:]
                        if ':' in header_body:
                            key, value = header_body.split(':', 1)
                            key = key.strip()
                            value = value.strip()
                            if key:
                                # 如果头部参数本身就是 PARAMETERS，先解析其内容再存入
                                if key == self.PARAMETERS_COLUMN:
                                    extra = self._parse_parameters_column(value)
                                    for ek, ev in extra.items():
                                        header_params[ek] = ev  # 各 key 平铺到 header_params
                                    logger.debug(f"检测到 @PARAMETERS 头部参数，展开了 {len(extra)} 个键值对")
                                else:
                                    header_params[key] = value
                                    logger.debug(f"检测到CSV头参数: {key}={value}")
                            else:
                                logger.warning(f"忽略格式错误的头参数行: {raw_line.rstrip()}")
                        else:
                            logger.warning(f"忽略无法解析的头参数行(缺少冒号): {raw_line.rstrip()}")
                        # 头部行不参与CSV正文解析
                        continue
                    
                    # 其他行按原有规则筛选是否为有效CSV正文行
                    if self._is_valid_csv_line(raw_line):
                        # 第一行有效行是表头
                        if header_line_num is None:
                            header_line_num = file_line_num
                            logger.debug(f"检测到表头行，文件行号: {header_line_num}")
                        else:
                            # 数据行：记录数据行索引到文件行号的映射
                            # 数据行索引 = valid_lines中已有行数 - 1（减去表头行）
                            data_index = len(valid_lines) - 1  # 此时valid_lines已包含表头，所以-1后从0开始
                            data_line_mapping[data_index] = file_line_num
                        valid_lines.append(raw_line)
                
                if not valid_lines:
                    raise ValueError(f"参数化数据文件没有有效数据行: {csv_path}")
                
                # 使用过滤后的行检测分隔符
                # 读取一小段样本用于检测分隔符（使用过滤后的前几行）
                sample = ''.join(valid_lines[:10])  # 取前10行作为样本
                
                # 使用csv.Sniffer自动检测分隔符
                delimiter = None
                try:
                    sniffer = csv.Sniffer()
                    dialect = sniffer.sniff(sample, delimiters=',\t')
                    delimiter = dialect.delimiter
                    logger.debug(f"检测到CSV分隔符: {'Tab' if delimiter == chr(9) else repr(delimiter)}")
                except Exception:
                    # 如果Sniffer检测失败，手动检测第一行有效行
                    first_line = valid_lines[0].strip()
                    
                    if first_line:
                        # 统计逗号和Tab的出现次数
                        comma_count = first_line.count(',')
                        tab_count = first_line.count('\t')
                        
                        if tab_count > comma_count:
                            delimiter = '\t'
                            logger.debug(f"手动检测到CSV分隔符: Tab (Tab出现{tab_count}次, 逗号出现{comma_count}次)")
                        elif comma_count > 0:
                            delimiter = ','
                            logger.debug(f"手动检测到CSV分隔符: 逗号 (逗号出现{comma_count}次, Tab出现{tab_count}次)")
                        else:
                            # 如果都没有，默认使用Tab（因为很多CSV文件实际是TSV）
                            delimiter = '\t'
                            logger.warning(f"无法检测到分隔符，使用默认Tab分隔符")
                    else:
                        delimiter = '\t'
                        logger.warning(f"文件为空或只有空行，使用默认Tab分隔符")
                
                # 使用过滤后的内容创建DictReader
                filtered_content = ''.join(valid_lines)
                reader = csv.DictReader(io.StringIO(filtered_content), delimiter=delimiter)
                rows = list(reader)
            
            if not rows:
                raise ValueError(f"参数化数据文件为空: {csv_path}")
            
            # 如果存在头部@参数，将其合并到每一行数据中 规则：行内同名列优先，可以覆盖头部参数；只为缺失字段填充默认值
            if header_params:
                for row in rows:
                    for k, v in header_params.items():
                        # 仅当该列不存在或为空字符串时才填充
                        if k not in row or row[k] in (None, ''):
                            row[k] = v
                logger.info(f"检测到 {len(header_params)} 个CSV头部参数，已合并到每一行数据中: {header_params}")
            
            # 解析并合并 PARAMETERS 特殊列
            self._apply_parameters_column(rows)
            if any(self.PARAMETERS_COLUMN in row for row in rows):
                logger.info(f"检测到 PARAMETERS 特殊列，已解析并合并额外参数到各行")
            
            # 应用行过滤（如果指定了过滤参数）
            if self.parameterized_data_filter:
                total_file_lines = len(all_lines)
                if header_line_num is None:
                    raise ValueError("无法确定表头行位置，无法应用行过滤")
                
                # 解析并验证过滤参数（行号从文件第一行开始计数）
                start_file_line, end_file_line = self._parse_row_filter(
                    self.parameterized_data_filter, 
                    header_line_num, 
                    total_file_lines
                )
                
                # 根据文件行号范围过滤数据行
                # 需要找到对应的数据行索引
                filtered_rows = []
                filtered_line_mapping = {}  # 重新构建过滤后的行号映射
                for data_index, row in enumerate(rows):
                    # 获取该数据行对应的文件行号
                    file_line_num = data_line_mapping.get(data_index)
                    if file_line_num is None:
                        # 如果找不到映射，说明这是第一行数据（索引0），需要计算文件行号
                        # 表头行号 + 1 = 第一行数据行号
                        file_line_num = header_line_num + 1
                        logger.debug(f"数据行索引 {data_index} 对应的文件行号: {file_line_num} (表头行号 {header_line_num} + 1)")
                    
                    # 如果文件行号在指定范围内，保留该行
                    if start_file_line <= file_line_num <= end_file_line:
                        # 重新映射：过滤后的索引 -> 原始文件行号
                        new_data_index = len(filtered_rows)
                        filtered_line_mapping[new_data_index] = file_line_num
                        filtered_rows.append(row)
                        logger.debug(f"保留数据行索引 {data_index} (文件行号 {file_line_num})")
                
                if not filtered_rows:
                    raise ValueError(f"过滤后没有数据行，过滤范围: {start_file_line}-{end_file_line}，总文件行数: {total_file_lines}")
                
                rows = filtered_rows
                # 更新行号映射为过滤后的映射
                data_line_mapping = filtered_line_mapping
                logger.info(f"应用行过滤: {self.parameterized_data_filter}，保留文件第 {start_file_line}-{end_file_line} 行的数据（共 {len(rows)} 行数据）")
            
            # 保存到实例属性，供后续参数化使用
            self.parameterized_header_params = header_params
            self.parameterized_data = rows
            # 保存全局CSV行号映射（数据行索引到文件行号的映射）
            self._global_csv_line_mapping = data_line_mapping
            # 保存全局CSV表头行号
            self._global_csv_header_line = header_line_num
            
            logger.info(f"成功加载参数化数据文件: {csv_path}, 共 {len(self.parameterized_data)} 行数据")
            logger.info(f"CSV列名: {list(self.parameterized_data[0].keys())}")
            
        except Exception as e:
            logger.error(f"加载参数化数据文件失败: {e}")
            raise

    def _load_case_csv_file(self, csv_file_path: str) -> List[Dict[str, str]]:
        """
        加载Case级CSV文件（支持缓存）
        
        Args:
            csv_file_path: CSV文件路径（相对路径或绝对路径）
            
        Returns:
            解析后的CSV数据列表（字典列表）
        """
        import csv
        
        try:
            # 检查文件是否存在
            if not os.path.exists(csv_file_path):
                raise FileNotFoundError(f"Case级CSV文件不存在: {csv_file_path} (原始路径: {csv_file_path})")
            
            # 使用绝对路径+过滤参数作为缓存key，确保同一文件和同一过滤参数只加载一次
            # 如果-PF参数存在，将其加入到缓存key中
            cache_key = csv_file_path
            if self.parameterized_data_filter:
                cache_key = f"{csv_file_path}::PF:{self.parameterized_data_filter}"
            
            # 检查缓存
            if cache_key in self._case_csv_cache:
                logger.debug(f"使用缓存的Case级CSV文件: {cache_key}")
                # 返回缓存的数据，行号映射也会被使用
                return self._case_csv_cache[cache_key]
            
            # 读取CSV文件 - 解析头部@参数，并对正文自动检测分隔符与过滤无效行
            with open(csv_file_path, 'r', encoding='utf-8') as f:
                # 读取所有行
                all_lines = f.readlines()
                
                header_params: Dict[str, str] = {}   # 头部@参数
                valid_lines = []                     # CSV正文有效行
                header_line_num = None               # 表头行在文件中的行号（从1开始）
                data_line_mapping = {}               # 数据行索引到文件行号的映射 {data_index: file_line_num}
                
                file_line_num = 0  # 文件行号计数器（从1开始）
                
                for raw_line in all_lines:
                    file_line_num += 1
                    stripped = raw_line.strip()
                    
                    # 解析以 @ 开头的头部参数行，例如：@DELAY: 0
                    if stripped.startswith('@'):
                        # 去掉前缀 @，按第一个冒号分割为 key:value
                        header_body = stripped[1:]
                        if ':' in header_body:
                            key, value = header_body.split(':', 1)
                            key = key.strip()
                            value = value.strip()
                            if key:
                                # 如果头部参数本身就是 PARAMETERS，先解析其内容再存入
                                if key == self.PARAMETERS_COLUMN:
                                    extra = self._parse_parameters_column(value)
                                    for ek, ev in extra.items():
                                        header_params[ek] = ev  # 各 key 平铺到 header_params
                                    logger.debug(f"检测到 @PARAMETERS 头部参数，展开了 {len(extra)} 个键值对")
                                else:
                                    header_params[key] = value
                                    logger.debug(f"检测到Case级CSV头参数: {key}={value}")
                        # 头部行不参与CSV正文解析
                        continue
                    
                    # 其他行按原有规则筛选是否为有效CSV正文行
                    if self._is_valid_csv_line(raw_line):
                        # 第一行有效行是表头
                        if header_line_num is None:
                            header_line_num = file_line_num
                            logger.debug(f"检测到Case级CSV表头行，文件行号: {header_line_num}")
                        else:
                            # 数据行：记录数据行索引到文件行号的映射
                            # 数据行索引 = valid_lines中已有行数 - 1（减去表头行）
                            data_index = len(valid_lines) - 1  # 此时valid_lines已包含表头，所以-1后从0开始
                            data_line_mapping[data_index] = file_line_num
                        valid_lines.append(raw_line)
                
                if not valid_lines:
                    raise ValueError(f"Case级CSV文件没有有效数据行: {csv_file_path}")
                
                # 使用过滤后的行检测分隔符
                sample = ''.join(valid_lines[:10])  # 取前10行作为样本
                
                # 使用csv.Sniffer自动检测分隔符
                delimiter = None
                try:
                    sniffer = csv.Sniffer()
                    dialect = sniffer.sniff(sample, delimiters=',\t')
                    delimiter = dialect.delimiter
                    logger.debug(f"检测到Case级CSV分隔符: {'Tab' if delimiter == chr(9) else repr(delimiter)}")
                except Exception:
                    # 如果Sniffer检测失败，手动检测第一行有效行
                    first_line = valid_lines[0].strip()
                    
                    if first_line:
                        # 统计逗号和Tab的出现次数
                        comma_count = first_line.count(',')
                        tab_count = first_line.count('\t')
                        
                        if tab_count > comma_count:
                            delimiter = '\t'
                        elif comma_count > 0:
                            delimiter = ','
                        else:
                            delimiter = '\t'
                    else:
                        delimiter = '\t'
                
                # 使用过滤后的内容创建DictReader
                filtered_content = ''.join(valid_lines)
                reader = csv.DictReader(io.StringIO(filtered_content), delimiter=delimiter)
                rows = list(reader)
            
            if not rows:
                raise ValueError(f"Case级CSV文件为空: {csv_file_path}")
            
            # 如果存在头部@参数，将其合并到每一行数据中
            if header_params:
                for row in rows:
                    for k, v in header_params.items():
                        # 仅当该列不存在或为空字符串时才填充
                        if k not in row or row[k] in (None, ''):
                            row[k] = v
                logger.debug(f"Case级CSV检测到 {len(header_params)} 个头部参数，已合并到每一行数据中")
            
            # 解析并合并 PARAMETERS 特殊列
            self._apply_parameters_column(rows)
            
            # 应用行过滤（如果指定了过滤参数 -PF）
            if self.parameterized_data_filter:
                total_file_lines = len(all_lines)
                if header_line_num is None:
                    raise ValueError(f"无法确定Case级CSV表头行位置，无法应用行过滤: {csv_file_path}")
                
                # 解析并验证过滤参数（行号从文件第一行开始计数）
                start_file_line, end_file_line = self._parse_row_filter(
                    self.parameterized_data_filter, 
                    header_line_num, 
                    total_file_lines
                )
                
                # 根据文件行号范围过滤数据行
                # 需要找到对应的数据行索引
                filtered_rows = []
                filtered_line_mapping = {}  # 重新构建过滤后的行号映射
                for data_index, row in enumerate(rows):
                    # 获取该数据行对应的文件行号
                    file_line_num = data_line_mapping.get(data_index)
                    if file_line_num is None:
                        # 如果找不到映射，说明这是第一行数据（索引0），需要计算文件行号
                        # 表头行号 + 1 = 第一行数据行号
                        file_line_num = header_line_num + 1
                        logger.debug(f"Case级CSV数据行索引 {data_index} 对应的文件行号: {file_line_num} (表头行号 {header_line_num} + 1)")
                    
                    # 如果文件行号在指定范围内，保留该行
                    if start_file_line <= file_line_num <= end_file_line:
                        # 重新映射：过滤后的索引 -> 原始文件行号
                        new_data_index = len(filtered_rows)
                        filtered_line_mapping[new_data_index] = file_line_num
                        filtered_rows.append(row)

                if not filtered_rows:
                    raise ValueError(f"Case级CSV过滤后没有数据行，过滤范围: {start_file_line}-{end_file_line}，总文件行数: {total_file_lines}，文件: {csv_file_path}")
                
                rows = filtered_rows
                # 更新行号映射为过滤后的映射
                data_line_mapping = filtered_line_mapping
                logger.info(f"Case级CSV应用行过滤: {self.parameterized_data_filter}，保留文件第 {start_file_line}-{end_file_line} 行的数据（共 {len(rows)} 行数据）")
            
            # 缓存结果（使用绝对路径作为key）
            self._case_csv_cache[cache_key] = rows
            # 缓存行号映射
            self._case_csv_line_mapping[cache_key] = data_line_mapping
            # 缓存表头行号
            if header_line_num is not None:
                self._case_csv_header_line[cache_key] = header_line_num
            
            logger.info(f"成功加载Case级CSV文件: {csv_file_path}, 共 {len(rows)} 行数据")
            logger.debug(f"CSV列名: {list(rows[0].keys())}")
            
            return rows
            
        except Exception as e:
            logger.error(f"加载Case级CSV文件失败: {csv_file_path}, 错误: {e}")
            raise

    def _load_steps_data(self):
        """
        加载动态步骤参数化数据CSV文件
        格式要求：必须包含 CaseID 和 StepCase 两列
        按CaseID分组存储步骤列表
        """
        import csv
        from collections import defaultdict
        
        try:
            # 支持相对路径和绝对路径
            csv_path = self.steps_data_file
            if not os.path.isabs(csv_path):
                # 相对路径：相对于.mgo文件所在目录
                if self.case_file:
                    mgo_dir = os.path.dirname(self.case_file)
                    csv_path = os.path.join(mgo_dir, csv_path)
            
            # 检查文件是否存在
            if not os.path.exists(csv_path):
                raise FileNotFoundError(f"动态步骤数据文件不存在: {csv_path}")
            
            # 读取CSV文件 - 自动检测分隔符并过滤无效行
            with open(csv_path, 'r', encoding='utf-8') as f:
                # 读取所有行并过滤无效行
                all_lines = f.readlines()
                valid_lines = [line for line in all_lines if self._is_valid_csv_line(line)]
                
                if not valid_lines:
                    raise ValueError(f"动态步骤数据文件没有有效数据行: {csv_path}")
                
                # 使用过滤后的行检测分隔符
                # 读取一小段样本用于检测分隔符（使用过滤后的前几行）
                sample = ''.join(valid_lines[:10])  # 取前10行作为样本
                
                try:
                    sniffer = csv.Sniffer()
                    dialect = sniffer.sniff(sample, delimiters=',\t')
                    delimiter = dialect.delimiter
                    logger.debug(f"检测到步骤CSV分隔符: {'Tab' if delimiter == chr(9) else repr(delimiter)}")
                except Exception:
                    delimiter = ','
                    logger.warning(f"无法自动检测步骤CSV分隔符，使用默认逗号分隔符")
                
                # 使用过滤后的内容创建DictReader
                filtered_content = ''.join(valid_lines)
                reader = csv.DictReader(io.StringIO(filtered_content), delimiter=delimiter)
                rows = list(reader)
            
            if not rows:
                raise ValueError(f"动态步骤数据文件为空: {csv_path}")
            
            # 验证必需的列
            if 'CaseID' not in rows[0] or 'StepCase' not in rows[0]:
                raise ValueError(
                    f"动态步骤CSV文件格式错误：必须包含 'CaseID' 和 'StepCase' 列\n"
                    f"当前列名: {list(rows[0].keys())}"
                )
            
            # 按CaseID分组
            grouped_steps = defaultdict(list)
            for row in rows:
                case_id = row['CaseID'].strip()
                step_case = row['StepCase'].strip()
                
                if not step_case:
                    logger.warning(f"跳过空步骤: CaseID={case_id}")
                    continue
                
                grouped_steps[case_id].append(step_case)
            
            self.steps_data = dict(grouped_steps)
            
            logger.info(f"成功加载动态步骤数据文件: {csv_path}")
            logger.info(f"共 {len(rows)} 个步骤，分布在 {len(self.steps_data)} 个CaseID中")
            for case_id, steps in self.steps_data.items():
                logger.debug(f"  CaseID={case_id}: {len(steps)} 个步骤")
            
        except Exception as e:
            logger.error(f"加载动态步骤数据文件失败: {e}")
            raise

    def _has_placeholder(self, text: str) -> bool:
        """检测文本中是否包含 ${variable} 占位符"""
        pattern = r'\$\{[^}]+\}'
        return re.search(pattern, text) is not None
    
    def _get_placeholders(self, text: str) -> List[str]:
        """提取文本中的所有占位符变量名"""
        pattern = r'\$\{([^}]+)\}'
        return re.findall(pattern, text)
    
    def _replace_placeholders(self, text: str, params: Dict[str, str]) -> str:
        """
        替换文本中的 ${variable} 占位符为实际值
        
        Args:
            text: 包含占位符的文本
            params: 参数字典 {变量名: 值}
            allow_empty: 是否允许空值（如果为True，空值返回空字符串；如果为False，空值会报错）
        
        Returns:
            替换后的文本
        """
        pattern = r'\$\{([^}]+)\}'
        
        def replacer(match):
            var_name = match.group(1)
            if var_name not in params:
                # 允许空值，返回空字符串
                return ""
            value = params[var_name]
            # 如果值为None或空字符串，根据allow_empty决定行为
            if value is None or (isinstance(value, str) and value.strip() == ""):
                # 允许空值，返回空字符串
                return ""
            return value
        
        try:
            result = re.sub(pattern, replacer, text)
            return result
        except ValueError as e:
            logger.error(f"替换占位符失败: {e}")
            raise

    def _case_has_placeholders(self, case: DSLCase) -> bool:
        """
        检测DSLCase中是否包含占位符
        
        Args:
            case: DSLCase对象
            
        Returns:
            True if 包含占位符，False otherwise
        """
        # 检查case中所有command的命令名和参数
        for command in case.commands:
            # 检查command命令名
            if self._has_placeholder(command.command):
                return True
            # 检查command的所有参数
            for param in command.params:
                if self._has_placeholder(param):
                    return True
        return False
    
    def _replace_case_placeholders(self, case: DSLCase, params: Dict[str, str]):
        """
        原地替换case中的所有占位符（用于SETUP/TEARDOWN）
        
        Args:
            case: DSLCase对象
            params: 参数字典 {变量名: 值}
        """
        commands_to_remove = []
        
        for command in case.commands:
            # 标记是否跳过该command
            skip_command = False

            # 替换命令名中的占位符（如 [EXP]${EXP_TYPE}）
            if self._has_placeholder(command.command):
                new_command = self._replace_placeholders(command.command, params)
                if new_command is None or (isinstance(new_command, str) and new_command.strip() == ""):
                    raise ValueError(
                        f"命令名占位符替换为空: [{command.client_type}]{command.command}"
                    )
                new_command = new_command.strip()
                if new_command not in CLIENT_COMMANDS.get(command.client_type, []):
                    raise ValueError(
                        f"命令名占位符替换后不合法: [{command.client_type}]{new_command}"
                    )
                command.command = new_command

            for i, param in enumerate(command.params):
                if self._has_placeholder(param):
                    result = self._replace_placeholders(param, params)
                    if result is None or len(result) == 0:
                        skip_command = True
                        break
                    command.params[i] = result
            
            if skip_command:
                commands_to_remove.append(command)
        
        for command in commands_to_remove:
            case.commands.remove(command)
    
    def _expand_parameterized_case(self, template_case: DSLCase, case_index: int, csv_file_path: str = None, use_global_csv: bool = False) -> List[DSLCase]:
        """
        展开参数化case：根据CSV数据生成多个case实例
        
        Args:
            template_case: 模板case（包含占位符）
            case_index: 原始case索引
            csv_file_path: Case级CSV文件路径（如果指定，优先使用）
            use_global_csv: 是否使用全局CSV（-P参数指定的）
            
        Returns:
            展开后的case列表
        """
        expanded_cases = []
        
        # 确定使用哪个CSV数据和行号映射
        csv_line_mapping = None
        csv_header_line_num = None
        
        if csv_file_path:
            # 使用Case级CSV文件
            parameterized_data = self._load_case_csv_file(csv_file_path)
            # 获取Case级CSV的行号映射和表头行号
            cache_key = csv_file_path
            if self.parameterized_data_filter:
                cache_key = f"{csv_file_path}::PF:{self.parameterized_data_filter}"
            csv_line_mapping = self._case_csv_line_mapping.get(cache_key, {})
            csv_header_line_num = self._case_csv_header_line.get(cache_key)
        elif use_global_csv:
            # 使用全局CSV
            parameterized_data = self.parameterized_data
            csv_line_mapping = self._global_csv_line_mapping
            csv_header_line_num = self._global_csv_header_line
        else:
            # 默认使用全局CSV（向后兼容）
            parameterized_data = self.parameterized_data
            csv_line_mapping = self._global_csv_line_mapping
            csv_header_line_num = self._global_csv_header_line
        
        if not parameterized_data:
            raise ValueError(f"无法获取参数化数据，Case索引: {case_index}")
        
        # 复制模板Case的行范围
        template_case_line_range = template_case.case_line_range
        
        for row_index, row_data in enumerate(parameterized_data, start=1):
            # 创建新的case实例
            new_case = DSLCase(
                casefile=template_case.casefile,
                case_content=template_case.case_content,
                index=f"{case_index}_P{row_index}",  # 例如: 0_P1, 0_P2
                repeat_count=1,
                case_type="TEST"
            )
            new_case.comment = template_case.comment
            new_case.case_line_range = template_case_line_range  # 复制Case行范围
            new_case.case_csv_file = template_case.case_csv_file  # 复制CSV文件路径
            
            # 计算CSV文件中的行号范围（用于-PF参数）
            # row_index是从1开始的，对应CSV数据行的索引（不包括表头）
            # data_index是从0开始的，对应CSV数据行的索引
            data_index = row_index - 1
            csv_file_line_num = csv_line_mapping.get(data_index)
            
            # 如果找不到映射，说明是第一行数据，需要计算文件行号
            # 第一行数据的行号 = header_line_num + 1
            if csv_file_line_num is None:
                if csv_header_line_num is not None:
                    csv_file_line_num = csv_header_line_num + 1
                else:
                    # 无法确定准确的行号，使用row_index + 1作为估算（假设表头在第1行）
                    csv_file_line_num = row_index + 1
            
            # 设置参数化Case的行号范围（单行）
            new_case.param_line_range = f"{csv_file_line_num}-{csv_file_line_num}"
            
            # 复制并替换commands中的占位符
            new_case.commands = []
            for cmd in template_case.commands:
                skip_command = False  # 是否跳过该命令
                new_command = cmd.command

                # 替换命令名中的占位符（如 [EXP]${EXP_TYPE}）
                if self._has_placeholder(cmd.command):
                    replaced_command = self._replace_placeholders(cmd.command, row_data)
                    if replaced_command is None or (isinstance(replaced_command, str) and replaced_command.strip() == ""):
                        raise ValueError(
                            f"Case[{case_index}] 参数化后命令名为空: [{cmd.client_type}]{cmd.command}"
                        )
                    new_command = replaced_command.strip()
                    if new_command not in CLIENT_COMMANDS.get(cmd.client_type, []):
                        raise ValueError(
                            f"Case[{case_index}] 参数化后命令名不合法: [{cmd.client_type}]{new_command}"
                        )
                
                # 替换参数中的占位符
                new_params = []
                for param in cmd.params:
                    if self._has_placeholder(param):
                        # 允许空值，替换占位符
                        new_param = self._replace_placeholders(param, row_data)
                        # 检查替换后的值是否为空（空字符串、None、或只包含空白字符）
                        if new_param is None or (isinstance(new_param, str) and new_param.strip() == ""):
                            # 如果占位符替换后为空，跳过该命令
                            skip_command = True
                            break  # 跳出参数循环，不添加该命令
                        new_params.append(new_param)
                    else:
                        new_params.append(param)
                
                # 如果命令被跳过，不添加到case中
                if skip_command:
                    continue
                
                # 创建新的command
                new_cmd = DSLCommand(
                    client_type=cmd.client_type,
                    command=new_command,
                    params=new_params,
                    timeout=cmd.timeout
                )
                new_case.commands.append(new_cmd)
            
            # 记录参数化信息（用于报告展示）
            new_case.param_row = row_data
            new_case.param_index = row_index
            
            expanded_cases.append(new_case)
        
        return expanded_cases

    def _expand_steps_case(self, template_content: str, case_index: int, repeat_count: int, base_comment: str = "") -> List[DSLCase]:
        """
        展开动态步骤case：根据steps CSV按CaseID生成多个case实例
        
        Args:
            template_content: 包含 ${NANO_STEPS} 的模板内容
            case_index: 原始case索引
            repeat_count: 重复次数
            
        Returns:
            展开后的case列表（每个CaseID一个case）
        """
        expanded_cases = []
        
        # 遍历所有CaseID
        for case_id, steps_list in self.steps_data.items():
            # 将步骤列表转换为字符串（每个步骤一行）
            steps_str = '\n'.join(steps_list)
            
            # 替换 ${NANO_STEPS} 占位符
            new_content = template_content.replace('${NANO_STEPS}', steps_str)
            
            # 创建新的case实例
            new_case = DSLCase(
                casefile=self.case_file,
                case_content=new_content,
                index=f"{case_index}_S{case_id}",  # 例如: 0_S0, 0_S1
                repeat_count=repeat_count,
                case_type="TEST"
            )
            new_case.comment = base_comment
            
            # 解析指令
            self._parse_case_commands(new_case)
            
            # 记录步骤参数化信息
            new_case.comment = f"[CaseID={case_id}] {new_case.comment}" if new_case.comment else f"[CaseID={case_id}]"
            
            expanded_cases.append(new_case)
            logger.debug(f"  展开CaseID={case_id}: {len(steps_list)} 个步骤 -> {len(new_case.commands)} 条指令")
        
        return expanded_cases

    def _validate_environment_variables(self, text: str) -> bool:
        """
        验证文本中的环境变量是否合法（在解析阶段使用）
        
        注意：本方法只验证环境变量 {VARIABLE_NAME}，不处理参数化变量 ${variable}
        - 环境变量：{VARIABLE_NAME} - 全大写字母和下划线
        - 动态表达式：{EVAL:expression} - Python表达式
        - 参数化变量：${variable} - 任意字符，由_replace_placeholders处理
        
        Args:
            text: 包含环境变量的文本
            
        Returns:
            bool: 如果所有环境变量都合法则返回True，否则抛出异常
            
        Raises:
            ValueError: 如果发现未定义的环境变量
        """
        if not text or '{' not in text:
            return True
            
        # 匹配环境变量模式:
        # 1. {VARIABLE_NAME} (必须全大写+下划线)
        # 2. {EVAL:expression}
        # 使用负向前瞻(?<!\$)确保不匹配 ${variable} 格式
        pattern = r'(?<!\$)\{([A-Z_]+|EVAL:[^}]+)\}'
        matches = re.findall(pattern, text)
        
        # 检查所有环境变量是否在支持列表中
        invalid_vars = []
        for var_name in matches:
            # EVAL表达式跳过检查
            if var_name.startswith('EVAL:'):
                continue

            if var_name not in self.supported_env_variables:
                invalid_vars.append(var_name)
        
        if invalid_vars:
            raise ValueError(
                f"检测到未定义的环境变量: {', '.join(invalid_vars)}\n"
                f"支持的环境变量列表: {', '.join(sorted(self.supported_env_variables))}"
            )
        
        return True

    def parse_case_file(self, file_path: str, case_filter) -> List[DSLCase]:
        """
        解析DSL测试用例文件
        
        -F 参数行为说明：
        - -F 只需要指定测试用例本身的行号范围
        - 如果文件中包含 SETUP 和 TEARDOWN，会自动加上这两个前置和后置
        - 如果文件中不包含 SETUP 和 TEARDOWN，则只执行过滤后的测试用例
        """
        try:
            self.case_file = file_path
            start, end = check_line_filter(case_filter)
            
            # 读取完整文件内容
            with open(file_path, 'r', encoding='utf-8') as file:
                all_lines = file.readlines()
            full_content = "".join(all_lines)
            
            # 如果没有指定 -F 过滤，直接解析完整内容
            if case_filter is None:
                return self.parse_case_content(full_content, None)
            
            # 查找 SETUP 和 TEARDOWN 块（包括其边界行 >>> 和 <<<）
            setup_block = ""
            teardown_block = ""
            
            # 使用正则表达式查找 SETUP 块（支持携带其紧邻前置注释行）
            setup_pattern = r'(?:(?:^[ \t]*#[^\n]*\n)*)^>>>\s*SETUP\s*\n[\s\S]*?\n<<<'
            setup_match = re.search(setup_pattern, full_content, re.MULTILINE)
            if setup_match:
                setup_block = setup_match.group(0)
                logger.debug(f"找到 SETUP 块: 行号范围内")
            
            # 使用正则表达式查找 TEARDOWN 块（支持携带其紧邻前置注释行）
            teardown_pattern = r'(?:(?:^[ \t]*#[^\n]*\n)*)^>>>\s*TEARDOWN\s*\n[\s\S]*?\n<<<'
            teardown_match = re.search(teardown_pattern, full_content, re.MULTILINE)
            if teardown_match:
                teardown_block = teardown_match.group(0)
                logger.debug(f"找到 TEARDOWN 块: 行号范围内")
            
            # 使用正则表达式查找 SUITE_TEARDOWN 块
            suite_teardown_block = ""
            suite_teardown_pattern = r'(?:(?:^[ \t]*#[^\n]*\n)*)^>>>\s*SUITE_TEARDOWN\s*\n[\s\S]*?\n<<<'
            suite_teardown_match = re.search(suite_teardown_pattern, full_content, re.MULTILINE)
            if suite_teardown_match:
                suite_teardown_block = suite_teardown_match.group(0)
                logger.debug(f"找到 SUITE_TEARDOWN 块: 行号范围内")
            
            case_setup_block = ""
            case_setup_pattern = r'(?:(?:^[ \t]*#[^\n]*\n)*)^>>>\s*CASE_SETUP\s*\n[\s\S]*?\n<<<'
            case_setup_match = re.search(case_setup_pattern, full_content, re.MULTILINE)
            if case_setup_match:
                case_setup_block = case_setup_match.group(0)
                logger.debug(f"找到 CASE_SETUP 块: 行号范围内")
            
            case_teardown_block = ""
            case_teardown_pattern = r'(?:(?:^[ \t]*#[^\n]*\n)*)^>>>\s*CASE_TEARDOWN\s*\n[\s\S]*?\n<<<'
            case_teardown_match = re.search(case_teardown_pattern, full_content, re.MULTILINE)
            if case_teardown_match:
                case_teardown_block = case_teardown_match.group(0)
                logger.debug(f"找到 CASE_TEARDOWN 块: 行号范围内")
            
            # 查找所有普通测试用例块，并根据行号过滤
            # 使用正则表达式查找所有测试用例块（排除 SETUP、TEARDOWN、SUITE_TEARDOWN）
            # 支持格式：>>> SETUP, >>> TEARDOWN, >>> SUITE_TEARDOWN, >>> PARAMETER xxx, >>> 数字, >>>
            # ^ 确保 >>> 在行首，避免匹配 #>>> 等注释
            test_case_pattern = r'(?:(?:^[ \t]*#[^\n]*\n)*)^>>>\s*(SETUP|TEARDOWN|SUITE_TEARDOWN|CASE_SETUP|CASE_TEARDOWN(?:[ \t]+[^\n]+)?|PARAMETER(?:[ \t]+[^\n]+)?|\d+)?\s*\n([\s\S]*?)\n<<<'
            filtered_test_cases = []
            # 保存Case内容到原始文件行号的映射（用于后续设置正确的行号）
            case_content_to_line_range: Dict[str, str] = {}
            
            # 遍历所有匹配，计算每个匹配的行号
            for match in re.finditer(test_case_pattern, full_content, re.MULTILINE):
                match_start_pos = match.start()
                match_end_pos = match.end()
                
                # 计算匹配开始位置对应的行号（从1开始，相对于原始文件）
                content_before_match = full_content[:match_start_pos]
                start_line = content_before_match.count('\n') + 1
                
                # 计算匹配结束位置对应的行号
                match_text = match.group(0)
                end_line = start_line + match_text.count('\n')
                
                # 检查是否是 SETUP、TEARDOWN 或 SUITE_TEARDOWN（通过检查匹配文本）
                type_marker = match.group(1)  # 可能是 SETUP, TEARDOWN, SUITE_TEARDOWN, PARAMETER xxx, 数字或 None
                full_match_text = match.group(0)
                # 仅使用从 >>> 开始的核心Case块作为映射key，避免前置注释导致key不一致
                case_start_in_match = full_match_text.find('>>>')
                core_case_text = full_match_text[case_start_in_match:] if case_start_in_match != -1 else full_match_text
                
                # 跳过 SETUP、TEARDOWN 和 SUITE_TEARDOWN 块（它们已经单独处理）
                if type_marker in ['SETUP', 'TEARDOWN', 'SUITE_TEARDOWN', 'CASE_SETUP', 'CASE_TEARDOWN']:
                    continue
                
                # 检查测试用例块是否与过滤范围有交集 条件：测试用例的任意部分在过滤范围内
                if not (end_line < start or start_line > end):
                    filtered_test_cases.append(full_match_text)
                    # 记录Case内容到原始文件行号的映射
                    case_content_to_line_range[core_case_text] = f"{start_line}-{end_line}"
            
            # 组合最终内容：SETUP + 过滤后的测试用例 + TEARDOWN + SUITE_TEARDOWN
            final_parts = []
            if setup_block:
                final_parts.append(setup_block)
                logger.info(f"自动添加 SETUP 块")
            
            if case_setup_block:
                final_parts.append(case_setup_block)
                logger.info(f"自动添加 CASE_SETUP 块")
            
            if filtered_test_cases:
                final_parts.extend(filtered_test_cases)
                logger.info(f"-F 参数过滤后保留 {len(filtered_test_cases)} 个测试用例块")
            else:
                logger.warning(f"-F 参数 {case_filter} 过滤后没有匹配的测试用例")
            
            if case_teardown_block:
                final_parts.append(case_teardown_block)
                logger.info(f"自动添加 CASE_TEARDOWN 块")
            
            if teardown_block:
                final_parts.append(teardown_block)
                logger.info(f"自动添加 TEARDOWN 块")
            
            if suite_teardown_block:
                final_parts.append(suite_teardown_block)
                logger.info(f"自动添加 SUITE_TEARDOWN 块")
            
            final_content = "\n\n".join(final_parts)
            # 解析内容，并传递行号映射信息
            cases = self.parse_case_content(final_content, case_content_to_line_range)
            return cases
            
        except Exception as e:
            logger.error(f"解析DSL文件失败: {file_path}, 错误: {e}")
            raise

    def parse_case_content(self, content: str, case_content_to_line_range: Dict[str, str] = None) -> List[DSLCase]:
        """
        解析DSL测试用例内容
        支持四种Case类型：
        1. >>> SETUP ... <<< : Session级别前置（每个并发进程执行一次）
        2. >>> TEARDOWN ... <<< : Session级别后置（每个并发进程执行一次）
        3. >>> SUITE_TEARDOWN ... <<< : Suite级别后置（只在主进程执行一次）
        4. >>> ... <<< : 普通测试用例
        5. >>> CASE_SETUP ... <<< : Case级别前置（每个并发进程执行一次）
        6. >>> CASE_TEARDOWN ... <<< : Case级别后置（每个并发进程执行一次）
        """
        cases = []
        setup_case = None
        teardown_case = None
        case_setup_case = None
        case_teardown_case = None
        suite_teardown_case = None

        # 查找所有的Case块，支持 >>> SETUP, >>> TEARDOWN, >>> SUITE_TEARDOWN, >>> PARAMETER xxx, >>> 或 >>> 数字
        # 匹配格式：>>> [SETUP|TEARDOWN|SUITE_TEARDOWN|PARAMETER xxx|数字] \n 内容 \n <<<
        # ^ 确保 >>> 在行首，避免匹配 #>>> 等注释
        case_pattern = r'^>>>\s*(SETUP|TEARDOWN|SUITE_TEARDOWN|CASE_SETUP|CASE_TEARDOWN(?:[ \t]+[^\n]+)?|PARAMETER(?:[ \t]+[^\n]+)?|\d+)?\s*\n(.*?)\n<<<'
        matches = list(re.finditer(case_pattern, content, re.DOTALL | re.MULTILINE))

        test_case_index = 0
        for match in matches:
            type_or_repeat_or_param, case_content = match.groups()
            
            # 计算Case块的行号范围（从1开始）
            match_start_pos = match.start()
            match_end_pos = match.end()
            match_text = match.group(0)
            case_comment = self._extract_adjacent_comment_before_case(content, match_start_pos)
            
            # 如果提供了case_content_to_line_range映射（说明使用了-F过滤），使用原始文件的行号
            if case_content_to_line_range and match_text in case_content_to_line_range:
                case_line_range = case_content_to_line_range[match_text]
            else:
                # 否则使用当前内容中的行号
                content_before_match = content[:match_start_pos]
                start_line = content_before_match.count('\n') + 1
                end_line = start_line + match_text.count('\n')
                case_line_range = f"{start_line}-{end_line}"
            
            # 解析PARAMETER语法（如果存在）
            case_csv_file = None  # None表示未指定，使用全局CSV；"default"表示显式使用全局CSV；文件路径表示使用指定CSV
            if type_or_repeat_or_param and type_or_repeat_or_param.startswith('PARAMETER'):
                # 提取PARAMETER后面的值
                param_value = type_or_repeat_or_param.replace('PARAMETER', '').strip()
                if param_value.lower() == 'default':
                    case_csv_file = "default"  # 显式使用全局CSV
                elif param_value:
                    case_csv_file = param_value  # 使用指定的CSV文件
                # 将type_or_repeat_or_param设为None，因为这是普通测试用例
                type_or_repeat_or_param = None
            
            # 判断Case类型
            if type_or_repeat_or_param == 'SETUP':
                if setup_case is not None:
                    raise ValueError(f"Case文件 {self.case_file} 中检测到多个SETUP块，每个文件只允许一个SETUP")
                case = DSLCase(self.case_file, case_content, -1, 1, "SETUP")
                case.comment = case_comment
                case.case_line_range = case_line_range  # 记录Case行范围
                self._parse_case_commands(case)
                
                # 处理SETUP中的占位符（使用CSV第一行数据）
                if self._case_has_placeholders(case):
                    if not self.parameterized_data:
                        raise ValueError(
                            f"SETUP块中包含参数化占位符 ${{variable}}，但未提供参数化数据文件。\n"
                            f"请使用 -P 参数指定CSV文件"
                        )
                    # 使用CSV第一行数据替换占位符
                    self._replace_case_placeholders(case, self.parameterized_data[0])
                    logger.info(f"SETUP块使用参数化数据第1行: {self.parameterized_data[0]}")
                
                setup_case = case
                logger.info(f"解析到SETUP块: {len(case.commands)} 条指令")
            
            elif type_or_repeat_or_param == 'CASE_SETUP':
                if case_setup_case is not None:
                    raise ValueError(f"Case文件 {self.case_file} 中检测到多个CASE_SETUP块，每个文件只允许一个CASE_SETUP")
                case = DSLCase(self.case_file, case_content, -1, 1, "CASE_SETUP")
                case.comment = case_comment
                case.case_line_range = case_line_range  # 记录Case行范围
                self._parse_case_commands(case)
                
                case_setup_case = case
                logger.info(f"解析到CASE_SETUP块: {len(case.commands)} 条指令（每个并发进程执行一次）")
            
            elif type_or_repeat_or_param == 'CASE_TEARDOWN':
                if case_teardown_case is not None:
                    raise ValueError(f"Case文件 {self.case_file} 中检测到多个CASE_TEARDOWN块，每个文件只允许一个CASE_TEARDOWN")
                case = DSLCase(self.case_file, case_content, -1, 1, "CASE_TEARDOWN")
                case.comment = case_comment
                case.case_line_range = case_line_range  # 记录Case行范围
                self._parse_case_commands(case)
                
                case_teardown_case = case
                logger.info(f"解析到CASE_TEARDOWN块: {len(case.commands)} 条指令（每个并发进程执行一次）")
            
            elif type_or_repeat_or_param == 'TEARDOWN':
                if teardown_case is not None:
                    raise ValueError(f"Case文件 {self.case_file} 中检测到多个TEARDOWN块，每个文件只允许一个TEARDOWN")
                case = DSLCase(self.case_file, case_content, -1, 1, "TEARDOWN")
                case.comment = case_comment
                case.case_line_range = case_line_range  # 记录Case行范围
                self._parse_case_commands(case)
                
                # 处理TEARDOWN中的占位符（使用CSV第一行数据）
                if self._case_has_placeholders(case):
                    if not self.parameterized_data:
                        raise ValueError(
                            f"TEARDOWN块中包含参数化占位符 ${{variable}}，但未提供参数化数据文件。\n"
                            f"请使用 -P 参数指定CSV文件"
                        )
                    # 使用CSV第一行数据替换占位符
                    self._replace_case_placeholders(case, self.parameterized_data[0])
                    logger.info(f"TEARDOWN块使用参数化数据第1行: {self.parameterized_data[0]}")
                
                teardown_case = case
                logger.info(f"解析到TEARDOWN块: {len(case.commands)} 条指令")
                
            elif type_or_repeat_or_param == 'SUITE_TEARDOWN':
                if suite_teardown_case is not None:
                    raise ValueError(f"Case文件 {self.case_file} 中检测到多个SUITE_TEARDOWN块，每个文件只允许一个SUITE_TEARDOWN")
                case = DSLCase(self.case_file, case_content, -1, 1, "SUITE_TEARDOWN")
                case.comment = case_comment
                case.case_line_range = case_line_range  # 记录Case行范围
                self._parse_case_commands(case)
                
                # 处理SUITE_TEARDOWN中的占位符（使用CSV第一行数据）
                if self._case_has_placeholders(case):
                    if not self.parameterized_data:
                        raise ValueError(
                            f"SUITE_TEARDOWN块中包含参数化占位符 ${{variable}}，但未提供参数化数据文件。\n"
                            f"请使用 -P 参数指定CSV文件"
                        )
                    # 使用CSV第一行数据替换占位符
                    self._replace_case_placeholders(case, self.parameterized_data[0])
                    logger.info(f"SUITE_TEARDOWN块使用参数化数据第1行: {self.parameterized_data[0]}")
                
                suite_teardown_case = case
                logger.info(f"解析到SUITE_TEARDOWN块: {len(case.commands)} 条指令（只在主进程执行一次）")
                
            else:
                # 普通测试用例
                repeat_count = int(type_or_repeat_or_param) if type_or_repeat_or_param and type_or_repeat_or_param.isdigit() else 1
                
                # 🔍 检查是否包含 ${NANO_STEPS} 占位符（动态步骤参数化）
                if '${NANO_STEPS}' in case_content:
                    # 动态步骤参数化模式
                    if not self.steps_data:
                        raise ValueError(
                            f"DSL用例中包含 ${{NANO_STEPS}} 占位符，但未提供动态步骤数据文件。\n"
                            f"请使用 -S 参数指定步骤CSV文件，例如：\n"
                            f"  python Run_Mango.py -f NANO -a test.mgo -S steps.csv\n"
                            f"用例位置: {self.case_file}, 第{test_case_index+1}个TEST case"
                        )
                    
                    # 按CaseID展开步骤，生成多个case
                    step_expanded_cases = self._expand_steps_case(case_content, test_case_index, repeat_count, case_comment)
                    
                    # 检查展开后的case是否还有普通占位符
                    for step_case in step_expanded_cases:
                        if self._case_has_placeholders(step_case):
                            # 还有普通占位符，需要再次进行传统参数化
                            if not self.parameterized_data:
                                raise ValueError(
                                    f"动态步骤展开后的用例中仍包含参数化占位符 ${{variable}}，但未提供参数化数据文件。\n"
                                    f"请使用 -P 参数指定CSV文件进行二次参数化"
                                )
                            # 二次参数化展开
                            final_cases = self._expand_parameterized_case(step_case, step_case.index)
                            cases.extend(final_cases)
                            logger.info(f"二次参数化展开: Case[{step_case.index}] -> {len(final_cases)} 个实例")
                        else:
                            # 没有普通占位符，直接添加
                            cases.append(step_case)
                    
                    logger.info(f"动态步骤展开: Case[{test_case_index}] -> {len(step_expanded_cases)} 个CaseID实例")
                else:
                    # 普通case（无${NANO_STEPS}占位符）
                    case = DSLCase(self.case_file, case_content, test_case_index, repeat_count, "TEST")
                    case.comment = case_comment
                    case.case_csv_file = case_csv_file  # 设置Case级CSV文件路径
                    case.case_line_range = case_line_range  # 记录Case行范围
                    self._parse_case_commands(case)
                    
                    # 检测是否包含普通参数化占位符
                    has_placeholders = self._case_has_placeholders(case)
                    
                    # 参数化逻辑：
                    # 1. 如果指定了PARAMETER（case_csv_file不为None），根据值决定使用哪个CSV
                    # 2. 如果未指定PARAMETER（case_csv_file为None），检查是否有占位符，有则使用全局CSV
                    if case_csv_file is not None:
                        # 指定了PARAMETER
                        if case_csv_file == "default":
                            # 显式使用全局CSV
                            if not self.parameterized_data:
                                raise ValueError(
                                    f"Case[{test_case_index+1}]指定了 PARAMETER default，但未提供全局参数化数据文件。\n"
                                    f"请使用 -P 参数指定CSV文件"
                                )
                            if has_placeholders:
                                expanded_cases = self._expand_parameterized_case(case, test_case_index, use_global_csv=True)
                                cases.extend(expanded_cases)
                                logger.info(f"参数化展开: Case[{test_case_index}] (PARAMETER default) -> {len(expanded_cases)} 个实例")
                            else:
                                # 没有占位符，但指定了default，直接添加（不进行参数化）
                                cases.append(case)
                        else:
                            # 使用指定的CSV文件
                            if has_placeholders:
                                expanded_cases = self._expand_parameterized_case(case, test_case_index, csv_file_path=case_csv_file)
                                cases.extend(expanded_cases)
                                logger.info(f"参数化展开: Case[{test_case_index}] (PARAMETER {case_csv_file}) -> {len(expanded_cases)} 个实例")
                            else:
                                # 没有占位符，但指定了CSV文件，直接添加（不进行参数化）
                                logger.warning(f"Case[{test_case_index+1}]指定了PARAMETER {case_csv_file}，但Case中没有参数化占位符，将不进行参数化")
                                cases.append(case)
                    else:
                        # 未指定PARAMETER，检查是否有占位符
                        if has_placeholders:
                            # 有占位符，使用全局CSV
                            if not self.parameterized_data:
                                raise ValueError(
                                    f"DSL用例中包含参数化占位符 ${{variable}}，但未提供参数化数据文件。\n"
                                    f"请使用 -P 参数指定CSV文件，例如：\n"
                                    f"  python Run_Mongo.py -f NANO -a test.mgo -P data.csv\n"
                                    f"或在Case中指定 PARAMETER file.csv\n"
                                    f"用例位置: {self.case_file}, 第{test_case_index+1}个TEST case"
                                )
                            expanded_cases = self._expand_parameterized_case(case, test_case_index, use_global_csv=True)
                            cases.extend(expanded_cases)
                            logger.info(f"参数化展开: Case[{test_case_index}] (使用全局CSV) -> {len(expanded_cases)} 个实例")
                        else:
                            # 没有占位符，直接添加
                            cases.append(case)
                
                test_case_index += 1
        
        # 验证SETUP和TEARDOWN必须成对出现
        if (setup_case is None) != (teardown_case is None):
            raise ValueError(
                f"Case文件 {self.case_file} 中SETUP和TEARDOWN必须成对出现！"
                f"当前状态: SETUP={'有' if setup_case else '无'}, TEARDOWN={'有' if teardown_case else '无'}"
            )
        
        # 将SETUP、TEARDOWN、SUITE_TEARDOWN放在cases列表中
        # 顺序：SETUP -> TEST cases -> TEARDOWN -> SUITE_TEARDOWN
        if setup_case:
            cases.insert(0, setup_case)
        if case_setup_case:
            cases.insert(1, case_setup_case)
        if case_teardown_case:
            cases.append(case_teardown_case)
        if teardown_case:
            cases.append(teardown_case)
        if suite_teardown_case:
            cases.append(suite_teardown_case)
        
        logger.info(f"解析完成: {len([c for c in cases if c.is_test()])} 个测试用例")
        if setup_case:
            logger.info(f"  - 包含SESSION级别SETUP: {len(setup_case.commands)} 条指令（每个并发进程执行一次）")
        if case_setup_case:
            logger.info(f"  - 包含CASE级别SETUP: {len(case_setup_case.commands)} 条指令（每个case开始执行一次）")
        if case_teardown_case:
            logger.info(f"  - 包含CASE级别TEARDOWN: {len(case_teardown_case.commands)} 条指令（每个case结束执行一次）")
        if teardown_case:
            logger.info(f"  - 包含SESSION级别TEARDOWN: {len(teardown_case.commands)} 条指令（每个并发进程执行一次）")
        if suite_teardown_case:
            logger.info(f"  - 包含SUITE级别TEARDOWN: {len(suite_teardown_case.commands)} 条指令（只在主进程执行一次）")
        
        return cases

    def _extract_adjacent_comment_before_case(self, content: str, case_start_pos: int) -> str:
        """提取 >>> 块前紧邻的注释行（连续 # 行）作为 case.comment"""
        lines_before_case = content[:case_start_pos].splitlines()
        if not lines_before_case:
            return ""

        comments = []
        idx = len(lines_before_case) - 1

        # 仅提取紧邻 >>> 的连续注释行；遇到空行或非注释行立即停止
        while idx >= 0:
            stripped = lines_before_case[idx].strip()
            if not stripped:
                break
            if not stripped.startswith('#'):
                break
            comments.append(stripped[1:].strip())
            idx -= 1

        comments.reverse()
        return "\n".join(comments)

    def _parse_case_commands(self, case: DSLCase):
        """解析单个用例的指令"""
        lines = case.case_content.split('\n')

        for line_num, line in enumerate(lines, 1):
            line = line.strip()

            # 跳过空行
            if not line:
                continue

            # 处理注释行
            if line.startswith('#'):
                continue

            try:
                # 处理尾部注释
                if "#" in line:
                    line = line.split('#')[0].strip()

                command = self._parse_command_line(line, line_num)
                if command:
                    case.commands.append(command)
            except Exception as e:
                logger.error(f"解析指令失败 (行{line_num}): {line}, 错误: {e}")
                raise

    def _parse_command_line(self, line: str, line_num: int) -> DSLCommand:
        """解析单行指令"""
        # 匹配指令格式: [CLIENT]COMMAND params <timeout=X>
        # timeout支持整数、小数和-1（无限等待），单位为秒
        # 不指定timeout时，默认为0（立即执行/断言）
        # COMMAND 支持普通指令名（如 ASSERT）和参数化占位符（如 ${EXP_TYPE}）
        pattern = r'\[(\w+)\](\S+)\s*(.*?)(?:\s*<timeout=([-\d.]+)>)?$'
        match = re.match(pattern, line)

        if not match:
            raise ValueError(f"指令格式错误: {line}")

        client_type, command, params_str, timeout_str = match.groups()

        # 验证客户端类型
        if client_type not in self.supported_clients:
            raise ValueError(f"不支持的客户端类型: {client_type}")

        # 验证指令
        # 对参数化命令名（${...}）延迟到参数化展开后再验证
        if not self._has_placeholder(command):
            if command not in CLIENT_COMMANDS.get(client_type, []):
                raise ValueError(f"客户端 {client_type} 不支持指令: {command}")

        # 解析参数
        params = self._parse_params(params_str.strip(), client_type, command)

        # 解析超时时间（秒）
        # timeout=0 或不指定: 立即执行
        # timeout>0: 等待指定秒数
        # timeout=-1: 无限等待
        timeout = float(timeout_str) if timeout_str else 0

        return DSLCommand(client_type, command, params, timeout)


    def _parse_params(self, params_str: str, client_type: str, command: str) -> List[str]:
        """解析指令参数"""
        if not params_str:
            return []

        # 验证环境变量是否合法（不进行替换）
        self._validate_environment_variables(params_str)
        
        # 优先处理EVENT/VREVENT的文件路径加载
        if command in ['EVENT', 'VREVENT']:
            param_trimmed = params_str.strip()
            if param_trimmed.endswith('.json'):
                # 注意：不检查文件是否存在，因为可能包含环境变量需要运行时替换
                # 文件存在性检查将在执行阶段进行
                return [param_trimmed]

        # 特殊处理TEXT命令 - TEXT命令后的整个字符串作为完整文本内容，不分割
        if command == 'TEXT':
            return [params_str.strip()]

        # 特殊处理TEXT_DATA命令
        # 支持：
        # 1) text='北京今天天气怎么样' lang=cmn engine=auto frame=320 delay=0 range=[0,-1]
        # 2) 北京今天天气怎么样 frame=320 delay=0
        if command == 'TEXT_DATA':
            return self._parse_text_data_params(params_str)

        # 特殊处理JSON格式参数（EVENT指令和PULL指令的车参）
        if (command == 'EVENT' and params_str.startswith('{')) or \
           (command == 'PULL' and client_type == 'SYS' and '{' in params_str):
            # 对于包含JSON的参数，需要特殊处理
            return self._parse_json_params(params_str)
        elif command == 'DATA' and ('=' in params_str or '[' in params_str):
            # DATA指令支持命名参数
            return self._parse_data_params(params_str)
        elif command == 'NLPResult' and 'ttsInfo' in params_str and client_type == 'EXP':
            params_str = tts_info_to_except(params_str, 'MangoDB.' + self.project)
            return params_str.split()
        else:
            # 简单按空格分割参数
            return params_str.split()

    def _parse_json_params(self, params_str: str) -> List[str]:
        """解析包含JSON的参数"""
        params = []
        current_param = ""
        brace_count = 0
        
        i = 0
        while i < len(params_str):
            char = params_str[i]
            
            if char == '{':
                brace_count += 1
                current_param += char
            elif char == '}':
                brace_count -= 1
                current_param += char
                # 如果大括号匹配完成，且后面是空格或结束，则认为是一个完整参数
                if brace_count == 0 and (i + 1 >= len(params_str) or params_str[i + 1] == ' '):
                    params.append(current_param.strip())
                    current_param = ""
            elif char == ' ' and brace_count == 0:
                # 只有在大括号外的空格才分割参数
                if current_param.strip():
                    params.append(current_param.strip())
                    current_param = ""
            else:
                current_param += char
                
            i += 1
        
        # 添加最后一个参数
        if current_param.strip():
            params.append(current_param.strip())
            
        return params

    def _parse_data_params(self, params_str: str) -> List[str]:
        """解析DATA指令的命名参数"""
        import re
        
        # 分割参数，支持命名参数和范围参数
        tokens = []
        current_token = ""
        bracket_count = 0
        
        i = 0
        while i < len(params_str):
            char = params_str[i]
            
            if char == '[':
                bracket_count += 1
                current_token += char
            elif char == ']':
                bracket_count -= 1
                current_token += char
            elif char == ' ' and bracket_count == 0:
                if current_token.strip():
                    tokens.append(current_token.strip())
                    current_token = ""
            else:
                current_token += char
            i += 1
        
        if current_token.strip():
            tokens.append(current_token.strip())
        
        # 解析为命名参数格式
        params = []
        for token in tokens:
            if '=' in token:
                # 命名参数：key=value
                params.append(token)
            elif token.startswith('[') and token.endswith(']'):
                # 范围参数：[start,end]
                params.append(f"range={token}")
            else:
                # 位置参数（音频路径）
                params.append(token)
        
        return params

    def _parse_text_data_params(self, params_str: str) -> List[str]:
        """解析TEXT_DATA命令参数。"""
        import shlex

        params_str = params_str.strip()
        if not params_str:
            return []

        named_part = params_str
        parsed_params = []
        text_value = None

        # 1) 优先解析 text='...' / text="..."
        quoted_text_match = re.search(r"""text\s*=\s*(['"])(.*?)\1""", params_str, re.DOTALL)
        if quoted_text_match:
            text_value = quoted_text_match.group(2).strip()
            named_part = (params_str[:quoted_text_match.start()] + params_str[quoted_text_match.end():]).strip()
        else:
            # 2) 解析 text=xxx（无引号单token）
            plain_text_match = re.search(r"""(?:^|\s)text\s*=\s*([^\s]+)""", params_str)
            if plain_text_match:
                text_value = plain_text_match.group(1).strip()
                named_part = (params_str[:plain_text_match.start()] + params_str[plain_text_match.end():]).strip()

        # 3) 没有显式 text= 时，取第一个命名参数之前的文本
        if text_value is None:
            first_named_match = re.search(r"""\b(?:lang|engine|frame|delay|range)\s*=""", params_str)
            if first_named_match:
                text_value = params_str[:first_named_match.start()].strip()
                named_part = params_str[first_named_match.start():].strip()
            else:
                text_value = params_str
                named_part = ""

        if text_value:
            parsed_params.append(f"text={text_value}")

        if not named_part:
            return parsed_params

        try:
            tokens = shlex.split(named_part)
        except Exception:
            # 兼容异常格式，回退到简单空格分割
            tokens = named_part.split()

        for token in tokens:
            if '=' in token:
                parsed_params.append(token)

        return parsed_params

    def validate_case(self, case: DSLCase) -> Tuple[bool, str]:
        """验证DSL用例的正确性"""
        try:
            # 检查是否有指令
            if not case.commands:
                return False, "用例没有任何指令"

            # 验证指令顺序和依赖关系
            client_states = {}  # 跟踪每个客户端的状态

            for i, cmd in enumerate(case.commands):
                # 验证指令语法
                if not self._validate_command_syntax(cmd):
                    return False, f"指令 {i+1} 语法错误: {cmd}"

                # 验证指令依赖关系
                if not self._validate_command_dependency(cmd, client_states):
                    return False, f"指令 {i+1} 依赖关系错误: {cmd}"

                # 更新客户端状态
                self._update_client_state(cmd, client_states)

            return True, "验证通过"

        except Exception as e:
            return False, f"验证异常: {e}"

    def _validate_command_syntax(self, cmd: DSLCommand) -> bool:
        """验证指令语法"""
        # 根据不同指令验证参数数量和格式
        if cmd.client_type in ['TSA', 'SET', 'VOI', 'OMS', 'TTS']:
            # 基础指令
            if cmd.command == 'CREATE':
                return len(cmd.params) >= 2  # 至少需要language和appid
            elif cmd.command == 'START':
                return len(cmd.params) >= 1  # 需要channel数量
            elif cmd.command == 'DATA':
                return len(cmd.params) >= 1  # 需要音频文件路径
            elif cmd.command == 'TEXT_DATA':
                return len(cmd.params) >= 1  # 需要 text 参数
            elif cmd.command == 'EVENT':
                return len(cmd.params) >= 1  # 需要JSON事件数据
            elif cmd.command in ['STOP', 'FREE', 'CANCEL']:
                return True  # 无参数要求

            # 扩展指令 - 无参数类型
            elif cmd.command in ['PAUSE', 'RESUME', 'GET_VERSION', 'START_RECORD', 'STOP_RECORD', 
                               'CLOSE_VOICE_INPUT', 'END_SPEAKER_ENROLL', 'CANCEL_VERIFY_VOICEPRINT',
                               'GET_SPEAKERS', 'GET_ENROLL_TEXT', 'CLEAR_VR_CONFIG', 'GET_FOTA_STATUS',
                               'GET_WAKEUP_WORD']:
                return True

            # 扩展指令 - 单参数类型
            elif cmd.command in ['MIC_STATUS', 'VR_STATUS', 'LINK_TYPE']:
                return len(cmd.params) == 1 and cmd.params[0].isdigit()
            elif cmd.command in ['CAR_TYPE', 'LOG_PATH', 'DELETE_SPEAKER', 'GET_SPEAKER_INFO',
                               'OPEN_VOICE_INPUT', 'SENSITIVE_WORD_CHECK', 'SET_VOICELOG_PATH',
                               'SET_LANGUAGE_MODE', 'SET_WORKMODE', 'GET_VR_CONFIG']:
                return len(cmd.params) >= 1
            elif cmd.command in ['VREVENT']:
                return len(cmd.params) >= 1  # JSON格式的事件数据
            elif cmd.command in ['SET_TTS_STATE']:
                return len(cmd.params) == 1 and cmd.params[0].lower() in ['true', 'false', '0', '1']

            # 扩展指令 - 多参数类型
            elif cmd.command == 'START_SPEAKER_ENROLL':
                return len(cmd.params) >= 4  # user_id text id channel_id
            elif cmd.command == 'RECOGNIZE_SPEAKER':
                return len(cmd.params) >= 3  # channel_id start_time end_time
            elif cmd.command == 'VERIFY_VOICEPRINT':
                return len(cmd.params) >= 3  # user_id text channel_id
            elif cmd.command == 'GET_CONFIG_ITEM':
                return len(cmd.params) >= 2  # filename key
            elif cmd.command == 'WRITE_LOG':
                return len(cmd.params) >= 3  # filename tag text [level]
            elif cmd.command == 'CONFIG_VOICELOG':
                return len(cmd.params) >= 2  # if_open mode
            elif cmd.command == 'SET_PARAM':
                return len(cmd.params) >= 2  # param_code param_value
            elif cmd.command == 'SET_WAKEUP_WORD':
                return len(cmd.params) >= 2  # word threshold
            elif cmd.command == 'SET_WAKEUP_ENABLE':
                return len(cmd.params) >= 2  # word enable
            elif cmd.command == 'UPDATE_PERSONALIZED':
                return len(cmd.params) >= 3  # json_userlist charset weight
            elif cmd.command == 'SET_PAGE_INTENT':
                return len(cmd.params) >= 2  # hmi_info app_name

        elif cmd.client_type == 'SYS':
            if cmd.command == 'SLEEP':
                return len(cmd.params) == 1 and cmd.params[0].isdigit()
            elif cmd.command in ['CMD', 'PRINT', 'EXPECT']:
                return len(cmd.params) >= 1
            elif cmd.command in ['PULL', 'KILL']:
                return len(cmd.params) >= 1
            elif cmd.command == 'UPLOAD':
                # UPLOAD需要至少3个参数: type file_path ...args
                return len(cmd.params) >= 3
            elif cmd.command == 'ALLURE':
                # ALLURE需要至少2个参数: attachment_type file_path
                return len(cmd.params) >= 2
            elif cmd.command == 'FOTA_RANDOM_ZIP':
                # FOTA_RANDOM_ZIP需要至少3个参数: source_dir target_zip count
                return len(cmd.params) >= 3

        elif cmd.client_type == 'EXP':
            if cmd.command == 'ASSERT':
                # EXP断言验证：必须有一个参数（断言语句）
                return len(cmd.params) == 1 and cmd.params[0].startswith('[EXP]')
        
        elif cmd.client_type == 'TSR':
            # TSR 客户端指令验证
            if cmd.command == 'DELAY_TEST':
                return len(cmd.params) >= 1  # 至少需要输出文件路径
            elif cmd.command == 'WAKEUP_FA':
                return len(cmd.params) >= 2  # 需要 CSV 文件和输出报告路径
            elif cmd.command == 'PASS_RATE':
                return True  # 参数可选
            elif cmd.command == 'FAILED_CASES':
                return True  # 参数可选
            elif cmd.command == 'GENERATE_REPORT':
                return len(cmd.params) >= 1  # 需要输出文件路径

        elif cmd.client_type == 'ENR':
            if cmd.command == 'SET_DOWNLINK':
                return len(cmd.params) >= 1
            if cmd.command in ('AMP_TYPE', 'ECNR_TYPE'):
                return len(cmd.params) == 1
            return True

        return False

    def _validate_command_dependency(self, cmd: DSLCommand, client_states: Dict[str, str]) -> bool:
        """验证指令依赖关系"""
        if cmd.client_type in ['SYS', 'TSR', 'EXP']:
            return True  # SYS、TSR、EXP 指令无依赖关系要求

        current_state = client_states.get(cmd.client_type, 'NONE')

        if cmd.command == 'CREATE':
            return current_state in ['NONE', 'FREED']
        elif cmd.command == 'START':
            return current_state == 'CREATED'
        elif cmd.command in ['DATA', 'EVENT']:
            return current_state == 'STARTED'
        elif cmd.command == 'STOP':
            return current_state == 'STARTED'
        elif cmd.command == 'FREE':
            return current_state in ['CREATED', 'STOPPED']
        elif cmd.command == 'CANCEL':
            return current_state == 'STARTED'

        return True

    def _update_client_state(self, cmd: DSLCommand, client_states: Dict[str, str]):
        """更新客户端状态"""
        if cmd.client_type == 'SYS':
            return

        if cmd.command == 'CREATE':
            client_states[cmd.client_type] = 'CREATED'
        elif cmd.command == 'START':
            client_states[cmd.client_type] = 'STARTED'
        elif cmd.command == 'STOP':
            client_states[cmd.client_type] = 'STOPPED'
        elif cmd.command == 'FREE':
            client_states[cmd.client_type] = 'FREED'
        elif cmd.command == 'CANCEL':
            client_states[cmd.client_type] = 'CANCELLED'

    def generate_execution_plan(self, cases: List[DSLCase]) -> List[Dict[str, Any]]:
        """生成执行计划"""
        execution_plan = []

        for case_index, case in enumerate(cases):
            for repeat_index in range(case.repeat_count):
                case_plan = {
                    'case_index': case_index,
                    'repeat_index': repeat_index,
                    'repeat_count': case.repeat_count,
                    'comment': case.comment,
                    'commands': []
                }

                for cmd_index, cmd in enumerate(case.commands):
                    cmd_plan = {
                        'cmd_index': cmd_index,
                        'client_type': cmd.client_type,
                        'command': cmd.command,
                        'params': cmd.params,
                        'delay': cmd.delay,
                        'raw_command': str(cmd)
                    }
                    case_plan['commands'].append(cmd_plan)

                execution_plan.append(case_plan)

        logger.info(f"生成执行计划: {len(execution_plan)} 个执行单元")
        return execution_plan
