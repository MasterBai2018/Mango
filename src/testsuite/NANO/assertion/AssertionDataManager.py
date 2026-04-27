#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2025/10/14
# @Author  : huidong.bai
# @File    : AssertionDataManager.py
# @Software: PyCharm  
# @Mail    : MasterBai2018@outlook.com
import time
import threading
from loguru import logger
from dataclasses import dataclass
from typing import Dict, List, Any, Optional
from src.testsuite.NANO.dsl_engine import DSLCommand, Status 


@dataclass 
class ApiCallRecord:
    """API调用记录"""
    interface_name: str        # 接口名称，如GET_VERSION, SETVRCONFIG等
    params: List[str]          # 调用参数
    return_value: Any          # 返回值
    timestamp: float           # 调用时间戳
    client_type: str           # 客户端类型
    call_id: str               # 调用ID，用于匹配断言
    assertion_type: str        # 对应的断言类型，如GET_VERSION_RET
    is_consumed: bool = False  # 是否已被断言消费

@dataclass
class CallbackRecord:
    """回调记录"""
    client_name: str
    status: int
    data: Dict
    callback_type: str
    channel: str
    timestamp: float
    is_consumed: bool = False  # 是否已被断言消费


class AssertionDataManager:
    """断言数据管理器 - 重新设计的数据收集和匹配系统"""
    
    def __init__(self):
        self.callback_records: List[CallbackRecord] = []
        self.api_call_records: List[ApiCallRecord] = []
        self._call_counter = 0  # 调用计数器
        self.lock = threading.Lock()
        self.condition = threading.Condition(self.lock)  # 条件变量，用于等待数据到达
    
    def get_assertion_type(self, interface_name: str, params: List[str]) -> str:
        """根据接口名和参数获取对应的断言类型"""
        if interface_name in ['SETVRCONFIG', 'SET_PARAM']:
            interface_name = params[0]
        return interface_name + '_RET'
    
    def add_callback_data(self, client_name: str, status: int, result_data: dict, channel: str, callback_type: str):
        """添加回调数据"""
        with self.condition:
            # VRConfig和ECNR类型特殊处理：合并到已有的VRConfig和ECNR记录中
            if callback_type in ['VRConfig', 'ECNR']:
                # 从已有列表中查找VRConfig和ECNR类型的记录
                singleton_record = None
                for record in self.callback_records:
                    if record.callback_type in ['VRConfig', 'ECNR']:
                        singleton_record = record
                        break
                
                if singleton_record:
                    # 将新的result_data按照key-value形式合并到data中
                    if isinstance(singleton_record.data, dict) and isinstance(result_data, dict):
                        singleton_record.data.update(result_data)
                    else:
                        # 如果data不是dict，则替换为新的result_data
                        singleton_record.data = result_data
                    logger.debug(f"更新VRConfig回调记录: {client_name}, 数据: {result_data}")
                else:
                    # 如果没有找到，创建新记录
                    record = CallbackRecord(
                        client_name=client_name,
                        status=status,
                        data=result_data,
                        callback_type=callback_type,
                        channel=str(channel),
                        timestamp=time.time()
                    )
                    self.callback_records.append(record)
                    logger.debug(f"创建{callback_type}回调记录: {client_name}, 数据: {result_data}")
            else:
                # 非VRConfig和ECNR类型，正常添加新记录
                record = CallbackRecord(
                    client_name=client_name,
                    status=status,
                    data=result_data,
                    callback_type=callback_type,
                    channel=str(channel),
                    timestamp=time.time()
                )
                self.callback_records.append(record)
                logger.debug(f"添加回调记录: {callback_type} from {client_name}")
            
            # 唤醒所有等待的断言线程
            self.condition.notify_all()
    
    def add_api_call_data(self, command: DSLCommand):
        """添加API调用数据"""
        with self.condition:
            self._call_counter += 1
            call_id = f"{command.command}_{self._call_counter}_{int(time.time() * 1000)}"
            assertion_type = self.get_assertion_type(command.command, command.params)
            
            record = ApiCallRecord(
                interface_name=command.command,
                params=command.params,
                return_value=command.return_code,
                timestamp=time.time(),
                client_type=command.client_type,
                call_id=call_id,
                assertion_type=assertion_type
            )
            self.api_call_records.append(record)
            logger.debug(f"添加API调用记录: {assertion_type} = {command.return_code}")
            # 唤醒所有等待的断言线程
            self.condition.notify_all()

    def find_callback_all_match(self, callback_type: str, channel: str = None) -> List[CallbackRecord]:
        """
        查找所有匹配的回调记录
        
        Args:
            callback_type: 回调类型
            channel: 通道ID，支持以下格式：
                - None: 匹配任意通道
                - "123": 匹配通道1、2、3（字符串拆解）
                - "[0,1,2,3]": 匹配通道0、1、2、3（列表格式）
                - "0": 匹配通道0（单个通道）
        
        Returns:
            匹配的回调记录列表
        """
        matched_records = []
        
        # 解析通道列表
        for record in self.callback_records:
            if record.callback_type != callback_type:
                continue

            if channel != "-1":
                channel_list = channel.split(',')
                if record.channel not in channel_list:
                    continue
            matched_records.append(record)
        return matched_records

    def find_callback_match(self, callback_type: str, channel: str = None, wait: bool = False) -> Optional[CallbackRecord]:
        """
        查找匹配的回调记录
        
        Args:
            callback_type: 回调类型
            channel: 通道ID，None表示任意通道
            wait: 是否在未找到时立即返回（False）还是仅查找不消费（True时用于wait逻辑）
        """
        # 注意：调用者需要持有 condition 锁
        for record in self.callback_records:
            # 如果当前记录结果已被消费，则跳过
            if callback_type in ['VRConfig', 'ECNR'] and record.callback_type in ['VRConfig', 'ECNR']:
                return record
            if record.is_consumed:
                continue
            # 如果回调类型不匹配，则跳过
            if record.callback_type != callback_type:
                continue
            # 如果通道不匹配，则跳过
            if channel is not None and record.channel != str(channel):
                continue
            if not wait:
                record.is_consumed = True  # 标记为已消费
            return record
        return None
    
    def find_api_call_match(self, assertion_type: str, wait: bool = False) -> Optional[ApiCallRecord]:
        """
        查找匹配的API调用记录
        
        Args:
            assertion_type: 断言类型
            wait: 是否在未找到时立即返回（False）还是仅查找不消费（True时用于wait逻辑）
        """
        # 注意：调用者需要持有 condition 锁
        # 按时间倒序查找最新的未消费记录
        for record in reversed(self.api_call_records):
            if record.is_consumed:
                continue
            if record.assertion_type != assertion_type:
                continue
            
            if not wait:
                record.is_consumed = True  # 标记为已消费
            return record
        return None
    
    def clear_case_data(self):
        """清理当前case的数据"""
        with self.condition:
            # 保留初始化回调，避免Case开始清理后无法断言LCSInit
            self.callback_records = [r for r in self.callback_records if r.callback_type == "LCSInit"]
            self.api_call_records.clear()
            self._call_counter = 0
            logger.debug("已清理case断言数据")
    
    def clear_callback_data(self, callback_type: str = None):
        """
        清空回调数据
        
        Args:
            callback_type: 指定要清空的回调类型，None表示清空所有回调数据
        """
        with self.condition:
            if callback_type:
                # 清空指定类型的回调数据
                before_count = len(self.callback_records)
                self.callback_records = [r for r in self.callback_records 
                                        if r.callback_type != callback_type]
                after_count = len(self.callback_records)
                logger.debug(f"已清空回调数据: {callback_type}, 清理数量: {before_count - after_count}")
            else:
                # 清空所有回调数据
                count = len(self.callback_records)
                self.callback_records.clear()
                logger.debug(f"已清空所有回调数据, 清理数量: {count}")

    def clear_api_data(self, api_type: str = None):
        """
        清空API调用数据
        
        Args:
            api_type: 指定要清空的API断言类型，None表示清空所有API数据
        """
        with self.condition:
            if api_type:
                # 清空指定类型的API数据
                before_count = len(self.api_call_records)
                self.api_call_records = [r for r in self.api_call_records 
                                        if r.assertion_type != api_type]
                after_count = len(self.api_call_records)
                logger.debug(f"已清空API数据: {api_type}, 清理数量: {before_count - after_count}")
            else:
                # 清空所有API数据
                count = len(self.api_call_records)
                self.api_call_records.clear()
                logger.debug(f"已清空所有API数据, 清理数量: {count}")
    
    def cleanup_consumed_data(self):
        """清理已消费的数据"""
        with self.condition:
            self.callback_records = [r for r in self.callback_records if not r.is_consumed]
            self.api_call_records = [r for r in self.api_call_records if not r.is_consumed]
            logger.debug("已清理已消费的断言数据")
