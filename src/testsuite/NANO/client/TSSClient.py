import os
import json
import threading
from typing import Optional, Callable
from src.utils.common import wait_gdb_attach
from ctypes import *
from loguru import logger
from src.testsuite.NANO.dsl_engine import DSLCommand, Status
from src.testsuite.NANO.client.AudioDataMixin import AudioDataMixin

# ──────────────────────────────────────────────────────────────
# AIBS 引擎 ctypes 封装（libAIBS_dynamic.so）
# ──────────────────────────────────────────────────────────────

class AIBSEngineResultSt(Structure):
    """对应 aibs_engine_api.h 中的 aibs_engine_result_st"""
    _fields_ = [
        ("time", c_ulong),
        ("flag", c_int),
        ("data", c_void_p),  # char*，NR 时为原始 PCM，用 string_at 按长度读取
    ]

class AIBSDataSt(Structure):
    """对应 aibs_engine_api.h 中的 aibs_data_st"""
    _fields_ = [
        ("mic_data", c_char_p * 4),
        ("ref_data", c_char_p),
        ("output", c_char_p),
        ("direction", c_int),
    ]


class AIBSEngineStatusCode:
    """AIBS 回调状态码（对应 aibs_engine_api.h）"""
    STATUS_AIBS_SR_INIT_SUCCESS = 0x01
    STATUS_AIBS_SR_INIT_FAILED = 0x02
    STATUS_AIBS_SR_START_SUCCESS = 0x03
    STATUS_AIBS_SR_START_FAILED = 0x04
    STATUS_AIBS_SR_SESSION_FINISH = 0xF0  # 会话结束信号
    STATUS_AIBS_NR_OUTPUT_DATA = 0x10   # 降噪后输出音频
    STATUS_AIBS_SR_SPEECH_START = 0x60   # 语音开始
    STATUS_AIBS_SR_SPEECH_END = 0x61    # 语音结束
    STATUS_AIBS_WAKEUP_UNIVERSAL_SUCCESS = 0x70   # 主唤醒词唤醒成功
    STATUS_AIBS_WAKEUP_SCENARIO_SUCCESS  = 0x71   # 场景唤醒词唤醒成功
    STATUS_AIBS_SESSION_BARGEIN = 0x72   # 会话侵入
    STATUS_AIBS_WAKEUP_SESSION_SIMPLE_ONE_SHOT = 0x73   # 会话简单单次唤醒
    STATUS_AIBS_WAKEUP_SMART_LINK_SUCCESS = 0x80   # 智能链接唤醒成功
    STATUS_AIBS_RESULT_TIMEOUT = 0x90   # 结果超时

