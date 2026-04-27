#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2026/01/20
# @Author  : baihuidong
# @File    : CarPlayClient.py
# @Software: PyCharm
# @Mail    : baihuidong@pachiratech.com
"""
CarPlay SDK 客户端封装

封装 libCarPlay_SDK.so 动态库，提供CarPlay相关功能：
- 唤醒词检测 (Wakeup)
- VAD状态检测 (Voice Activity Detection)
- 音频数据回调 (Audio Data)
- CarPlay状态回调 (Status Callback)

使用示例 (DSL):
    [CPL]CREATE 16000 16 1 cmn {CARPLAY_CONFIG}
    [CPL]STATUS 0
    [CPL]FREE
"""
import os
import json
import threading
from ctypes import *
from loguru import logger
from src.utils.common import wait_gdb_attach
from src.utils.common import get_timestamp
from src.testsuite.NANO.dsl_engine import DSLCommand, Status


# ================== CarPlay 模式常量 ==================
class CarPlayMode:
    """CarPlay 工作模式"""
    NONE_TYPE = 0           # 无模式
    WAKEUP_DATA_TYPE = 1    # 唤醒词数据模式
    VAD_INFO_DATA_TYPE = 2  # VAD信息模式
    AUDIO_DATA_TYPE = 3     # 音频数据模式


# ================== 回调函数类型定义 ==================
# 唤醒词回调: (text: char*, time_stamp: long, duration: int) -> void
WAKEUP_CALLBACK = CFUNCTYPE(None, c_char_p, c_long, c_int)

# VAD状态回调: (time_stamp: long, state: int) -> void
VAD_CALLBACK = CFUNCTYPE(None, c_long, c_int)

# 音频数据回调: (data: char*, length: int, channelNum: int, time_stamp: long) -> void
AUDIO_CALLBACK = CFUNCTYPE(None, POINTER(c_char), c_int, c_int, c_long)

# CarPlay状态回调: (code: int, text: char*) -> void
CARPLAY_CALLBACK = CFUNCTYPE(None, c_int, c_char_p)


# ================== 回调结构体定义 ==================
class ESIRIHookST(Structure):
    """CarPlay SDK 回调钩子结构体"""
    _fields_ = [
        ("carplay_wakeup_info", WAKEUP_CALLBACK),   # 唤醒词信息回调
        ("carplay_vad_info", VAD_CALLBACK),         # VAD信息回调
        ("carplay_data", AUDIO_CALLBACK),           # 音频数据回调
        ("carplay_callback", CARPLAY_CALLBACK)      # CarPlay状态回调
    ]


