#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2025/11/22
# @Author  : Claude Code
# @File    : SpeechEngineClient.py

import os
import time
import json
import threading
from loguru import logger
from ctypes import *
from src.utils.common import uuid, get_timestamp, wait_gdb_attach
from src.utils.jsonUtil import JsonUtil
from src.testsuite.NANO.dsl_engine import DSLCommand, Status
from src.testsuite.NANO.client.AudioDataMixin import AudioDataMixin

# 定义Hawk引擎的回调结构体
class SpeechEngineResultSt(Structure):
    _fields_ = [
        ("time", c_ulong),
        ("flag", c_int),
        ("back", c_int),
        ("data", c_char_p)
    ]

class SpeechEngineStatusCode:
    STATUS_SPEECH_SR_INIT_SUCCESS = 1         # 初始化成功
    STATUS_SPEECH_SR_INIT_FAILED = 2          # 初始化失败
    STATUS_SPEECH_SR_START_SUCCESS = 3        # 开始会话成功
    STATUS_SPEECH_SR_START_FAILED = 4         # 开始会话失败
    STATUS_SPEECH_SR_PROCESS_DATA_FAILED = 5  # 送音频失败
    STATUS_SPEECH_SR_RESULT_SUCCESS = 6       # when the asr result gained, it occurs.
    STATUS_SPEECH_SR_RESULT_FAILED = 7        # it occurs, when getting result failed

    STATUS_SPEECH_NLU_RESULT_SUCCESS = 8      # ASR结果
    STATUS_SPEECH_SR_REALTIME_RESULT = 9      # real-time result of offline decoder would be return
    STATUS_SPEECH_NLG_RESULT_FAILED = 10      # no result when the work mode is NLG, it occurs.
    STATUS_SPEECH_NR_OUTPUT_DATA = 16         # json信号
    STATUS_SPEECH_VOICE_DB_LEVEL = 17         # voice level, range 0 to 100

    STATUS_SPEECH_SET_PERSONALIZED_INFO_SUCCESS = 48   # 个性化加载成功
    STATUS_SPEECH_SET_PERSONALIZED_INFO_FAILED = 49    # 个性化加载失败
    STATUS_SPEECH_SAVE_DATA_FAILED = 50                # data save error
    STATUS_SPEECH_DB_LOCKED = 51                       # locked db file finish, mean no longer read it

    STATUS_SPEECH_SR_SPEECH_START = 96                  # 语音信号开始
    STATUS_SPEECH_SR_SPEECH_END = 97                    # 语音信号结束
    STATUS_SPEECH_SR_SILENCE_TIMEOUT = 98               # input too much silence
    STATUS_SPEECH_SR_SPEECH_NOINPUT = 99                # 没有语音信号

    STATUS_SPEECH_WAKEUP_UNIVERSAL_SUCCESS = 112        # 主唤醒词唤醒成功
    STATUS_SPEECH_WAKEUP_SCENARIO_SUCCESS = 113         # 场景唤醒词唤醒成功
    STATUS_SPEECH_SESSION_BARGEIN = 114                 # session barge in
    STATUS_SPEECH_WAKEUP_SESSION_SIMPLE_ONE_SHOT = 115  # session instant respond

    STATUS_SPEECH_WAKEUP_SMART_LINK_SUCCESS = 128       # the third party assist wakeup success

    STATUS_SPEECH_RESULT_TIMEOUT = 144                          # get the asr or nlu result timeout
    STATUS_SPEECH_ERR_NETWORK_NOT_AVAILABLE = 145       # online decode, but network unavailable
    STATUS_SPEECH_ERR_SERVICE_NOT_AVAILABLE = 146       # online decode, network available, but VCG or PSTT service unavailable
    STATUS_SPEECH_CONNECT_NETWORK_SUCCESS = 147         # connect network successfully
    STATUS_SPEECH_CONNECT_NETWORK_FAILED = 148          # connect network failed
    STATUS_SPEECH_ERR_AUTHORIZATION_EXPIRED = 160       # authorization expires
    STATUS_SPEECH_ENGINE_RESET_SERVER_FINISHED = 161    # reset engine finished when the server was killed

    STATUS_SPEECH_SESSION_SPEAKER_ENROLL_SUCCESS = 176  # session speaker enroll
    STATUS_SPEECH_SRE_EVENT = 192                       # speaker verification event
    STATUS_SPEECH_SESSION_FINISH = 240                  # session finished, next session can be started.
    STATUS_SPEECH_HICAR_SESSION_SUCCESS = 243                  # session finished, next session can be started.


# 参数枚举
class SpeechEngineParam:
    SPEECH_ENGINE_PARAM_LINK_TYPE = 0x01
    SPEECH_ENGINE_PARAM_SEAT_SIGNAL = 0x02
    SPEECH_ENGINE_FULL_VEHICLE_SPEECH = 0x03
    SPEECH_ENGINE_PARAM_REAL_TIME_RESULT = 0x04
    SPEECH_ENGINE_PARAM_PUNC_RESULT = 0x05
    SPEECH_ENGINE_PARAM_DIGIT_CONVERT_RESULT = 0x06
    SPEECH_ENGINE_PARAM_SILENCE_DURATION = 0x07
    SPEECH_ENGINE_PARAM_SILENCE_TIMEOUT = 0x08
    SPEECH_ENGINE_PARAM_SPEECH_TIMEOUT = 0x09
    SPEECH_ENGINE_PARAM_SCENAROI_NAME = 0x0A
    SPEECH_ENGINE_PARAM_WAKEUP_SCENE = 0x0B
    SPEECH_ENGINE_PARAM_WAKEUP_DELAY_ONESHOT_DURATION = 0x0C
    SPEECH_ENGINE_PARAM_SOUND_EVENT_OPTION = 0x0D
    SPEECH_ENGINE_PARAM_EMOTION_OPTION = 0x0F
    SPEECH_ENGINE_PARAM_SR_PTT_OPTION = 0x18
    SPEECH_ENGINE_PARAM_SR_REALTIME_RESULT = 0x11
    SPEECH_ENGINE_PARAM_SR_VOICE_WAKEUP = 0x12
    SPEECH_ENGINE_PARAM_FULLTIME_OPTION = 0x13
    SPEECH_ENGINE_PARAM_SR_WAKEUP_SCENE_ENABLE = 0x14
    SPEECH_ENGINE_PARAM_SYSTEM_RESET = 0x15
    SPEECH_ENGINE_PARAM_AUDIO_FILENAME = 0x40
    SPEECH_ENGINE_PARAM_HMI_CONTEXT = 0x51