class AIBSEngineParam:
    """AIBS 引擎参数（对应 aibs_engine_api.h）"""
    ENGINE_PARAM_DEVICE_ID               = 0x01  # device id, as long as the only device can be distinguished. 
    ENGINE_PARAM_CONFIDENCE_THRESHOLD    = 0x02  # if confidence lower than this given value,will output result by effective integration
    ENGINE_PARAM_HYBRID_AIBS_STRATEGY    = 0x03  # set decoder's strategy, 1: only offline, 2: only online, 3:offline first, 4:onlne first, 5:net available, online, or offline
    ENGINE_PARAM_FULL_VEHICLE_SPEECH     = 0x04  # set full vehicle option: True(1) or False(0)
    ENGINE_PARAM_SR_REAL_TIME_RESULT     = 0x05  # real-time resule switch
    ENGINE_PARAM_SR_PUNCT_RESULT         = 0x06  # punctuation switch
    ENGINE_PARAM_SR_DIGIT_CONVERT_RESULT = 0x07  # digit convert func switch
    ENGINE_PARAM_SR_DETECT_SPEECH_END    = 0x09  # vad end switch
    ENGINE_PARAM_SR_SILENCE_TIMEOUT      = 0x0A  #  set vad silence timeout
    ENGINE_PARAM_SR_SPEECH_TIMEOUT       = 0x0B  # set speech timeout
    ENGINE_PARAM_SR_SR_SILENCE_DURATION  = 0x0C  # set silence duration
    ENGINE_PARAM_SR_KEYWORD_SPEECH_TIMEOUT   = 0x0D  # set keyword speech timeout
    ENGINE_PARAM_SR_REFUSAL_RATE_FACTOR  = 0x15     # set the ability to recognize words which not in the model
    ENGINE_PARAM_SR_DIALOGUE_KEYWORD_CONFIRM = 0x16 # set dialogue keyword confirm
    ENGINE_PARAM_SR_DIALOGUE_KEYWORD_CHOICE  = 0x17 #set dialogue keyword choice
    ENGINE_PARAM_SR_PTT_OPTION           = 0x18,
    ENGINE_PARAM_SR_VAD_STATE_OPTION     = 0x19  # speech signal switch ,0 No callback speech signal,1 callback speech start and speech end signal
    ENGINE_PARAM_SR_KD_OPTION            = 0x20  # keyword detection switch,To be effective under link-type is carplay, both speech signal switch and VAD switch are true
                                                # 0 : Return a speech signal according to the default speech trans length
                                                # 1 : Return a speech signal according to the speech trans time of 50ms
    ENGINE_PARAM_SR_DATA_PATH            = 0x31 # set data path
    ENGINE_PARAM_SERVICE_HOST            = 0x33 # set engine's ip address and port, for example "api.pachira.cn:80"
    ENGINE_PARAM_SR_PLAIN_RESULT         = 0x34 # set engine's callback result:
                                                # True(1) : only callback text info
                                                # False(0): callback text info and confidence 
    ENGINE_PARAM_SR_SCENARIO_NAME        = 0x35 # set scenario name for asr.
    ENGINE_PARAM_SR_SEAT_SIGNAL          = 0x36 # set seat signal
                                                # 0 Nobody
                                                # 1 Driver
                                                # 2 Passenger
                                                # 4 Middle Right
                                                # 8 Middle Left
                                                # 16 Rear Right
                                                # 32 Rear Left
    ENGINE_PARAM_NLP_DIALOGUE_CONTEXT    = 0x50 #set nlp parameters in a cJson
    ENGINE_PARAM_SESSION_LINK_TYPE       = 0x61 #link type, 1 : carplay (siri)
                                                #            2 : carlife (xiaoduxiaodu)
    ENGINE_PARAM_SESSION_DIALOG_MODE     = 0x62 # dialog mode, 0: "NORMAL"
                                                #              1: "DICTATION"
    ENGINE_PARAM_SESSION_BARGE_IN_OPTION = 0x63 # if it supports barge-in event during playing tts or not
                                                # if it is not set(value == 0), user can't input anything util finish play tts
                                                # default value is 1.
    ENGINE_PARAM_WAKEUP_SCENE            = 0x70 # set wakeup scene, param type is uint32_t
    ENGINE_PARAM_WAKEUP_LEVEL            = 0x71 # wanke up threshold setting
    ENGINE_PARAM_WAKEUP_PLAIN_RESULT     = 0x72 # set engine's wakeup callback result: 
                                                # False(0): callback text and confidence
                                                # True(1) : only callback text
    ENGINE_PARAM_ONLINE_SERVICE_EXPIRED  = 0x73 # whether the service is expired
                                                # 0 : no expiration
                                                # 1 : expired
    ENGINE_PARAM_WAKEUP_DELAY_ONESHOT_DURATION = 0x74