class CarPlayClient:
    """
    CarPlay SDK 客户端封装
    
    职责：
    1. 加载和管理 libCarPlay_SDK.so 动态库
    2. 提供CarPlay引擎的创建、状态设置、销毁等接口
    3. 处理各类回调（唤醒词、VAD、音频、状态）
    
    回调数据格式：
    - CarPlayWakeup: {"type": "CarPlayWakeup", "text": "唤醒词", "kadStart": 时间戳, "kadEnd": 时间戳, "duration": 时长}
    - CarPlayVad: {"type": "CarPlayVad", "vadStart": 时间戳, "vadEnd": 时间戳, "state": 状态}
    - CarPlayAudio: {"type": "CarPlayAudio", "length": 长度, "channelNum": 通道数, "timestamp": 时间戳}
    - CarPlayStatus: {"type": "CarPlayStatus", "code": 状态码, "text": 描述}
    """

    def __init__(self, client_name: str, lib_path: str):
        """
        初始化CarPlay客户端
        
        Args:
            client_name: 客户端名称（如 "CPL"）
            lib_path: 动态库所在目录
        """
        self.client_name = client_name
        self.lib_path = os.path.join(lib_path, "libCarplay_SDK.so")
        
        # 检查动态库是否存在
        if not os.path.exists(self.lib_path):
            raise FileNotFoundError(f"libCarPlay_SDK.so 不存在: {self.lib_path}")
        
        # 动态库和引擎句柄
        self.m_library = None
        self.m_engine = None
        
        # 回调结构体和函数指针（需要保持引用，防止GC回收）
        self.hooks = None
        self._wakeup_callback = None
        self._vad_callback = None
        self._audio_callback = None
        self._carplay_callback = None
        
        # 外部回调处理函数
        self.m_callback = None
        
        # VAD状态跟踪
        self._vad_start_time = 0
        
        # 音频输出文件句柄（可选，用于保存CarPlay回传的音频）
        self.audio_output_file = None
        
        # 线程锁
        self.m_lock = threading.Lock()
        
        # 加载动态库
        self._load_library()
        
        logger.info(f"[{self.client_name}] CarPlay客户端初始化完成")

    def _load_library(self):
        """加载动态库"""
        try:
            self.m_library = cdll.LoadLibrary(self.lib_path)
            logger.debug(f"[{self.client_name}] 加载动态库成功: {self.lib_path}")

            # 如果GDB模式，则等待GDB attach
            if os.environ.get("GDB_OPTION") == "1":
                wait_gdb_attach(self.client_name, os.getpid())

        except Exception as e:
            logger.error(f"[{self.client_name}] 加载动态库失败: {e}")
            raise

    def set_callback(self, callback_func):
        """
        设置外部回调处理函数
        
        Args:
            callback_func: 回调函数，签名为 callback(client_name, callback_type, callback_data)
        """
        self.m_callback = callback_func

    def _invoke_callback(self, callback_type: str, callback_data: dict):
        """
        调用外部回调函数
        
        Args:
            callback_type: 回调类型（如 CarPlayWakeup, CarPlayVad 等）
            callback_data: 回调数据字典
        """
        if self.m_callback:
            try:
                self.m_callback(self.client_name, callback_type, callback_data)
            except Exception as e:
                logger.error(f"[{self.client_name}] 回调处理异常: {e}")

    # ================== 内部回调函数 ==================

    def _on_wakeup(self, text, time_stamp, duration):
        """
        唤醒词检测回调
        
        Args:
            text: 唤醒词文本 (bytes)
            time_stamp: 时间戳 (ms)
            duration: 持续时长 (ms)
        """
        try:
            text_str = text.decode('utf-8') if text else ""
            kad_start = time_stamp - duration
            kad_end = time_stamp
            
            logger.info(f"[{self.client_name}][Wakeup] text={text_str}, kadStart={kad_start}, kadEnd={kad_end}, duration={duration}")
            
            callback_data = {
                "type": "CarPlayWakeup",
                "text": text_str,
                "kadStart": kad_start,
                "kadEnd": kad_end,
                "duration": duration,
                "timestamp": get_timestamp()
            }
            
            # 设置CarPlay唤醒状态为1，表示唤醒词检测开始
            self._invoke_set_carplay_status(1)
            self._invoke_callback("CarPlayWakeup", callback_data)
            
        except Exception as e:
            logger.error(f"[{self.client_name}] 唤醒词回调处理异常: {e}")

    def _on_vad(self, time_stamp, state):
        """
        VAD状态回调
        
        Args:
            time_stamp: 时间戳 (ms)
            state: VAD状态 (0=开始, 1=结束)
        """
        try:
            state_str = "开始" if state == 0 else "结束"
            logger.info(f"[{self.client_name}][VAD] state={state}({state_str}), timestamp={time_stamp}")
            
            if state == 0:
                # VAD开始
                callback_data = {
                    "type": "CarPlayVadStart",
                    "state": state,
                    "timestamp": time_stamp
                }
                self._invoke_callback("CarPlayVadStart", callback_data)
            elif state == 1:
                # VAD结束
                callback_data = {
                    "type": "CarPlayVadEnd",
                    "state": state,
                    "timestamp": time_stamp
                }
                # 设置CarPlay唤醒状态为1，表示唤醒词检测开始
                self._invoke_set_carplay_status(1)
                self._invoke_callback("CarPlayVadEnd", callback_data)
            
        except Exception as e:
            logger.error(f"[{self.client_name}] VAD回调处理异常: {e}")

    def _on_audio(self, data, length, channel_num, time_stamp):
        """
        音频数据回调
        
        Args:
            data: 音频数据指针
            length: 数据长度
            channel_num: 通道数
            time_stamp: 时间戳
        """
        try:
            # 如果设置了音频输出文件，写入数据
            if self.audio_output_file and not self.audio_output_file.closed:
                if data and length > 0:
                    audio_bytes = bytes(data[:length])
                    self.audio_output_file.write(audio_bytes)
        
        except Exception as e:
            logger.error(f"[{self.client_name}] 音频回调处理异常: {e}")

    def _on_carplay_status(self, code, text):
        """
        CarPlay状态回调
        
        Args:
            code: 状态码
            text: 状态描述 (bytes)
        """
        try:
            text_str = text.decode('utf-8', errors='replace') if text else ""
            logger.info(f"[{self.client_name}][Status] code={code}, text={text_str}")

            if code == 0:
                # CarPlay连接上之后，设置CarPlay唤醒状态为0
                self._invoke_set_carplay_status(0)

            if text_str and text_str.strip():
                try:
                    data = json.loads(text_str)
                except json.JSONDecodeError:
                    data = {"raw": text_str}
            else:
                data = {}

            callback_data = {
                "type": "CarPlayStatus",
                "code": code,
                "text": data,
                "timestamp": get_timestamp()
            }
            
            self._invoke_callback("CarPlayStatus", callback_data)
            
        except Exception as e:
            logger.error(f"[{self.client_name}] 状态回调处理异常: {e}")

    # ================== DSL指令接口 ==================
    def create(self, command: DSLCommand):
        """
        创建CarPlay引擎
        
        DSL语法: [CPL]CREATE mode lang config_path
        
        参数说明:
            mode: 工作模式（0=无, 1=唤醒词, 2=VAD, 3=音频）
            lang: 语言代码（如 cmn, eng）
        Example:
            [CPL]CREATE 1 cmn
        """
        try:
            # 参数解析
            if len(command.params) < 3:
                command.status = Status.ERROR
                command.message = f"[{self.client_name}] CREATE参数不足，需要至少3个参数: mode lang config_path"
                logger.error(command.message)
                return -1
            
            mode = int(command.params[0])
            lang = command.params[1]
            config_path = command.params[2]
            
            # 检查配置文件
            if not os.path.exists(config_path):
                command.status = Status.ERROR
                command.message = f"[{self.client_name}] 配置文件不存在: {config_path}"
                logger.error(command.message)
                return -1
            
            # 创建回调结构体
            self.hooks = ESIRIHookST()
            # 创建回调函数包装器（必须保持引用）
            self._wakeup_callback = WAKEUP_CALLBACK(self._on_wakeup)
            self._vad_callback = VAD_CALLBACK(self._on_vad)
            self._audio_callback = AUDIO_CALLBACK(self._on_audio)
            self._carplay_callback = CARPLAY_CALLBACK(self._on_carplay_status)
            
            # 设置回调
            self.hooks.carplay_wakeup_info = self._wakeup_callback
            self.hooks.carplay_vad_info = self._vad_callback
            self.hooks.carplay_data = self._audio_callback
            self.hooks.carplay_callback = self._carplay_callback
            
            # 调用C接口创建引擎
            self.m_library.create_carplay_link.restype = c_void_p
            self.m_engine = self.m_library.create_carplay_link(
                c_int(16000),
                c_int(16),
                c_int(mode),
                c_char_p(lang.encode('utf-8')),
                c_char_p(config_path.encode('utf-8')),
                pointer(self.hooks)
            )
            
            if self.m_engine is None:
                command.status = Status.FAILED
                command.return_code = -2
                command.message = f"[{self.client_name}] create_carplay_link 返回 None"
                logger.error(command.message)
                return -2
            
            command.status = Status.PASSED
            command.return_code = 0
            logger.info(f"[{self.client_name}] CarPlay引擎创建成功: mode={mode}, lang={lang}")
            return 0
            
        except Exception as e:
            command.status = Status.ERROR
            command.message = f"[{self.client_name}] CREATE异常: {e}"
            logger.error(command.message)
            return -1

    def _invoke_set_carplay_status(self, status_code: int) -> int:
        """
        设置CarPlay状态
        """
        self.m_library.set_carplay_status.argtypes = [c_void_p, c_int]
        self.m_library.set_carplay_status.restype = c_int
        return self.m_library.set_carplay_status(self.m_engine, c_int(status_code))

    def free(self, command: DSLCommand):
        """
        释放CarPlay引擎资源
        
        DSL语法: [CPL]FREE
        
        Example:
            [CPL]FREE
        """
        try:
            # 关闭音频输出文件
            if self.audio_output_file and not self.audio_output_file.closed:
                self.audio_output_file.close()
                logger.info(f"[{self.client_name}] 音频输出文件已关闭")
            
            if self.m_engine is None:
                command.status = Status.PASSED
                command.return_code = 0
                logger.warning(f"[{self.client_name}] 引擎未创建或已释放")
                return 0
            
            # 调用C接口销毁引擎
            self.m_library.destroy_carplay_link.argtypes = [POINTER(c_void_p)]
            ret = self.m_library.destroy_carplay_link(pointer(c_void_p(self.m_engine)))
            
            # 清理引用
            self.m_engine = None
            self.hooks = None
            self._wakeup_callback = None
            self._vad_callback = None
            self._audio_callback = None
            self._carplay_callback = None
            
            command.return_code = ret
            if ret == 0:
                command.status = Status.PASSED
                logger.info(f"[{self.client_name}] CarPlay引擎已释放")
            else:
                command.status = Status.FAILED
                command.message = f"[{self.client_name}] destroy_carplay_link 返回: {ret}"
                logger.warning(command.message)
            
            return ret
            
        except Exception as e:
            command.status = Status.ERROR
            command.message = f"[{self.client_name}] FREE异常: {e}"
            logger.error(command.message)
            return -1