class SpeechEngineClient(AudioDataMixin):
    """
    SpeechEngine客户端实现 (HWK)
    封装了 libSpeechEngineAPIDynamic.so 的接口
    """
    audio_path = "NULL"     # 音频路径
    
    def __init__(self, client_name: str, lib_path: str):
        self.client_name = client_name
        self.lib_path = os.path.join(lib_path, "libSpeechEngineAPIDynamic.so")
        if not os.path.exists(self.lib_path):
            raise FileNotFoundError(f"libSpeechEngineAPIDynamic.so不存在: {self.lib_path}")
        self.m_library = None
        self.m_engine = None
        self.m_callback = None
        self.m_ctypes_callback = None  # 保存ctypes回调函数引用，防止GC回收
        self.m_status = 0
        self.m_timestamp = 0
        
        # 线程同步锁和条件变量
        self.m_lock = threading.Lock()
        self.m_create_cond = threading.Condition(self.m_lock)
        self.m_start_cond = threading.Condition(self.m_lock)
        self.m_finish_cond = threading.Condition(self.m_lock)
        
        SpeechEngineClient.audio_path = "NULL"
        # 初始化动态库
        self._load_library()
    
    def _load_library(self):
        """加载动态库"""
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
    
    def reset(self):
        """重置状态"""
        self.m_timestamp = 0
        SpeechEngineClient.audio_path = "NULL"
    
    def _callback_wrapper(self, status, result, arg):
        """回调函数包装器"""
        try:
            if not result or not result[0].data:
                return 0

            _data = result[0].data.decode(encoding="utf-8", errors='ignore')
            if not _data:
                return 0

            # 处理不同状态的回调
            if status in [SpeechEngineStatusCode.STATUS_SPEECH_SR_INIT_SUCCESS, 
                         SpeechEngineStatusCode.STATUS_SPEECH_SR_INIT_FAILED]:
                with self.m_lock:
                    self.m_status = status
                    self.m_create_cond.notify()
            
            elif status in [SpeechEngineStatusCode.STATUS_SPEECH_SR_START_SUCCESS, 
                           SpeechEngineStatusCode.STATUS_SPEECH_SR_START_FAILED]:
                with self.m_lock:
                    self.m_status = status
                    self.m_start_cond.notify()
            
            elif status == SpeechEngineStatusCode.STATUS_SPEECH_SESSION_FINISH:
                with self.m_lock:
                    self.m_status = status
                    self.m_finish_cond.notify()
            
            # 调用外部回调函数
            callback_func = self.m_callback
            if callback_func and status in [
                SpeechEngineStatusCode.STATUS_SPEECH_NLU_RESULT_SUCCESS,
                SpeechEngineStatusCode.STATUS_SPEECH_WAKEUP_UNIVERSAL_SUCCESS,
                SpeechEngineStatusCode.STATUS_SPEECH_WAKEUP_SCENARIO_SUCCESS,
                SpeechEngineStatusCode.STATUS_SPEECH_SR_SPEECH_START,
                SpeechEngineStatusCode.STATUS_SPEECH_SR_SPEECH_END,
                SpeechEngineStatusCode.STATUS_SPEECH_SESSION_FINISH,
            ]:
                try:
                    callback_data = json.loads(_data)
                    callback_data['audiotime'] = str(round(self.m_timestamp/1000, 2))
                    # 添加source字段
                    callback_data['source'] = 'SpeechEngine'
                    # 添加audio字段
                    callback_data['audio'] = SpeechEngineClient.audio_path
                    # 根据status设置type字段
                    if status == SpeechEngineStatusCode.STATUS_SPEECH_NLU_RESULT_SUCCESS:
                        if callback_data.get("resultType") == "asrTemp":
                            callback_data['type'] = 'SpeechASRResultTemp'
                        elif callback_data.get("resultType") == "asrResult":
                            callback_data['type'] = 'SpeechASRResult'
                        else:
                            callback_data['type'] = 'SpeechASRResult'
                    elif status in [SpeechEngineStatusCode.STATUS_SPEECH_WAKEUP_UNIVERSAL_SUCCESS, SpeechEngineStatusCode.STATUS_SPEECH_WAKEUP_SCENARIO_SUCCESS]:
                        callback_data['type'] = 'SpeechEngineWakeup'
                    elif status == SpeechEngineStatusCode.STATUS_SPEECH_SR_SPEECH_START:
                        callback_data['type'] = 'SpeechStart'
                    elif status == SpeechEngineStatusCode.STATUS_SPEECH_SR_SPEECH_END:
                        callback_data['type'] = 'SpeechEnd'
                    elif status == SpeechEngineStatusCode.STATUS_SPEECH_SESSION_FINISH:
                        callback_data['type'] = 'SessionFinish'
                    callback_func(self.client_name, status, callback_data)
                except Exception as callback_error:
                    logger.error(f"[{self.client_name}] 处理异常: {callback_error}")
            
            return 0
            
        except Exception as e:
            logger.error(f"[{self.client_name}] 回调异常: {e}")
            return -1
    
    # ==================== DSL指令处理方法 ====================
    def create(self, command: DSLCommand, decoder_config: str, log_path: str) -> int:
        """
        CREATE接口 - 创建引擎
        DSL格式: [HWK]CREATE
        
        Args:
            command: DSL指令对象，params=[config]
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            if self.m_engine is not None:
                logger.info(f"[{self.client_name}] 引擎已存在，直接返回成功")
                command.return_code = 0
                command.status = Status.PASSED
                return 0

            # 定义回调函数类型
            callback_t = CFUNCTYPE(c_int, c_int, POINTER(SpeechEngineResultSt), c_void_p)

            # 设置函数参数类型
            self.m_library.attach_speech_engine.argtypes = [c_char_p, c_char_p, callback_t, c_void_p]
            self.m_library.attach_speech_engine.restype = c_void_p

            # 创建ctypes回调函数
            if self.m_ctypes_callback is None:
                self.m_ctypes_callback = callback_t(self._callback_wrapper)

            logger.info(f"[{self.client_name}] CREATE: config={decoder_config}, log_path={log_path}")
            
            # 创建引擎
            self.m_engine = self.m_library.attach_speech_engine(
                decoder_config.encode('utf-8'),
                None,
                self.m_ctypes_callback,
                None
            )

            import time;time.sleep(2)
            self.m_library.set_start_init.argtypes = [c_void_p, c_int, c_char_p]
            self.m_library.set_start_init.restype = c_int
            self.m_library.set_start_init(self.m_engine, 2, "Start SpeechEngine".encode("utf-8"))
            self.internal_set_log_path(log_path)

            if self.m_engine is None:
                logger.error(f"[{self.client_name}] CREATE失败: engine为空")
                command.return_code = -1
                command.status = Status.FAILED
                return -1
            
            # 等待初始化完成
            with self.m_lock:
                self.m_create_cond.wait(timeout=self._get_timeout(30))
                if self.m_status == SpeechEngineStatusCode.STATUS_SPEECH_SR_INIT_SUCCESS:
                    logger.info(f"[{self.client_name}] CREATE成功")
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
        DSL格式: [HWK]START [channel_num]
        
        Args:
            command: DSL指令对象，params=[channel_num]
        
        Returns:
            0: 成功, 其他: 失败
        """
        try:
            # 🎯 参数解析
            channel_num = int(command.params[0]) if command.params else 1
            
            logger.info(f"[{self.client_name}] START: channel_num={channel_num}")
            self.reset()

            with self.m_lock:
                ret = self.m_library.start_speech_engine(self.m_engine, channel_num, None)
                self.m_start_cond.wait(timeout=self._get_timeout(10))

                if ret == 0:
                    logger.info(f"[{self.client_name}] START成功")
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
    
    def stop(self, command: DSLCommand) -> int:
        """
        STOP接口 - 停止会话
        DSL格式: [HWK]STOP
        
        Args:
            command: DSL指令对象，无参数
        
        Returns:
            0: 成功, 其他: 失败
        """
        try:
            logger.info(f"[{self.client_name}] STOP")

            with self.m_lock:
                ret = self.m_library.stop_speech_engine(self.m_engine)
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
        DSL格式: [HWK]FREE
        
        Args:
            command: DSL指令对象，无参数
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            if self.m_engine:
                logger.info(f"[{self.client_name}] FREE")
                ret = self.m_library.free_speech_engine(self.m_engine)
                
                # 重置引擎和回调函数引用
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

    def _process_pcm_chunk(self, data_chunk: bytes, delta_ms: int):
        """
        发送单包PCM数据并推进SpeechEngine实例时间戳
        """
        self.m_library.speech_engine_process_data(
            self.m_engine,
            data_chunk,
            len(data_chunk),
            c_ulong(self.m_timestamp)
        )

        self.m_timestamp += delta_ms
    
    def data(self, command: DSLCommand) -> int:
        """
        DATA接口 - 处理音频数据
        DSL格式: [HWK]DATA audio_path [frame=320] [delay=0.0] [range=[0,-1]]
        
        Args:
            command: DSL指令对象
        
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
                    elif key == 'range':
                        if value.startswith('[') and value.endswith(']'):
                            range_str = value[1:-1]
                            parts = range_str.split(',')
                            if len(parts) == 2:
                                start = float(parts[0].strip())
                                end = float(parts[1].strip()) if parts[1].strip() != '-1' else -1
                                audio_range = [start, end]
            
            logger.info(f"[{self.client_name}] DATA: {audio_path}, frame={frame_size}, range={audio_range}, delay={delay}")
            SpeechEngineClient.audio_path = audio_path

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
        DSL格式: [HWK]CANCEL
        
        Args:
            command: DSL指令对象，无参数
        
        Returns:
            0: 成功, 其他: 失败
        """
        try:
            logger.info(f"[{self.client_name}] CANCEL")
            ret = self.m_library.cancel_speech_engine(self.m_engine, c_int(0))

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
    
    def set_param(self, command: DSLCommand) -> int:
        """
        设置引擎参数
        DSL格式: [HWK]SET_PARAM param_code param_value
        
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
            
            param_code_str = command.params[0]
            param_value_str = command.params[1]
            
            # 参数代码映射
            param_mapping = {
                'SPEECH_ENGINE_PARAM_LINK_TYPE': SpeechEngineParam.SPEECH_ENGINE_PARAM_LINK_TYPE,
                'SPEECH_ENGINE_PARAM_SEAT_SIGNAL': SpeechEngineParam.SPEECH_ENGINE_PARAM_SEAT_SIGNAL,
                'SPEECH_ENGINE_FULL_VEHICLE_SPEECH': SpeechEngineParam.SPEECH_ENGINE_FULL_VEHICLE_SPEECH,
                'SPEECH_ENGINE_PARAM_REAL_TIME_RESULT': SpeechEngineParam.SPEECH_ENGINE_PARAM_REAL_TIME_RESULT,
                'SPEECH_ENGINE_PARAM_PUNC_RESULT': SpeechEngineParam.SPEECH_ENGINE_PARAM_PUNC_RESULT,
                'SPEECH_ENGINE_PARAM_DIGIT_CONVERT_RESULT': SpeechEngineParam.SPEECH_ENGINE_PARAM_DIGIT_CONVERT_RESULT,
                'SPEECH_ENGINE_PARAM_SILENCE_DURATION': SpeechEngineParam.SPEECH_ENGINE_PARAM_SILENCE_DURATION,
                'SPEECH_ENGINE_PARAM_SILENCE_TIMEOUT': SpeechEngineParam.SPEECH_ENGINE_PARAM_SILENCE_TIMEOUT,
                'SPEECH_ENGINE_PARAM_SPEECH_TIMEOUT': SpeechEngineParam.SPEECH_ENGINE_PARAM_SPEECH_TIMEOUT,
                'SPEECH_ENGINE_PARAM_SCENAROI_NAME': SpeechEngineParam.SPEECH_ENGINE_PARAM_SCENAROI_NAME,
                'SPEECH_ENGINE_PARAM_WAKEUP_SCENE': SpeechEngineParam.SPEECH_ENGINE_PARAM_WAKEUP_SCENE,
                'SPEECH_ENGINE_PARAM_WAKEUP_DELAY_ONESHOT_DURATION': SpeechEngineParam.SPEECH_ENGINE_PARAM_WAKEUP_DELAY_ONESHOT_DURATION,
                'SPEECH_ENGINE_PARAM_SOUND_EVENT_OPTION': SpeechEngineParam.SPEECH_ENGINE_PARAM_SOUND_EVENT_OPTION,
                'SPEECH_ENGINE_PARAM_EMOTION_OPTION': SpeechEngineParam.SPEECH_ENGINE_PARAM_EMOTION_OPTION,
                'SPEECH_ENGINE_PARAM_SR_PTT_OPTION': SpeechEngineParam.SPEECH_ENGINE_PARAM_SR_PTT_OPTION,
                'SPEECH_ENGINE_PARAM_SR_VOICE_WAKEUP': SpeechEngineParam.SPEECH_ENGINE_PARAM_SR_VOICE_WAKEUP,
                'SPEECH_ENGINE_PARAM_SR_WAKEUP_SCENE_ENABLE': SpeechEngineParam.SPEECH_ENGINE_PARAM_SR_WAKEUP_SCENE_ENABLE,
            }
            
            if param_code_str not in param_mapping:
                logger.error(f"[{self.client_name}] 不支持的参数代码: {param_code_str}")
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] 不支持的参数代码: {param_code_str}'
                return -1
            
            param_code = param_mapping[param_code_str]
            
            # 转换参数值类型
            param_value = self._convert_param_value(param_value_str)
            
            logger.info(f"[{self.client_name}] SET_PARAM: {param_code_str}={param_value}")
            
            # 根据参数值类型调用相应接口
            if isinstance(param_value, int):
                ret = self.m_library.set_speech_engine_param(self.m_engine, param_code, byref(c_int(param_value)))
            elif isinstance(param_value, float):
                ret = self.m_library.set_speech_engine_param(self.m_engine, param_code, byref(c_float(param_value)))
            elif isinstance(param_value, str):
                ret = self.m_library.set_speech_engine_param(self.m_engine, param_code, c_char_p(param_value.encode('utf-8')))
            elif isinstance(param_value, bool):
                ret = self.m_library.set_speech_engine_param(self.m_engine, param_code, byref(c_bool(param_value)))
            else:
                logger.error(f"[{self.client_name}] 不支持的参数值类型: {type(param_value)}")
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] 不支持的参数值类型'
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
    
    def hmi(self, command: DSLCommand) -> int:
        """
        hmi指令
        DSL格式: [HWK]HMI json_file
        command: DSL指令对象，params=[hmi_file_or_json]
        hmi_file_or_json: 可以是文件路径（.json）或JSON字符串
        Returns: 0: 成功, -1: 失败
        """
        try:
            # 🎯 参数解析
            if len(command.params) < 1:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] HMI参数不足'
                return -1
            
            hmi_param = "".join(command.params)
            hmi_origin_data = None
            
            # 判断参数是文件路径还是JSON字符串
            try:
                if hmi_param.endswith('.json') and os.path.exists(hmi_param):
                    with open(hmi_param, 'r', encoding='utf-8') as f:
                        hmi_origin_data = json.load(f)
                else:
                    hmi_origin_data = json.loads(hmi_param)
            except json.JSONDecodeError as e:
                raise ValueError(f"[{self.client_name}] 读取或解析JSON文件失败: {e}, 字符串: {hmi_param}")
            
            hmi_data = hmi_origin_data.get("data", None)
            if hmi_data is None:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] HMI json中无法获取到data字段'
                return -1
            
            # 将JSON数据转换为字符串，通过set_speech_engine_param设置HMI上下文
            hmi_json_str = json.dumps(hmi_data, ensure_ascii=False, separators=(',', ':'))
            
            logger.info(f"[{self.client_name}] HMI: {hmi_json_str}")
            
            # 调用set_speech_engine_param设置HMI上下文
            ret = self.m_library.set_speech_engine_param(
                self.m_engine, 
                SpeechEngineParam.SPEECH_ENGINE_PARAM_HMI_CONTEXT, 
                c_char_p(hmi_json_str.encode('utf-8'))
            )
            
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
    
    def internal_set_log_path(self, log_path: str) -> int:
        try:
            logger.info(f"[{self.client_name}] SET_LOG_PATH: {log_path}")
            # 设置函数参数类型
            self.m_library.set_speech_engine_log_path.argtypes = [c_void_p, c_char_p]
            self.m_library.set_speech_engine_log_path.restype = c_int
            ret = self.m_library.set_speech_engine_log_path(self.m_engine, log_path.encode('utf-8'))
            if ret != 0:
                logger.error(f"[{self.client_name}] SET_LOG_PATH 失败: ret={ret}")
            return ret
        except Exception as e:
            logger.error(f"[{self.client_name}] SET_LOG_PATH 异常: {e}")
            return -1
    
    def set_data_type(self, command: DSLCommand) -> int:
        """
        设置数据类型
        DSL格式: [HWK]SET_DATA_TYPE type
        
        Args:
            command: DSL指令对象，params=[type] (0: mono, 1: after ECNR, 2: need ECNR)
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            # 🎯 参数解析
            if not command.params:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] SET_DATA_TYPE参数不足'
                return -1
            
            data_type = int(command.params[0])
            
            logger.info(f"[{self.client_name}] SET_DATA_TYPE: {data_type}")
            
            # 设置函数参数类型
            self.m_library.speech_engine_set_data_type.argtypes = [c_void_p, c_int]
            self.m_library.speech_engine_set_data_type.restype = None
            
            self.m_library.speech_engine_set_data_type(self.m_engine, data_type)
            
            # 🎯 设置命令状态
            command.return_code = 0
            command.status = Status.PASSED
            return 0
            
        except Exception as e:
            logger.error(f"[{self.client_name}] SET_DATA_TYPE异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] SET_DATA_TYPE异常: {e}'
            return -1
    
    def update_personalized_info(self, command: DSLCommand) -> int:
        """
        更新个性化信息
        DSL格式: [HWK]UPDATE_PERSONALIZED json_ulist charset weight
        
        Args:
            command: DSL指令对象，params=[json_ulist, charset, weight]
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            # 🎯 参数解析
            if len(command.params) < 3:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] UPDATE_PERSONALIZED参数不足'
                return -1
            
            json_ulist = command.params[0]
            charset = command.params[1]
            weight = float(command.params[2])
            
            logger.info(f"[{self.client_name}] UPDATE_PERSONALIZED: weight={weight}")
            
            # 设置函数参数类型
            self.m_library.update_personalized_info.argtypes = [c_void_p, c_char_p, c_char_p, c_float]
            self.m_library.update_personalized_info.restype = c_int
            
            ret = self.m_library.update_personalized_info(
                self.m_engine,
                json_ulist.encode('utf-8'),
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
    
    def set_work_mode(self, command: DSLCommand) -> int:
        """
        设置工作模式
        DSL格式: [HWK]SET_WORKMODE mode
        
        Args:
            command: DSL指令对象，params=[mode] (0: WAKEUP, 1: ASR, 2: WAKEUP_ASR)
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            # 🎯 参数解析
            if not command.params:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] SET_WORKMODE参数不足'
                return -1
            
            mode = int(command.params[0])
            
            logger.info(f"[{self.client_name}] SET_WORKMODE: {mode}")
            
            # 设置函数参数类型
            self.m_library.set_speech_engine_work_mode.argtypes = [c_void_p, c_int]
            self.m_library.set_speech_engine_work_mode.restype = c_int
            
            ret = self.m_library.set_speech_engine_work_mode(self.m_engine, mode)
            
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
    
    def set_tts_state(self, command: DSLCommand) -> int:
        """
        设置TTS状态
        DSL格式: [HWK]SET_TTS_STATE state
        
        Args:
            command: DSL指令对象，params=[state] (true/false)
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            # 🎯 参数解析
            if not command.params:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] SET_TTS_STATE参数不足'
                return -1
            
            state_str = command.params[0].lower()
            state = state_str in ['true', '1', 'on', 'enable']
            
            logger.info(f"[{self.client_name}] SET_TTS_STATE: {state}")
            
            # 设置函数参数类型
            self.m_library.set_tts_state.argtypes = [c_void_p, c_bool]
            self.m_library.set_tts_state.restype = c_int
            
            ret = self.m_library.set_tts_state(self.m_engine, c_bool(state))
            
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
    
    def set_freetalk_state(self, command: DSLCommand) -> int:
        """
        设置自由对话状态
        DSL格式: [HWK]SET_FREETALK_STATE state [channel_id] [source]
        
        Args:
            command: DSL指令对象，params=[state, channel_id, source]
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            # 🎯 参数解析
            if not command.params:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] SET_FREETALK_STATE参数不足'
                return -1
            
            state_str = command.params[0].lower()
            state = state_str in ['true', '1', 'on', 'enable']
            channel_id = int(command.params[1]) if len(command.params) > 1 else 0
            source = int(command.params[2]) if len(command.params) > 2 else 0  # 0: NLU, 1: LCS
            
            logger.info(f"[{self.client_name}] SET_FREETALK_STATE: state={state}, channel_id={channel_id}, source={source}")
            
            # 设置函数参数类型
            self.m_library.set_freetalk_state.argtypes = [c_void_p, c_bool, c_int, c_int]
            self.m_library.set_freetalk_state.restype = c_int
            
            ret = self.m_library.set_freetalk_state(self.m_engine, c_bool(state), c_int(channel_id), c_int(source))
            
            if ret == 0:
                logger.info(f"[{self.client_name}] SET_FREETALK_STATE成功")
            else:
                logger.error(f"[{self.client_name}] SET_FREETALK_STATE失败: ret={ret}")
            
            # 🎯 设置命令状态
            command.return_code = ret
            command.status = Status.PASSED if ret == 0 else Status.FAILED
            return ret
            
        except Exception as e:
            logger.error(f"[{self.client_name}] SET_FREETALK_STATE异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] SET_FREETALK_STATE异常: {e}'
            return -1
    
    def add_wakeup_word(self, command: DSLCommand) -> int:
        """
        添加唤醒词
        DSL格式: [HWK]ADD_WAKEUP_WORD lang word threshold
        
        Args:
            command: DSL指令对象，params=[lang, word, threshold]
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            # 🎯 参数解析
            if len(command.params) < 3:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] ADD_WAKEUP_WORD参数不足'
                return -1
            
            lang = command.params[0]
            word = command.params[1]
            threshold = float(command.params[2])
            
            logger.info(f"[{self.client_name}] ADD_WAKEUP_WORD: {word}, threshold={threshold}")
            
            # 设置函数参数类型
            self.m_library.add_wakeup_word.argtypes = [c_void_p, c_char_p, c_char_p, c_float]
            self.m_library.add_wakeup_word.restype = c_int
            
            ret = self.m_library.add_wakeup_word(
                self.m_engine,
                lang.encode('utf-8'),
                word.encode('utf-8'),
                c_float(threshold)
            )
            
            if ret == 0:
                logger.info(f"[{self.client_name}] ADD_WAKEUP_WORD成功")
            else:
                logger.error(f"[{self.client_name}] ADD_WAKEUP_WORD失败: ret={ret}")
            
            # 🎯 设置命令状态
            command.return_code = ret
            command.status = Status.PASSED if ret == 0 else Status.FAILED
            return ret
            
        except Exception as e:
            logger.error(f"[{self.client_name}] ADD_WAKEUP_WORD异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] ADD_WAKEUP_WORD异常: {e}'
            return -1
    
    def get_wakeup_term(self, command: DSLCommand) -> str:
        """
        获取唤醒词
        DSL格式: [HWK]GET_WAKEUP_TERM lang type
        
        Args:
            command: DSL指令对象，params=[lang, type]
        
        Returns:
            唤醒词字符串
        """
        try:
            # 🎯 参数解析
            if len(command.params) < 2:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] GET_WAKEUP_TERM参数不足'
                return ""
            
            lang = command.params[0]
            word_type = int(command.params[1])
            
            logger.info(f"[{self.client_name}] GET_WAKEUP_TERM: lang={lang}, type={word_type}")
            
            # 设置函数参数类型
            self.m_library.get_wakeup_term.argtypes = [c_void_p, c_char_p, c_int]
            self.m_library.get_wakeup_term.restype = c_char_p
            
            result = self.m_library.get_wakeup_term(
                self.m_engine,
                lang.encode('utf-8'),
                word_type
            )
            
            if result:
                wakeup_word = result.decode('utf-8')
                logger.info(f"[{self.client_name}] GET_WAKEUP_TERM成功: {wakeup_word}")
                # 🎯 设置命令状态
                command.return_code = wakeup_word
                command.status = Status.PASSED
                return wakeup_word
            else:
                logger.error(f"[{self.client_name}] GET_WAKEUP_TERM失败: 返回空")
                command.return_code = ""
                command.status = Status.FAILED
                return ""
            
        except Exception as e:
            logger.error(f"[{self.client_name}] GET_WAKEUP_TERM异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] GET_WAKEUP_TERM异常: {e}'
            return ""
    
    def set_wakeup_word_enable(self, command: DSLCommand) -> int:
        """
        设置唤醒词使能
        DSL格式: [HWK]SET_WAKEUP_ENABLE word option
        
        Args:
            command: DSL指令对象，params=[word, option] (true/false)
        
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
            option_str = command.params[1].lower()
            option = option_str in ['true', '1', 'on', 'enable']
            
            logger.info(f"[{self.client_name}] SET_WAKEUP_ENABLE: {word}, option={option}")
            
            # 设置函数参数类型
            self.m_library.set_wakeup_word_enable.argtypes = [c_void_p, c_char_p, c_bool]
            self.m_library.set_wakeup_word_enable.restype = c_int
            
            ret = self.m_library.set_wakeup_word_enable(
                self.m_engine,
                word.encode('utf-8'),
                c_bool(option)
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
    
    def set_sre_request(self, command: DSLCommand) -> int:
        """
        设置声纹请求
        DSL格式: [HWK]SET_SRE_REQUEST json_buffer
        
        Args:
            command: DSL指令对象，params=[json_buffer]
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            # 🎯 参数解析
            if not command.params:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] SET_SRE_REQUEST参数不足'
                return -1
            
            json_buffer = command.params[0]
            
            logger.info(f"[{self.client_name}] SET_SRE_REQUEST: {json_buffer}")
            
            # 设置函数参数类型
            self.m_library.set_speech_engine_sre_request.argtypes = [c_void_p, c_char_p]
            self.m_library.set_speech_engine_sre_request.restype = c_int
            
            ret = self.m_library.set_speech_engine_sre_request(
                self.m_engine,
                json_buffer.encode('utf-8')
            )
            
            if ret == 0:
                logger.info(f"[{self.client_name}] SET_SRE_REQUEST成功")
            else:
                logger.error(f"[{self.client_name}] SET_SRE_REQUEST失败: ret={ret}")
            
            # 🎯 设置命令状态
            command.return_code = ret
            command.status = Status.PASSED if ret == 0 else Status.FAILED
            return ret
            
        except Exception as e:
            logger.error(f"[{self.client_name}] SET_SRE_REQUEST异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] SET_SRE_REQUEST异常: {e}'
            return -1
    
    def open_voice_input(self, command: DSLCommand) -> int:
        """
        打开语音输入
        DSL格式: [HWK]OPEN_VOICE_INPUT param
        
        Args:
            command: DSL指令对象，params=[param]
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            # 🎯 参数解析
            if not command.params:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] OPEN_VOICE_INPUT参数不足'
                return -1
            
            param = command.params[0]
            
            logger.info(f"[{self.client_name}] OPEN_VOICE_INPUT: {param}")
            
            # 设置函数参数类型
            self.m_library.speech_engine_open_voice_input.argtypes = [c_void_p, c_char_p]
            self.m_library.speech_engine_open_voice_input.restype = c_int
            
            ret = self.m_library.speech_engine_open_voice_input(
                self.m_engine,
                param.encode('utf-8')
            )
            
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
        关闭语音输入
        DSL格式: [HWK]CLOSE_VOICE_INPUT
        
        Args:
            command: DSL指令对象，无参数
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            logger.info(f"[{self.client_name}] CLOSE_VOICE_INPUT")
            
            # 设置函数参数类型
            self.m_library.speech_engine_close_voice_input.argtypes = [c_void_p]
            self.m_library.speech_engine_close_voice_input.restype = c_int
            
            ret = self.m_library.speech_engine_close_voice_input(self.m_engine)
            
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
    
    def set_voice_wakeup_option(self, command: DSLCommand) -> int:
        """
        设置语音唤醒选项
        DSL格式: [HWK]SET_VOICE_WAKEUP_OPTION option
        
        Args:
            command: DSL指令对象，params=[option] (0:关闭, 1:打开)
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            # 🎯 参数解析
            if not command.params:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] SET_VOICE_WAKEUP_OPTION参数不足'
                return -1
            
            option = int(command.params[0])
            
            logger.info(f"[{self.client_name}] SET_VOICE_WAKEUP_OPTION: {option}")
            
            # 设置函数参数类型
            self.m_library.speech_engine_set_voice_wakeup_option.argtypes = [c_void_p, c_int]
            self.m_library.speech_engine_set_voice_wakeup_option.restype = c_int
            
            ret = self.m_library.speech_engine_set_voice_wakeup_option(self.m_engine, c_int(option))
            
            if ret == 0:
                logger.info(f"[{self.client_name}] SET_VOICE_WAKEUP_OPTION成功")
            else:
                logger.error(f"[{self.client_name}] SET_VOICE_WAKEUP_OPTION失败: ret={ret}")
            
            # 🎯 设置命令状态
            command.return_code = ret
            command.status = Status.PASSED if ret == 0 else Status.FAILED
            return ret
            
        except Exception as e:
            logger.error(f"[{self.client_name}] SET_VOICE_WAKEUP_OPTION异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] SET_VOICE_WAKEUP_OPTION异常: {e}'
            return -1
    
    def set_language_info(self, command: DSLCommand) -> int:
        """
        设置语言信息
        DSL格式: [HWK]SET_LANGUAGE_INFO info
        
        Args:
            command: DSL指令对象，params=[info]
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            # 🎯 参数解析
            if not command.params:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] SET_LANGUAGE_INFO参数不足'
                return -1
            
            lang = command.params[0]

            if lang not in ["cmn", "eng"]:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] SET_LANGUAGE_INFO 参数错误: {lang}'
                return -1

            json_data = json.dumps({"wakeup":[lang],"asr":[lang]}, ensure_ascii=False, separators=(',', ':'))
            logger.info(f"[{self.client_name}] SET_LANGUAGE_INFO: {json_data}")
            
            # 设置函数参数类型
            self.m_library.speech_engine_set_language_info.argtypes = [c_void_p, c_char_p]
            self.m_library.speech_engine_set_language_info.restype = c_int
            
            ret = self.m_library.speech_engine_set_language_info(
                self.m_engine,
                json_data.encode('utf-8')
            )
            
            if ret == 0:
                logger.info(f"[{self.client_name}] SET_LANGUAGE_INFO成功")
            else:
                logger.error(f"[{self.client_name}] SET_LANGUAGE_INFO失败: ret={ret}")
            
            # 🎯 设置命令状态
            command.return_code = ret
            command.status = Status.PASSED if ret == 0 else Status.FAILED
            return ret
            
        except Exception as e:
            logger.error(f"[{self.client_name}] SET_LANGUAGE_INFO异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] SET_LANGUAGE_INFO异常: {e}'
            return -1
    
    def config_voicelog(self, command: DSLCommand) -> int:
        """
        配置语音日志
        DSL格式: [HWK]CONFIG_VOICELOG if_open mode
        
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
            
            # 设置函数参数类型
            self.m_library.speech_config_voicelog.argtypes = [c_void_p, c_bool, c_int]
            self.m_library.speech_config_voicelog.restype = c_int
            
            ret = self.m_library.speech_config_voicelog(self.m_engine, c_bool(if_open), c_int(mode))
            
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
    
    def set_voicelog_path(self, command: DSLCommand) -> int:
        """
        设置语音日志路径
        DSL格式: [HWK]SET_VOICELOG_PATH path
        
        Args:
            command: DSL指令对象，params=[path]
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            # 🎯 参数解析
            if not command.params:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] SET_VOICELOG_PATH参数不足'
                return -1
            
            path = command.params[0]
            
            logger.info(f"[{self.client_name}] SET_VOICELOG_PATH: {path}")
            
            # 设置函数参数类型
            self.m_library.speech_set_voicelog_path.argtypes = [c_void_p, c_char_p]
            self.m_library.speech_set_voicelog_path.restype = c_int
            
            ret = self.m_library.speech_set_voicelog_path(self.m_engine, path.encode('utf-8'))
            
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
    
    def set_vr_silence_timeout(self, command: DSLCommand) -> int:
        """
        设置VR静音超时
        DSL格式: [HWK]SET_VR_SILENCE_TIMEOUT channel_id duration
        
        Args:
            command: DSL指令对象，params=[channel_id, duration]
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            # 🎯 参数解析
            if len(command.params) < 2:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] SET_VR_SILENCE_TIMEOUT参数不足'
                return -1
            
            channel_id = int(command.params[0])
            duration = int(command.params[1])
            
            logger.info(f"[{self.client_name}] SET_VR_SILENCE_TIMEOUT: channel_id={channel_id}, duration={duration}")
            
            # 设置函数参数类型
            self.m_library.set_vr_silence_timeout.argtypes = [c_void_p, c_int, c_int]
            self.m_library.set_vr_silence_timeout.restype = c_int
            
            ret = self.m_library.set_vr_silence_timeout(self.m_engine, c_int(channel_id), c_int(duration))
            
            if ret == 0:
                logger.info(f"[{self.client_name}] SET_VR_SILENCE_TIMEOUT成功")
            else:
                logger.error(f"[{self.client_name}] SET_VR_SILENCE_TIMEOUT失败: ret={ret}")
            
            # 🎯 设置命令状态
            command.return_code = ret
            command.status = Status.PASSED if ret == 0 else Status.FAILED
            return ret
            
        except Exception as e:
            logger.error(f"[{self.client_name}] SET_VR_SILENCE_TIMEOUT异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] SET_VR_SILENCE_TIMEOUT异常: {e}'
            return -1
    
    def set_link_type(self, command: DSLCommand) -> int:
        """
        设置连接类型
        DSL格式: [HWK]SET_LINK_TYPE type
        
        Args:
            command: DSL指令对象，params=[type]
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            # 🎯 参数解析
            if not command.params:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] SET_LINK_TYPE参数不足'
                return -1
            
            link_type = int(command.params[0])
            
            logger.info(f"[{self.client_name}] SET_LINK_TYPE: {link_type}")
            
            # 设置函数参数类型
            self.m_library.speech_set_link_type.argtypes = [c_void_p, c_int]
            self.m_library.speech_set_link_type.restype = c_int
            
            ret = self.m_library.speech_set_link_type(self.m_engine, c_int(link_type))
            
            if ret == 0:
                logger.info(f"[{self.client_name}] SET_LINK_TYPE成功")
            else:
                logger.error(f"[{self.client_name}] SET_LINK_TYPE失败: ret={ret}")
            
            # 🎯 设置命令状态
            command.return_code = ret
            command.status = Status.PASSED if ret == 0 else Status.FAILED
            return ret
            
        except Exception as e:
            logger.error(f"[{self.client_name}] SET_LINK_TYPE异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] SET_LINK_TYPE异常: {e}'
            return -1
    
    def set_mic_status(self, command: DSLCommand) -> int:
        """
        设置MIC状态
        DSL格式: [HWK]SET_MIC_STATUS status
        
        Args:
            command: DSL指令对象，params=[status]
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            # 🎯 参数解析
            if not command.params:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] SET_MIC_STATUS参数不足'
                return -1
            
            status = int(command.params[0])
            
            logger.info(f"[{self.client_name}] SET_MIC_STATUS: {status}")
            
            # 设置函数参数类型
            self.m_library.speech_set_mic_status.argtypes = [c_void_p, c_int]
            self.m_library.speech_set_mic_status.restype = c_int
            
            ret = self.m_library.speech_set_mic_status(self.m_engine, c_int(status))
            
            if ret == 0:
                logger.info(f"[{self.client_name}] SET_MIC_STATUS成功")
            else:
                logger.error(f"[{self.client_name}] SET_MIC_STATUS失败: ret={ret}")
            
            # 🎯 设置命令状态
            command.return_code = ret
            command.status = Status.PASSED if ret == 0 else Status.FAILED
            return ret
            
        except Exception as e:
            logger.error(f"[{self.client_name}] SET_MIC_STATUS异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] SET_MIC_STATUS异常: {e}'
            return -1
    
    def start_record(self, command: DSLCommand) -> int:
        """
        开始录音
        DSL格式: [HWK]START_RECORD
        
        Args:
            command: DSL指令对象，无参数
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            logger.info(f"[{self.client_name}] START_RECORD")
            
            # 设置函数参数类型
            self.m_library.speech_start_record.argtypes = [c_void_p]
            self.m_library.speech_start_record.restype = c_int
            
            ret = self.m_library.speech_start_record(self.m_engine)
            
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
        DSL格式: [HWK]STOP_RECORD
        
        Args:
            command: DSL指令对象，无参数
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            logger.info(f"[{self.client_name}] STOP_RECORD")
            
            # 设置函数参数类型
            self.m_library.speech_stop_record.argtypes = [c_void_p]
            self.m_library.speech_stop_record.restype = c_int
            
            ret = self.m_library.speech_stop_record(self.m_engine)
            
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
    
    def sensitive_word_check(self, command: DSLCommand) -> int:
        """
        敏感词检测
        DSL格式: [HWK]SENSITIVE_WORD_CHECK words
        
        Args:
            command: DSL指令对象，params=[words]
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            # 🎯 参数解析
            if not command.params:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] SENSITIVE_WORD_CHECK参数不足'
                return -1
            
            words = ' '.join(command.params)
            
            logger.info(f"[{self.client_name}] SENSITIVE_WORD_CHECK: {words}")
            
            # 设置函数参数类型
            self.m_library.sensitive_word_judgment.argtypes = [c_void_p, c_char_p]
            self.m_library.sensitive_word_judgment.restype = c_int
            
            ret = self.m_library.sensitive_word_judgment(
                self.m_engine,
                words.encode('utf-8')
            )
            
            if ret == 0:
                logger.info(f"[{self.client_name}] SENSITIVE_WORD_CHECK成功")
            else:
                logger.error(f"[{self.client_name}] SENSITIVE_WORD_CHECK失败: ret={ret}")
            
            # 🎯 设置命令状态
            command.return_code = ret
            command.status = Status.PASSED if ret == 0 else Status.FAILED
            return ret
            
        except Exception as e:
            logger.error(f"[{self.client_name}] SENSITIVE_WORD_CHECK异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] SENSITIVE_WORD_CHECK异常: {e}'
            return -1
    
    def set_car_type(self, command: DSLCommand) -> int:
        """
        设置车型
        DSL格式: [HWK]SET_CAR_TYPE car_type
        
        Args:
            command: DSL指令对象，params=[car_type]
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            # 🎯 参数解析
            if not command.params:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] SET_CAR_TYPE参数不足'
                return -1
            
            car_type = ' '.join(command.params)
            
            logger.info(f"[{self.client_name}] SET_CAR_TYPE: {car_type}")
            
            # 设置函数参数类型
            self.m_library.speech_set_car_type.argtypes = [c_void_p, c_char_p]
            self.m_library.speech_set_car_type.restype = c_int
            
            ret = self.m_library.speech_set_car_type(
                self.m_engine,
                car_type.encode('utf-8')
            )
            
            if ret == 0:
                logger.info(f"[{self.client_name}] SET_CAR_TYPE成功")
            else:
                logger.error(f"[{self.client_name}] SET_CAR_TYPE失败: ret={ret}")
            
            # 🎯 设置命令状态
            command.return_code = ret
            command.status = Status.PASSED if ret == 0 else Status.FAILED
            return ret
            
        except Exception as e:
            logger.error(f"[{self.client_name}] SET_CAR_TYPE异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] SET_CAR_TYPE异常: {e}'
            return -1
    
    def set_sre_enable_option(self, command: DSLCommand) -> int:
        """
        设置声纹使能选项
        DSL格式: [HWK]SET_SRE_ENABLE_OPTION option
        
        Args:
            command: DSL指令对象，params=[option] (0:关闭, 1:开启)
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            # 🎯 参数解析
            if not command.params:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] SET_SRE_ENABLE_OPTION参数不足'
                return -1
            
            option = int(command.params[0])
            
            logger.info(f"[{self.client_name}] SET_SRE_ENABLE_OPTION: {option}")
            
            # 设置函数参数类型
            self.m_library.set_sre_enable_option.argtypes = [c_void_p, c_int]
            self.m_library.set_sre_enable_option.restype = c_int
            
            ret = self.m_library.set_sre_enable_option(self.m_engine, c_int(option))
            
            if ret == 0:
                logger.info(f"[{self.client_name}] SET_SRE_ENABLE_OPTION成功")
            else:
                logger.error(f"[{self.client_name}] SET_SRE_ENABLE_OPTION失败: ret={ret}")
            
            # 🎯 设置命令状态
            command.return_code = ret
            command.status = Status.PASSED if ret == 0 else Status.FAILED
            return ret
            
        except Exception as e:
            logger.error(f"[{self.client_name}] SET_SRE_ENABLE_OPTION异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] SET_SRE_ENABLE_OPTION异常: {e}'
            return -1
    