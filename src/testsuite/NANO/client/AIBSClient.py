#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2025/09/28
# @Author  : baihuidong
# @File    : NANOClient.py
# @Software: PyCharm
# @Mail    : baihuidong@pachiratech.com
import os
import time
import json
import threading
from datetime import datetime
from ctypes import *
from loguru import logger
from src.utils.jsonUtil import JsonUtil
from src.utils.common import is_digit, wait_gdb_attach, timer
from src.utils.common import uuid, get_timestamp, get_environment
from src.core.Status.AIBSSessionStatus import AIBSStatusCode, AIBSVRConfigCode
from src.testsuite.NANO.dsl_engine import DSLCommand, Status
from src.testsuite.NANO.client.AudioDataMixin import AudioDataMixin


# 定义回调结构体
class AIBSResultST(Structure):
    _fields_ = [
        ("flag", c_int),
        ("data", c_char_p),
        ("type", POINTER(c_char) * 128),
    ]


class AIBSClient(AudioDataMixin):
    """AIBS客户端封装"""
    # 类变量：所有实例共享的时间戳和音频进度
    _shared_lock = threading.Lock()  # 类级别的锁，用于保护共享变量
    m_timestamp = None  # 共享时间戳
    audio_progress = 0  # 共享音频进度
    audio_path = "NULL" # 音频路径
    abstime = 1         # 共享抽象时间戳
    dirCallbackType = None   # default / internal_event 使用
    dirCallbacketId = None   # etID 使用
    m_switch_lang_finish_event = threading.Event() # 切换语种信号

    def __init__(self, client_name: str, lib_path: str, config=None):
        self.client_name = client_name
        self.lib_path = os.path.join(lib_path, "libAIBSClientDynamic.so")
        if not os.path.exists(self.lib_path):
            raise FileNotFoundError(f"libAIBSClientDynamic.so不存在: {self.lib_path}")
        self.m_library = None
        self.m_engine = None
        self.config = config
        self.m_callback = None
        self.m_ctypes_callback = None  # 保存ctypes回调函数引用，防止GC回收
        self.m_status = 0
        
        # 初始化共享变量（仅在第一次实例化时）
        with AIBSClient._shared_lock:
            if AIBSClient.m_timestamp is None:
                AIBSClient.m_timestamp = get_timestamp()
                AIBSClient.audio_progress = 0
                AIBSClient.audio_path = "NULL"
                AIBSClient.abstime = 1
        
        # 线程同步锁和条件变量
        self.m_lock = threading.Lock()
        self.m_create_cond = threading.Condition(self.m_lock)
        self.m_start_cond = threading.Condition(self.m_lock)
        self.m_finish_cond = threading.Condition(self.m_lock)
        self.m_sreRegister_event = threading.Event()

        # 初始化动态库
        self._load_library()

    def _load_library(self):
        """加载动态库，子类可重写以添加特定逻辑"""
        try:
            self.m_library = cdll.LoadLibrary(self.lib_path)
            
            # 如果GDB模式，则等待GDB attach
            if os.environ.get("GDB_OPTION") == "1":
                wait_gdb_attach(self.client_name, os.getpid())
                
        except Exception as e:
            logger.error(f"[{self.client_name}] 加载库失败: {e}")
            raise

    def set_callback(self, callback_func):
        """设置外部回调函数"""
        self.m_callback = callback_func

    def _get_timeout(self, default_timeout: int):
        """获取超时时间，支持GDB模式下的无限等待"""
        try:
            return None if os.environ.get("GDB_OPTION") == "1" else default_timeout
        except:
            return default_timeout

    def _process_vr_config_value(self, config_name: str, value):
        """处理VR配置值，根据配置类型进行相应的数据转换"""
        try:
            if config_name in ['SRE_MEMORY', 'VEHICLE_MEMORY']:
                return str(int(value))

            # 简单数值类型配置
            if config_name in ['VR_OPTION', 'SHOW_STYLE', 'DIALOGUE_STYLE', 'SOUND_AREA_OPTION', 
                              'WAKEUP_KEYWORD_OPTION', 'VOICE_WAKEUP_OPTION', 'MULTI_DIALOGUE',
                              'EXPERIENCE_IMPROVENMENT', 'PERSONAL_SENSITIVE_AUTHORIZATION',
                              'VOICE_SENSITIVE_AUTHORIZATION', 'SRE_SENSITIVE_EMPOWER_OPTION',
                              'SRE_FUNC_ENABLE_OPTION', 'GPT_ENABLE_OPTION']:
                return int(value)
            
            # 语言配置 - 需要构建复杂的JSON结构
            elif config_name == 'DIALOGUE_LANGUAGE':
                # 简化语法：DIALOGUE_LANGUAGE cmn 或 DIALOGUE_LANGUAGE cmn,eng
                if isinstance(value, str):
                    langs = value.split(',')
                    # 唤醒默认是cmn和eng同时存在
                    return {"wakeup": ["cmn", "eng"], "asr": langs}
                return value
            
            # 唤醒词别名配置
            elif config_name == 'WAKEUP_ALIAS':
                # 简化语法：WAKEUP_ALIAS 你好小白 cmn 或 WAKEUP_ALIAS 你好小白
                if isinstance(value, str):
                    parts = value.split()
                    if len(parts) >= 2:
                        # 有语种参数：WAKEUP_ALIAS 你好小白 cmn
                        wakeup_word = ' '.join(parts[:-1])  # 支持多词唤醒词
                        language = parts[-1]
                        return {"language": [language], "name": wakeup_word, "level": 3}
                    else:
                        # 没有语种参数，使用默认cmn：WAKEUP_ALIAS 你好小白
                        return {"language": ["cmn"], "name": value, "level": 3}
                return value
            
            # 唤醒词使能配置
            elif config_name == 'WAKEUP_ENABLE':
                # 简化语法：WAKEUP_ENABLE 你好丰田 cmn 或 WAKEUP_ENABLE 你好丰田
                if isinstance(value, str):
                    parts = value.split()
                    if len(parts) >= 2:
                        # 有语种参数：WAKEUP_ENABLE 你好丰田 cmn
                        wakeup_word = ' '.join(parts[:-1])  # 支持多词唤醒词
                        language = parts[-1]
                        return {"language": [language], "name": wakeup_word, "enable": 1}
                    else:
                        # 没有语种参数，使用默认cmn：WAKEUP_ENABLE 你好丰田
                        return {"language": ["cmn"], "name": value, "enable": 1}
                return value
            
            # 字符串类型配置
            elif config_name in ['SET_TTS_VOICE_TYPE', 'SERVER_CACHE_LANGUAGE']:
                return str(value)
            
            # 默认返回原值
            else:
                return value
                
        except Exception as e:
            logger.error(f"处理VR配置值异常: {config_name}={value}, 错误: {e}")
            return value

    def _callback_wrapper(self, status, result):
        """回调函数包装器"""
        try:
            if status == AIBSStatusCode.STATUS_AIBS_AUDIO_ENERGY:
                return 0

            _data = result[0].data.decode(encoding="utf-8", errors='ignore')
            if not _data:
                return 0

            _type = create_string_buffer(128)
            memmove(_type, result[0].type, 128)
            callback_data = json.loads(_data)
            callback_type = JsonUtil.parse(callback_data, 'type')

            # 处理不同状态的回调
            if status == AIBSStatusCode.STATUS_AIBS_VR_CLOSED and callback_type == "VRClosed":
                with self.m_lock:
                    self.m_start_cond.notify()

            elif status in [AIBSStatusCode.STATUS_AIBS_INIT_SUCCESS, AIBSStatusCode.STATUS_AIBS_INIT_FAILED]:
                with self.m_lock:
                    self.m_status = status
                    self.m_create_cond.notify()

            elif status in [AIBSStatusCode.STATUS_AIBS_SESSION_START_SUCCESS, AIBSStatusCode.STATUS_AIBS_SESSION_START_FAILED]:
                with self.m_lock:
                    self.m_status = status
                    self.m_start_cond.notify()
                
            # elif status == AIBSStatusCode.STATUS_AIBS_EVENT and callback_type in ["FreetalkStart", "FreetalkStop"]:
            #     with self.m_lock:
            #         self.m_freeWakeup_cond.notify()
            
            elif status in [AIBSStatusCode.STATUS_AIBS_SESSION_FINISH] and callback_type == "LCSFinish":
                with self.m_lock:
                    self.m_status = status
                    self.m_finish_cond.notify()
                
            elif callback_type == "VoiceInput-SilenceTimeout":
                self.m_library.aibs_close_voice_input(self.m_engine)
                
            elif callback_type == "startEnroll":
                self.m_sreRegister_event.set()

            elif callback_type == "SwitchLangFinish":
                self.__class__.m_switch_lang_finish_event.set()

            elif callback_type == "NLPResult":
                cls = self.__class__
                callback_type = JsonUtil.parse(callback_data, 'data.directives.0.callback.type')
                if callback_type not in ["None", None, ""]:
                    cls.dirCallbackType = callback_type
                    cls.dirCallbacketId = JsonUtil.parse(callback_data, 'data.directives.0.callback.etId')

                # 解析NLPResult中的vr字段，按workMode自动补发TSAStatus事件
                vr_data = JsonUtil.parse(callback_data, 'data.vr')
                if isinstance(vr_data, dict):
                    work_mode = str(vr_data.get("workMode", "")).strip()
                    channel_status = str(vr_data.get("channelStatus", "")).strip().lower()
                    wakeup_channels = []

                    if channel_status == "all":
                        wakeup_channels = [0, 1, 2, 3, 4, 5]
                    elif channel_status == "part":
                        channels = vr_data.get("channels", [])
                        if isinstance(channels, list):
                            for channel in channels:
                                channel_id = JsonUtil.parse(channel, 'channelId')
                                try:
                                    wakeup_channels.append(int(channel_id))
                                except (TypeError, ValueError):
                                    continue

                    if work_mode == "MODE_WAKEUP" and wakeup_channels:
                        self.internal_event({
                            "source": "TSA",
                            "type": "TSAStatus",
                            "data": {"status": "ON_SLEEP", "wakeupChannels": wakeup_channels}
                        })
                    elif work_mode == "MODE_VR" and wakeup_channels:
                        self.internal_event({
                            "source": "TSA",
                            "type": "TSAStatus",
                            "data": {"status": "ON_WAKEUP", "wakeupChannels": wakeup_channels}
                        })

            # 调用外部回调函数 - 增加线程安全保护
            callback_func = self.m_callback  # 保存当前回调函数引用
            if callback_func:
                try:
                    callback_data['audiotime'] = str(round(AIBSClient.audio_progress/1000, 2))
                    callback_data['audio'] = AIBSClient.audio_path
                    callback_func(self.client_name, status, callback_data)
                except Exception as callback_error:
                    logger.error(f"[{self.client_name}] 外部回调函数异常: {callback_error}")

            return 0

        except Exception as e:
            logger.error(f"[{self.client_name}] 回调异常: {e}")
            return -1

    def reset(self):
        """重置状态（重置所有实例共享的时间戳和音频进度）"""
        with AIBSClient._shared_lock:
            AIBSClient.m_timestamp = get_timestamp()
            AIBSClient.audio_progress = 0
            AIBSClient.audio_path = "NULL"
            AIBSClient.abstime = 1
            cls = self.__class__
            cls.dirCallbackType = None
            cls.dirCallbacketId = None

    def create(self, command: DSLCommand) -> int:
        """
        CREATE接口 - 创建AIBS引擎
        DSL格式: [TSA]CREATE lang appid [config]
        
        Args:
            command: DSL指令对象，params=[lang, appid, config]
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            # 在create之前先创建一个车参的log
            self._invoke_set_vehicle_info(True)
            # 🎯 参数解析
            if len(command.params) < 3:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] CREATE参数不足: {command.params}'
                return -1
            
            lang = command.params[0]
            appid = command.params[1]
            config = command.params[2]
            
            # 检查引擎是否已经创建，避免重复创建导致回调函数失效
            if self.m_engine is not None:
                logger.info(f"[{self.client_name}] 引擎已存在，直接返回成功")
                command.return_code = 0
                command.status = Status.PASSED
                return 0

            # 定义回调函数类型
            aibs_callback_t = CFUNCTYPE(c_int, c_int, POINTER(AIBSResultST))

            # 设置函数参数类型
            self.m_library.aibs_create_engine.argtypes = [aibs_callback_t, c_void_p, c_char_p, c_char_p, c_char_p]
            self.m_library.aibs_create_engine.restype = c_void_p

            # 创建ctypes回调函数并保存引用（只在首次创建时）
            if self.m_ctypes_callback is None:
                self.m_ctypes_callback = aibs_callback_t(self._callback_wrapper)

            # 创建引擎
            self.m_engine = self.m_library.aibs_create_engine(
                self.m_ctypes_callback, None,
                config.encode('utf-8'),
                lang.encode('utf-8'),
                appid.encode('utf-8')
            )

            if self.m_engine is None:
                logger.error(f"[{self.client_name}] CREATE失败: engine为空")
                command.return_code = -1
                command.status = Status.FAILED
                return -1
            
            # 如果客户端不是TSA，则直接返回成功
            if self.client_name != "TSA":
                command.return_code = 0
                command.status = Status.PASSED
                return 0

            # 等待初始化完成
            with self.m_lock:
                self.m_create_cond.wait(timeout=self._get_timeout(30))
                if self.m_status == AIBSStatusCode.STATUS_AIBS_INIT_SUCCESS:
                    # 设置初始车参
                    self._invoke_set_vehicle_info()
                    # 设置默认工作模式为2
                    self.m_library.aibs_set_workmode(self.m_engine, c_int(2))
                    command.return_code = 0
                    command.status = Status.PASSED
                    return 0
                else:
                    logger.error(f"[{self.client_name}] CREATE失败: status={self.m_status}")
                    command.return_code = -1
                    command.status = Status.FAILED
                    return -1

        except Exception as e:
            logger.error(f"[{self.client_name}] CREATE异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] CREATE异常: {e}'
            return -1

    def start(self, command: DSLCommand) -> int:
        """
        START接口 - 启动会话
        DSL格式: [TSA]START [channel_num]
        
        Args:
            command: DSL指令对象，params=[channel_num]（可选，默认为1）
        
        Returns:
            0: 成功, 其他: 失败
        """
        try:
            # 🎯 参数解析
            channel_num = int(command.params[0]) if command.params else 1
            
            logger.info(f"[{self.client_name}] START: channel_num={channel_num}")
            self.reset()

            with self.m_lock:
                ret = self.m_library.aibs_start_engine(self.m_engine, channel_num, None)
                self.m_start_cond.wait(timeout=self._get_timeout(10))

                if ret == 0:
                    logger.info(f"[{self.client_name}] START成功")
                    self._invoke_set_vehicle_info()

                    if self.client_name == "TSA" and self.config.mango_mini_dialogue == "true":
                        self.internal_event({"source": "TSA", "type": "ImmersionModeSwitch", "data": {"immersionMode": True}})
                        self.m_library.aibs_set_vr_config(self.m_engine, AIBSVRConfigCode.AIBS_SETTING_SHOW_STYLE, byref(c_uint(2)))

                    # 🎯 设置命令状态
                    command.return_code = 0
                    command.status = Status.PASSED
                    return 0
                else:
                    logger.error(f"[{self.client_name}] START失败: ret={ret}")
                    command.return_code = ret
                    command.status = Status.FAILED
                    return ret

        except Exception as e:
            logger.error(f"[{self.client_name}] START异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] START异常: {e}'
            return -1
    
    def _invoke_set_vehicle_info(self, is_create: bool = False) -> int:
        """
        设置车辆信息
        """
        try:
            car_type = json.loads(self.config.car_type)
            brand_id = car_type.get("brand", "0")
            device_name = car_type.get("device_name", "410D")
            model_name = self.config.model_name
            brand_map = {
                "0": "Lexus",
                "1": "FAW-Toyota",
                "2": "GAC-Toyota",
            }
            brand = brand_map.get(brand_id, "Lexus")

            product_type_map = {
                "0": 0,
                "p": 1,
                "T1": 2,
                "T2": 3,
            }
            productType = product_type_map.get(model_name, 4)
            deviceID = {
                "source": "TSA",
                "type": "VehicleInfo",
                "et_id": uuid(),
                "mts": get_timestamp(),
                "deadline": -1,
                "data": {
                    "vin": uuid("Mongo"),
                    "productType": productType,
                    "brand": brand,
                    "model": device_name,
                    "originImei": "",
                    "imei": "",
                    "mmVersion": "",
                    "tsaVersion": "Mongo3.7.0",
                    "segmentId": 20000014
                }
            }
            car_info = {"VehicleInfo": deviceID}
            if is_create:
                with open(os.path.join(self.config.log_path, "context.log"), "w") as f:
                    f.write(json.dumps(car_info, ensure_ascii=False, separators=(',', ':')))
                return 0
            return self.internal_vr_event(deviceID)
        except Exception as e:
            logger.error(f"[{self.client_name}] _invoke_set_vehicle_info异常: {e}")

    def stop(self, command: DSLCommand) -> int:
        """
        STOP接口 - 停止会话
        DSL格式: [TSA]STOP
        
        Args:
            command: DSL指令对象，无参数
        
        Returns:
            0: 成功, 其他: 失败
        """
        try:
            logger.info(f"[{self.client_name}] STOP")

            with self.m_lock:
                ret = self.m_library.aibs_stop_engine(self.m_engine)
                self.m_finish_cond.wait(timeout=self._get_timeout(10))

                if ret == 0:
                    logger.info(f"[{self.client_name}] STOP成功")
                else:
                    logger.error(f"[{self.client_name}] STOP失败: ret={ret}")

                # 🎯 设置命令状态
                command.return_code = ret
                command.status = Status.PASSED if ret == 0 else Status.FAILED
                return ret

        except Exception as e:
            logger.error(f"[{self.client_name}] STOP异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] STOP异常: {e}'
            return -1

    def free(self, command: DSLCommand) -> int:
        """
        FREE接口 - 释放资源
        DSL格式: [TSA]FREE
        
        Args:
            command: DSL指令对象，无参数
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            if self.m_engine:
                logger.info(f"[{self.client_name}] FREE")
                ret = self.m_library.aibs_free_engine(self.m_engine)
                
                # 重置引擎和回调函数引用，允许下次重新创建
                self.m_engine = None
                self.m_ctypes_callback = None
                self.m_status = 0
                
                if ret == 0:
                    logger.info(f"[{self.client_name}] FREE成功")
                else:
                    logger.error(f"[{self.client_name}] FREE失败: ret={ret}")

                # 🎯 设置命令状态
                command.return_code = ret
                command.status = Status.PASSED if ret == 0 else Status.FAILED
                return ret
            
            # 引擎不存在，直接返回成功
            command.return_code = 0
            command.status = Status.PASSED
            return 0

        except Exception as e:
            logger.error(f"[{self.client_name}] FREE异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] FREE异常: {e}'
            return -1

    def event(self, command: DSLCommand) -> int:
        """发送事件"""
        try:
            if not command.params:
                command.status = Status.ERROR
                command.message = f'[Running Error][{self.client_name}] EVENT指令缺少事件数据, command: {command}'
                return

            event_param = command.params[0]
            event_data = None
            
            # 判断参数是文件路径还是JSON字符串
            if event_param.endswith('.json') and os.path.exists(event_param):
                try:
                    with open(event_param, 'r', encoding='utf-8') as f:
                        event_data = json.load(f)
                except Exception as e:
                    raise IOError(f"[{self.client_name}] 读取或解析JSON文件失败: {event_param}, 错误: {e}")
            else:
                try:
                    event_data = json.loads(event_param)
                except json.JSONDecodeError as e:
                    raise ValueError(f"[{self.client_name}] 解析JSON字符串失败: {e}, 字符串: {event_param}")

            ret = self.internal_event(event_data)

            command.return_code = ret
            command.status = Status.PASSED

        except Exception as e:
            logger.error(f"[{self.client_name}] SendEvent异常: {e}, command: {command}")
            command.status = Status.ERROR
            command.message = f'[Running Error][{self.client_name}] SendEvent异常: {e}, command: {command}'

    def internal_event(self, event_data: dict) -> int:
        """
        原始的event接口, 对应aibs_set_event
        """
        try:
            event_type = str(event_data.get("type", ""))
            cls = self.__class__
            if "DIRCallback" not in event_type:
                resolved_et_id = uuid()
            elif cls.dirCallbackType == event_type:
                resolved_et_id = cls.dirCallbacketId
                cls.dirCallbackType = None
                cls.dirCallbacketId = None
            else:
                resolved_et_id = uuid()

            event_data.update({
                "et_id": resolved_et_id,
                "mts": get_timestamp()
            })

            json_data = json.dumps(event_data, ensure_ascii=False, separators=(',', ':'))
            ret = self.m_library.aibs_set_event(self.m_engine, json_data.encode('utf-8'))

            if ret != 0:
                logger.error(f"[{self.client_name}] EVENT失败: ret={ret}")

            return ret
        except Exception as e:
            logger.error(f"[{self.client_name}] EVENT异常: {e}")
            return -1
        
    def internal_vr_event(self, event_data: dict, et_id: str = None) -> int:
        """
        原始的event接口, 对应aibs_set_event
        """
        try:
            # 添加时间戳和事件ID
            event_data.update({
                "et_id": et_id if et_id else uuid(),
                "mts": get_timestamp()
            })

            json_data = json.dumps(event_data, ensure_ascii=False, separators=(',', ':'))
            ret = self.m_library.aibs_set_vr_event(self.m_engine, json_data.encode('utf-8'))

            if ret != 0:
                logger.error(f"[{self.client_name}] EVENT失败: ret={ret}")

            return ret
        except Exception as e:
            logger.error(f"[{self.client_name}] EVENT异常: {e}")
            return -1

    def _process_pcm_chunk(self, data_chunk: bytes, delta_ms: int):
        """
        发送单包PCM数据并推进AIBS共享时间戳
        """
        with AIBSClient._shared_lock:
            current_timestamp = AIBSClient.m_timestamp if AIBSClient.abstime == 1 else AIBSClient.audio_progress
            self.m_library.aibs_process_data(
                self.m_engine,
                data_chunk,
                len(data_chunk),
                c_ulong(current_timestamp)
            )

            AIBSClient.audio_progress += delta_ms
            AIBSClient.m_timestamp += delta_ms

    def data(self, command: DSLCommand) -> int:
        """
        DATA接口 - 处理音频数据
        DSL格式: [TSA]DATA audio_path [frame=320] [delay=0.0] [range=[0,-1]]
        
        Args:
            command: DSL指令对象，params=[audio_path, frame=320, delay=0.0, range=[0,-1]]
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            # 🎯 参数解析
            if not command.params:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] DATA指令缺少音频文件路径'
                return -1
            
            # 解析参数（支持命名参数）
            audio_path = command.params[0]
            frame_size = 320
            delay = 0.0
            audio_range = [0, -1]
            
            # 解析命名参数
            for param in command.params[1:]:
                if '=' in param:
                    key, value = param.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    if key == 'frame':
                        frame_size = int(value)
                    elif key == 'delay':
                        delay = float(value)
                    elif key == 'abstime':
                        AIBSClient.abstime = int(value)
                    elif key == 'range':
                        if value.startswith('[') and value.endswith(']'):
                            range_str = value[1:-1]
                            parts = range_str.split(',')
                            if len(parts) == 2:
                                start = float(parts[0].strip())
                                end = float(parts[1].strip()) if parts[1].strip() != '-1' else -1
                                audio_range = [start, end]
            
            # 🎯 执行逻辑
            logger.info(f"[{self.client_name}] DATA: {audio_path}, frame={frame_size}, range={audio_range}, delay={delay}")
            AIBSClient.audio_path = audio_path

            if not os.path.exists(audio_path):
                logger.error(f"[{self.client_name}] 音频文件不存在: {audio_path}")
                command.return_code = -1
                command.status = Status.FAILED
                return -1

            # 计算音频时间范围
            start_time = audio_range[0] if len(audio_range) > 0 else 0
            end_time = audio_range[1] if len(audio_range) > 1 else -1

            # 1) 识别音频类型并读取原始PCM
            pcm_data, meta = self._load_pcm_and_meta(audio_path, frame_size)
            channels = meta["channels"]
            sample_width = meta["sample_width"]
            sample_rate = meta["sample_rate"]
            block_align = meta["block_align"]

            # 2) 按start_time/end_time精确切片
            sliced_pcm, start_frame_idx, end_frame_idx = self._slice_pcm_by_time(
                pcm_data=pcm_data,
                sample_rate=sample_rate,
                block_align=block_align,
                start_time=start_time,
                end_time=end_time
            )

            logger.info(
                f"[{self.client_name}] DATA音频信息: type={meta['audio_type']}, rate={sample_rate}, "
                f"channels={channels}, sampwidth={sample_width}, block_align={block_align}, "
                f"start_frame={start_frame_idx}, end_frame={end_frame_idx}, bytes={len(sliced_pcm)}"
            )

            # 连续多条 DATA 时：起点取 max(墙钟, 上一段发包结束时刻)，避免快发音频时时间轴压回墙钟导致与上一段重叠
            with AIBSClient._shared_lock:
                wall = get_timestamp()
                stream_end = AIBSClient.m_timestamp
                AIBSClient.m_timestamp = max(wall, stream_end)
                os.environ["AUDIO_BASE_TIMESTAMP"] = str(AIBSClient.m_timestamp)

            # 3) 分包发送切片后的PCM数据
            self._send_pcm_chunks(
                pcm_data=sliced_pcm,
                frame_size=frame_size,
                block_align=block_align,
                sample_rate=sample_rate,
                delay=delay
            )

            logger.info(f"[{self.client_name}] DATA处理完成")
            
            # 🎯 设置命令状态
            command.return_code = 0
            command.status = Status.PASSED
            return 0

        except Exception as e:
            logger.error(f"[{self.client_name}] DATA异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] DATA异常: {e}'
            return -1

    def cancel(self, command: DSLCommand) -> int:
        """
        CANCEL接口 - 取消会话
        DSL格式: [TSA]CANCEL
        
        Args:
            command: DSL指令对象，无参数
        
        Returns:
            0: 成功, 其他: 失败
        """
        try:
            logger.info(f"[{self.client_name}] CANCEL")
            ret = self.m_library.aibs_cancel_engine(self.m_engine, c_int(0))

            if ret == 0:
                logger.info(f"[{self.client_name}] CANCEL成功")
            else:
                logger.error(f"[{self.client_name}] CANCEL失败: ret={ret}")

            # 🎯 设置命令状态
            command.return_code = ret
            command.status = Status.PASSED if ret == 0 else Status.FAILED
            return ret

        except Exception as e:
            logger.error(f"[{self.client_name}] CANCEL异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] CANCEL异常: {e}'
            return -1

    def free_wakeup(self, command: DSLCommand) -> int:
        """
        FREEWAKEUP接口 - 设置自由唤醒状态
        DSL格式: [TSA]FREEWAKEUP status(0/1)
        
        Args:
            command: DSL指令对象，params=[status]
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            # 🎯 参数解析
            if not command.params:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] FREEWAKEUP参数不足'
                return -1
            
            status = int(command.params[0])
            if status not in [0, 1]:
                logger.error(f"[{self.client_name}] FREEWAKEUP参数错误: status={status}")
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] FREEWAKEUP状态无效: {status}'
                return -1

            logger.info(f"[{self.client_name}] FREEWAKEUP: status={status}")

            with self.m_lock:
                # 构建SetFreeWakeup事件数据
                event_data = {
                    "source": "TSA", 
                    "type": "SetFreeWakeup", 
                    "data": {"value": 63, "status": status}
                }
                
                ret = self.internal_event(event_data)
                
                if ret != 0:
                    logger.error(f"[{self.client_name}] FREEWAKEUP事件发送失败: ret={ret}")
                    command.return_code = ret
                    command.status = Status.FAILED
                    return ret

                # 等待回调信号，支持GDB模式
                # self.m_freeWakeup_cond.wait(timeout=self._get_timeout(2))

                # 如果status为1，再设置一个TSAStatus事件
                if status == 1:
                    self.internal_event({"source": "TSA", "type": "TSAStatus", "data": {"status": "ON_WAKEUP", "wakeupChannels": [0, 1, 2, 3, 4, 5]}})
                if status == 0:
                    self.internal_event({"source": "TSA", "type": "TSAStatus", "data": {"status": "ON_SLEEP", "wakeupChannels": []}})

                logger.info(f"[{self.client_name}] FREEWAKEUP成功")
                
                # 🎯 设置命令状态
                command.return_code = 0
                command.status = Status.PASSED
                return 0

        except Exception as e:
            logger.error(f"[{self.client_name}] FREEWAKEUP异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] FREEWAKEUP异常: {e}'
            return -1

    def parallelSR(self, command: DSLCommand) -> int:
        try:
            # 🎯 参数解析
            if not command.params:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] SetParallelSR参数不足'
                return -1

            status = int(command.params[0])
            if status not in [0, 1, 2]:
                logger.error(f"[{self.client_name}] SetParallelSR参数错误: status={status}")
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] SetParallelSR状态无效: {status}'
                return -1

            logger.info(f"[{self.client_name}] SetParallelSR: status={status}")

            # 构建SetParallelSR事件数据
            event_data = {
                "source": "TSA",
                "type": "SetParallelSR",
                "data": {"value": status}
            }

            ret = self.internal_event(event_data)

            if ret != 0:
                logger.error(f"[{self.client_name}] SetParallelSR事件发送失败: ret={ret}")
                command.return_code = ret
                command.status = Status.FAILED
                return ret

            logger.info(f"[{self.client_name}] SetParallelSR成功")

            # 🎯 设置命令状态
            command.return_code = 0
            command.status = Status.PASSED
            return 0

        except Exception as e:
            logger.error(f"[{self.client_name}] SetParallelSR异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] SetParallelSR异常: {e}'
            return -1

    def send_text(self, command: DSLCommand) -> int:
        """
        TEXT送文本接口 - 设置理解文本
        DSL格式: [TSA]TEXT text_content
        
        Args:
            command: DSL指令对象，params=[text]
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            # 🎯 参数解析
            if not command.params:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] TEXT参数不足'
                return -1
            
            text = command.params[0]
            
            logger.info(f"[{self.client_name}] SEND TEXT: {text}")

            with self.m_lock:
                # 构建TEXT事件数据
                event_data = {
                    "source": "TSA", 
                    "type": "TextRequest", 
                    "data": {"text": str(text).strip()}
                }

                # 在设置TextRequest之前，先设置TSAStatus事件
                self.internal_event({"source": "TSA", "type": "TSAStatus", "data": {"status": "ON_WAKEUP", "wakeupChannels": [0, 1, 2, 3]}})
                ret = self.internal_event(event_data)
                
                if ret != 0:
                    logger.error(f"[{self.client_name}] TEXT事件发送失败: ret={ret}")
                    command.return_code = ret
                    command.status = Status.FAILED
                    return ret
                
                logger.info(f"[{self.client_name}] SEND TEXT: {text} SEND SUCCESS.")
                
                # 🎯 设置命令状态
                command.return_code = 0
                command.status = Status.PASSED
                return 0

        except Exception as e:
            logger.error(f"[{self.client_name}] TEXT事件发送异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] TEXT异常: {e}'
            return -1
    
    def set_strategy(self, command: DSLCommand) -> int:
        """
        设置STRATEGY接口 - 设置策略模式
        DSL格式: [TSA]STRATEGY status(0/1/2)
        
        Args:
            command: DSL指令对象，params=[status]
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            # 🎯 参数解析
            if not command.params:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] STRATEGY参数不足'
                return -1
            
            status = int(command.params[0])
            if status not in [0, 1, 2]:
                logger.error(f"[{self.client_name}] 设置STRATEGY接口参数错误: status={status}")
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] STRATEGY状态无效: {status}'
                return -1

            logger.info(f"[{self.client_name}] 设置STRATEGY接口: status={status}")

            with self.m_lock:
                # 构建STRATEGY事件数据
                event_data = {"source":"TSA","type":"SetStrategy","data":{"value":status}}

                # 如果STRATEGY是0，同时给LCS发送网络未连接事件：DISCONNECTED
                if status == 0:
                    disconnecnt_data = {"source":"TSA","type":"NetworkInfo","data":{"networkStatus":"DISCONNECTED","networkType":"TYPE_MOBILE","segmentId":20000009}}
                    dret = self.internal_event(disconnecnt_data)
                    if dret != 0:
                        logger.error(f"[{self.client_name}] DISCONNECTED事件发送失败: ret={dret}")
                        command.return_code = dret
                        command.status = Status.FAILED
                        return dret

                ret = self.internal_event(event_data)
                
                if ret != 0:
                    logger.error(f"[{self.client_name}] SET STRATEGY事件发送失败: ret={ret}")
                    command.return_code = ret
                    command.status = Status.FAILED
                    return ret
                
                logger.info(f"[{self.client_name}] SET STRATEGY成功")
                
                # 🎯 设置命令状态
                command.return_code = 0
                command.status = Status.PASSED
                return 0

        except Exception as e:
            logger.error(f"[{self.client_name}] SET STRATEGY异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] STRATEGY异常: {e}'
            return -1

    def set_vr_config(self, command: DSLCommand) -> int:
        """
        设置VR配置项
        DSL格式: [TSA]SETVRCONFIG config_name config_value
        
        Args:
            command: DSL指令对象，params=[config_name, config_value...]
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            # 🎯 参数解析
            if len(command.params) < 2:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] SETVRCONFIG参数不足'
                return -1
            
            config_name = command.params[0]
            config_value = ' '.join(command.params[1:])  # 支持多词参数
            
            # 动态查找AIBSVRConfigCode中对应的字段值
            try:
                if str(config_name).isdigit():
                    param_code = c_int(int(config_name))
                else:
                    param_code = getattr(AIBSVRConfigCode, f"AIBS_SETTING_{config_name}")
            except AttributeError:
                logger.error(f"[{self.client_name}] 不支持的VR配置项: {config_name}")
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] 不支持的VR配置项: {config_name}'
                return -1
            
            # 处理特殊配置项的数据格式
            processed_value = self._process_vr_config_value(config_name, config_value)
            
            logger.info(f"[{self.client_name}] SETVRCONFIG: {config_name}={processed_value}")

            if config_name == "DIALOGUE_LANGUAGE":
                self.__class__.m_switch_lang_finish_event.clear()

            # 调用底层接口
            if type(processed_value) == int:
                ret = self.m_library.aibs_set_vr_config(self.m_engine, param_code, byref(c_uint(processed_value)))
            elif type(processed_value) == str:
                ret = self.m_library.aibs_set_vr_config(self.m_engine, param_code, c_char_p(processed_value.encode('utf-8')))
            elif type(processed_value) == dict:
                data = json.dumps(processed_value, ensure_ascii=False, separators=(',', ':'))
                ret = self.m_library.aibs_set_vr_config(self.m_engine, param_code, c_char_p(data.encode('utf-8')))
            else:
                logger.error(f"[{self.client_name}] 不支持的VR配置值类型: {type(processed_value)}")
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] 不支持的VR配置值类型: {type(processed_value)}'
                return -1

            if ret == 0:
                logger.info(f"[{self.client_name}] SETVRCONFIG成功: {config_name}")
                if config_name == "DIALOGUE_LANGUAGE":
                    self.__class__.m_switch_lang_finish_event.wait(timeout=self._get_timeout(2))
            else:
                logger.error(f"[{self.client_name}] SETVRCONFIG失败: {config_name}, ret={ret}")

            # 🎯 设置命令状态
            command.return_code = ret
            command.status = Status.PASSED if ret == 0 else Status.FAILED
            return ret

        except Exception as e:
            logger.error(f"[{self.client_name}] SETVRCONFIG异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] SETVRCONFIG异常: {e}'
            return -1

    # ==================== 扩展接口封装 ====================

    def pause(self, command: DSLCommand) -> int:
        """
        暂停引擎
        DSL格式: [TSA]PAUSE
        
        Args:
            command: DSL指令对象，无参数
        
        Returns:
            0: 成功, 其他: 失败
        """
        try:
            logger.info(f"[{self.client_name}] PAUSE")
            ret = self.m_library.aibs_pause_engine(self.m_engine)
            
            if ret == 0:
                logger.info(f"[{self.client_name}] PAUSE成功")
            else:
                logger.error(f"[{self.client_name}] PAUSE失败: ret={ret}")
            
            # 🎯 设置命令状态
            command.return_code = ret
            command.status = Status.PASSED if ret == 0 else Status.FAILED
            return ret
            
        except Exception as e:
            logger.error(f"[{self.client_name}] PAUSE异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] PAUSE异常: {e}'
            return -1

    def resume(self, command: DSLCommand) -> int:
        """
        恢复引擎
        DSL格式: [TSA]RESUME
        
        Args:
            command: DSL指令对象，无参数
        
        Returns:
            0: 成功, 其他: 失败
        """
        try:
            logger.info(f"[{self.client_name}] RESUME")
            ret = self.m_library.aibs_resume_engine(self.m_engine)
            
            if ret == 0:
                logger.info(f"[{self.client_name}] RESUME成功")
            else:
                logger.error(f"[{self.client_name}] RESUME失败: ret={ret}")
            
            # 🎯 设置命令状态
            command.return_code = ret
            command.status = Status.PASSED if ret == 0 else Status.FAILED
            return ret
            
        except Exception as e:
            logger.error(f"[{self.client_name}] RESUME异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] RESUME异常: {e}'
            return -1

    def get_version(self, command: DSLCommand) -> int:
        """
        获取引擎版本
        DSL格式: [TSA]GET_VERSION
        
        Args:
            command: DSL指令对象，无参数
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            logger.info(f"[{self.client_name}] GET_VERSION")
            self.m_library.aibs_get_engine_version.restype = c_char_p
            result = self.m_library.aibs_get_engine_version(self.m_engine)
            version = result.decode('utf-8') if result else "未知版本"
            logger.info(f"[{self.client_name}] GET_VERSION: {version}")
            
            # 🎯 设置命令状态
            command.return_code = version
            command.status = Status.PASSED
            return 0
            
        except Exception as e:
            logger.error(f"[{self.client_name}] GET_VERSION异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] GET_VERSION异常: {e}'
            return -1

    def set_car_type(self, command: DSLCommand) -> int:
        """
        设置车机参数
        DSL格式: [TSA]CAR_TYPE device_info
        
        Args:
            command: DSL指令对象，params=[device_info]
        
        Returns:
            0: 成功, 其他: 失败
        """
        try:
            # 🎯 参数解析
            if not command.params:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] CAR_TYPE参数不足'
                return -1
            
            device_info = ' '.join(command.params)
            
            logger.info(f"[{self.client_name}] CAR_TYPE: {device_info}")
            ret = self.m_library.aibs_set_car_type(device_info.encode('utf-8'))
            
            if ret == 0:
                logger.info(f"[{self.client_name}] CAR_TYPE成功")
            else:
                logger.error(f"[{self.client_name}] CAR_TYPE失败: ret={ret}")
            
            # 🎯 设置命令状态
            command.return_code = ret
            command.status = Status.PASSED if ret == 0 else Status.FAILED
            return ret
            
        except Exception as e:
            logger.error(f"[{self.client_name}] CAR_TYPE异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] CAR_TYPE异常: {e}'
            return -1

    def set_log_path(self, command: DSLCommand) -> int:
        """
        设置日志路径
        DSL格式: [TSA]LOG_PATH log_path
        
        Args:
            command: DSL指令对象，params=[log_path]
        
        Returns:
            0: 成功, 其他: 失败
        """
        try:
            # 🎯 参数解析
            if not command.params:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] LOG_PATH参数不足'
                return -1
            
            log_path = command.params[0]
            
            logger.info(f"[{self.client_name}] LOG_PATH: {log_path}")
            ret = self.m_library.set_aibs_logpath(log_path.encode('utf-8'))
            
            if ret == 0:
                logger.info(f"[{self.client_name}] LOG_PATH成功")
            else:
                logger.error(f"[{self.client_name}] LOG_PATH失败: ret={ret}")
            
            # 🎯 设置命令状态
            command.return_code = ret
            command.status = Status.PASSED if ret == 0 else Status.FAILED
            return ret
            
        except Exception as e:
            logger.error(f"[{self.client_name}] LOG_PATH异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] LOG_PATH异常: {e}'
            return -1

    def set_mic_status(self, command: DSLCommand) -> int:
        """
        设置mic状态
        DSL格式: [TSA]MIC_STATUS status
        
        Args:
            command: DSL指令对象，params=[status]
        
        Returns:
            0: 成功, 其他: 失败
        """
        try:
            # 🎯 参数解析
            if not command.params:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] MIC_STATUS参数不足'
                return -1
            
            status = int(command.params[0])
            
            logger.info(f"[{self.client_name}] MIC_STATUS: {status}")
            ret = self.m_library.aibs_set_mic_status(self.m_engine, status)
            
            if ret == 0:
                logger.info(f"[{self.client_name}] MIC_STATUS成功")
            else:
                logger.error(f"[{self.client_name}] MIC_STATUS失败: ret={ret}")
            
            # 🎯 设置命令状态
            command.return_code = ret
            command.status = Status.PASSED if ret == 0 else Status.FAILED
            return ret
            
        except Exception as e:
            logger.error(f"[{self.client_name}] MIC_STATUS异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] MIC_STATUS异常: {e}'
            return -1

    def set_vr_status(self, command: DSLCommand) -> int:
        """
        设置VR状态
        DSL格式: [TSA]VR_STATUS status(1/true/on/enable 或 0/false/off/disable)
        
        Args:
            command: DSL指令对象，params=[status]
        
        Returns:
            0: 成功, 其他: 失败
        """
        try:
            # 🎯 参数解析
            if not command.params:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] VR_STATUS参数不足'
                return -1
            
            status = command.params[0].lower() in ['1', 'true', 'on', 'enable']
            
            logger.info(f"[{self.client_name}] VR_STATUS: {status}")
            ret = self.m_library.aibs_set_vr_status(self.m_engine, status)
            
            if ret == 0:
                logger.info(f"[{self.client_name}] VR_STATUS成功")
            else:
                logger.error(f"[{self.client_name}] VR_STATUS失败: ret={ret}")
            
            # 🎯 设置命令状态
            command.return_code = ret
            command.status = Status.PASSED if ret == 0 else Status.FAILED
            return ret
            
        except Exception as e:
            logger.error(f"[{self.client_name}] VR_STATUS异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] VR_STATUS异常: {e}'
            return -1

    def set_link_type(self, command: DSLCommand) -> int:
        """
        设置连接类型
        DSL格式: [TSA]LINK_TYPE link_type
        
        Args:
            command: DSL指令对象，params=[link_type]
        
        Returns:
            0: 成功, 其他: 失败
        """
        try:
            # 🎯 参数解析
            if not command.params:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] LINK_TYPE参数不足'
                return -1
            
            link_type = int(command.params[0])
            
            logger.info(f"[{self.client_name}] LINK_TYPE: {link_type}")
            ret = self.m_library.aibs_set_link_type(self.m_engine, link_type)
            
            if ret == 0:
                logger.info(f"[{self.client_name}] LINK_TYPE成功")
            else:
                logger.error(f"[{self.client_name}] LINK_TYPE失败: ret={ret}")
            
            # 🎯 设置命令状态
            command.return_code = ret
            command.status = Status.PASSED if ret == 0 else Status.FAILED
            return ret
            
        except Exception as e:
            logger.error(f"[{self.client_name}] LINK_TYPE异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] LINK_TYPE异常: {e}'
            return -1

    def set_vr_event(self, command: DSLCommand) -> int:
        """
        设置VR事件
        DSL格式: [TSA]VREVENT json_data_or_file
        
        Args:
            command: DSL指令对象，params=[event_data]
        
        Returns:
            0: 成功, 其他: 失败
        """
        try:
            # 🎯 参数解析
            if not command.params:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] VREVENT参数不足'
                return -1
            
            event_param = command.params[0]
            event_data_str = None

            # 判断参数是文件路径还是JSON字符串
            if event_param.endswith('.json') and os.path.exists(event_param):
                with open(event_param, 'r', encoding='utf-8') as f:
                    json_content = json.load(f)
                    event_data_str = json.dumps(json_content, ensure_ascii=False, separators=(',', ':'))
            else:
                # 如果不是文件路径，则将所有参数拼接为字符串
                event_data_str = ' '.join(command.params)
            
            logger.info(f"[{self.client_name}] VREVENT: {event_data_str}")
            event_data_json = json.loads(event_data_str)

            # 添加时间戳和事件ID
            event_data_json.update({
                "et_id": uuid(),
                "mts": AIBSClient.m_timestamp
            })

            json_data = json.dumps(event_data_json, ensure_ascii=False, separators=(',', ':'))
            ret = self.m_library.aibs_set_vr_event(self.m_engine, json_data.encode('utf-8'))

            if ret == 0:
                logger.info(f"[{self.client_name}] VREVENT 成功")
            else:
                logger.error(f"[{self.client_name}] VREVENT 失败: ret={ret}")

            # 🎯 设置命令状态
            command.return_code = ret
            command.status = Status.PASSED if ret == 0 else Status.FAILED
            return ret

        except Exception as e:
            logger.error(f"[{self.client_name}] VREVENT异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] VREVENT异常: {e}'
            return -1

    def start_record(self, command: DSLCommand) -> int:
        """
        开始录音
        DSL格式: [TSA]START_RECORD
        
        Args:
            command: DSL指令对象，无参数
        
        Returns:
            0: 成功, 其他: 失败
        """
        try:
            logger.info(f"[{self.client_name}] START_RECORD")
            ret = self.m_library.aibs_start_record(self.m_engine)
            
            if ret == 0:
                logger.info(f"[{self.client_name}] START_RECORD成功")
            else:
                logger.error(f"[{self.client_name}] START_RECORD失败: ret={ret}")
            
            # 🎯 设置命令状态
            command.return_code = ret
            command.status = Status.PASSED if ret == 0 else Status.FAILED
            return ret
            
        except Exception as e:
            logger.error(f"[{self.client_name}] START_RECORD异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] START_RECORD异常: {e}'
            return -1

    def stop_record(self, command: DSLCommand) -> int:
        """
        停止录音
        DSL格式: [TSA]STOP_RECORD
        
        Args:
            command: DSL指令对象，无参数
        
        Returns:
            0: 成功, 其他: 失败
        """
        try:
            logger.info(f"[{self.client_name}] STOP_RECORD")
            ret = self.m_library.aibs_stop_record(self.m_engine)
            
            if ret == 0:
                logger.info(f"[{self.client_name}] STOP_RECORD成功")
            else:
                logger.error(f"[{self.client_name}] STOP_RECORD失败: ret={ret}")
            
            # 🎯 设置命令状态
            command.return_code = ret
            command.status = Status.PASSED if ret == 0 else Status.FAILED
            return ret
            
        except Exception as e:
            logger.error(f"[{self.client_name}] STOP_RECORD异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] STOP_RECORD异常: {e}'
            return -1

    def open_voice_input(self, command: DSLCommand) -> int:
        """
        开启语音输入模式
        DSL格式: [TSA]OPEN_VOICE_INPUT param
        
        Args:
            command: DSL指令对象，params=[param]
        
        Returns:
            0: 成功, 其他: 失败
        """
        try:
            # 🎯 参数解析
            if not command.params:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] OPEN_VOICE_INPUT参数不足'
                return -1
            
            param = ' '.join(command.params)
            
            logger.info(f"[{self.client_name}] OPEN_VOICE_INPUT: {param}")
            ret = self.m_library.aibs_open_voice_input(self.m_engine, param.encode('utf-8'))
            
            if ret == 0:
                logger.info(f"[{self.client_name}] OPEN_VOICE_INPUT成功")
            else:
                logger.error(f"[{self.client_name}] OPEN_VOICE_INPUT失败: ret={ret}")
            
            # 🎯 设置命令状态
            command.return_code = ret
            command.status = Status.PASSED if ret == 0 else Status.FAILED
            return ret
            
        except Exception as e:
            logger.error(f"[{self.client_name}] OPEN_VOICE_INPUT异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] OPEN_VOICE_INPUT异常: {e}'
            return -1

    def close_voice_input(self, command: DSLCommand) -> int:
        """
        关闭语音输入模式
        DSL格式: [TSA]CLOSE_VOICE_INPUT
        
        Args:
            command: DSL指令对象，无参数
        
        Returns:
            0: 成功, 其他: 失败
        """
        try:
            logger.info(f"[{self.client_name}] CLOSE_VOICE_INPUT")
            ret = self.m_library.aibs_close_voice_input(self.m_engine)
            
            if ret == 0:
                logger.info(f"[{self.client_name}] CLOSE_VOICE_INPUT成功")
            else:
                logger.error(f"[{self.client_name}] CLOSE_VOICE_INPUT失败: ret={ret}")
            
            # 🎯 设置命令状态
            command.return_code = ret
            command.status = Status.PASSED if ret == 0 else Status.FAILED
            return ret
            
        except Exception as e:
            logger.error(f"[{self.client_name}] CLOSE_VOICE_INPUT异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] CLOSE_VOICE_INPUT异常: {e}'
            return -1

    def get_fota_status(self, command: DSLCommand) -> int:
        """
        获取FOTA状态
        DSL格式: [TSA]GET_FOTA_STATUS
        
        Args:
            command: DSL指令对象，无参数
        
        Returns:
            0: 成功, 其他: 失败
        """
        try:
            logger.info(f"[{self.client_name}] GET_FOTA_STATUS")
            ret = self.m_library.get_fota_status(self.m_engine)
            logger.info(f"[{self.client_name}] GET_FOTA_STATUS: {ret}")
            
            # 🎯 设置命令状态
            command.return_code = ret
            command.status = Status.PASSED
            return 0
            
        except Exception as e:
            logger.error(f"[{self.client_name}] GET_FOTA_STATUS异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] GET_FOTA_STATUS异常: {e}'
            return -1

    def clear_vr_config(self, command: DSLCommand) -> int:
        """
        恢复出厂设置
        DSL格式: [TSA]CLEAR_VR_CONFIG
        
        Args:
            command: DSL指令对象，无参数
        
        Returns:
            0: 成功, 其他: 失败
        """
        try:
            logger.info(f"[{self.client_name}] CLEAR_VR_CONFIG")
            ret = self.m_library.aibs_clear_vr_config(self.m_engine)
            
            if ret == 0:
                logger.info(f"[{self.client_name}] CLEAR_VR_CONFIG成功")
            else:
                logger.error(f"[{self.client_name}] CLEAR_VR_CONFIG失败: ret={ret}")
            
            # 🎯 设置命令状态
            command.return_code = ret
            command.status = Status.PASSED if ret == 0 else Status.FAILED
            return ret
            
        except Exception as e:
            logger.error(f"[{self.client_name}] CLEAR_VR_CONFIG异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] CLEAR_VR_CONFIG异常: {e}'
            return -1

    # ==================== 新增扩展接口封装 ====================

    def set_param(self, command: DSLCommand) -> int:
        """
        设置引擎参数
        DSL格式: [TSA]SET_PARAM param_code param_value
        
        Args:
            command: DSL指令对象，params=[param_code, param_value]
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            # 🎯 参数解析
            if len(command.params) < 2:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] SET_PARAM参数不足'
                return -1
            
            param_code = command.params[0]
            param_value_str = command.params[1]
            
            # 尝试转换参数值类型
            param_value = self._convert_param_value(param_value_str)
            
            logger.info(f"[{self.client_name}] SET_PARAM: {param_code}={param_value}")
            
            # 参数代码映射
            param_mapping = {
                'AIBS_PARAM_SESSION_LINK_TYPE': 0x01,
                'AIBS_PARAM_SEAT_SIGNAL': 0x02,
                'AIBS_PARAM_FULL_VEHICLE_SPEECH': 0x03,
                'AIBS_PARAM_REAL_TIME_RESULT': 0x04,
                'AIBS_PARAM_PUNC_RESULT': 0x05,
                'AIBS_PARAM_DIGIT_CONVERT_RESULT': 0x06,
                'AIBS_PARAM_SILENCE_DURATION': 0x07,
                'AIBS_PARAM_SILENCE_TIMEOUT': 0x08,
                'AIBS_PARAM_SPEECH_TIMEOUT': 0x09,
                'AIBS_PARAM_SCENAROI_NAME': 0x0A,
                'AIBS_PARAM_WAKEUP_SCENE': 0x0B,
                'AIBS_PARAM_WAKEUP_DELAY_ONESHOT_DURATION': 0x0C,
                'AIBS_PARAM_SOUND_EVENT_OPTION': 0x0D,
                'AIBS_PARAM_DISABLE_BUTTON_WAKEUP': 0x0E,
                'AIBS_PARAM_EMOTION_OPTION': 0x0F,
                'AIBS_PARAM_SR_PTT_OPTION': 0x10,
                'AIBS_PARAM_SR_VOICE_WAKEUP': 0x12,
                'AIBS_PARAM_SR_WAKEUP_SCENE_ENABLE': 0x14,
                'AIBS_PARAM_SR_AUDIO_SPECTRAL': 0x15,
                'AIBS_PARAM_SR_RECORD_DEVICE_STATE': 0x16
            }
            
            if param_code not in param_mapping:
                logger.error(f"[{self.client_name}] 不支持的参数代码: {param_code}")
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] 不支持的参数代码: {param_code}'
                return -1
                
            param_id = param_mapping[param_code]
            
            # 根据参数值类型调用相应接口
            if isinstance(param_value, int):
                ret = self.m_library.set_aibs_param(self.m_engine, param_id, byref(c_uint(param_value)))
            elif isinstance(param_value, float):
                ret = self.m_library.set_aibs_param(self.m_engine, param_id, byref(c_float(param_value)))
            elif isinstance(param_value, str):
                ret = self.m_library.set_aibs_param(self.m_engine, param_id, c_char_p(param_value.encode('utf-8')))
            elif isinstance(param_value, bool):
                ret = self.m_library.set_aibs_param(self.m_engine, param_id, byref(c_bool(param_value)))
            else:
                logger.error(f"[{self.client_name}] 不支持的参数值类型: {type(param_value)}")
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] 不支持的参数值类型: {type(param_value)}'
                return -1
            
            if ret == 0:
                logger.info(f"[{self.client_name}] SET_PARAM成功")
            else:
                logger.error(f"[{self.client_name}] SET_PARAM失败: ret={ret}")
            
            # 🎯 设置命令状态
            command.return_code = ret
            command.status = Status.PASSED if ret == 0 else Status.FAILED
            return ret
            
        except Exception as e:
            logger.error(f"[{self.client_name}] SET_PARAM异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] SET_PARAM异常: {e}'
            return -1
    
    def _convert_param_value(self, value_str: str):
        """转换参数值类型（内部工具方法）"""
        # 尝试转换为整数
        try:
            return int(value_str)
        except ValueError:
            pass
        
        # 尝试转换为浮点数
        try:
            return float(value_str)
        except ValueError:
            pass
        
        # 尝试转换为布尔值
        if value_str.lower() in ['true', 'false']:
            return value_str.lower() == 'true'
        
        # 默认作为字符串
        return value_str

    def update_personalized_info(self, command: DSLCommand) -> int:
        """
        更新个性化信息
        DSL格式: [TSA]UPDATE_PERSONALIZED json_userlist charset weight
        
        Args:
            command: DSL指令对象，params=[json_userlist, charset, weight]
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            # 🎯 参数解析
            if len(command.params) < 3:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] UPDATE_PERSONALIZED参数不足'
                return -1
            
            json_userlist = command.params[0]
            charset = command.params[1]
            weight = float(command.params[2])
            
            logger.info(f"[{self.client_name}] UPDATE_PERSONALIZED: charset={charset}, weight={weight}")
            ret = self.m_library.aibs_update_personalized_info(
                self.m_engine, 
                json_userlist.encode('utf-8'),
                charset.encode('utf-8'),
                c_float(weight)
            )
            
            if ret == 0:
                logger.info(f"[{self.client_name}] UPDATE_PERSONALIZED成功")
            else:
                logger.error(f"[{self.client_name}] UPDATE_PERSONALIZED失败: ret={ret}")
            
            # 🎯 设置命令状态
            command.return_code = ret
            command.status = Status.PASSED if ret == 0 else Status.FAILED
            return ret
            
        except Exception as e:
            logger.error(f"[{self.client_name}] UPDATE_PERSONALIZED异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] UPDATE_PERSONALIZED异常: {e}'
            return -1

    def set_tts_state(self, command: DSLCommand) -> int:
        """
        设置TTS状态
        DSL格式: [TSA]SET_TTS_STATE state(true/false/1/0)
        
        Args:
            command: DSL指令对象，params=[state]
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            # 🎯 参数解析
            if len(command.params) < 1:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] SET_TTS_STATE参数不足'
                return -1
            
            state_str = command.params[0].lower()
            state = state_str in ['true', '1', 'on', 'enable']
            
            logger.info(f"[{self.client_name}] SET_TTS_STATE: {state}")
            ret = self.m_library.aibs_set_tts_state(self.m_engine, c_bool(state))
            
            if ret == 0:
                logger.info(f"[{self.client_name}] SET_TTS_STATE成功")
            else:
                logger.error(f"[{self.client_name}] SET_TTS_STATE失败: ret={ret}")
            
            # 🎯 设置命令状态
            command.return_code = ret
            command.status = Status.PASSED if ret == 0 else Status.FAILED
            return ret
            
        except Exception as e:
            logger.error(f"[{self.client_name}] SET_TTS_STATE异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] SET_TTS_STATE异常: {e}'
            return -1

    def set_page_intent(self, command: DSLCommand) -> int:
        """
        设置页面意图
        DSL格式: [TSA]SET_PAGE_INTENT hmi_info app_name
        
        Args:
            command: DSL指令对象，params=[hmi_info, app_name]
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            # 🎯 参数解析
            if len(command.params) < 2:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] SET_PAGE_INTENT参数不足'
                return -1
            
            hmi_info = command.params[0]
            app_name = command.params[1]
            
            logger.info(f"[{self.client_name}] SET_PAGE_INTENT: app={app_name}")
            ret = self.m_library.aibs_set_page_intent(
                self.m_engine,
                hmi_info.encode('utf-8'),
                app_name.encode('utf-8')
            )
            
            if ret == 0:
                logger.info(f"[{self.client_name}] SET_PAGE_INTENT成功")
            else:
                logger.error(f"[{self.client_name}] SET_PAGE_INTENT失败: ret={ret}")
            
            # 🎯 设置命令状态
            command.return_code = ret
            command.status = Status.PASSED if ret == 0 else Status.FAILED
            return ret
            
        except Exception as e:
            logger.error(f"[{self.client_name}] SET_PAGE_INTENT异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] SET_PAGE_INTENT异常: {e}'
            return -1

    def set_language_mode(self, command: DSLCommand) -> int:
        """
        设置语言模式
        DSL格式: [TSA]SET_LANGUAGE_MODE mode
        
        Args:
            command: DSL指令对象，params=[mode]
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            # 🎯 参数解析
            if len(command.params) < 1:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] SET_LANGUAGE_MODE参数不足'
                return -1
            
            mode = command.params[0]
            
            logger.info(f"[{self.client_name}] SET_LANGUAGE_MODE: {mode}")
            ret = self.m_library.aibs_set_language_mode(self.m_engine, mode.encode('utf-8'))
            
            if ret == 0:
                logger.info(f"[{self.client_name}] SET_LANGUAGE_MODE成功")
            else:
                logger.error(f"[{self.client_name}] SET_LANGUAGE_MODE失败: ret={ret}")
            
            # 🎯 设置命令状态
            command.return_code = ret
            command.status = Status.PASSED if ret == 0 else Status.FAILED
            return ret
            
        except Exception as e:
            logger.error(f"[{self.client_name}] SET_LANGUAGE_MODE异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] SET_LANGUAGE_MODE异常: {e}'
            return -1

    def set_wakeup_word(self, command: DSLCommand) -> int:
        """
        设置唤醒词(带阈值)
        DSL格式: [TSA]SET_WAKEUP_WORD word threshold
        
        Args:
            command: DSL指令对象，params=[word, threshold]
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            # 🎯 参数解析
            if len(command.params) < 2:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] SET_WAKEUP_WORD参数不足'
                return -1
            
            word = command.params[0]
            threshold = float(command.params[1])
            
            logger.info(f"[{self.client_name}] SET_WAKEUP_WORD: {word}, threshold={threshold}")
            ret = self.m_library.aibs_set_wakeup_word(
                self.m_engine,
                word.encode('utf-8'),
                c_float(threshold)
            )
            
            if ret == 0:
                logger.info(f"[{self.client_name}] SET_WAKEUP_WORD成功")
            else:
                logger.error(f"[{self.client_name}] SET_WAKEUP_WORD失败: ret={ret}")
            
            # 🎯 设置命令状态
            command.return_code = ret
            command.status = Status.PASSED if ret == 0 else Status.FAILED
            return ret
            
        except Exception as e:
            logger.error(f"[{self.client_name}] SET_WAKEUP_WORD异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] SET_WAKEUP_WORD异常: {e}'
            return -1

    def set_wakeup_word_enable(self, command: DSLCommand) -> int:
        """
        设置唤醒词使能
        DSL格式: [TSA]SET_WAKEUP_ENABLE word enable(true/false/1/0)
        
        Args:
            command: DSL指令对象，params=[word, enable]
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            # 🎯 参数解析
            if len(command.params) < 2:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] SET_WAKEUP_ENABLE参数不足'
                return -1
            
            word = command.params[0]
            enable_str = command.params[1].lower()
            enable = enable_str in ['true', '1', 'on', 'enable']
            
            logger.info(f"[{self.client_name}] SET_WAKEUP_ENABLE: {word}, enable={enable}")
            ret = self.m_library.aibs_set_wakeup_word_enable(
                self.m_engine,
                word.encode('utf-8'),
                c_bool(enable)
            )
            
            if ret == 0:
                logger.info(f"[{self.client_name}] SET_WAKEUP_ENABLE成功")
            else:
                logger.error(f"[{self.client_name}] SET_WAKEUP_ENABLE失败: ret={ret}")
            
            # 🎯 设置命令状态
            command.return_code = ret
            command.status = Status.PASSED if ret == 0 else Status.FAILED
            return ret
            
        except Exception as e:
            logger.error(f"[{self.client_name}] SET_WAKEUP_ENABLE异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] SET_WAKEUP_ENABLE异常: {e}'
            return -1

    def set_workmode(self, command: DSLCommand) -> int:
        """
        设置工作模式
        DSL格式: [TSA]SET_WORKMODE mode(WAKEUP/ASR/WAKEUP_ASR/SMART_LINK)
        
        Args:
            command: DSL指令对象，params=[mode]
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            # 🎯 参数解析
            if len(command.params) < 1:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] SET_WORKMODE参数不足'
                return -1
            
            mode = int(command.params[0])
            
            logger.info(f"[{self.client_name}] SET_WORKMODE: {mode}")
            
            # 工作模式映射
            mode_mapping = [0, 1, 2, 3]
            
            if mode not in mode_mapping:
                logger.error(f"[{self.client_name}] 不支持的工作模式: {mode}")
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] 不支持的工作模式: {mode}'
                return -1
                
            ret = self.m_library.aibs_set_workmode(self.m_engine, c_int(mode))
            
            if ret == 0:
                logger.info(f"[{self.client_name}] SET_WORKMODE成功")
            else:
                logger.error(f"[{self.client_name}] SET_WORKMODE失败: ret={ret}")
            
            # 🎯 设置命令状态
            command.return_code = ret
            command.status = Status.PASSED if ret == 0 else Status.FAILED
            return ret
            
        except Exception as e:
            logger.error(f"[{self.client_name}] SET_WORKMODE异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] SET_WORKMODE异常: {e}'
            return -1

    def get_vr_config(self, command: DSLCommand) -> dict:
        """
        获取VR配置
        DSL格式: [TSA]GET_VR_CONFIG config_name
        
        Args:
            command: DSL指令对象，params=[config_name]
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            # 🎯 参数解析
            if len(command.params) < 1:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] GET_VR_CONFIG参数不足'
                return {}
            
            config_name = command.params[0]
            
            logger.info(f"[{self.client_name}] GET_VR_CONFIG: {config_name}")
            
            # 动态查找AIBSVRConfigCode中对应的字段值
            try:
                if str(config_name).isdigit():
                    param_code = c_int(int(config_name))
                else:
                    param_code = getattr(AIBSVRConfigCode, f"AIBS_SETTING_{config_name}")
            except AttributeError:
                logger.error(f"[{self.client_name}] 不支持的VR配置项: {config_name}")
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] 不支持的VR配置项: {config_name}'
                return {}

            self.m_library.aibs_get_vr_config.restype = c_char_p
            result = self.m_library.aibs_get_vr_config(self.m_engine, param_code)
            config_value = result.decode('utf-8') if result else ""

            return_data = None
            if param_code.value == AIBSVRConfigCode.AIBS_SETTING_DEVICE_INFO.value:
                return_data = {"deviceInfo": json.loads(config_value)}
            elif param_code.value == AIBSVRConfigCode.AIBS_SETTING_VR_OPTION.value:
                return_data = {"vrOption": config_value}
            elif param_code.value == AIBSVRConfigCode.AIBS_SETTING_SHOW_STYLE.value:
                return_data = {"showStyle": config_value}
            elif param_code.value == AIBSVRConfigCode.AIBS_SETTING_WAKEUP_ALIAS.value:
                return_data = {"wakeupAlias": json.loads(config_value)[0] if len(json.loads(config_value)) > 0 else []}
            elif param_code.value == AIBSVRConfigCode.AIBS_SETTING_DIALOGUE_STYLE.value:
                return_data = {"dialogueStyle": config_value}
            elif param_code.value == AIBSVRConfigCode.AIBS_SETTING_DIALOGUE_LANGUAGE.value:
                return_data = {"dialogueLanguage": config_value}
            elif param_code.value == AIBSVRConfigCode.AIBS_SETTING_SOUND_AREA_OPTION.value:
                return_data = {"SoundAreaOption": config_value}
            elif param_code.value == AIBSVRConfigCode.AIBS_SETTING_WAKEUP_KEYWORD_OPTION.value:
                return_data = {"WakupKeyWordOption": config_value}
            elif param_code.value == AIBSVRConfigCode.AIBS_SETTING_VOICE_WAKEUP_OPTION.value:
                return_data = {"VoiceWakeupOption": config_value}
            elif param_code.value == AIBSVRConfigCode.AIBS_SETTING_WAKEUP_ENABLE.value:
                return_data = {"WakeupEnable": config_value}
            elif param_code.value == AIBSVRConfigCode.AIBS_SETTING_GET_WAKEUP_WORD.value:
                try:
                    # 解析JSON数据
                    wakeup_data = json.loads(config_value) if isinstance(config_value, str) else config_value
                    # 提取所有enabled为true的唤醒词
                    enabled_wakeup_words = []
                    wakeup_words_all_list = []
                    wakeup_Word_Main = []
                    wakeupRecomTrue = []
                    wakeupRecomFalse = []
                    if isinstance(wakeup_data, list):
                        for lang_item in wakeup_data:
                            if isinstance(lang_item, dict):
                                lang = lang_item.get("lang", "")
                                wakeuplist = lang_item.get("wakeuplist", {})
                                fix_data = wakeuplist.get("wakeup", {}).get("data", {}).get("fix_data", [])
                                # 遍历fix_data，找出enabled为true的唤醒词
                                for item in fix_data:
                                    if isinstance(item, dict):
                                        wakeup_words_all_list.append(item.get("word"))
                                    if isinstance(item, dict) and item.get("enabled") is True:
                                        enabled_wakeup_words.append(item.get("word"))
                                    if isinstance(item, dict) and item.get("isPrimary") is True:
                                        wakeup_Word_Main.append(item.get("word"))
                                    if isinstance(item, dict) and item.get("isRecommend") is True:
                                        wakeupRecomTrue.append(item.get("word"))
                                    if isinstance(item, dict) and item.get("isRecommend") is False:
                                        wakeupRecomFalse.append(item.get("word"))
                    return_data = {"wakeupWordList": str(enabled_wakeup_words),
                                   "wakeupWordListAll": str(wakeup_words_all_list),
                                   "wakeupWordMain": str(wakeup_Word_Main),
                                   "wakeupRecomTrue": str(wakeupRecomTrue),
                                   "wakeupRecomFalse": str(wakeupRecomFalse)}
                except (json.JSONDecodeError, KeyError, TypeError) as e:
                    logger.warning(f"[{self.client_name}] 解析GET_WAKEUP_WORD数据失败: {e}, 使用原始值")
                    return_data = {"GetWakeupWord": config_value}
            elif param_code.value == AIBSVRConfigCode.AIBS_SETTING_SET_TTS_VOICE_TYPE.value:
                return_data = {"SetTtsVoiceType": config_value}
            elif param_code.value == AIBSVRConfigCode.AIBS_SETTING_MULTI_DIALOGUE.value:
                return_data = {"MultiDialogue": config_value}
            elif param_code.value == AIBSVRConfigCode.AIBS_SETTING_EXPERIENCE_IMPROVENMENT.value:
                return_data = {"ExperienceImprovenment": config_value}
            elif param_code.value == AIBSVRConfigCode.AIBS_SETTING_PERSONAL_SENSITIVE_AUTHORIZATION.value:
                return_data = {"PersonalSensitiveAuthorization": config_value}
            elif param_code.value == AIBSVRConfigCode.AIBS_SETTING_VOICE_SENSITIVE_AUTHORIZATION.value:
                return_data = {"VoiceSensitiveAuthorization": config_value}
            elif param_code.value == AIBSVRConfigCode.AIBS_SETTING_ACTIVE_INTERACTION.value:
                return_data = {"ActiveInteraction": config_value}
            elif param_code.value == AIBSVRConfigCode.AIBS_SETTING_SRE_SENSITIVE_EMPOWER_OPTION.value:
                return_data = {"SreSensitiveEmpowerOption": config_value}
            elif param_code.value == AIBSVRConfigCode.AIBS_SETTING_SRE_FUNC_ENABLE_OPTION.value:
                return_data = {"SreFuncEnableOption": config_value}
            elif param_code.value == AIBSVRConfigCode.AIBS_SETTING_SERVER_CACHE_LANGUAGE.value:
                return_data = {"ServerCacheLanguage": config_value}
            elif param_code.value == AIBSVRConfigCode.AIBS_SETTING_GPT_ENABLE_OPTION.value:
                return_data = {"GptEnableOption": config_value}
            elif param_code.value == AIBSVRConfigCode.AIBS_SETTING_SRE_MEMORY.value:
                return_data = {"SreMemory": config_value}
            elif param_code.value == AIBSVRConfigCode.AIBS_SETTING_VEHICLE_MEMORY.value:
                return_data = {"VehicleMemory": config_value}
            else:
                return_data = {}
            
            logger.info(f"[{self.client_name}] GET_VR_CONFIG: {config_name}={return_data}")
            
            # 🎯 设置命令状态
            command.return_code = return_data
            command.status = Status.PASSED
            return return_data
            
        except Exception as e:
            logger.error(f"[{self.client_name}] GET_VR_CONFIG异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] GET_VR_CONFIG异常: {e}'
            return {}

    # ==================== 声纹功能接口封装 ====================

    def start_speaker_enroll(self, command: DSLCommand) -> int:
        """
        注册声纹信息
        DSL格式: [TSA]START_SPEAKER_ENROLL user_id text enroll_id channel_id
        
        Args:
            command: DSL指令对象，params=[user_id, text, enroll_id, channel_id]
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            # 🎯 参数解析
            if len(command.params) < 4:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] START_SPEAKER_ENROLL参数不足'
                return -1
            
            user_id = command.params[0]
            text = command.params[1]
            enroll_id = int(command.params[2])
            channel_id = int(command.params[3])
            
            logger.info(f"[{self.client_name}] START_SPEAKER_ENROLL: user_id={user_id}, text={text}, id={enroll_id}, channel_id={channel_id}")
            ret = self.m_library.aibs_start_speaker_enroll(
                self.m_engine,
                user_id.encode('utf-8'),
                text.encode('utf-8'),
                enroll_id,
                channel_id
            )
            
            if ret == 0:
                logger.info(f"[{self.client_name}] START_SPEAKER_ENROLL成功")
            else:
                logger.error(f"[{self.client_name}] START_SPEAKER_ENROLL失败: ret={ret}")
            
            # 🎯 设置命令状态
            command.return_code = ret
            command.status = Status.PASSED if ret == 0 else Status.FAILED
            return ret
            
        except Exception as e:
            logger.error(f"[{self.client_name}] START_SPEAKER_ENROLL异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] START_SPEAKER_ENROLL异常: {e}'
            return -1

    def end_speaker_enroll(self, command: DSLCommand) -> int:
        """
        结束声纹注册
        DSL格式: [TSA]END_SPEAKER_ENROLL
        
        Args:
            command: DSL指令对象，无参数
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            logger.info(f"[{self.client_name}] END_SPEAKER_ENROLL")
            ret = self.m_library.aibs_end_speaker_enroll(self.m_engine)
            
            if ret == 0:
                logger.info(f"[{self.client_name}] END_SPEAKER_ENROLL成功")
            else:
                logger.error(f"[{self.client_name}] END_SPEAKER_ENROLL失败: ret={ret}")
            
            # 🎯 设置命令状态
            command.return_code = ret
            command.status = Status.PASSED if ret == 0 else Status.FAILED
            return ret
            
        except Exception as e:
            logger.error(f"[{self.client_name}] END_SPEAKER_ENROLL异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] END_SPEAKER_ENROLL异常: {e}'
            return -1
    
    def register_voiceprint_list(self, command: DSLCommand) -> int:
        """
        注册多个用户声纹
        DSL格式: [TSA]REGISTER_VOICEPRINT_LIST param_file frame_size delay
        
        param_file格式（Tab分隔）：
        audio_path	user_id:xxx;text:xxx;index:1;channel:0
        
        Args:
            command: DSL指令对象，params=[param_file, frame_size, delay]
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            # 🎯 参数解析
            if len(command.params) < 3:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] REGISTER_VOICEPRINT_LIST参数不足'
                return -1
            
            param_file = command.params[0]

            # 解析命名参数
            for param in command.params[1:]:
                if '=' in param:
                    key, value = param.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    if key == 'frame':
                        frame_size = int(value)
                    elif key == 'delay':
                        delay = float(value)
            
            # 解析参数文件（这部分逻辑从 NANORunner 移过来）
            if not os.path.exists(param_file):
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] 参数文件不存在: {param_file}'
                return -1
            
            # 解析声纹参数列表
            sre_dict = {}
            with open(param_file, 'r', encoding='utf-8') as fp:
                for line in fp.readlines():
                    line = line.strip()
                    if not line or line.startswith("#") or line.startswith("//"):
                        continue
                    audio, params = line.split("\t")
                    pairs = params.split(';')
                    param_dict = {pair.split(':')[0]: pair.split(':')[1] for pair in pairs}
                    item = {"audio_path": audio, **param_dict}
                    
                    user_id = param_dict.get('user_id')
                    if user_id not in sre_dict:
                        sre_dict[user_id] = []
                    sre_dict[user_id].append(item)
            
            register_user_list = list(sre_dict.values())
            logger.info(f"[{self.client_name}] REGISTER_VOICEPRINT_LIST: 共{len(register_user_list)}个用户")

            # 遍历每个用户的声纹数据
            for single_user_list in register_user_list:
                for user_info in single_user_list:
                    user_id = user_info.get("user_id")
                    text = user_info.get("text")
                    index = user_info.get("index")
                    channel = user_info.get("channel")
                    audio_path = user_info.get("audio_path")

                    # 创建临时 command 调用 start_speaker_enroll
                    enroll_cmd = DSLCommand(self.client_name, 'START_SPEAKER_ENROLL', 
                                           [user_id, text, str(index), str(channel)], 0)
                    self.start_speaker_enroll(enroll_cmd)
                    
                    # 创建临时 command 调用 data
                    data_cmd = DSLCommand(self.client_name, 'DATA', 
                                         [audio_path, f'frame={frame_size}', f'delay={delay}'], 0)
                    self.data(data_cmd)
                    
                    self.m_sreRegister_event.wait(timeout=5)
                    self.m_sreRegister_event.clear()

                # 调用end_enroll接口
                end_cmd = DSLCommand(self.client_name, 'END_SPEAKER_ENROLL', [], 0)
                ret = self.end_speaker_enroll(end_cmd)
            
            if ret != 0:
                logger.error(f"[{self.client_name}] REGISTER_VOICEPRINT_LIST失败: ret={ret}")
            
            # 🎯 设置命令状态
            command.return_code = ret
            command.status = Status.PASSED if ret == 0 else Status.FAILED
            return ret
            
        except Exception as e:
            logger.error(f"[{self.client_name}] REGISTER_VOICEPRINT_LIST异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] REGISTER_VOICEPRINT_LIST异常: {e}'
            return -1

    def voiceprint_login(self, command: DSLCommand) -> int:
        """
        声纹登录
        DSL格式: [TSA]VOICEPRINT_LOGIN audio_path [frame_size] [delay]
        
        Args:
            command: DSL指令对象，params=[audio_path, frame_size, delay]
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            # 🎯 参数解析
            if not command.params:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] VOICEPRINT_LOGIN参数不足'
                return -1
            
            # 解析参数（支持命名参数）
            audio_path = command.params[0]
            frame_size = 320
            delay = 0.0
            
            # 解析命名参数
            for param in command.params[1:]:
                if '=' in param:
                    key, value = param.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    if key == 'frame':
                        frame_size = int(value)
                    elif key == 'delay':
                        delay = float(value)

            logger.info(f"[{self.client_name}] VOICEPRINT_LOGIN: audio_path={audio_path}, frame_size={frame_size}, delay={delay}")
            
            # 创建临时 command 调用 data
            value = os.getenv("VOICE_LOGIN_NLP")
            if value is not None:
                del os.environ["VOICE_LOGIN_NLP"]

            data_cmd = DSLCommand(self.client_name, 'DATA', 
                                 [audio_path, f'frame={frame_size}', f'delay={delay}'], 0)
            self.data(data_cmd)
            
            # 等待NLP结果
            voice_login_nlp = get_environment("VOICE_LOGIN_NLP", timeout=3)
            
            if voice_login_nlp is None:
                logger.error(f"[{self.client_name}] 无理解结果, voice_login_nlp: {voice_login_nlp}")
                command.return_code = "No NLP"
                command.status = Status.FAILED
                return -1
            
            channel_id, start_time, end_time = voice_login_nlp.split()
            
            # 创建临时 command 调用 recognize_speaker
            recognize_cmd = DSLCommand(self.client_name, 'RECOGNIZE_SPEAKER', 
                                      [channel_id, start_time, end_time], 0)
            self.recognize_speaker(recognize_cmd)
            user_id = recognize_cmd.return_code
            
            if user_id is None or user_id == "":
                logger.debug(f"[{self.client_name}] 声纹校验失败 user_id: {user_id}")
                command.return_code = "None"
                command.status = Status.FAILED
                return -1
            
            # 🎯 设置命令状态
            command.return_code = user_id
            command.status = Status.PASSED
            return 0
            
        except Exception as e:
            logger.error(f"[{self.client_name}] VOICEPRINT_LOGIN异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] VOICEPRINT_LOGIN异常: {e}'
            return -1

    def recognize_speaker(self, command: DSLCommand) -> int:
        """
        识别发话人
        DSL格式: [TSA]RECOGNIZE_SPEAKER channel_id start_time end_time
        
        Args:
            command: DSL指令对象，params=[channel_id, start_time, end_time]
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            # 🎯 参数解析
            if len(command.params) < 3:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] RECOGNIZE_SPEAKER参数不足'
                return -1
            
            channel_id = int(command.params[0])
            start_time = int(command.params[1])
            end_time = int(command.params[2])
            
            logger.info(f"[{self.client_name}] RECOGNIZE_SPEAKER: channel_id={channel_id}, start_time={start_time}, end_time={end_time}")
            self.m_library.aibs_recognize_speaker.restype = c_char_p
            result = self.m_library.aibs_recognize_speaker(self.m_engine, c_int(channel_id), c_long(start_time), c_long(end_time))
            speaker_info = json.loads(result.decode('utf-8')).get("data").get("user_id") if result else ""
            logger.info(f"[{self.client_name}] RECOGNIZE_SPEAKER: {speaker_info}")
            
            # 🎯 设置命令状态
            command.return_code = speaker_info
            command.status = Status.PASSED
            return 0
            
        except Exception as e:
            logger.error(f"[{self.client_name}] RECOGNIZE_SPEAKER异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] RECOGNIZE_SPEAKER异常: {e}'
            return -1

    def verify_voiceprint(self, command: DSLCommand) -> int:
        """
        声纹验证
        DSL格式: [TSA]VERIFY_VOICEPRINT user_id text channel_id
        
        Args:
            command: DSL指令对象，params=[user_id, text, channel_id]
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            # 🎯 参数解析
            if len(command.params) < 3:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] VERIFY_VOICEPRINT参数不足'
                return -1
            
            user_id = command.params[0]
            text = command.params[1]
            channel_id = int(command.params[2])
            
            logger.info(f"[{self.client_name}] VERIFY_VOICEPRINT: user_id={user_id}, text={text}, channel_id={channel_id}")
            ret = self.m_library.aibs_verify_voiceprint(
                self.m_engine,
                user_id.encode('utf-8'),
                text.encode('utf-8'),
                channel_id
            )
            
            if ret == 0:
                logger.info(f"[{self.client_name}] VERIFY_VOICEPRINT成功")
            else:
                logger.error(f"[{self.client_name}] VERIFY_VOICEPRINT失败: ret={ret}")
            
            # 🎯 设置命令状态
            command.return_code = ret
            command.status = Status.PASSED if ret == 0 else Status.FAILED
            return ret
            
        except Exception as e:
            logger.error(f"[{self.client_name}] VERIFY_VOICEPRINT异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] VERIFY_VOICEPRINT异常: {e}'
            return -1

    def cancel_verify_voiceprint(self, command: DSLCommand) -> int:
        """
        取消声纹验证
        DSL格式: [TSA]CANCEL_VERIFY_VOICEPRINT
        
        Args:
            command: DSL指令对象，无参数
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            logger.info(f"[{self.client_name}] CANCEL_VERIFY_VOICEPRINT")
            ret = self.m_library.aibs_cancel_verify_voiceprint(self.m_engine)
            
            if ret == 0:
                logger.info(f"[{self.client_name}] CANCEL_VERIFY_VOICEPRINT成功")
            else:
                logger.error(f"[{self.client_name}] CANCEL_VERIFY_VOICEPRINT失败: ret={ret}")
            
            # 🎯 设置命令状态
            command.return_code = ret
            command.status = Status.PASSED if ret == 0 else Status.FAILED
            return ret
            
        except Exception as e:
            logger.error(f"[{self.client_name}] CANCEL_VERIFY_VOICEPRINT异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] CANCEL_VERIFY_VOICEPRINT异常: {e}'
            return -1

    def delete_speaker(self, command: DSLCommand) -> int:
        """
        删除声纹信息
        DSL格式: [TSA]DELETE_SPEAKER user_id
        
        Args:
            command: DSL指令对象，params=[user_id]
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            # 🎯 参数解析
            if len(command.params) < 1:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] DELETE_SPEAKER参数不足'
                return -1
            
            user_id = command.params[0]
            
            logger.info(f"[{self.client_name}] DELETE_SPEAKER: user_id={user_id}")
            ret = self.m_library.aibs_delete_speaker_info(self.m_engine, user_id.encode('utf-8'))
            
            if ret == 0:
                logger.info(f"[{self.client_name}] DELETE_SPEAKER成功")
            else:
                logger.error(f"[{self.client_name}] DELETE_SPEAKER失败: ret={ret}")
            
            # 🎯 设置命令状态
            command.return_code = ret
            command.status = Status.PASSED if ret == 0 else Status.FAILED
            return ret
            
        except Exception as e:
            logger.error(f"[{self.client_name}] DELETE_SPEAKER异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] DELETE_SPEAKER异常: {e}'
            return -1

    def get_speaker_info(self, command: DSLCommand) -> int:
        """
        获取说话人信息
        DSL格式: [TSA]GET_SPEAKER_INFO user_id
        
        Args:
            command: DSL指令对象，params=[user_id]
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            # 🎯 参数解析
            if len(command.params) < 1:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] GET_SPEAKER_INFO参数不足'
                return -1
            
            user_id = command.params[0]
            
            logger.info(f"[{self.client_name}] GET_SPEAKER_INFO: user_id={user_id}")
            self.m_library.aibs_get_speaker_info.restype = c_char_p
            result = self.m_library.aibs_get_speaker_info(self.m_engine, user_id.encode('utf-8'))
            speaker_info = result.decode('utf-8') if result else ""
            logger.info(f"[{self.client_name}] GET_SPEAKER_INFO: {speaker_info}")
            
            # 🎯 设置命令状态
            command.return_code = speaker_info
            command.status = Status.PASSED
            return 0
            
        except Exception as e:
            logger.error(f"[{self.client_name}] GET_SPEAKER_INFO异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] GET_SPEAKER_INFO异常: {e}'
            return -1

    def get_registered_speakers(self, command: DSLCommand) -> int:
        """
        获取已注册声纹列表
        DSL格式: [TSA]GET_SPEAKERS
        Args: command: DSL指令对象，无参数
        Returns: 0: 成功, -1: 失败
        """
        try:
            logger.info(f"[{self.client_name}] GET_SPEAKERS")
            self.m_library.aibs_get_registered_speaker.restype = c_char_p
            result = self.m_library.aibs_get_registered_speaker(self.m_engine)
            speakers_info = result.decode('utf-8') if result else ""
            userinfo_list = json.loads(speakers_info).get("data")
            user_list = []
            if len(userinfo_list) == 0 or userinfo_list is None:
                command.return_code = str(user_list)
                command.status = Status.PASSED
                return 0

            # 按照 create_time 进行排序
            def parse_create_time(item):
                if type(item) == dict and "create_time" in item:
                    create_time_str = item.get("create_time", "")
                    if len(create_time_str) >= 10:
                        if len(create_time_str) >= 19:
                            formatted_time = create_time_str
                        else:
                            formatted_time = create_time_str[:10] + " " + create_time_str[10:]
                        try:
                            return datetime.strptime(formatted_time, "%Y-%m-%d %H:%M:%S")
                        except ValueError:
                            return datetime.min
                return datetime.min
            
            # 对 userinfo_list 按照 create_time 升序排序
            sorted_userinfo_list = sorted(userinfo_list, key=parse_create_time)
            
            for item in sorted_userinfo_list:
                if type(item) == dict:
                    user_list.append(item.get("user_id"))
                else:
                    user_list.append(item)
            logger.info(f"[{self.client_name}] GET_SPEAKERS: {user_list}")
            
            # 🎯 设置命令状态
            command.return_code = str(user_list).replace(" ", "")
            command.status = Status.PASSED
            return 0
            
        except Exception as e:
            logger.error(f"[{self.client_name}] GET_SPEAKERS异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] GET_SPEAKERS异常: {e}'
            return -1

    def get_enroll_text(self, command: DSLCommand) -> int:
        """
        获取语音录入文本
        DSL格式: [TSA]GET_ENROLL_TEXT
        
        Args:
            command: DSL指令对象，无参数
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            logger.info(f"[{self.client_name}] GET_ENROLL_TEXT")
            self.m_library.aibs_get_enroll_text.restype = c_char_p
            result = self.m_library.aibs_get_enroll_text(self.m_engine)
            enroll_text = result.decode('utf-8') if result else ""
            logger.info(f"[{self.client_name}] GET_ENROLL_TEXT: {enroll_text}")
            
            # 🎯 设置命令状态
            command.return_code = enroll_text
            command.status = Status.PASSED
            return 0
            
        except Exception as e:
            logger.error(f"[{self.client_name}] GET_ENROLL_TEXT异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] GET_ENROLL_TEXT异常: {e}'
            return -1

    def sensitive_word_check(self, command: DSLCommand) -> int:
        """
        敏感词检查
        DSL格式: [TSA]SENSITIVE_WORD_CHECK text
        
        Args:
            command: DSL指令对象，params=[text...]
        
        Returns:
            0: 无敏感词, -9: 包含敏感词, -10: 输入超限, -1: 异常
        """
        try:
            # 🎯 参数解析
            if len(command.params) < 1:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] SENSITIVE_WORD_CHECK参数不足'
                return -1
            
            text = ' '.join(command.params)  # 支持多词文本
            
            logger.info(f"[{self.client_name}] SENSITIVE_WORD_CHECK: {text}")
            ret = self.m_library.aibs_sensitive_word_judgment(self.m_engine, text.encode('utf-8'))
            
            # 解释返回值
            if ret == 0:
                result_msg = "无敏感词"
                logger.info(f"[{self.client_name}] SENSITIVE_WORD_CHECK结果: {result_msg}")
            elif ret == -9:
                result_msg = "包含敏感词"
                logger.warning(f"[{self.client_name}] SENSITIVE_WORD_CHECK结果: {result_msg}")
            elif ret == -10:
                result_msg = "输入长度超限"
                logger.error(f"[{self.client_name}] SENSITIVE_WORD_CHECK结果: {result_msg}")
            else:
                result_msg = f"未知结果码: {ret}"
                logger.error(f"[{self.client_name}] SENSITIVE_WORD_CHECK结果: {result_msg}")
            
            # 🎯 设置命令状态
            command.return_code = ret
            command.status = Status.PASSED  # 敏感词检查总是成功，只是结果不同
            return 0
            
        except Exception as e:
            logger.error(f"[{self.client_name}] SENSITIVE_WORD_CHECK异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] SENSITIVE_WORD_CHECK异常: {e}'
            return -1

    # ==================== 其他功能接口封装 ====================
    def get_config_item(self, command: DSLCommand) -> int:
        """
        获取配置项
        DSL格式: [TSA]GET_CONFIG_ITEM filename key
        
        Args:
            command: DSL指令对象，params=[filename, key]
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            # 🎯 参数解析
            if len(command.params) < 2:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] GET_CONFIG_ITEM参数不足'
                return -1
            
            filename = command.params[0]
            key = command.params[1]
            
            logger.info(f"[{self.client_name}] GET_CONFIG_ITEM: file={filename}, key={key}")
            self.m_library.aibs_get_config_item.restype = c_char_p
            result = self.m_library.aibs_get_config_item(filename.encode('utf-8'), key.encode('utf-8'))
            config_value = result.decode('utf-8') if result else ""
            logger.info(f"[{self.client_name}] GET_CONFIG_ITEM: {key}={config_value}")
            
            # 🎯 设置命令状态
            command.return_code = config_value
            command.status = Status.PASSED
            return 0
            
        except Exception as e:
            logger.error(f"[{self.client_name}] GET_CONFIG_ITEM异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] GET_CONFIG_ITEM异常: {e}'
            return -1

    def write_log(self, command: DSLCommand) -> int:
        """
        写入日志
        DSL格式: [TSA]WRITE_LOG filename tag text [level]
        
        Args:
            command: DSL指令对象，params=[filename, tag, text, level]
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            # 🎯 参数解析
            if len(command.params) < 3:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] WRITE_LOG参数不足'
                return -1
            
            filename = command.params[0]
            tag = command.params[1]
            text = command.params[2]
            level = int(command.params[3]) if len(command.params) > 3 else 1
            
            logger.info(f"[{self.client_name}] WRITE_LOG: file={filename}, tag={tag}, level={level}")
            self.m_library.aibs_write_log(
                filename.encode('utf-8'),
                tag.encode('utf-8'),
                text.encode('utf-8'),
                level
            )
            logger.info(f"[{self.client_name}] WRITE_LOG成功")
            
            # 🎯 设置命令状态
            command.return_code = 0
            command.status = Status.PASSED
            return 0
            
        except Exception as e:
            logger.error(f"[{self.client_name}] WRITE_LOG异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] WRITE_LOG异常: {e}'
            return -1

    def config_voicelog(self, command: DSLCommand) -> int:
        """
        配置voicelog
        DSL格式: [TSA]CONFIG_VOICELOG if_open(true/false) mode
        
        Args:
            command: DSL指令对象，params=[if_open, mode]
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            # 🎯 参数解析
            if len(command.params) < 2:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] CONFIG_VOICELOG参数不足'
                return -1
            
            if_open_str = command.params[0].lower()
            if_open = if_open_str in ['true', '1', 'on', 'enable']
            mode = int(command.params[1])
            
            logger.info(f"[{self.client_name}] CONFIG_VOICELOG: if_open={if_open}, mode={mode}")
            ret = self.m_library.aibs_config_voicelog(self.m_engine, c_bool(if_open), mode)
            
            if ret == 0:
                logger.info(f"[{self.client_name}] CONFIG_VOICELOG成功")
            else:
                logger.error(f"[{self.client_name}] CONFIG_VOICELOG失败: ret={ret}")
            
            # 🎯 设置命令状态
            command.return_code = ret
            command.status = Status.PASSED if ret == 0 else Status.FAILED
            return ret
            
        except Exception as e:
            logger.error(f"[{self.client_name}] CONFIG_VOICELOG异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] CONFIG_VOICELOG异常: {e}'
            return -1
    
    def hmi(self, command: DSLCommand) -> int:
        """
        hmi指令
        DSL格式: [TSA]HMI json_file
        
        Args:
            command: DSL指令对象，params=[hmi_file_or_json]
            hmi_file_or_json: 可以是文件路径（.json）或JSON字符串
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            # 🎯 参数解析
            if len(command.params) < 1:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] HMI参数不足'
                return -1
            
            hmi_param = "".join(command.params)
            hmi_data = None
            
            # 判断参数是文件路径还是JSON字符串
            try:
                if hmi_param.endswith('.json') and os.path.exists(hmi_param):
                    with open(hmi_param, 'r', encoding='utf-8') as f:
                        hmi_data = json.load(f)
                else:
                    hmi_data = json.loads(hmi_param)
            except json.JSONDecodeError as e:
                raise ValueError(f"[{self.client_name}] 读取或解析JSON文件失败: {e}, 字符串: {hmi_param}")
            
            # 调用内部的set_event接口
            ret = self.internal_event(hmi_data)
            
            if ret == 0:
                logger.info(f"[{self.client_name}] HMI成功")
            else:
                logger.error(f"[{self.client_name}] HMI失败: ret={ret}")
            
            # 🎯 设置命令状态
            command.return_code = ret
            command.status = Status.PASSED if ret == 0 else Status.FAILED
            return ret
            
        except Exception as e:
            logger.error(f"[{self.client_name}] HMI异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] HMI异常: {e}'
            return -1

    def set_voicelog_path(self, command: DSLCommand) -> int:
        """
        设置voicelog路径
        DSL格式: [TSA]SET_VOICELOG_PATH path
        
        Args:
            command: DSL指令对象，params=[path]
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            # 🎯 参数解析
            if len(command.params) < 1:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] SET_VOICELOG_PATH参数不足'
                return -1
            
            path = command.params[0]
            
            logger.info(f"[{self.client_name}] SET_VOICELOG_PATH: {path}")
            ret = self.m_library.aibs_set_voicelog_path(self.m_engine, path.encode('utf-8'))
            
            if ret == 0:
                logger.info(f"[{self.client_name}] SET_VOICELOG_PATH成功")
            else:
                logger.error(f"[{self.client_name}] SET_VOICELOG_PATH失败: ret={ret}")
            
            # 🎯 设置命令状态
            command.return_code = ret
            command.status = Status.PASSED if ret == 0 else Status.FAILED
            return ret
            
        except Exception as e:
            logger.error(f"[{self.client_name}] SET_VOICELOG_PATH异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] SET_VOICELOG_PATH异常: {e}'
            return -1

    def get_wakeup_word(self, command: DSLCommand) -> int:
        """
        获取唤醒词
        DSL格式: [TSA]GET_WAKEUP_WORD
        
        Args:
            command: DSL指令对象，无参数
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            result = []
            logger.info(f"[{self.client_name}] GET_WAKEUP_WORD")
            self.m_library.aibs_get_wakeup_word.restype = c_char_p
            ref = self.m_library.aibs_get_wakeup_word(self.m_engine)
            data = ref.decode(encoding="utf-8")
            wakeup_list = json.loads(data).get("wakeup").get("data").get("fix_data")
            for i in wakeup_list:
                result.append(i.get("word"))
            
            ret = ",".join(result)
            logger.info(f"[{self.client_name}] GET_WAKEUP_WORD: {ret}")
            
            # 🎯 设置命令状态
            command.return_code = ret
            command.status = Status.PASSED
            return 0
            
        except Exception as e:
            logger.error(f"[{self.client_name}] GET_WAKEUP_WORD异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] GET_WAKEUP_WORD异常: {e}'
            return -1
