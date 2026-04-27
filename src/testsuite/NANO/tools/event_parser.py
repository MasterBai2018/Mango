#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2025/11/20
# @Author  : huidong.bai
# @File    : event_parser.py
# @Software: PyCharm
# @Mail    : MasterBai2018@outlook.com

import os
import json
import copy
from loguru import logger
from src.utils.common import trans_digit


class NANOEventParser:
    """
    NANO DSL事件解析器
    用于INPUTEVENT和CALLBACK指令的JSON事件处理
    简化版的NluEventParser，专为NANO设计
    """

    def __init__(self, input_path: str, callback_path: str):
        """
        初始化事件解析器
        
        Args:
            input_path: InputEvent事件JSON文件夹路径
            callback_path: CallBackEvent事件JSON文件夹路径
        """
        self.input_path = input_path
        self.callback_path = callback_path
        self.input_events = {}  # 存储Input事件：{event_name: json_data}
        self.callback_events = {}  # 存储Callback事件：{event_name: json_data}
        
        # 加载事件JSON文件
        self._load_events()

    def _load_events(self):
        """加载Input和Callback事件JSON文件"""
        try:
            # 加载Input事件（直接使用文件名）
            if os.path.exists(self.input_path):
                self.input_events = self._load_input_json_files(self.input_path)
                logger.info(f"成功加载 {len(self.input_events)} 个InputEvent")
            else:
                logger.warning(f"InputEvent路径不存在: {self.input_path}")
            
            # 加载Callback事件（使用"文件夹名.文件名"格式）
            if os.path.exists(self.callback_path):
                self.callback_events = self._load_callback_json_files(self.callback_path)
                logger.info(f"成功加载 {len(self.callback_events)} 个CallbackEvent")
            else:
                logger.warning(f"CallbackEvent路径不存在: {self.callback_path}")
        
        except Exception as e:
            logger.error(f"加载事件文件失败: {e}")
            raise

    def _load_input_json_files(self, folder_path: str) -> dict:
        """
        加载Input事件JSON文件
        命名规则：直接使用文件名（不含.json）
        
        Args:
            folder_path: Input事件文件夹路径
            
        Returns:
            {文件名: json数据} 的字典
            
        Example:
            文件: InputEvent/AppStatus.json
            Key: AppStatus
        """
        events = {}
        # 黑名单文件夹路径，这些路径下的文件不处理
        blacklist_paths = [
            'InputEvent/HMI',
        ]
        
        for root, dirs, files in os.walk(folder_path):
            # 检查当前路径是否在黑名单中
            normalized_root = root.replace('\\', '/')
            is_blacklisted = any(blacklist_path in normalized_root for blacklist_path in blacklist_paths)
            if is_blacklisted:
                logger.debug(f"跳过黑名单路径: {root}")
                continue
            for file in files:
                if file.endswith('.json'):
                    file_path = os.path.join(root, file)
                    event_name = file.replace('.json', '')
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            events[event_name] = json.load(f)
                    except Exception as e:
                        pass
        
        return events

    def _load_callback_json_files(self, folder_path: str) -> dict:
        """
        加载Callback事件JSON文件
        命名规则：父文件夹名.文件名（不含.json）
        
        Args:
            folder_path: Callback事件文件夹路径
            
        Returns:
            {父文件夹名.文件名: json数据} 的字典
            
        Example:
            文件: CallBackEvent/AppDIRCallback/open.json
            Key: AppDIRCallback.open
        """
        events = {}

        for root, dirs, files in os.walk(folder_path):
            for file in files:
                if file.endswith('.json'):
                    file_path = os.path.join(root, file)
                    # 获取父文件夹名
                    parent_folder = os.path.basename(os.path.dirname(file_path))
                    # 组合命名：父文件夹名.文件名
                    event_name = parent_folder + '.' + file.replace('.json', '')
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            events[event_name] = json.load(f)
                    except Exception as e:
                        pass
        
        return events

    def get_input_event(self, event_name: str, modifications: str = None) -> dict:
        """
        获取Input事件JSON，并可选地修改字段值
        
        Args:
            event_name: 事件名称（JSON文件名，不含.json）
            modifications: 修改参数，格式：path1:value1;path2:value2
            
        Returns:
            JSON字典（修改后的）
            
        Raises:
            ValueError: 事件不存在或修改失败
        """
        if event_name not in self.input_events:
            raise ValueError(f"InputEvent '{event_name}' 不存在")
        
        # 深拷贝原始JSON
        event_json = copy.deepcopy(self.input_events[event_name])
        
        # 如果有修改参数，应用修改
        if modifications:
            event_json = self._apply_modifications(event_json, modifications, event_name)
        
        return event_json

    def get_callback_event(self, event_name: str, modifications: str = None) -> dict:
        """
        获取Callback事件JSON，并可选地修改字段值
        
        Args:
            event_name: 事件名称（JSON文件名，不含.json）
            modifications: 修改参数，格式：path1:value1;path2:value2
            
        Returns:
            JSON字典（修改后的）
            
        Raises:
            ValueError: 事件不存在或修改失败
        """
        if event_name not in self.callback_events:
            raise ValueError(f"CallbackEvent '{event_name}' 不存在。")
        
        # 深拷贝原始JSON
        event_json = copy.deepcopy(self.callback_events[event_name])
        
        # 如果有修改参数，应用修改
        if modifications:
            event_json = self._apply_modifications(event_json, modifications, event_name)
        
        return event_json

    def _apply_modifications(self, json_data: dict, modifications: str, event_name: str) -> dict:
        """
        应用字段修改到JSON数据
        
        Args:
            json_data: 原始JSON数据
            modifications: 修改参数，格式：path1:value1;path2:value2
            event_name: 事件名称（用于日志）
            
        Returns:
            修改后的JSON数据
            
        Example:
            modifications = "data.AppStoreGBookStatus:-2;source:TSA2"
            原始JSON: {"source":"TSA","data":{"AppStoreGBookStatus":0}}
            修改后: {"source":"TSA2","data":{"AppStoreGBookStatus":-2}}
        """
        if not modifications:
            return json_data
        
        # 解析修改参数：path1:value1;path2:value2
        modifications_list = modifications.split(';')
        
        for modification in modifications_list:
            modification = modification.strip()
            if not modification:
                continue
            
            if ':' not in modification:
                logger.warning(f"跳过无效的修改参数: {modification}")
                continue
            
            # 分割path和value
            path, value = modification.split(':', 1)
            path = path.strip()
            value = value.strip()
            
            # 应用修改
            json_data = self._set_nested_value(json_data, path, value, event_name)
        
        return json_data

    def _set_nested_value(self, json_data: dict, path: str, value: str, event_name: str) -> dict:
        """
        设置嵌套JSON中的值
        
        Args:
            json_data: JSON数据
            path: 字段路径，使用.分隔，例如：data.AppStoreGBookStatus
            value: 新值（字符串，会自动转换类型）
            event_name: 事件名称（用于日志）
            
        Returns:
            修改后的JSON数据
        """
        keys = path.split('.')
        current = json_data
        
        # 遍历到倒数第二层
        for key in keys[:-1]:
            if key not in current:
                logger.error(f"事件 '{event_name}' 中找不到路径: {path}（缺少键: {key}）")
                raise ValueError(f"路径 '{path}' 在事件 '{event_name}' 中不存在")
            current = current[key]
        
        # 设置最后一层的值
        last_key = keys[-1]
        if last_key not in current:
            logger.error(f"事件 '{event_name}' 中找不到路径: {path}（缺少键: {last_key}）")
            raise ValueError(f"路径 '{path}' 在事件 '{event_name}' 中不存在")
        
        # 自动类型转换
        converted_value = self._convert_value(value)
        current[last_key] = converted_value
        
        logger.debug(f"  修改字段: {path} = {converted_value} (原值: {current.get(last_key)})")
        
        return json_data

    def _convert_value(self, value: str):
        """
        自动类型转换：字符串 -> 合适的Python类型
        
        Args:
            value: 字符串值
            
        Returns:
            转换后的值（int、float、bool或str）
        """
        # 尝试转换为数字（int或float）
        numeric_value = trans_digit(value)
        if numeric_value is not None:
            return numeric_value
        
        # 转换布尔值
        if value.lower() == "true":
            return True
        elif value.lower() == "false":
            return False
        
        # 如果是文件路径，加载JSON
        if os.path.exists(value) and value.endswith('.json'):
            try:
                with open(value, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"加载JSON文件失败: {value}, 错误: {e}，使用字符串")
        
        # 默认返回字符串
        return value


if __name__ == '__main__':
    # 测试代码
    input_path = "TestCase/caselist/MongoCase/events/InputEvent"
    callback_path = "TestCase/caselist/MongoCase/events/CallBackEvent"
    
    try:
        parser = NANOEventParser(input_path, callback_path)
        
        # 测试获取Input事件
        event = parser.get_input_event("AppStatus", "app.status:-2")
        print("Modified Input Event:", json.dumps(event, ensure_ascii=False, indent=2))
        
        # 测试获取Callback事件
        event2 = parser.get_callback_event("NaviCallBackDir", "data.text:111;status.abc:233")
        print("Modified Callback Event:", json.dumps(event2, ensure_ascii=False, indent=2))
        
    except Exception as e:
        print(f"Error: {e}")

