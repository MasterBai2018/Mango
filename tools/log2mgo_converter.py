#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志转MGO时序文件转换器

本脚本用于解析AIBS客户端SDK日志文件，并转换成MGO格式的DSL时序文件。
支持TSA、SET、VOI三种客户端类型的日志解析。

特性:
    - 自动识别客户端类型（TSA/SET/VOI）
    - 自动在指定目录下查找客户端日志文件
    - 自动找到最后一次createAttachEngine位置，只解析最新一次启动后的日志
    - 支持多客户端日志合并，按时间戳排序
    - 支持去重连续重复的指令

使用方法:
    python3 log2mgo_converter.py <log_dir> [options]
    
参数说明:
    log_dir     : 日志文件所在目录，自动查找以下日志文件:
                  - TSA: com_autoai_vr_service*_Client.log
                  - SET: com_iauto_systemsetting*_Client.log
                  - VOI: com_toyota_cn_agentservice*_Client.log
    -o, --output: 输出的mgo文件路径（默认: <log_dir>/output.mgo）
    -v, --verbose: 显示详细信息（包含时间戳和注释）

示例:
    python3 log2mgo_converter.py ./实机log -o result.mgo
    python3 log2mgo_converter.py ./实机log -v

作者: baihuidong
日期: 2025/01/29
"""

import re
import sys
import os
import glob
import json
import argparse
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field


@dataclass
class LogEntry:
    """日志条目数据类"""
    timestamp: datetime          # 时间戳
    level: str                   # 日志级别 INFO/NOTICE/WARN/ERROR
    source: str                  # 来源模块 (AIBSClient/aibs_client_api/appid)
    method: str                  # 方法名
    message: str                 # 日志消息内容
    line_number: int             # 行号
    raw_line: str                # 原始日志行
    client_type: str = None      # 客户端类型 (TSA/SET/VOI等)，用于多文件合并


@dataclass
class MgoCommand:
    """MGO指令数据类"""
    client: str                  # 客户端类型 TSA/SET/SYS/EXP
    command: str                 # 指令名称
    params: str                  # 参数
    timestamp: datetime          # 时间戳
    comment: str = ""            # 注释
    is_callback: bool = False    # 是否为回调断言


# ============================================================================
# VR配置项映射表
# ============================================================================
VR_CONFIG_KEY_MAP = {
    0: "DEVICE_INFO",
    1: "VR_OPTION",
    2: "SHOW_STYLE",
    3: "WAKEUP_ALIAS",
    4: "DIALOGUE_STYLE",
    5: "DIALOGUE_LANGUAGE",
    6: "SOUND_AREA_OPTION",
    7: "WAKEUP_KEYWORD_OPTION",
    8: "VOICE_WAKEUP_OPTION",
    9: "WAKEUP_ENABLE",
    16: "GET_WAKEUP_WORD",
    17: "SET_TTS_VOICE_TYPE",
    18: "MULTI_DIALOGUE",
    19: "EXPERIENCE_IMPROVENMENT",
    20: "PERSONAL_SENSITIVE_AUTHORIZATION",
    21: "VOICE_SENSITIVE_AUTHORIZATION",
    23: "ACTIVE_INTERACTION",
    24: "SRE_SENSITIVE_EMPOWER_OPTION",
    25: "SRE_FUNC_ENABLE_OPTION",
    32: "SERVER_CACHE_LANGUAGE",
    33: "GPT_ENABLE_OPTION",
    34: "SRE_MEMORY",
    35: "VEHICLE_MEMORY",
}

# AIBS参数映射表
AIBS_PARAM_MAP = {
    0x01: "AIBS_PARAM_SESSION_LINK_TYPE",
    0x02: "AIBS_PARAM_SEAT_SIGNAL",
    0x03: "AIBS_PARAM_FULL_VEHICLE_SPEECH",
    0x04: "AIBS_PARAM_REAL_TIME_RESULT",
    0x05: "AIBS_PARAM_PUNC_RESULT",
    0x06: "AIBS_PARAM_DIGIT_CONVERT_RESULT",
    0x07: "AIBS_PARAM_SILENCE_DURATION",
    0x08: "AIBS_PARAM_SILENCE_TIMEOUT",
    0x09: "AIBS_PARAM_SPEECH_TIMEOUT",
    0x0A: "AIBS_PARAM_SCENAROI_NAME",
    0x0B: "AIBS_PARAM_WAKEUP_SCENE",
    0x0C: "AIBS_PARAM_WAKEUP_DELAY_ONESHOT_DURATION",
    0x0D: "AIBS_PARAM_SOUND_EVENT_OPTION",
    0x0E: "AIBS_PARAM_DISABLE_BUTTON_WAKEUP",
    0x0F: "AIBS_PARAM_EMOTION_OPTION",
    0x10: "AIBS_PARAM_SR_PTT_OPTION",
    0x12: "AIBS_PARAM_SR_VOICE_WAKEUP",
    0x14: "AIBS_PARAM_SR_WAKEUP_SCENE_ENABLE",
    0x15: "AIBS_PARAM_SR_AUDIO_SPECTRAL",
    0x16: "AIBS_PARAM_SR_RECORD_DEVICE_STATE",
}


class LogParser:
    """日志解析器"""
    
    # 日志行正则表达式
    LOG_PATTERN = re.compile(
        r'^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2},\d{3})\s+'
        r'\[(\w+)\]\s+'
        r'(\w+)\[(\w+)\]\s+'
        r'(.*)$'
    )
    
    # 特殊日志行模式（writeLog）
    WRITELOG_PATTERN = re.compile(
        r'^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2},\d{3})\s+'
        r'\[(\w+)\]\s+'
        r'([\w.]+)\[writeLog\]\s+'
        r'(.*)$'
    )
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.entries: List[LogEntry] = []
        self.client_type: Optional[str] = None
        self.appid: Optional[str] = None
        
    def parse_file(self, filepath: str, force_client_type: str = None) -> List[LogEntry]:
        """解析日志文件
        
        Args:
            filepath: 日志文件路径
            force_client_type: 强制指定客户端类型（用于多文件合并时保持独立性）
        """
        self.entries = []
        self.client_type = force_client_type
        self.appid = None
        
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # 找到最后一次出现 "createAttachEngine config_path" 的行号
        # 这标志着最新一次车机重启后的日志起始位置
        start_line_idx = 0
        for idx, line in enumerate(lines):
            if "createAttachEngine" in line and "config_path" in line:
                start_line_idx = idx
                
        if self.verbose and start_line_idx > 0:
            print(f"[INFO] 找到最后一次createAttachEngine在第 {start_line_idx + 1} 行，从该位置开始解析")
            print(f"[INFO] 跳过前 {start_line_idx} 行历史日志")
            
        for line_num, line in enumerate(lines, 1):
            # 只解析最后一次createAttachEngine之后的日志
            if line_num - 1 < start_line_idx:
                continue
                
            line = line.strip()
            if not line:
                continue
                
            entry = self._parse_line(line, line_num)
            if entry:
                self.entries.append(entry)
                # 自动检测客户端类型（仅当未强制指定时）
                if not self.appid:
                    self._detect_client_type(entry)
                    
        # 为每个条目标记客户端类型
        for entry in self.entries:
            entry.client_type = self.client_type
                    
        if self.verbose:
            print(f"[INFO] 解析完成，共 {len(self.entries)} 条日志记录")
            print(f"[INFO] 检测到客户端类型: {self.client_type}, AppID: {self.appid}")
            
        return self.entries
    
    def _parse_line(self, line: str, line_num: int) -> Optional[LogEntry]:
        """解析单行日志"""
        # 尝试匹配标准格式
        match = self.LOG_PATTERN.match(line)
        if match:
            timestamp_str, level, source, method, message = match.groups()
            timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S,%f')
            return LogEntry(
                timestamp=timestamp,
                level=level,
                source=source,
                method=method,
                message=message,
                line_number=line_num,
                raw_line=line
            )
            
        # 尝试匹配writeLog格式
        match = self.WRITELOG_PATTERN.match(line)
        if match:
            timestamp_str, level, source, message = match.groups()
            timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S,%f')
            return LogEntry(
                timestamp=timestamp,
                level=level,
                source=source,
                method="writeLog",
                message=message,
                line_number=line_num,
                raw_line=line
            )
            
        return None
    
    def _detect_client_type(self, entry: LogEntry):
        """检测客户端类型"""
        if entry.method == "createAttachEngine" and "appid" in entry.message:
            # 从createAttachEngine中提取appid
            appid_match = re.search(r'appid\s*\[([^\]]+)\]', entry.message)
            if appid_match:
                self.appid = appid_match.group(1)
                # 如果未强制指定客户端类型，则自动检测
                if not self.client_type:
                    # 根据appid判断客户端类型
                    if "vrassistant" in self.appid.lower() or "vr.service" in self.appid.lower():
                        self.client_type = "TSA"
                    elif "setting" in self.appid.lower() or "vrsetting" in self.appid.lower():
                        self.client_type = "SET"
                    elif "agentservice" in self.appid.lower() or "toyota" in self.appid.lower():
                        self.client_type = "VOI"
                    else:
                        self.client_type = "TSA"  # 默认TSA
                    

class MgoConverter:
    """MGO格式转换器"""
    
    def __init__(self, client_type: str = "TSA", with_callbacks: bool = False, verbose: bool = False):
        self.default_client_type = client_type  # 默认客户端类型（当条目没有client_type时使用）
        self.with_callbacks = with_callbacks
        self.verbose = verbose
        self.commands: List[MgoCommand] = []
        
    def convert(self, entries: List[LogEntry]) -> List[MgoCommand]:
        """将日志条目转换为MGO指令"""
        self.commands = []
        
        i = 0
        while i < len(entries):
            entry = entries[i]
            cmd = self._convert_entry(entry, entries, i)
            if cmd:
                if isinstance(cmd, list):
                    self.commands.extend(cmd)
                else:
                    self.commands.append(cmd)
            i += 1
            
        if self.verbose:
            print(f"[INFO] 转换完成，共生成 {len(self.commands)} 条MGO指令")
            
        return self.commands
    
    def _get_client_type(self, entry: LogEntry) -> str:
        """获取日志条目对应的客户端类型"""
        return entry.client_type if entry.client_type else self.default_client_type
    
    def _convert_entry(self, entry: LogEntry, entries: List[LogEntry], index: int) -> Optional[MgoCommand]:
        """转换单条日志为MGO指令"""
        client_type = self._get_client_type(entry)
        
        # 1. 创建引擎 createAttachEngine
        if entry.method == "createAttachEngine" and "createAttachEngine config_path" in entry.message:
            return self._parse_create_engine(entry, client_type)
            
        # 2. 设置工作模式 aibs_set_workmode
        if entry.source == "aibs_client_api" and entry.method == "aibs_set_workmode":
            return self._parse_set_workmode(entry, client_type)
            
        # 3. 启动引擎 aibs_start_engine
        if entry.source == "aibs_client_api" and entry.method == "aibs_start_engine":
            return self._parse_start_engine(entry, client_type)
            
        # 4. 停止引擎 aibs_stop_engine
        if entry.source == "aibs_client_api" and entry.method == "aibs_stop_engine":
            return MgoCommand(
                client=client_type,
                command="STOP",
                params="",
                timestamp=entry.timestamp
            )
            
        # 5. 释放引擎 aibs_free_engine
        if entry.source == "aibs_client_api" and entry.method == "aibs_free_engine":
            return MgoCommand(
                client=client_type,
                command="FREE",
                params="",
                timestamp=entry.timestamp
            )
            
        # 6. 开始录音 aibs_start_record
        if entry.source == "aibs_client_api" and entry.method == "aibs_start_record":
            return MgoCommand(
                client=client_type,
                command="START_RECORD",
                params="",
                timestamp=entry.timestamp,
                comment="开始录音"
            )
            
        # 7. 停止录音 aibs_stop_record
        if entry.source == "aibs_client_api" and entry.method == "aibs_stop_record":
            return MgoCommand(
                client=client_type,
                command="STOP_RECORD",
                params="",
                timestamp=entry.timestamp,
                comment="停止录音"
            )
            
        # 8. 设置车型 aibs_set_car_type
        if entry.source == "aibs_client_api" and entry.method == "aibs_set_car_type":
            return self._parse_set_car_type(entry, client_type)
            
        # 9. 设置参数 set_aibs_param
        if entry.source == "aibs_client_api" and entry.method == "set_aibs_param":
            return self._parse_set_param(entry, entries, index, client_type)
            
        # 10. 设置事件 aibs_set_event (TSA)
        if entry.source == "aibs_client_api" and entry.method == "aibs_set_event":
            return self._parse_set_event(entry, entries, index, client_type)
            
        # 11. 设置VR事件 aibs_set_vr_event (SET)
        if entry.source == "aibs_client_api" and entry.method == "aibs_set_vr_event":
            return self._parse_set_vr_event(entry, entries, index, client_type)
            
        # 12. 设置VR配置 aibs_set_vr_config
        if entry.source == "aibs_client_api" and entry.method == "aibs_set_vr_config":
            return self._parse_set_vr_config(entry, entries, index, client_type)
            
        # 13. 获取VR配置 aibs_get_vr_config
        if entry.source == "aibs_client_api" and entry.method == "aibs_get_vr_config":
            return self._parse_get_vr_config(entry, client_type)
            
        # 14. 获取已注册声纹 aibs_get_registered_speaker
        if entry.source == "aibs_client_api" and entry.method == "aibs_get_registered_speaker":
            return MgoCommand(
                client=client_type,
                command="GET_SPEAKERS",
                params="",
                timestamp=entry.timestamp,
                comment="获取已注册声纹列表"
            )
            
        # 15. 获取FOTA状态 get_fota_status
        if entry.source == "aibs_client_api" and entry.method == "get_fota_status":
            return MgoCommand(
                client=client_type,
                command="GET_FOTA_STATUS",
                params="",
                timestamp=entry.timestamp,
                comment="获取FOTA状态"
            )
            
        # 16. 回调处理 doCallback
        if self.with_callbacks and entry.method == "doCallback":
            return self._parse_callback(entry, client_type)
            
        return None
    
    def _parse_create_engine(self, entry: LogEntry, client_type: str) -> Optional[MgoCommand]:
        """解析创建引擎指令"""
        # 示例: createAttachEngine config_path:[/xxx] lang [cmn] appid [com.xxx]
        lang_match = re.search(r'lang\s*\[(\w+)\]', entry.message)
        appid_match = re.search(r'appid\s*\[([^\]]+)\]', entry.message)
        
        if lang_match and appid_match:
            lang = lang_match.group(1)
            appid = appid_match.group(1)
            return MgoCommand(
                client=client_type,
                command="CREATE",
                params=f"{lang} {appid}",
                timestamp=entry.timestamp,
                comment=f"创建{client_type}客户端"
            )
        return None
    
    def _parse_set_workmode(self, entry: LogEntry, client_type: str) -> Optional[MgoCommand]:
        """解析设置工作模式指令"""
        # 示例: aibs set workmode - 2
        mode_match = re.search(r'workmode\s*-\s*(\d+)', entry.message)
        if mode_match:
            mode = mode_match.group(1)
            return MgoCommand(
                client=client_type,
                command="SET_WORKMODE",
                params=mode,
                timestamp=entry.timestamp,
                comment=f"设置工作模式: {mode}"
            )
        return None
    
    def _parse_start_engine(self, entry: LogEntry, client_type: str) -> Optional[MgoCommand]:
        """解析启动引擎指令"""
        return MgoCommand(
            client=client_type,
            command="START",
            params="1",  # 默认单通道
            timestamp=entry.timestamp,
            comment="启动会话"
        )
    
    def _parse_set_car_type(self, entry: LogEntry, client_type: str) -> Optional[MgoCommand]:
        """解析设置车型指令"""
        # 示例: aibs set car type {"brand":"1","device_name":"312D","mic_num":"4"}
        json_match = re.search(r'car type\s*(\{.*\})', entry.message)
        if json_match:
            car_type_json = json_match.group(1)
            return MgoCommand(
                client=client_type,
                command="CAR_TYPE",
                params=car_type_json,
                timestamp=entry.timestamp,
                comment="设置车型信息"
            )
        return None
    
    def _parse_set_param(self, entry: LogEntry, entries: List[LogEntry], index: int, client_type: str) -> Optional[MgoCommand]:
        """解析设置参数指令"""
        # 需要查找下一行的writeLog获取具体参数
        for i in range(index + 1, min(index + 3, len(entries))):
            next_entry = entries[i]
            if next_entry.method == "writeLog" and "setAIBSEngineParam" in next_entry.message:
                # 示例: AIBSMergeServiceSolution.setAIBSEngineParam param=ENGINE_PARAM_WAKEUP_SCENE, value=2049
                param_match = re.search(r'param=(\w+),\s*value=(\S+)', next_entry.message)
                if param_match:
                    param_name = param_match.group(1).replace("ENGINE_PARAM", "AIBS_PARAM")
                    param_value = param_match.group(2)
                    return MgoCommand(
                        client=client_type,
                        command="SET_PARAM",
                        params=f"{param_name} {param_value}",
                        timestamp=entry.timestamp,
                        comment=f"设置引擎参数: {param_name}"
                    )
        return None
    
    def _parse_set_event(self, entry: LogEntry, entries: List[LogEntry], index: int, client_type: str) -> Optional[MgoCommand]:
        """解析设置事件指令 (TSA)"""
        # 查找下一行的writeLog获取事件JSON
        for i in range(index + 1, min(index + 3, len(entries))):
            next_entry = entries[i]
            if next_entry.method == "writeLog" and "setAIBSEvent" in next_entry.message:
                # 示例: AIBSMergeServiceSolution.setAIBSEvent event={...}, return ret=0
                event_match = re.search(r'event=(\{.*\}),\s*return', next_entry.message)
                if event_match:
                    event_json = event_match.group(1)
                    # 尝试解析JSON获取事件类型，并移除不需要的字段
                    try:
                        event_data = json.loads(event_json)
                        event_type = event_data.get("type", "Unknown")
                        # 移除不需要的字段
                        event_data.pop("et_id", None)
                        event_data.pop("mts", None)
                        event_json = json.dumps(event_data, ensure_ascii=False, separators=(',', ':'))
                    except:
                        event_type = "Unknown"
                    return MgoCommand(
                        client=client_type,
                        command="EVENT",
                        params=event_json,
                        timestamp=entry.timestamp,
                        comment=f"发送事件: {event_type}"
                    )
        return None
    
    def _parse_set_vr_event(self, entry: LogEntry, entries: List[LogEntry], index: int, client_type: str) -> Optional[MgoCommand]:
        """解析设置VR事件指令 (SET)"""
        # 查找下一行的writeLog获取事件JSON
        for i in range(index + 1, min(index + 3, len(entries))):
            next_entry = entries[i]
            if next_entry.method == "writeLog" and "setAIBSVREvent" in next_entry.message:
                # 示例: AIBSMergeServiceSolution.setAIBSVREvent event={...}, return ret=0
                event_match = re.search(r'event=(\{.*\}),\s*return', next_entry.message)
                if event_match:
                    event_json = event_match.group(1)
                    try:
                        event_data = json.loads(event_json)
                        event_type = event_data.get("type", "Unknown")
                        # 移除不需要的字段
                        event_data.pop("et_id", None)
                        event_data.pop("mts", None)
                        event_json = json.dumps(event_data, ensure_ascii=False, separators=(',', ':'))
                    except:
                        event_type = "Unknown"
                    return MgoCommand(
                        client=client_type,
                        command="VREVENT",
                        params=event_json,
                        timestamp=entry.timestamp,
                        comment=f"发送VR事件: {event_type}"
                    )
        return None
    
    def _parse_set_vr_config(self, entry: LogEntry, entries: List[LogEntry], index: int, client_type: str) -> Optional[MgoCommand]:
        """解析设置VR配置指令"""
        # 示例: aibs set vr config,key:23
        key_match = re.search(r'key:(\d+)', entry.message)
        if key_match:
            key_code = int(key_match.group(1))
            key_name = VR_CONFIG_KEY_MAP.get(key_code, f"KEY_{key_code}")
            
            # 查找下一行获取具体值
            for i in range(index + 1, min(index + 5, len(entries))):
                next_entry = entries[i]
                if next_entry.source == "AIBSClient" and next_entry.method == "setAIBSVRConfig":
                    # 示例: set aibs vr config key 23 str value {"categoryInfo":[...]}
                    value_match = re.search(r'value\s+(.+)$', next_entry.message)
                    if value_match:
                        value = value_match.group(1).strip()
                        return MgoCommand(
                            client=client_type,
                            command="SETVRCONFIG",
                            params=f"{key_name} {value}",
                            timestamp=entry.timestamp,
                            comment=f"设置VR配置: {key_name}"
                        )
        return None
    
    def _parse_get_vr_config(self, entry: LogEntry, client_type: str) -> Optional[MgoCommand]:
        """解析获取VR配置指令"""
        # 示例: aibs get vr config, key:8
        key_match = re.search(r'key:(\d+)', entry.message)
        if key_match:
            key_code = int(key_match.group(1))
            key_name = VR_CONFIG_KEY_MAP.get(key_code, f"KEY_{key_code}")
            return MgoCommand(
                client=client_type,
                command="GET_VR_CONFIG",
                params=key_name,
                timestamp=entry.timestamp,
                comment=f"获取VR配置: {key_name}"
            )
        return None
    
    def _parse_callback(self, entry: LogEntry, client_type: str) -> Optional[MgoCommand]:
        """解析回调指令"""
        # 示例: AIBSClient status[16], result.datalen[627], result.type[NLPResult]
        type_match = re.search(r'result\.type\[(\w+)\]', entry.message)
        if type_match:
            callback_type = type_match.group(1)
            # 过滤掉一些频繁的状态回调
            skip_types = ['NetworkStatus', 'FreeWakeupSwitch', 'KeyTraceInfo', 'BigdataReport']
            if callback_type in skip_types:
                return None
            return MgoCommand(
                client="EXP",
                command=callback_type,
                params="<timeout=5>",
                timestamp=entry.timestamp,
                is_callback=True,
                comment=f"回调断言: {callback_type}"
            )
        return None


class MgoWriter:
    """MGO文件写入器"""
    
    def __init__(self, client_type: str = "TSA", client_appid_map: Dict[str, str] = None, car_info: str = '{"brand":"0"}'):
        self.client_type = client_type
        # 客户端类型到appid的映射 {client_type: appid}
        self.client_appid_map = client_appid_map or {}
        # Server.log 中解析的 carInfo
        self.car_info = car_info
        
    def write(self, commands: List[MgoCommand], output_path: str, 
              verbose: bool = False, dedup_threshold: float = 1.0):
        """写入MGO文件
        
        Args:
            commands: MGO指令列表
            output_path: 输出文件路径
            verbose: 是否包含详细信息（时间戳和注释）
            dedup_threshold: 去重时间阈值（秒），连续相同指令在此时间内视为重复
        """
        
        # 去重：移除连续且参数相同、时间间隔短的重复指令
        commands = self._deduplicate_commands(commands, dedup_threshold)
        
        # 收集所有涉及的客户端类型
        all_clients = set()
        for cmd in commands:
            if cmd.client not in ['EXP', 'SYS']:  # 排除断言和系统客户端
                all_clients.add(cmd.client)
        
        # 如果没有收集到，使用 client_appid_map 中的客户端类型
        if not all_clients:
            all_clients = set(self.client_appid_map.keys())
            
        with open(output_path, 'w', encoding='utf-8') as f:
            # 写入文件头注释
            f.write("#" * 70 + "\n")
            f.write("# 自动生成的MGO时序文件\n")
            f.write(f"# 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# 客户端类型: {', '.join(sorted(all_clients))}\n")
            f.write(f"# 指令数量: {len(commands)}\n")
            f.write("#" * 70 + "\n\n")
            
            # 写入SETUP块 - 拉起服务并创建客户端引擎
            f.write(">>> SETUP\n")
            # 1. 先拉起系统服务（carInfo 从 Server.log 动态获取）
            f.write(f'[SYS]PULL         AIBSServer cmn {self.car_info}\n')
            f.write('[SYS]PULL         LCSEngine cmn\n')
            f.write('[SYS]PULL         SpeechEngine cmn\n')
            # 2. 再创建客户端
            setup_commands = [c for c in commands if c.command in ['CREATE']]
            # 按客户端类型分组，确保每个客户端只创建一次
            created_clients = set()
            for cmd in setup_commands:
                if cmd.client not in created_clients:
                    self._write_command(f, cmd, verbose)
                    created_clients.add(cmd.client)
            # 3. 确保所有涉及的客户端都被创建（即使日志中没有createAttachEngine）
            for client in sorted(all_clients):
                if client not in created_clients:
                    # 为没有CREATE命令的客户端生成默认CREATE指令，使用从文件名提取的appid
                    appid = self.client_appid_map.get(client, "")
                    f.write(f"[{client}]CREATE cmn {appid}\n")
                    created_clients.add(client)
            f.write("<<<\n\n")
            
            # 写入主测试块 - 按时间戳排序的所有指令
            f.write(">>>\n")
            main_commands = [c for c in commands if c.command not in ['CREATE', 'FREE']]
            
            last_timestamp = None
            for cmd in main_commands:
                # 检查时间间隔，如果超过1秒且verbose模式，添加注释
                if verbose and last_timestamp:
                    time_diff = (cmd.timestamp - last_timestamp).total_seconds()
                    if time_diff > 1:
                        f.write(f"\n# --- 间隔 {time_diff:.1f}s ---\n")
                        
                self._write_command(f, cmd, verbose)
                last_timestamp = cmd.timestamp
                
            f.write("<<<\n\n")
            
            # 写入TEARDOWN块 - 释放客户端并杀掉服务
            f.write(">>> TEARDOWN\n")
            # 1. 先释放所有客户端
            for client in sorted(all_clients):
                f.write(f"[{client}]FREE\n")
            # 2. 再杀掉系统服务（顺序与拉起相反）
            f.write('[SYS]KILL         SpeechEngine\n')
            f.write('[SYS]KILL         LCSEngine\n')
            f.write('[SYS]KILL         AIBSServer\n')
            f.write("<<<\n")
            
    def _deduplicate_commands(self, commands: List[MgoCommand], threshold: float) -> List[MgoCommand]:
        """去重：移除重复指令
        
        去重规则：
        1. 连续相同指令（相同客户端+命令+参数）在阈值时间内视为重复
        2. 关键指令（START/STOP/CREATE/FREE）即使不连续，在阈值时间内也去重
        
        Args:
            commands: 原始指令列表
            threshold: 时间阈值（秒），相同指令在此时间内视为重复
            
        Returns:
            去重后的指令列表
        """
        if not commands:
            return commands
        
        # 关键指令列表 - 这些指令即使不连续也要去重
        KEY_COMMANDS = {'START', 'STOP', 'CREATE', 'FREE', 'SET_WORKMODE'}
        
        deduplicated = [commands[0]]
        
        # 记录每个客户端的关键指令最近出现时间和参数
        key_cmd_tracker = {}  # {(client, command, params): timestamp}
        
        # 初始化第一条指令的跟踪
        first_cmd = commands[0]
        if first_cmd.command in KEY_COMMANDS:
            key = (first_cmd.client, first_cmd.command, first_cmd.params)
            key_cmd_tracker[key] = first_cmd.timestamp
        
        for i in range(1, len(commands)):
            current = commands[i]
            previous = deduplicated[-1]
            
            # 检查是否为连续重复指令
            is_consecutive_duplicate = (
                current.client == previous.client and
                current.command == previous.command and
                current.params == previous.params
            )
            
            # 检查时间间隔
            time_diff_consecutive = (current.timestamp - previous.timestamp).total_seconds()
            
            # 规则1：连续相同指令在阈值内去重
            if is_consecutive_duplicate and abs(time_diff_consecutive) <= threshold:
                continue
            
            # 规则2：关键指令即使不连续也要去重
            if current.command in KEY_COMMANDS:
                key = (current.client, current.command, current.params)
                if key in key_cmd_tracker:
                    time_diff_key = (current.timestamp - key_cmd_tracker[key]).total_seconds()
                    if abs(time_diff_key) <= threshold:
                        # 在阈值内的重复关键指令，跳过
                        continue
                # 更新跟踪器
                key_cmd_tracker[key] = current.timestamp
                
            deduplicated.append(current)
            
        return deduplicated
    
    def _write_command(self, f, cmd: MgoCommand, verbose: bool):
        """写入单条指令"""
        line = f"[{cmd.client}]{cmd.command}"
        if cmd.params:
            line += f" {cmd.params}"
            
        # 只在verbose模式下添加时间戳和注释
        if verbose:
            timestamp_str = cmd.timestamp.strftime('%H:%M:%S.%f')[:-3]
            line = line.ljust(80) + f" # {timestamp_str}"
            if cmd.comment:
                line += f" - {cmd.comment}"
            
        f.write(line + "\n")


def parse_server_log(log_dir: str, verbose: bool = False) -> str:
    """从Server.log中解析carInfo参数
    
    查找最后一次 "START AIBS SERVER with file" 日志行，提取carInfo JSON。
    
    Args:
        log_dir: 日志文件所在目录
        verbose: 是否显示详细信息
        
    Returns:
        carInfo JSON字符串，如 {"brand":"1","device_name":"312D"}
        如果未找到则返回默认值 {"brand":"0"}
    """
    server_log_path = os.path.join(log_dir, "Server.log")
    default_car_info = '{"brand":"0"}'
    
    if not os.path.exists(server_log_path):
        if verbose:
            print(f"[WARN] 未找到 Server.log，使用默认 carInfo: {default_car_info}")
        return default_car_info
    
    car_info = default_car_info
    
    try:
        with open(server_log_path, 'r', encoding='utf-8') as f:
            for line in f:
                if "START AIBS SERVER with file" in line:
                    # 提取 carInfo[...] 中的 JSON
                    match = re.search(r'carInfo\[(\{[^]]+\})\]', line)
                    if match:
                        car_info = match.group(1)
        
        if verbose:
            print(f"[INFO] 从 Server.log 解析到 carInfo: {car_info}")
            
    except Exception as e:
        if verbose:
            print(f"[WARN] 解析 Server.log 失败: {e}，使用默认 carInfo: {default_car_info}")
    
    return car_info


def extract_appid_from_filename(filename: str) -> str:
    """从日志文件名中提取appid
    
    文件名格式: com_xxx_yyy_Client.log -> com.xxx.yyy
    
    Args:
        filename: 日志文件名（不含路径）
        
    Returns:
        提取的appid，如 com.autoai.vr.service_vrassistant
    """
    # 去掉 _Client.log 后缀
    base_name = filename.replace("_Client.log", "")
    # 把下划线替换成点（但保留连续部分，如 vr_service_vrassistant -> vr.service_vrassistant）
    # 实际规则：只替换 com_ 开头的部分的下划线
    # com_autoai_vr_service_vrassistant -> com.autoai.vr.service_vrassistant
    # 简化处理：把所有下划线替换成点
    appid = base_name.replace("_", ".").replace("service.vrassistant", "service_vrassistant")
    return appid


def find_client_logs(log_dir: str, verbose: bool = False) -> Dict[str, Tuple[str, str]]:
    """在指定目录下自动查找客户端日志文件
    
    支持的客户端日志文件:
        - TSA: com_autoai_vr_service*_Client.log
        - SET: com_iauto_systemsetting*_Client.log
        - VOI: com_toyota_cn_agentservice*_Client.log
    
    Args:
        log_dir: 日志文件所在目录
        verbose: 是否显示详细信息
        
    Returns:
        文件路径到(客户端类型, appid)的映射 {filepath: (client_type, appid)}
    """
    if not os.path.isdir(log_dir):
        raise ValueError(f"目录不存在: {log_dir}")
    
    # 定义三种客户端的日志文件名模式
    client_patterns = {
        "TSA": "com_autoai_vr_service*_Client.log",
        "SET": "com_iauto_systemsetting*_Client.log",
        "VOI": "com_toyota_cn_agentservice*_Client.log",
    }
    
    # 返回 {文件路径: (客户端类型, appid)} 的映射
    file_client_map = {}
    found_clients = []
    
    for client_type, pattern in client_patterns.items():
        full_pattern = os.path.join(log_dir, pattern)
        matches = glob.glob(full_pattern)
        if matches:
            for f in matches:
                appid = extract_appid_from_filename(os.path.basename(f))
                file_client_map[f] = (client_type, appid)
            if client_type not in found_clients:
                found_clients.append(client_type)
            if verbose:
                for f in matches:
                    appid = extract_appid_from_filename(os.path.basename(f))
                    print(f"[INFO] 找到 {client_type} 日志: {os.path.basename(f)} (appid: {appid})")
    
    if not file_client_map:
        raise FileNotFoundError(
            f"在目录 {log_dir} 中未找到客户端日志文件\n"
            f"支持的文件名模式:\n"
            f"  - TSA: com_autoai_vr_service*_Client.log\n"
            f"  - SET: com_iauto_systemsetting*_Client.log\n"
            f"  - VOI: com_toyota_cn_agentservice*_Client.log"
        )
    
    if verbose:
        print(f"[INFO] 共找到 {len(file_client_map)} 个日志文件，客户端类型: {', '.join(found_clients)}")
    
    return file_client_map


def merge_logs(file_client_map: Dict[str, Tuple[str, str]], verbose: bool = False) -> Tuple[List[LogEntry], Dict[str, str]]:
    """合并多个日志文件，返回合并后的条目和客户端类型到appid的映射
    
    Args:
        file_client_map: 文件路径到(客户端类型, appid)的映射 {filepath: (client_type, appid)}
        verbose: 是否显示详细信息
        
    Returns:
        tuple: (合并后的日志条目列表, 客户端类型到appid的映射 {client_type: appid})
    """
    all_entries = []
    # 客户端类型到appid的映射
    client_appid_map = {}
    
    for filepath, (client_type, appid) in file_client_map.items():
        parser = LogParser(verbose=verbose)
        # 使用 force_client_type 强制指定客户端类型，避免依赖日志内容检测
        entries = parser.parse_file(filepath, force_client_type=client_type)
        
        # 记录客户端类型和appid的映射（如果同类型有多个文件，使用第一个）
        if client_type not in client_appid_map:
            client_appid_map[client_type] = appid
            
        all_entries.extend(entries)
        
        if verbose:
            print(f"[INFO] 文件 {os.path.basename(filepath)} -> 客户端类型: {client_type}, appid: {appid}, 条目数: {len(entries)}")
        
    # 按时间戳排序 - 这是关键，确保两个日志的时序正确合并
    all_entries.sort(key=lambda x: x.timestamp)
    
    if verbose:
        print(f"[INFO] 合并完成，总条目数: {len(all_entries)}")
        print(f"[INFO] 涉及的客户端类型: {list(client_appid_map.keys())}")
    
    return all_entries, client_appid_map


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='AIBS日志转MGO时序文件转换器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
    # 指定日志目录，自动查找TSA/SET/VOI客户端日志
    python3 log2mgo_converter.py ./实机log -o result.mgo
    
    # 显示详细信息（时间戳和注释）
    python3 log2mgo_converter.py ./实机log -v
        '''
    )
    
    parser.add_argument('log_dir', help='日志文件所在目录，自动查找*_Client.log文件')
    parser.add_argument('-o', '--output', help='输出的mgo文件路径（默认: <log_dir>/output.mgo）')
    parser.add_argument('-v', '--verbose', action='store_true', help='显示详细信息（包含时间戳和注释）')
    
    args = parser.parse_args()
    
    try:
        # 自动查找日志文件，返回 {文件路径: (客户端类型, appid)} 映射
        file_client_map = find_client_logs(args.log_dir, verbose=args.verbose)
        
        # 从 Server.log 解析 carInfo
        car_info = parse_server_log(args.log_dir, verbose=args.verbose)
        
        # 设置默认输出路径
        output_path = args.output or os.path.join(args.log_dir, "output.mgo")
        
        print(f"[INFO] 合并 {len(file_client_map)} 个日志文件...")
        
        # 合并日志 - 使用文件名确定的客户端类型和appid
        all_entries, client_appid_map = merge_logs(file_client_map, verbose=args.verbose)
        
        # 使用第一个文件的客户端类型作为默认
        first_client_type, _ = list(file_client_map.values())[0] if file_client_map else ("TSA", "")
        
        # 转换 - 每个条目会使用其自身的client_type
        converter = MgoConverter(
            client_type=first_client_type,
            with_callbacks=False,
            verbose=args.verbose
        )
        commands = converter.convert(all_entries)
        
        # 写入MGO文件 - 传入客户端appid映射和carInfo
        writer = MgoWriter(client_type=first_client_type, client_appid_map=client_appid_map, car_info=car_info)
        writer.write(
            commands,
            output_path,
            verbose=args.verbose
        )
        
        print(f"[SUCCESS] 转换完成！输出文件: {output_path}")
        print(f"[INFO] 共生成 {len(commands)} 条MGO指令")
        client_types = list(client_appid_map.keys())
        if len(client_types) > 1:
            print(f"[INFO] 涉及客户端: {', '.join(client_types)}")
        
    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] 转换失败: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