class TSSClient(AudioDataMixin):

    audio_path = "NULL"
    # 通道数映射
    CHANNEL_MAP = {
        '01h': 0,
        '02h': 1,
        '03h': 2,
        '04h': 3,
    }
    def __init__(self, client_name: str, lib_path: str, config=None):
        self.client_name = client_name
        self.m_callback: Optional[Callable] = None
        self._lib_path = lib_path
        self._decoder_config = getattr(config, "decoder_config", "") if config else ""
        # ── AIBS 引擎（libAIBS_dynamic.so）──
        self._aibs_lib = None
        self._aibs_client = None  # create_aibs_client 返回的句柄
        self._aibs_ctypes_callback = None
        self._aibs_speech_started = False   # 是否已收到 SPEECH_START
        self._aibs_buffer_lock = threading.Lock()
        self._aibs_create_ready = threading.Event()
        self._aibs_create_status = 0
        self._aibs_start_ready = threading.Event()
        self._aibs_finish_ready = threading.Event()
        self._aibs_start_status = 0
        self._aibs_frame_size = 320
        self._aibs_input_channels = 1
        self._aibs_sample_width = 2
        self._aibs_use_frame_data = False
        # 送入 process_data 的毫秒时间戳（与 SpeechEngineClient.m_timestamp 一致，每包累加 delta_ms）
        self._aibs_process_timestamp = 0
        if not self._load_aibs_library():
            logger.error("[TSS] 无法加载 libAIBS_dynamic.so")
            raise Exception("[TSS] 无法加载 libAIBS_dynamic.so")

    
    def _load_aibs_library(self) -> bool:
        """加载 libAIBS_dynamic.so"""
        lib_path = os.path.join(self._lib_path, "libAIBS_dynamic.so")
        if not os.path.exists(lib_path):
            logger.error(f"[TSS] 未找到 libAIBS_dynamic.so，路径：{lib_path}")
            return False
        try:
            self._aibs_lib = cdll.LoadLibrary(lib_path)
            if os.environ.get("GDB_OPTION") == "1":
                wait_gdb_attach(self.client_name, os.getpid())
            logger.info(f"[TSS] 加载 AIBS 库成功：{lib_path}")
            return True
        except Exception as e:
            logger.warning(f"[TSS] 加载 {lib_path} 失败：{e}")
            return False

    def set_callback(self, callback: Callable):
        self.m_callback = callback

    def _aibs_callback_wrapper(self, status: int, result, arg) -> int:
        """
        AIBS 引擎回调。在 C 线程中调用。
        """
        try:
            if status in (AIBSEngineStatusCode.STATUS_AIBS_SR_INIT_SUCCESS, AIBSEngineStatusCode.STATUS_AIBS_SR_INIT_FAILED):
                self._aibs_create_status = status
                self._aibs_create_ready.set()
                return 0
            if status in (AIBSEngineStatusCode.STATUS_AIBS_SR_START_SUCCESS, AIBSEngineStatusCode.STATUS_AIBS_SR_START_FAILED):
                self._aibs_start_status = status
                self._aibs_start_ready.set()
                return 0
            
            if status == AIBSEngineStatusCode.STATUS_AIBS_SR_SESSION_FINISH:
                self._aibs_finish_ready.set()
                return 0

            # 调用外部回调函数
            callback_func = self.m_callback
            if callback_func and status in [
                AIBSEngineStatusCode.STATUS_AIBS_SR_SPEECH_START,
                AIBSEngineStatusCode.STATUS_AIBS_SR_SPEECH_END,
                AIBSEngineStatusCode.STATUS_AIBS_WAKEUP_UNIVERSAL_SUCCESS,
            ]:
                try:
                    if not result or not result.contents:
                        return 0
                    addr = result.contents.data
                    raw = string_at(addr)
                    text = raw.decode("utf-8", errors="ignore").strip()
                    data = json.loads(text)
                    speaker = data['speaker']
                    channel = TSSClient.CHANNEL_MAP.get(speaker, 0)
                    payload = {"source": "TSS", "type": "","channel": channel, "data": {}, "audio": TSSClient.audio_path, "audiotime": str(round(self._aibs_process_timestamp/1000, 2))}
                    if status == AIBSEngineStatusCode.STATUS_AIBS_SR_SPEECH_START:
                        payload['type'] = 'SpeechStart'
                        payload['data'] = data
                    elif status == AIBSEngineStatusCode.STATUS_AIBS_SR_SPEECH_END:
                        payload['type'] = 'SpeechEnd'
                        payload['data'] = data
                    elif status == AIBSEngineStatusCode.STATUS_AIBS_WAKEUP_UNIVERSAL_SUCCESS:
                        payload['type'] = 'TSSAIBSWakeup'
                        data['end_time'] = data['start_time'] + data['duration']
                        payload['data'] = data
                    callback_func(self.client_name, 0, payload, channel, payload['type'])
                except Exception as e:
                    logger.error(f"[{self.client_name}] 处理异常: {e}")
            return 0
        except Exception as e:
            logger.error(f"[TSS] AIBS 回调异常：{e}")
            return -1

    def _process_pcm_chunk(self, data_chunk: bytes, delta_ms: int):
        """AudioDataMixin 回调：将 PCM 块送入 AIBS process_data。"""
        if not self._aibs_lib or not self._aibs_client:
            logger.error("[TSS] _process_pcm_chunk 失败：AIBS 未就绪")
            return

        if self._aibs_use_frame_data:
            ret = self._process_frame_data_chunk(data_chunk)
        else:
            self._aibs_lib.process_data.argtypes = [c_void_p, c_char_p, c_int, c_ulong]
            self._aibs_lib.process_data.restype = c_int
            ret = self._aibs_lib.process_data(
                self._aibs_client,
                data_chunk,
                len(data_chunk),
                c_ulong(self._aibs_process_timestamp),
            )
        if ret != 0:
            api_name = "process_frame_data" if self._aibs_use_frame_data else "process_data"
            logger.warning(f"[TSS] {api_name} 返回 {ret}")
        self._aibs_process_timestamp += delta_ms

    def _process_frame_data_chunk(self, data_chunk: bytes) -> int:
        """将多通道交织PCM拆分为非交织通道数据，并调用 process_frame_data。"""
        channels = self._aibs_input_channels
        sample_width = self._aibs_sample_width
        if channels not in (2, 4):
            logger.error(f"[TSS] process_frame_data 仅支持2/4通道，当前={channels}")
            return -1
        frame_bytes = channels * sample_width
        if frame_bytes <= 0 or len(data_chunk) % frame_bytes != 0:
            logger.error(
                f"[TSS] 非法分包长度：len={len(data_chunk)}, channels={channels}, sample_width={sample_width}"
            )
            return -1

        channel_payloads = [bytearray() for _ in range(channels)]
        total_frames = len(data_chunk) // frame_bytes
        for frame_idx in range(total_frames):
            base = frame_idx * frame_bytes
            for ch_idx in range(channels):
                start = base + ch_idx * sample_width
                end = start + sample_width
                channel_payloads[ch_idx].extend(data_chunk[start:end])

        mic_ptrs = (c_char_p * 4)()
        channel_buffers = []
        for ch_idx in range(4):
            mic_ptrs[ch_idx] = None
            if ch_idx < channels:
                raw = bytes(channel_payloads[ch_idx])
                buf = create_string_buffer(raw, len(raw))
                channel_buffers.append(buf)
                mic_ptrs[ch_idx] = cast(buf, c_char_p)

        frame_data = AIBSDataSt()
        frame_data.mic_data = mic_ptrs
        frame_data.ref_data = None
        frame_data.output = None
        frame_data.direction = 1

        self._aibs_lib.process_frame_data.argtypes = [c_void_p, POINTER(AIBSDataSt), c_ulong]
        self._aibs_lib.process_frame_data.restype = c_int
        return self._aibs_lib.process_frame_data(
            self._aibs_client,
            byref(frame_data),
            c_ulong(self._aibs_process_timestamp),
        )

    def _get_timeout(self, default_timeout: int):
        """获取超时时间，支持GDB模式下的无限等待"""
        try:
            return None if os.environ.get("GDB_OPTION") == "1" else default_timeout
        except:
            return default_timeout

    def start_aibs_service(self, command: DSLCommand, decoder_config: str) -> int:
        """
        启动 AIBS 语音服务。对应 start_aibs_service。
        格式：[TSS]START_SERVICE cmn
        """
        lang = command.params[0] if command.params else "cmn"
        config_path = decoder_config or self._decoder_config
        if not config_path or not os.path.isfile(config_path):
            msg = f"[TSS] AIBSServer 失败：配置文件不存在 {config_path}"
            logger.error(msg)
            command.status = Status.ERROR
            command.message = msg
            return -1
        self._aibs_lib.start_aibs_service.argtypes = [c_char_p, c_char_p]
        self._aibs_lib.start_aibs_service.restype = c_int
        ret = self._aibs_lib.start_aibs_service(
            config_path.encode("utf-8"),
            lang.encode("utf-8"),
        )
        if ret != 0:
            msg = f"[TSS] AIBSServer 失败：start_aibs_service 返回 {ret}"
            logger.error(msg)
            command.status = Status.ERROR
            command.message = msg
            return -1
        logger.info(f"[TSS] AIBSServer 已启动：config={config_path}, lang={lang}")
        command.status = Status.PASSED
        command.return_code = 0
        return 0
    
    def set_car_type(self, command: DSLCommand) -> int:
        """
        设置 AIBS 设备类型。对应 set_aibs_engine_device_type，需在 create_aibs_client 前调用。
        格式：[TSS]SET_CARTYPE "KAICHENG_TWO"
        """
        if not command.params:
            msg = "[TSS] SET_CARTYPE 缺少参数，格式：[TSS]SET_CARTYPE \"KAICHENG_TWO\""
            logger.error(msg)
            command.status = Status.ERROR
            command.message = msg
            return -1
        car_type = command.params[0].strip('"').strip("'")
        self._aibs_lib.set_aibs_engine_device_type.argtypes = [c_char_p]
        self._aibs_lib.set_aibs_engine_device_type.restype = c_int
        ret = self._aibs_lib.set_aibs_engine_device_type(car_type.encode("utf-8"))
        if ret != 0:
            msg = f"[TSS] SET_CARTYPE 失败：set_aibs_engine_device_type 返回 {ret}"
            logger.error(msg)
            command.status = Status.ERROR
            command.message = msg
            return -1
        logger.info(f"[TSS] SET_CARTYPE 成功：{car_type}")
        command.status = Status.PASSED
        command.return_code = 0
        return 0

    def set_work_mode(self, command: DSLCommand) -> int:
        """
        设置 AIBS 工作模式。对应 set_engine_work_mode。
        格式：[TSS]SET_WORK_MODE 0 或 [TSS]SET_WORK_MODE NORMAL
        模式：0=NORMAL, 1=WAKEUP, 2=ASR, 3=NLU, 4=NLG, 5=ONE_SHOT, 6=SMART_LINK, 7=FREE_TALK
        """
        if not command.params:
            msg = "[TSS] AIBS_SET_WORK_MODE 缺少参数，格式：[TSS]SET_WORK_MODE 0 或 NORMAL"
            logger.error(msg)
            command.status = Status.ERROR
            command.message = msg
            return -1

        try:
            mode = int(command.params[0])
            if mode not in (0, 1, 2, 3, 4, 5, 6, 7):
                raise ValueError(f"[TSS] SET_WORK_MODE 参数非法：{mode}，支持 0-7 或 NORMAL/WAKEUP/ASR 等")
        except ValueError as e:
            logger.error(e)
            command.status = Status.ERROR
            command.message = str(e)
            return -1
        
        self._aibs_lib.set_engine_work_mode.argtypes = [c_void_p, c_int]
        self._aibs_lib.set_engine_work_mode.restype = c_int
        ret = self._aibs_lib.set_engine_work_mode(self._aibs_client, mode)
        if ret != 0:
            msg = f"[TSS] SET_WORK_MODE 失败：set_engine_work_mode 返回 {ret}"
            logger.error(msg)
            command.status = Status.ERROR
            command.message = msg
            return -1
        logger.info(f"[TSS] SET_WORK_MODE 成功：mode={mode}")
        command.status = Status.PASSED
        command.return_code = 0
        return 0

    def create_client(self, command: DSLCommand, decoder_config: str) -> int:
        """
        创建 AIBS 客户端。对应 create_aibs_client。
        格式：[TSS]CREATE cmn
        """
        if self._aibs_client is not None:
            logger.info("[TSS] AIBS 客户端已存在，跳过 CREATE")
            command.status = Status.PASSED
            command.return_code = 0
            return 0
        lang = command.params[0] if command.params else "cmn"
        config_path = decoder_config or self._decoder_config
        if not config_path or not os.path.isfile(config_path):
            msg = f"[TSS] CREATE 失败：配置文件不存在 {config_path}"
            logger.error(msg)
            command.status = Status.ERROR
            command.message = msg
            return -1
        callback_t = CFUNCTYPE(c_int, c_int, POINTER(AIBSEngineResultSt), c_void_p)
        self._aibs_ctypes_callback = callback_t(self._aibs_callback_wrapper)
        self._aibs_lib.create_aibs_client.argtypes = [c_char_p, c_char_p, callback_t, c_void_p]
        self._aibs_lib.create_aibs_client.restype = c_void_p
        self._aibs_create_ready.clear()
        self._aibs_client = self._aibs_lib.create_aibs_client(
            config_path.encode("utf-8"),
            lang.encode("utf-8"),
            self._aibs_ctypes_callback,
            None,
        )
        if self._aibs_client is None:
            msg = "[TSS] CREATE 失败：create_aibs_client 返回 NULL"
            logger.error(msg)
            command.status = Status.ERROR
            command.message = msg
            return -1
        if not self._aibs_create_ready.wait(timeout=self._get_timeout(30)):
            msg = "[TSS] CREATE 超时：未收到 init 回调"
            logger.error(msg)
            command.status = Status.ERROR
            command.message = msg
            return -1
        if self._aibs_create_status != AIBSEngineStatusCode.STATUS_AIBS_SR_INIT_SUCCESS:
            msg = f"[TSS] CREATE 失败：init 回调 status={self._aibs_create_status}"
            logger.error(msg)
            command.status = Status.ERROR
            command.message = msg
            return -1
        logger.info(f"[TSS] CREATE 成功：config={config_path}, lang={lang}")
        command.status = Status.PASSED
        command.return_code = 0
        return 0

    def start_engine(self, command: DSLCommand) -> int:
        """
        启动 AIBS 会话。对应 start_aibs_engine。
        格式：[TSS]START
        """
        if not self._aibs_client:
            msg = "[TSS] START 失败：请先执行 START_SERVICE 和 CREATE"
            logger.error(msg)
            command.status = Status.ERROR
            command.message = msg
            return -1
        self._aibs_lib.start_aibs_engine.argtypes = [c_void_p, c_void_p]
        self._aibs_lib.start_aibs_engine.restype = c_int
        self._aibs_start_ready.clear()
        ret = self._aibs_lib.start_aibs_engine(self._aibs_client, None)
        if ret != 0:
            msg = f"[TSS] START 失败：start_aibs_engine 返回 {ret}"
            logger.error(msg)
            command.status = Status.ERROR
            command.message = msg
            return -1
        if not self._aibs_start_ready.wait(timeout=self._get_timeout(10)):
            msg = "[TSS] START 超时：未收到 start 回调"
            logger.error(msg)
            command.status = Status.ERROR
            command.message = msg
            return -1
        if self._aibs_start_status != AIBSEngineStatusCode.STATUS_AIBS_SR_START_SUCCESS:
            msg = f"[TSS] START 失败：start 回调 status={self._aibs_start_status}"
            logger.error(msg)
            command.status = Status.ERROR
            command.message = msg
            return -1
        logger.info("[TSS] START 成功")
        command.status = Status.PASSED
        command.return_code = 0
        return 0

    def stop(self, command: DSLCommand) -> int:
        """
        停止 AIBS 会话。对应 stop_aibs_engine。
        格式：[TSS]STOP
        """
        if not self._aibs_client:
            logger.warning("[TSS] STOP：AIBS 客户端未创建，跳过")
            command.status = Status.PASSED
            command.return_code = 0
            return 0
        
        try:
            logger.info(f"[{self.client_name}] STOP")

            self._aibs_finish_ready.clear()
            self._aibs_lib.stop_aibs_engine.argtypes = [c_void_p]
            self._aibs_lib.stop_aibs_engine.restype = c_int
            ret = self._aibs_lib.stop_aibs_engine(self._aibs_client)
            self._aibs_finish_ready.wait(timeout=self._get_timeout(60))

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
        """清理所有资源，包括 AIBS 引擎和 WebSocket。"""
        # 1. 释放 AIBS 客户端
        if self._aibs_lib and self._aibs_client:
            try:
                self._aibs_lib.free_aibs_engine.argtypes = [c_void_p]
                self._aibs_lib.free_aibs_engine.restype = c_int
                self._aibs_lib.free_aibs_engine(self._aibs_client)
                logger.info("[TSS] AIBS 客户端已释放")
            except Exception as e:
                logger.warning(f"[TSS] free_aibs_engine 异常：{e}")
            self._aibs_client = None
        # 2. 停止 AIBS 服务
        if self._aibs_lib:
            try:
                self._aibs_lib.stop_aibs_service.argtypes = []
                self._aibs_lib.stop_aibs_service.restype = c_int
                self._aibs_lib.stop_aibs_service()
                logger.info("[TSS] AIBS 服务已停止")
            except Exception as e:
                logger.warning(f"[TSS] stop_aibs_service 异常：{e}")
        self._aibs_lib = None
        self._aibs_ctypes_callback = None

        logger.info("[TSS] FREE 完成，资源已释放")
        command.status = Status.PASSED
        command.return_code = 0
        return 0
    
    def data(self, command: DSLCommand) -> int:
        """
        同步阻塞发送音频文件到 AIBS

        格式：[TSS]DATA audio.wav [frame=320] [delay=1] [range=[0,-1]]
            frame  — 每帧字节数（默认 320，对应 16kHz/16bit/1ch/10ms）
            delay  — 时延系数，1.0 表示按实时语速发送，0 表示全速发送
            range  — 时间范围（秒），如 [4,8] 只发第 4~8 秒的音频

        推流时序：
            - frame<=320：原始 PCM → process_data → AIBS 回调
            - frame>320：原始 PCM(交织) → 非交织拆分 → process_frame_data → AIBS 回调
        """
        if not command.params:
            msg = "[TSS]DATA 缺少音频文件路径"
            logger.error(msg)
            command.status = Status.ERROR
            command.message = msg
            return -1

        if not self._aibs_lib or not self._aibs_client:
            msg = "[TSS]DATA 失败：请先执行 [TSS]START_SERVICE 和 [TSS]CREATE、[TSS]START"
            logger.error(msg)
            command.status = Status.ERROR
            command.message = msg
            return -1

        audio_path = command.params[0].strip('"').strip("'")
        frame_size = self._aibs_frame_size
        delay = 1.0
        audio_range = [0, -1]

        for param in command.params[1:]:
            if '=' in param:
                key, value = param.split('=', 1)
                key = key.strip()
                value = value.strip()
                if key == 'frame':
                    try:
                        frame_size = int(value)
                    except ValueError:
                        logger.warning(f"[TSS] DATA frame 参数非法：{value}，使用默认值 {frame_size}")
                elif key == 'delay':
                    try:
                        delay = float(value)
                    except ValueError:
                        logger.warning(f"[TSS] DATA delay 参数非法：{value}，使用默认值 0.0")
                elif key == 'range':
                    if value.startswith('[') and value.endswith(']'):
                        parts = value[1:-1].split(',')
                        if len(parts) == 2:
                            try:
                                start = float(parts[0].strip())
                                end = float(parts[1].strip()) if parts[1].strip() != '-1' else -1
                                audio_range = [start, end]
                            except ValueError:
                                logger.warning(f"[TSS] DATA range 参数非法：{value}，使用默认值 [0,-1]")

        if not os.path.isfile(audio_path):
            msg = f"[TSS]DATA 音频文件不存在：{audio_path}"
            logger.error(msg)
            command.status = Status.ERROR
            command.message = msg
            return -1
        
        TSSClient.audio_path = audio_path
        logger.info(
            f"[TSS] DATA: {os.path.basename(audio_path)}, "
            f"frame={frame_size}, delay={delay}, range={audio_range}）"
        )

        try:
            pcm_data, meta = self._load_pcm_and_meta(audio_path, frame_size)
            derived_channels = max(1, int(frame_size // 320))
            self._aibs_input_channels = derived_channels
            self._aibs_sample_width = meta["sample_width"]
            self._aibs_use_frame_data = frame_size > 320 and derived_channels in (2, 4)
            if frame_size > 320 and not self._aibs_use_frame_data:
                logger.warning(
                    f"[TSS] frame={frame_size} 导出的通道数={derived_channels} 不在(2,4)，回退 process_data"
                )

            block_align = meta["block_align"]
            if self._aibs_use_frame_data:
                block_align = self._aibs_input_channels * self._aibs_sample_width

            sliced_pcm, _, _ = self._slice_pcm_by_time(
                pcm_data,
                meta["sample_rate"],
                block_align,
                audio_range[0],
                audio_range[1],
            )
            # 分包送入 AIBS process_data，时间戳从 0 开始每包按采样累加 delta_ms
            self._aibs_process_timestamp = 0
            self._send_pcm_chunks(
                sliced_pcm,
                frame_size,
                block_align,
                meta["sample_rate"],
                delay,
            )
        except Exception as e:
            logger.error(f"[TSS] DATA 推流异常：{e}")
            command.status = Status.ERROR
            command.message = f"[TSS] DATA 推流异常：{e}"
            return -1

        logger.info(
            f"[TSS] DATA 推流完成（{os.path.basename(audio_path)}，"
        )
        command.status = Status.PASSED
        command.return_code = 0
        return 0

    def set_aibs_engine_param(self, command: DSLCommand) -> int:
        """
        设置 AIBS 引擎参数。对应 set_aibs_engine_param。
        格式：[TSS]  SET_PARAM param value
        """
        if not self._aibs_client:
            msg = "[TSS]SET_PARAM 失败：请先执行 [TSS]START_SERVICE 和 [TSS]CREATE、[TSS]START"
            logger.error(msg)
            command.status = Status.ERROR
            command.message = msg
            return -1

        if len(command.params) < 2:
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] SET_PARAME参数不足'
            return -1

        key = command.params[0]
        value = command.params[1]
        key_index = getattr(AIBSEngineParam, key)
        if not key_index:
            print(f"[TSS] SET_PARAM 失败：{key} 不是有效的参数")
            command.status = Status.ERROR
            command.message = f"[TSS] SET_PARAM 失败：{key} 不是有效的参数"
            return -1
        self._aibs_lib.set_aibs_engine_param.argtypes = [c_void_p, c_int, c_void_p]
        self._aibs_lib.set_aibs_engine_param.restype = c_int
        ret = self._aibs_lib.set_aibs_engine_param(self._aibs_client, key_index, value)
        if ret != 0:
            print(f"[TSS] SET_PARAM 失败：set_aibs_engine_param 返回 {ret}")
            command.status = Status.ERROR
            command.message = f"[TSS] SET_PARAM 失败：set_aibs_engine_param 返回 {ret}"
            return -1
        command.status = Status.PASSED
        command.return_code = 0
        return 0
    
    def set_language_mode(self, command: DSLCommand) -> int:
        """
        设置 AIBS 语言模式。对应 set_language_mode。
        格式：[TSS]SET_LANGUAGE_MODE mode=value
        """
        if not self._aibs_client:
            msg = "[TSS]SET_LANGUAGE_MODE 失败：请先执行 [TSS]START_SERVICE 和 [TSS]CREATE、[TSS]START"
            logger.error(msg)
            command.status = Status.ERROR
            command.message = msg
            return -1
        
        if not command.params:
            msg = "[TSS]SET_LANGUAGE_MODE 失败：缺少语言参数"
            logger.error(msg)
            command.status = Status.ERROR
            command.message = msg
            return -1

        language = command.params[0].strip().lower()
        if language not in ["cmn", "eng", "yue"]:
            msg = f"[TSS]SET_LANGUAGE_MODE 失败：{language} 不是有效的语言模式"
            logger.error(msg)
            command.status = Status.ERROR
            command.message = msg
            return -1
        self._aibs_lib.set_language_mode.argtypes = [c_void_p, c_char_p]
        self._aibs_lib.set_language_mode.restype = c_char_p
        ret = self._aibs_lib.set_language_mode(self._aibs_client, language.encode("utf-8"))
        if not ret:
            logger.error("[TSS] SET_LANGUAGE_MODE 失败：set_language_mode 返回 NULL")
            return -1
        command.status = Status.PASSED
        command.return_code = 0
        return 0

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
            if len(command.params) < 2:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] SET_WAKEUP_WORD参数不足'
                return -1
            
            word = command.params[0]
            threshold = float(command.params[1])
            
            logger.info(f"[{self.client_name}] SET_WAKEUP_WORD: {word}, threshold={threshold}")
            ret = self._aibs_lib.set_wakeup_word(
                self._aibs_client,
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

        
    def set_wakeup_word_online(self, command: DSLCommand) -> int:
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
            self._aibs_lib.set_wakeup_word_online.argtypes = [c_void_p, c_char_p, c_bool]
            self._aibs_lib.set_wakeup_word_online.restype = c_int
            ret = self._aibs_lib.set_wakeup_word_online(
                self._aibs_client,
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
            logger.info(f"[{self.client_name}] GET_WAKEUP_WORD")
            self._aibs_lib.get_wakeup_word.argtypes = [c_void_p]
            self._aibs_lib.get_wakeup_word.restype = c_char_p
            ref = self._aibs_lib.get_wakeup_word(self._aibs_client)
            if not ref:
                raise ValueError("get_wakeup_word 返回空指针")

            raw = ref.decode("utf-8", errors="ignore")
            logger.debug(f"[{self.client_name}] GET_WAKEUP_WORD raw: {raw}")
            obj = json.loads(raw)

            words: list[str] = []
            if isinstance(obj, dict) and "words" in obj:
                for item in obj.get("words") or []:
                    w = item.get("word")
                    if w:
                        words.append(str(w))

            result = ",".join(words)
            logger.info(f"[{self.client_name}] GET_WAKEUP_WORD: {result}")
            print(f"[{self.client_name}] GET_WAKEUP_WORD: {result}")
            command.return_code = result
            command.status = Status.PASSED
            return 0

        except Exception as e:
            logger.error(f"[{self.client_name}] GET_WAKEUP_WORD异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] GET_WAKEUP_WORD异常: {e}'
            return -1
