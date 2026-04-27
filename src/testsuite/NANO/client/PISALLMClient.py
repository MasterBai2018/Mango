#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2026/03/10
# @Author  : baihuidong
# @File    : PISALLMClient.py
# @Software: PyCharm
# @Mail    : baihuidong@pachiratech.com
#
# PISA 大模型全双工 WebSocket 客户端
# 协议参考：PISA_REALTIME_API_PROTOCOL.md
#
# 架构说明：
#   - 组件 A：WS 守护协程（_ws_daemon）—— 在独立 asyncio 事件循环线程中接收下行消息
#   - 组件 B：同步 DATA 推流 —— 继承 AudioDataMixin，在主线程阻塞执行，DSL 上行完全由用户编排
#   - 组件 C：WAIT 信号量 —— 主线程阻塞等待下行事件/文本，基于 threading.Event/Condition 事件驱动


import os
import re
import time
import json
import wave
import base64
import datetime
import requests
import asyncio
import threading
import uuid as _uuid_mod
from src.utils.file_reader import FileReader
from typing import Optional, Callable, List, Dict, Any
from ctypes import *
from loguru import logger

try:
    import websockets
    import websockets.exceptions
    _websockets_available = True
except ImportError:
    websockets = None
    _websockets_available = False

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


class AIBSEngineStatusCode:
    """AIBS 回调状态码（对应 aibs_engine_api.h）"""
    STATUS_AIBS_SR_INIT_SUCCESS = 0x01
    STATUS_AIBS_SR_INIT_FAILED = 0x02
    STATUS_AIBS_SR_START_SUCCESS = 0x03
    STATUS_AIBS_SR_START_FAILED = 0x04
    STATUS_AIBS_NR_OUTPUT_DATA = 0x10   # 降噪后输出音频
    STATUS_AIBS_SR_SPEECH_START = 0x60   # 语音开始
    STATUS_AIBS_SR_SPEECH_END = 0x61    # 语音结束
    STATUS_AIBS_WAKEUP_UNIVERSAL_SUCCESS = 0x70   # 主唤醒词唤醒成功


# ──────────────────────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────────────────────

def _new_event_id(client_id: str) -> str:
    ts = int(time.time() * 1000)
    return f"{client_id}-{ts}-{_uuid_mod.uuid4().hex[:6]}"


# ──────────────────────────────────────────────────────────────
# 主客户端类
# ──────────────────────────────────────────────────────────────

class PISALLMClient(AudioDataMixin):
    """
    PISA 大模型端到端测试客户端（全双工 WebSocket）。

    使用 `websockets`（asyncio 版）实现，asyncio 事件循环运行在独立守护线程中，
    专职接收下行消息；上行（DATA 推流）在主线程同步阻塞执行，DSL 编排完全自由。

    支持的 DSL 指令：
        [PIS]CREATE      [url=ws://...] [client_id=xxx] [video_url=http://...]
        [PIS]AIBSServer  cmn           # 启动 AIBS 服务（使用 decoder.conf）
        [PIS]AIBS_SET_CARTYPE "KAICHENG_TWO"  # 设置设备类型（需在 AIBS_CREATE 前调用）
        [PIS]AIBS_SET_WORK_MODE 0       # 设置工作模式（0=NORMAL, 1=WAKEUP, 2=ASR 等）
        [PIS]AIBS_CREATE cmn           # 创建 AIBS 客户端
        [PIS]AIBS_START                # 启动 AIBS 会话
        [PIS]START       [<timeout=15>]
        [PIS]DATA        audio.wav [frame=320] [delay=1] [range=[0,-1]]  # 经 AIBS 降噪后转发到 WebSocket
        [PIS]AIBS_STOP                 # 停止 AIBS 会话
        [PIS]VEDIO       image=path.png [lat=39] [lon=110] [nlat=38] [nlon=121]
        [PIS]WAIT        type=response.done [response_type=query] [timeout=3.0]
        [PIS]WAIT        text=关键词   [timeout=10.0]
        [PIS]UPDATE      [session_config.json | quit=true | instructions="..."]
        [PIS]STOP
        [PIS]FREE

    回调数据类型（写入 AssertionDataManager）：
        PISASRResult     — response.input_audio_transcription.completed
        PISToolCall      — response.tool_call.info
        PISAVedioText    — [PIS]VEDIO 成功后的图片理解结果（image_path, image_text, time_id）
        PISFinalResponse — response.done（汇总本轮 ASR + 回复文本 + 工具调用）
        PISAIBSEvent     — AIBS 层回调：speech_start、speech_end、wakeup_universal_success
        PISEvent         — 其余所有非音频流下行事件
        PISDialogueSummary — [PIS]STOP 时下发：本段 START～STOP 内按方案 B 组装的 {prelude, rounds}（不含 case 元信息）
    """

    def __init__(self, client_name: str, lib_path: str = "", config=None):
        self.client_name = client_name
        self.m_callback: Optional[Callable] = None
        self._lib_path = lib_path
        self._decoder_config = getattr(config, "decoder_config", "") if config else ""
        self._suite_dir = getattr(config, "suite_dir", None)
        self._config_reder = FileReader(self._decoder_config)
        self._default_ws_subprotocol = self._config_reder.get_config("DEFAULT_WS_SUBPROTOCOL")
        self._session_ready_timeout = float(self._config_reder.get_config("SESSION_READY_TIMEOUT"))
        self._send_timeout = float(self._config_reder.get_config("SEND_TIMEOUT"))
        self._video_request_timeout = int(self._config_reder.get_config("VIDEO_REQUEST_TIMEOUT"))
        self._aibs_nr_buffer_duration_sec = float(self._config_reder.get_config("AIBS_NR_BUFFER_DURATION_SEC"))
        self._aibs_sample_rate = int(self._config_reder.get_config("AIBS_SAMPLE_RATE"))
        self._aibs_frame_size = int(self._config_reder.get_config("AIBS_FRAME_SIZE"))
        # ── AIBS 引擎（libAIBS_dynamic.so）──
        self._aibs_lib = None
        self._aibs_client = None  # create_aibs_client 返回的句柄
        self._aibs_ctypes_callback = None
        self._aibs_nr_buffer = bytearray()  # NR 输出预缓存（最多 2 秒）
        self._aibs_speech_started = False   # 是否已收到 SPEECH_START
        self._aibs_buffer_lock = threading.Lock()
        self._aibs_create_ready = threading.Event()
        self._aibs_create_status = 0
        self._aibs_start_ready = threading.Event()
        self._aibs_start_status = 0
        # 送入 process_data 的毫秒时间戳（与 SpeechEngineClient.m_timestamp 一致，每包累加 delta_ms）
        self._aibs_process_timestamp = 0

        # ── 连接参数 ──
        self._ws_url = self._config_reder.get_config("DEFAULT_WS_URL")
        self._client_id = "mango_pis_client"
        self._video_base_url = self._config_reder.get_config("DEFAULT_VIDEO_URL")  # Video LLM 服务地址

        # ── Video 信息池（VEDIO 指令成功后的结果堆栈）──
        self._video_info_stack: list = []

        # ── asyncio 事件循环（运行在守护线程）──
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None
        self._ws_conn = None  # websockets.WebSocketClientProtocol

        # ── 连接生命周期同步原语 ──
        self._session_ready = threading.Event()
        self._ws_closed = threading.Event()

        # ── 流式文本缓存：Condition 实现推送式唤醒（替代轮询）──
        self._text_cond = threading.Condition()
        self._current_text_buffer: str = ""

        # 下行音频流缓存区
        self._current_audio_buffer = bytearray()

        # ── 本轮回调数据 ──
        self._current_asr: str = ""
        self._current_tool_calls: list = []

        # ── 轮次隔离（DATA 每次调用自增，用于日志关联）──
        self._turn_id: int = 0
        self._turn_lock = threading.Lock()

        # ── 服务端事件信号量池（WAIT event= 使用）──
        self._event_lock = threading.Lock()
        self._event_flags: dict = {}
        # ── WAIT 过滤条件（type=response.done response_type=query）──
        self._wait_event_filter: Optional[dict] = None

        # ── 对话归档（方案 B）：[PIS]START 清空，[PIS]STOP 组装为 PISDialogueSummary 后回调，再断连 ──
        self._dialogue_lock = threading.Lock()
        self._dialogue_events: List[Dict[str, Any]] = []

        if not self._load_aibs_library():
            logger.error("[PIS] 无法加载 libAIBS_dynamic.so")
            raise Exception("[PIS] 无法加载 libAIBS_dynamic.so")

    # ══════════════════════════════════════════════════════════
    # AIBS 引擎封装
    # ══════════════════════════════════════════════════════════

    def _load_aibs_library(self) -> bool:
        """加载 libAIBS_dynamic.so"""
        lib_path = os.path.join(self._lib_path, "libAIBS_dynamic.so")
        if not os.path.exists(lib_path):
            logger.error(f"[PIS] 未找到 libAIBS_dynamic.so，路径：{lib_path}")
            return False
        try:
            self._aibs_lib = cdll.LoadLibrary(lib_path)
            logger.info(f"[PIS] 加载 AIBS 库成功：{lib_path}")
            return True
        except Exception as e:
            logger.warning(f"[PIS] 加载 {lib_path} 失败：{e}")
            return False

    def _aibs_callback_wrapper(self, status: int, result, arg) -> int:
        """
        AIBS 引擎回调。在 C 线程中调用。
        STATUS_AIBS_NR_OUTPUT_DATA -> 缓存/转发到 WebSocket
        STATUS_AIBS_SR_SPEECH_START -> 发送 speech_start，并发送缓存的 2 秒数据
        STATUS_AIBS_SR_SPEECH_END -> 发送 speech_stop
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
            if status == AIBSEngineStatusCode.STATUS_AIBS_NR_OUTPUT_DATA:
                if not result or not result.contents or not result.contents.data:
                    return 0
                # flag 作为数据长度（若无效则默认 320）
                length = result.contents.flag if 0 < result.contents.flag <= 65536 else self._aibs_frame_size
                pcm_data = bytes(string_at(result.contents.data, length))
                if not pcm_data:
                    return 0
                with self._aibs_buffer_lock:
                    self._aibs_nr_buffer.extend(pcm_data)
                    max_len = int(self._aibs_nr_buffer_duration_sec * self._aibs_sample_rate * 2)  # 16bit=2 bytes
                    if len(self._aibs_nr_buffer) > max_len:
                        del self._aibs_nr_buffer[: len(self._aibs_nr_buffer) - max_len]
                    if self._aibs_speech_started:
                        self._send_nr_to_websocket(pcm_data)
                return 0

            if status == AIBSEngineStatusCode.STATUS_AIBS_SR_SPEECH_START:
                with self._aibs_buffer_lock:
                    self._aibs_speech_started = True
                    # 先发送 speech_start
                    images = [v["image_text"] for v in self._video_info_stack]
                    images_id = [v["time_id"] for v in self._video_info_stack]
                    self._send_json({
                        "type": "input_audio_buffer.speech_start",
                        "event_id": _new_event_id(self._client_id),
                        "context_info": {"images": images, "images_id": images_id},
                    })
                    # 再发送缓存的 2 秒数据（按 320 字节分包）
                    buf = bytes(self._aibs_nr_buffer)
                    self._aibs_nr_buffer.clear()
                for i in range(0, len(buf), self._aibs_frame_size):
                    chunk = buf[i : i + self._aibs_frame_size]
                    if len(chunk) == self._aibs_frame_size:
                        self._send_json({
                            "type": "input_audio_buffer.append",
                            "event_id": _new_event_id(self._client_id),
                            "audio": base64.b64encode(chunk).decode("utf-8"),
                        })
                logger.info("[PIS] AIBS SPEECH_START，已发送 speech_start 及预缓存音频")
                self._emit_callback("PISAIBSEvent", self._build_aibs_event_payload(status, result))
                return 0

            if status == AIBSEngineStatusCode.STATUS_AIBS_SR_SPEECH_END:
                with self._aibs_buffer_lock:
                    self._aibs_speech_started = False
                self._send_json({
                    "type": "input_audio_buffer.speech_stop",
                    "event_id": _new_event_id(self._client_id),
                })
                logger.info("[PIS] AIBS SPEECH_END，已发送 speech_stop")
                self._emit_callback("PISAIBSEvent", self._build_aibs_event_payload(status, result))
                return 0

            if status == AIBSEngineStatusCode.STATUS_AIBS_WAKEUP_UNIVERSAL_SUCCESS:
                self._emit_callback("PISAIBSEvent", self._build_aibs_event_payload(status, result))
                return 0

            return 0
        except Exception as e:
            logger.error(f"[PIS] AIBS 回调异常：{e}")
            return -1

    def _send_nr_to_websocket(self, pcm_data: bytes):
        """将 NR 输出按 320 字节分包发送到 WebSocket"""
        for i in range(0, len(pcm_data), self._aibs_frame_size):
            chunk = pcm_data[i : i + self._aibs_frame_size]
            if len(chunk) == self._aibs_frame_size:
                self._send_json({
                    "type": "input_audio_buffer.append",
                    "event_id": _new_event_id(self._client_id),
                    "audio": base64.b64encode(chunk).decode("utf-8"),
                })

    # ══════════════════════════════════════════════════════════
    # AudioDataMixin 抽象方法实现
    # ══════════════════════════════════════════════════════════

    def _process_pcm_chunk(self, data_chunk: bytes, delta_ms: int):
        """
        AudioDataMixin 回调：将 PCM 块送入 AIBS process_data。
        与 SpeechEngineClient._process_pcm_chunk 一致：第三参为 length，第四参为毫秒时间戳 c_ulong(t)。
        AIBS 通过回调返回 NR 输出、SPEECH_START、SPEECH_END，由 _aibs_callback_wrapper 转发到 WebSocket。
        """
        if not self._aibs_lib or not self._aibs_client:
            logger.error("[PIS] _process_pcm_chunk 失败：AIBS 未就绪")
            return
        self._aibs_lib.process_data.argtypes = [
            c_void_p, c_char_p, c_int, c_ulong,
        ]
        self._aibs_lib.process_data.restype = c_int
        ret = self._aibs_lib.process_data(
            self._aibs_client,
            data_chunk,
            len(data_chunk),
            c_ulong(self._aibs_process_timestamp),
        )
        if ret != 0:
            logger.warning(f"[PIS] process_data 返回 {ret}")
        self._aibs_process_timestamp += delta_ms
        logger.debug(
            f"[PIS] 送 AIBS 音频帧：{len(data_chunk)} bytes, "
            f"t={self._aibs_process_timestamp - delta_ms}ms, delta={delta_ms}ms"
        )

    # ══════════════════════════════════════════════════════════
    # 公共接口：回调注入
    # ══════════════════════════════════════════════════════════

    def set_callback(self, callback: Callable):
        self.m_callback = callback

    # ══════════════════════════════════════════════════════════
    # DSL 指令实现
    # ══════════════════════════════════════════════════════════

    def create(self, command: DSLCommand) -> int:
        """解析连接参数（url=, client_id=），不建立连接。"""
        if not _websockets_available:
            msg = "[PIS]CREATE 失败：未安装 websockets 库，请执行 pip install websockets"
            logger.error(msg)
            command.status = Status.ERROR
            command.message = msg
            return -1

        for param in command.params:
            if param.startswith("url="):
                self._ws_url = param[4:].strip().strip('"').strip("'")
            elif param.startswith("client_id="):
                self._client_id = param[10:].strip().strip('"').strip("'")
            elif param.startswith("video_url="):
                self._video_base_url = param[10:].strip().strip('"').strip("'")

        logger.info(
            f"[PIS] CREATE: url={self._ws_url}, client_id={self._client_id}, "
            f"video_url={self._video_base_url}"
        )
        command.status = Status.PASSED
        command.return_code = 0
        return 0

    def aibs_server(self, command: DSLCommand, decoder_config: str) -> int:
        """
        启动 AIBS 语音服务。对应 start_aibs_service。
        格式：[PIS]AIBSServer cmn
        """
        lang = command.params[0] if command.params else "cmn"
        config_path = decoder_config or self._decoder_config
        if not config_path or not os.path.isfile(config_path):
            msg = f"[PIS] AIBSServer 失败：配置文件不存在 {config_path}"
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
            msg = f"[PIS] AIBSServer 失败：start_aibs_service 返回 {ret}"
            logger.error(msg)
            command.status = Status.ERROR
            command.message = msg
            return -1
        logger.info(f"[PIS] AIBSServer 已启动：config={config_path}, lang={lang}")
        command.status = Status.PASSED
        command.return_code = 0
        return 0

    def aibs_set_car_type(self, command: DSLCommand) -> int:
        """
        设置 AIBS 设备类型。对应 set_aibs_engine_device_type，需在 create_aibs_client 前调用。
        格式：[PIS]AIBS_SET_CARTYPE "KAICHENG_TWO"
        """
        if not command.params:
            msg = "[PIS] AIBS_SET_CARTYPE 缺少参数，格式：[PIS]AIBS_SET_CARTYPE \"KAICHENG_TWO\""
            logger.error(msg)
            command.status = Status.ERROR
            command.message = msg
            return -1
        car_type = command.params[0].strip('"').strip("'")
        self._aibs_lib.set_aibs_engine_device_type.argtypes = [c_char_p]
        self._aibs_lib.set_aibs_engine_device_type.restype = c_int
        ret = self._aibs_lib.set_aibs_engine_device_type(car_type.encode("utf-8"))
        if ret != 0:
            msg = f"[PIS] AIBS_SET_CARTYPE 失败：set_aibs_engine_device_type 返回 {ret}"
            logger.error(msg)
            command.status = Status.ERROR
            command.message = msg
            return -1
        logger.info(f"[PIS] AIBS_SET_CARTYPE 成功：{car_type}")
        command.status = Status.PASSED
        command.return_code = 0
        return 0

    def aibs_set_work_mode(self, command: DSLCommand) -> int:
        """
        设置 AIBS 工作模式。对应 set_engine_work_mode。
        格式：[PIS]AIBS_SET_WORK_MODE 0 或 [PIS]AIBS_SET_WORK_MODE NORMAL
        模式：0=NORMAL, 1=WAKEUP, 2=ASR, 3=NLU, 4=NLG, 5=ONE_SHOT, 6=SMART_LINK, 7=FREE_TALK
        """
        if not command.params:
            msg = "[PIS] AIBS_SET_WORK_MODE 缺少参数，格式：[PIS]AIBS_SET_WORK_MODE 0 或 NORMAL"
            logger.error(msg)
            command.status = Status.ERROR
            command.message = msg
            return -1

        try:
            mode = int(command.params[0])
            if mode not in (0, 1, 2, 3, 4, 5, 6, 7):
                raise ValueError(f"[PIS] AIBS_SET_WORK_MODE 参数非法：{mode}，支持 0-7 或 NORMAL/WAKEUP/ASR 等")
        except ValueError as e:
            logger.error(e)
            command.status = Status.ERROR
            command.message = str(e)
            return -1
        
        self._aibs_lib.set_engine_work_mode.argtypes = [c_void_p, c_int]
        self._aibs_lib.set_engine_work_mode.restype = c_int
        ret = self._aibs_lib.set_engine_work_mode(self._aibs_client, mode)
        if ret != 0:
            msg = f"[PIS] AIBS_SET_WORK_MODE 失败：set_engine_work_mode 返回 {ret}"
            logger.error(msg)
            command.status = Status.ERROR
            command.message = msg
            return -1
        logger.info(f"[PIS] AIBS_SET_WORK_MODE 成功：mode={mode}")
        command.status = Status.PASSED
        command.return_code = 0
        return 0

    def aibs_create(self, command: DSLCommand, decoder_config: str) -> int:
        """
        创建 AIBS 客户端。对应 create_aibs_client。
        格式：[PIS]AIBS_CREATE cmn
        """
        if self._aibs_client is not None:
            logger.info("[PIS] AIBS 客户端已存在，跳过 AIBS_CREATE")
            command.status = Status.PASSED
            command.return_code = 0
            return 0
        lang = command.params[0] if command.params else "cmn"
        config_path = decoder_config or self._decoder_config
        if not config_path or not os.path.isfile(config_path):
            msg = f"[PIS] AIBS_CREATE 失败：配置文件不存在 {config_path}"
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
            msg = "[PIS] AIBS_CREATE 失败：create_aibs_client 返回 NULL"
            logger.error(msg)
            command.status = Status.ERROR
            command.message = msg
            return -1
        if not self._aibs_create_ready.wait(timeout=30):
            msg = "[PIS] AIBS_CREATE 超时：未收到 init 回调"
            logger.error(msg)
            command.status = Status.ERROR
            command.message = msg
            return -1
        if self._aibs_create_status != AIBSEngineStatusCode.STATUS_AIBS_SR_INIT_SUCCESS:
            msg = f"[PIS] AIBS_CREATE 失败：init 回调 status={self._aibs_create_status}"
            logger.error(msg)
            command.status = Status.ERROR
            command.message = msg
            return -1
        logger.info(f"[PIS] AIBS_CREATE 成功：config={config_path}, lang={lang}")
        command.status = Status.PASSED
        command.return_code = 0
        return 0

    def aibs_start(self, command: DSLCommand) -> int:
        """
        启动 AIBS 会话。对应 start_aibs_engine。
        格式：[PIS]AIBS_START
        """
        if not self._aibs_client:
            msg = "[PIS] AIBS_START 失败：请先执行 AIBSServer 和 AIBS_CREATE"
            logger.error(msg)
            command.status = Status.ERROR
            command.message = msg
            return -1
        self._aibs_lib.start_aibs_engine.argtypes = [c_void_p, c_void_p]
        self._aibs_lib.start_aibs_engine.restype = c_int
        self._aibs_start_ready.clear()
        ret = self._aibs_lib.start_aibs_engine(self._aibs_client, None)
        if ret != 0:
            msg = f"[PIS] AIBS_START 失败：start_aibs_engine 返回 {ret}"
            logger.error(msg)
            command.status = Status.ERROR
            command.message = msg
            return -1
        if not self._aibs_start_ready.wait(timeout=10):
            msg = "[PIS] AIBS_START 超时：未收到 start 回调"
            logger.error(msg)
            command.status = Status.ERROR
            command.message = msg
            return -1
        if self._aibs_start_status != AIBSEngineStatusCode.STATUS_AIBS_SR_START_SUCCESS:
            msg = f"[PIS] AIBS_START 失败：start 回调 status={self._aibs_start_status}"
            logger.error(msg)
            command.status = Status.ERROR
            command.message = msg
            return -1
        logger.info("[PIS] AIBS_START 成功")
        command.status = Status.PASSED
        command.return_code = 0
        return 0

    def aibs_stop(self, command: DSLCommand) -> int:
        """
        停止 AIBS 会话。对应 stop_aibs_engine。
        格式：[PIS]AIBS_STOP
        """
        if not self._aibs_client:
            logger.warning("[PIS] AIBS_STOP：AIBS 客户端未创建，跳过")
            command.status = Status.PASSED
            command.return_code = 0
            return 0
        self._aibs_lib.stop_aibs_engine.argtypes = [c_void_p]
        self._aibs_lib.stop_aibs_engine.restype = c_int
        self._aibs_lib.stop_aibs_engine(self._aibs_client)
        logger.info("[PIS] AIBS_STOP 完成")
        command.status = Status.PASSED
        command.return_code = 0
        return 0

    def start(self, command: DSLCommand) -> int:
        """
        在守护线程中启动 asyncio 事件循环，建立 WebSocket 长连接。
        阻塞主线程直到收到 session.created 后返回。
        """
        if not _websockets_available:
            msg = "[PIS]START 失败：websockets 库不可用"
            logger.error(msg)
            command.status = Status.ERROR
            command.message = msg
            return -1

        if self._loop_thread and self._loop_thread.is_alive():
            logger.warning("[PIS] 事件循环已运行，跳过重复 START")
            command.status = Status.PASSED
            command.return_code = 0
            return 0

        with self._dialogue_lock:
            self._dialogue_events.clear()

        self._session_ready.clear()
        self._ws_closed.clear()

        self._loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(
            target=self._run_event_loop,
            name=f"PIS-EventLoop-{self._client_id}",
            daemon=True,
        )
        self._loop_thread.start()
        wait_timeout = command.timeout if command.timeout > 0 else self._session_ready_timeout
        ready = self._session_ready.wait(timeout=wait_timeout)

        if not ready:
            msg = f"[PIS] START 超时（{wait_timeout}s）：未收到 session.created"
            logger.error(msg)
            command.status = Status.ERROR
            command.message = msg
            return -1

        logger.info("[PIS] START 成功，WebSocket 长连接已就绪")
        
        # 监听首个 response.final_done，避免沿用旧轮次的已触发状态
        self._wait_for_final_done(command)

        command.status = Status.PASSED
        command.return_code = 0
        return 0

    def data(self, command: DSLCommand) -> int:
        """
        同步阻塞发送音频文件到 AIBS，由 AIBS 回调将 NR 输出、speech_start、speech_stop 转发到 WebSocket。

        格式：[PIS]DATA audio.wav [frame=320] [delay=1] [range=[0,-1]]
            frame  — 每帧字节数（默认 320，对应 16kHz/16bit/1ch/10ms）
            delay  — 时延系数，1.0 表示按实时语速发送，0 表示全速发送
            range  — 时间范围（秒），如 [4,8] 只发第 4~8 秒的音频

        推流时序：原始 PCM → process_data → AIBS 回调 → WebSocket（speech_start + append + speech_stop）
        """
        if not command.params:
            msg = "[PIS]DATA 缺少音频文件路径"
            logger.error(msg)
            command.status = Status.ERROR
            command.message = msg
            return -1

        if not self._aibs_lib or not self._aibs_client:
            msg = "[PIS]DATA 失败：请先执行 [PIS]AIBSServer 和 [PIS]AIBS_CREATE、[PIS]AIBS_START"
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
                        logger.warning(f"[PIS] DATA frame 参数非法：{value}，使用默认值 {frame_size}")
                elif key == 'delay':
                    try:
                        delay = float(value)
                    except ValueError:
                        logger.warning(f"[PIS] DATA delay 参数非法：{value}，使用默认值 0.0")
                elif key == 'range':
                    if value.startswith('[') and value.endswith(']'):
                        parts = value[1:-1].split(',')
                        if len(parts) == 2:
                            try:
                                start = float(parts[0].strip())
                                end = float(parts[1].strip()) if parts[1].strip() != '-1' else -1
                                audio_range = [start, end]
                            except ValueError:
                                logger.warning(f"[PIS] DATA range 参数非法：{value}，使用默认值 [0,-1]")

        if not os.path.isfile(audio_path):
            msg = f"[PIS]DATA 音频文件不存在：{audio_path}"
            logger.error(msg)
            command.status = Status.ERROR
            command.message = msg
            return -1

        with self._turn_lock:
            self._turn_id += 1
            current_turn = self._turn_id

        # 清空本轮缓存，通知等待中的 WAIT text= 重新判断
        with self._text_cond:
            self._current_text_buffer = ""
            self._current_audio_buffer.clear()
            self._text_cond.notify_all()
        self._current_asr = ""
        self._current_tool_calls = []

        with self._event_lock:
            self._event_flags.clear()

        # 每轮 DATA 重置 AIBS NR 缓存和 speech 状态
        with self._aibs_buffer_lock:
            self._aibs_nr_buffer.clear()
            self._aibs_speech_started = False

        logger.info(
            f"[PIS] DATA: {os.path.basename(audio_path)}, "
            f"frame={frame_size}, delay={delay}, range={audio_range}（轮次 #{current_turn}）"
        )

        try:
            pcm_data, meta = self._load_pcm_and_meta(audio_path, frame_size)
            sliced_pcm, _, _ = self._slice_pcm_by_time(
                pcm_data,
                meta["sample_rate"],
                meta["block_align"],
                audio_range[0],
                audio_range[1],
            )
            # 分包送入 AIBS process_data，时间戳从 0 开始每包按采样累加 delta_ms
            self._aibs_process_timestamp = 0
            self._send_pcm_chunks(
                sliced_pcm,
                frame_size,
                meta["block_align"],
                meta["sample_rate"],
                delay,
            )
        except Exception as e:
            logger.error(f"[PIS] DATA 推流异常：{e}")
            command.status = Status.ERROR
            command.message = f"[PIS] DATA 推流异常：{e}"
            return -1

        logger.info(
            f"[PIS] DATA 推流完成（轮次 #{current_turn}）：{os.path.basename(audio_path)}，"
            f"等待 AIBS 回调及服务端 response.done"
        )

        # 等待 response.final_done 事件
        self._wait_for_final_done(command)

        command.status = Status.PASSED
        command.return_code = 0
        return 0
    
    def _wait_for_final_done(self, command: DSLCommand) -> int:
        """
        等待 response.final_done 事件
        """
        event_flag = self._get_event_flag("response.final_done")
        event_flag.clear()
        final_done_timeout = command.timeout if command.timeout > 0 else self._session_ready_timeout
        if event_flag.wait(timeout=final_done_timeout):
            logger.info("[PIS] 收到 response.final_done 事件")
        else:
            logger.debug(
                f"[PIS] {final_done_timeout}s 内未收到 response.final_done，"
                "继续执行"
            )

    def vedio(self, command: DSLCommand) -> int:
        """
        上传关键帧图片到 Video LLM 服务，获取视觉理解结果。

        格式：[PIS]VEDIO image=path.png [lat=39] [lon=110] [nlat=38] [nlon=121]
            image — 必填，图片文件路径
            lat   — 可选，纬度（空表示前置摄像头）
            lon   — 可选，经度
            nlat  — 可选，下一位置纬度
            nlon  — 可选，下一位置经度

        chatid 使用 client_id。请求成功后，将 image_path、image_text、time_id
        组装成字典加入 _video_info_stack，并回调 PISAVedioText。
        """
        image_path = ""
        lat = ""
        lon = ""
        nlat = ""
        nlon = ""

        for param in command.params:
            param = param.strip()
            if param.startswith("image="):
                image_path = param[6:].strip().strip('"').strip("'")
            elif param.startswith("lat="):
                lat = param[4:].strip().strip('"').strip("'")
            elif param.startswith("lon="):
                lon = param[4:].strip().strip('"').strip("'")
            elif param.startswith("nlat="):
                nlat = param[5:].strip().strip('"').strip("'")
            elif param.startswith("nlon="):
                nlon = param[5:].strip().strip('"').strip("'")

        if not image_path:
            msg = "[PIS]VEDIO 缺少必填参数 image=，格式：[PIS]VEDIO image=path.png [lat=...] [lon=...]"
            logger.error(msg)
            command.status = Status.ERROR
            command.message = msg
            return -1

        if not os.path.isfile(image_path):
            msg = f"[PIS]VEDIO 图片文件不存在：{image_path}"
            logger.error(msg)
            command.status = Status.ERROR
            command.message = msg
            return -1

        url = f"{self._video_base_url.rstrip('/')}/receive_key_image"
        file_ext = os.path.splitext(image_path)[1].lower()
        mime_map = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
            ".gif": "image/gif", ".bmp": "image/bmp", ".webp": "image/webp",
        }
        mime_type = mime_map.get(file_ext, "image/jpeg")
        time_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        try:
            with open(image_path, "rb") as f:
                files = {"image_file": (os.path.basename(image_path), f, mime_type)}
                data = {
                    "chatid": self._client_id,
                    "latitude": lat,
                    "longitude": lon,
                    "nextLatitude": nlat,
                    "nextLongitude": nlon,
                    "time_id": time_id,
                }
                resp = requests.post(
                    url, files=files, data=data, timeout=self._video_request_timeout
                )

            if resp.status_code != 200:
                try:
                    err = resp.json()
                except Exception:
                    err = {"detail": resp.text[:300]}
                msg = f"请求失败 (HTTP {resp.status_code})：{err}"
                logger.error(msg)
                command.status = Status.ERROR
                command.message = msg
                return -1

            result = resp.json()
            if result.get("error"):
                msg = f"服务返回错误：{result.get('error')}"
                logger.error(msg)
                command.status = Status.ERROR
                command.message = msg
                return -1

            image_text = result.get("image_text", "")
            time_id = result.get("time_id", time_id)

            video_info = {
                "image_path": image_path,
                "image_text": image_text,
                "time_id": time_id,
            }
            self._video_info_stack.append(video_info)

            self._emit_callback("PISAVedioText", {
                "source": "PIS",
                "type": "PISAVedioText",
                "image": image_path,
                "image_text": image_text,
                "time_id": time_id,
            })

            logger.info(
                f"[PIS] VEDIO 成功：{os.path.basename(image_path)}，"
                f"image_text={image_text[:50]!r}...，已加入 video_info_stack"
            )
            command.status = Status.PASSED
            command.return_code = 0
            return 0

        except requests.exceptions.Timeout:
            msg = f"[PIS]VEDIO 请求超时（>{self._video_request_timeout}s）"
            logger.error(msg)
            command.status = Status.ERROR
            command.message = msg
            return -1
        except requests.exceptions.ConnectionError as e:
            msg = f"[PIS]VEDIO 无法连接到 Video LLM 服务：{e}"
            logger.error(msg)
            command.status = Status.ERROR
            command.message = msg
            return -1
        except Exception as e:
            logger.error(f"[PIS]VEDIO 异常：{e}")
            command.status = Status.ERROR
            command.message = f"[PIS]VEDIO 异常：{e}"
            return -1

    def wait(self, command: DSLCommand) -> int:
        """
        主线程阻塞等待下行事件或文本条件满足（基于事件驱动，无 CPU 空转）。

        格式：
            [PIS]WAIT type=response.done [response_type=query] [timeout=3.0]  — 支持过滤
            [PIS]WAIT type=response.done [timeout=3.0]                        — 不过滤
            [PIS]WAIT text=关键词   [timeout=10.0]                             — 等待流式文本

        超时优先级：命令行 timeout= 参数 > command.timeout > 默认 10.0 秒。
        超时后返回 -1 并置 command.status = ERROR。
        """
        if not command.params:
            msg = "[PIS]WAIT 缺少条件参数，格式：[PIS]WAIT <event_type|text=xxx> [timeout=N]"
            logger.error(msg)
            command.status = Status.ERROR
            command.message = msg
            return -1

        timeout = command.timeout if command.timeout > 0 else 10.0
        wait_text: Optional[str] = None
        wait_event: Optional[str] = None
        wait_filter: dict = {}

        RESERVED = ("timeout", "text", "type")
        for param in command.params:
            param = param.strip()
            if param.startswith("timeout="):
                try:
                    timeout = float(param[8:])
                except ValueError:
                    logger.warning(f"[PIS] WAIT timeout 参数非法：{param[8:]}，使用默认值 {timeout}s")
            elif param.startswith("text="):
                wait_text = param[5:].strip('"').strip("'")
            elif param.startswith("type="):
                wait_event = param[5:].strip('"').strip("'")
            elif "=" in param:
                k, v = param.split("=", 1)
                k = k.strip()
                if k not in RESERVED:
                    wait_filter[k] = v.strip().strip('"').strip("'")
            else:
                if wait_event is None:
                    wait_event = param

        if not wait_text and not wait_event:
            msg = f"[PIS]WAIT 参数无效，需要事件类型或 text=，当前参数：{command.params}"
            logger.error(msg)
            command.status = Status.ERROR
            command.message = msg
            return -1

        start_time = time.time()

        # ── 事件等待：基于 threading.Event，后台收到该事件类型时 set ──
        if wait_event:
            self._wait_event_filter = {"event": wait_event, **wait_filter}
            try:
                event_flag = self._get_event_flag(wait_event)
                remaining = max(timeout - (time.time() - start_time), 0)
                triggered = event_flag.wait(timeout=remaining)
                if triggered:
                    event_flag.clear()
                    logger.info(
                        f"[PIS] WAIT event={wait_event!r} 满足，"
                        f"耗时 {time.time()-start_time:.2f}s"
                    )
                    command.status = Status.PASSED
                    command.return_code = 0
                    return 0
                else:
                    msg = f"[PIS] WAIT 超时（{timeout}s）：event={wait_event!r} 未触发"
                    logger.warning(msg)
                    command.status = Status.ERROR
                    command.message = msg
                    return -1
            finally:
                self._wait_event_filter = None

        # ── 文本等待：基于 Condition，每次新 delta 到达时 notify，无 CPU 空转 ──
        deadline = start_time + timeout
        with self._text_cond:
            while True:
                if wait_text in self._current_text_buffer:
                    logger.info(
                        f"[PIS] WAIT text={wait_text!r} 满足，"
                        f"耗时 {time.time()-start_time:.2f}s，"
                        f"缓存长度 {len(self._current_text_buffer)} 字"
                    )
                    command.status = Status.PASSED
                    command.return_code = 0
                    return 0

                remaining = deadline - time.time()
                if remaining <= 0:
                    msg = (
                        f"[PIS] WAIT 超时（{timeout}s）：text={wait_text!r} 未在流式输出中出现，"
                        f"当前缓存：{self._current_text_buffer[:80]!r}..."
                    )
                    logger.warning(msg)
                    command.status = Status.ERROR
                    command.message = msg
                    return -1

                # 最长等 1 秒唤醒一次（防止 deadline 到达时无 notify 导致永久阻塞）
                self._text_cond.wait(timeout=min(remaining, 1.0))

    def update(self, command: DSLCommand) -> int:
        """发送 session.update 事件，更新会话配置或清空上下文。"""
        session_payload: dict = {"instructions": "", "status": {"quit": False}}

        for param in command.params:
            param = param.strip()
            if param.endswith(".json") and os.path.isfile(param):
                try:
                    with open(param, "r", encoding="utf-8") as f:
                        session_payload = json.load(f)
                    break
                except Exception as e:
                    logger.warning(f"[PIS] UPDATE 读取 JSON 文件失败：{e}")
            elif param.startswith("quit="):
                val = param[5:].lower()
                session_payload.setdefault("status", {})["quit"] = val in ("true", "1", "yes")
            elif param.startswith("instructions="):
                session_payload["instructions"] = param[13:].strip('"').strip("'")

        event = {
            "type": "session.update",
            "event_id": _new_event_id(self._client_id),
            "session": session_payload,
        }
        ret = self._send_json(event)
        if ret == 0:
            logger.info("[PIS] UPDATE 已发送 session.update")
            command.status = Status.PASSED
            command.return_code = 0
        else:
            command.status = Status.ERROR
            command.message = "[PIS] UPDATE 发送失败，WebSocket 未连接"
        return ret

    def stop(self, command: DSLCommand) -> int:
        """
        先组装 PISDialogueSummary 并回调，再关闭 WebSocket、等待事件循环线程退出。
        """
        with self._dialogue_lock:
            events = list(self._dialogue_events)
            self._dialogue_events.clear()

        summary = self._build_pisa_dialogue_scheme_b(events)
        if self.m_callback:
            try:
                self.m_callback(
                    self.client_name, 0, summary, "0", "PISDialogueSummary"
                )
            except Exception as e:
                logger.error(f"[PIS] PISDialogueSummary 回调失败：{e}")

        self._close_ws()
        if self._loop_thread and self._loop_thread.is_alive():
            self._loop_thread.join(timeout=5.0)
        logger.info("[PIS] STOP 完成")

        with self._text_cond:
            self._current_text_buffer = ""
            self._text_cond.notify_all()
        self._current_asr = ""
        self._current_tool_calls = []
        self._video_info_stack.clear()
        with self._event_lock:
            self._event_flags.clear()
        self._session_ready.clear()

        command.status = Status.PASSED
        command.return_code = 0
        return 0

    def free(self, command: DSLCommand) -> int:
        """清理所有资源，包括 AIBS 引擎和 WebSocket。"""
        # 1. 释放 AIBS 客户端
        if self._aibs_lib and self._aibs_client:
            try:
                self._aibs_lib.free_aibs_engine.argtypes = [c_void_p]
                self._aibs_lib.free_aibs_engine.restype = c_int
                self._aibs_lib.free_aibs_engine(self._aibs_client)
                logger.info("[PIS] AIBS 客户端已释放")
            except Exception as e:
                logger.warning(f"[PIS] free_aibs_engine 异常：{e}")
            self._aibs_client = None
        # 2. 停止 AIBS 服务
        if self._aibs_lib:
            try:
                self._aibs_lib.stop_aibs_service.argtypes = []
                self._aibs_lib.stop_aibs_service.restype = c_int
                self._aibs_lib.stop_aibs_service()
                logger.info("[PIS] AIBS 服务已停止")
            except Exception as e:
                logger.warning(f"[PIS] stop_aibs_service 异常：{e}")
        self._aibs_lib = None
        self._aibs_ctypes_callback = None

        # 3. 关闭 WebSocket
        self._close_ws()
        if self._loop and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._loop_thread and self._loop_thread.is_alive():
            self._loop_thread.join(timeout=5.0)

        self._ws_conn = None
        self._loop = None
        self.m_callback = None

        logger.info("[PIS] FREE 完成，资源已释放")
        command.status = Status.PASSED
        command.return_code = 0
        return 0

    # ══════════════════════════════════════════════════════════
    # 组件 A：asyncio 事件循环 + WS 守护协程
    # ══════════════════════════════════════════════════════════

    def _run_event_loop(self):
        """守护线程入口：设置并运行专属 asyncio 事件循环。"""
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._ws_daemon())
        except Exception as e:
            logger.error(f"[PIS] 事件循环异常退出：{e}")
        finally:
            self._ws_closed.set()
            try:
                self._loop.close()
            except Exception:
                pass

    async def _ws_daemon(self):
        """
        WebSocket 守护协程（运行于独立 asyncio 事件循环线程）。
        建立连接后进入接收循环，直到连接关闭。
        """
        ws_url = self._ws_url
        if "?" not in ws_url:
            ws_url = f"{ws_url}?client_id={self._client_id}"
        else:
            ws_url = f"{ws_url}&client_id={self._client_id}"
        try:
            async with websockets.connect(
                ws_url,
                subprotocols=[self._default_ws_subprotocol],
                ping_interval=20,
                ping_timeout=30,
            ) as ws:
                self._ws_conn = ws
                logger.info(f"[PIS] WebSocket 已连接：{ws_url}")
                async for raw_message in ws:
                    self._dispatch_message(raw_message)

        except websockets.exceptions.ConnectionClosedOK:
            logger.info("[PIS] WebSocket 正常关闭")
        except websockets.exceptions.ConnectionClosedError as e:
            logger.warning(f"[PIS] WebSocket 异常关闭：{e}")
        except OSError as e:
            logger.error(f"[PIS] WebSocket 连接失败（网络/地址错误）：{e}")
            self._session_ready.set()
        except Exception as e:
            logger.error(f"[PIS] WS 守护协程异常：{e}")
            self._session_ready.set()
        finally:
            self._ws_conn = None
            self._ws_closed.set()

    def _dispatch_message(self, raw_message: str):
        """
        下行事件分发器（在 asyncio 线程中调用）。

        处理原则：
          - response.audio.delta（纯音频流）：不打日志，不回调，静默丢弃
          - response.audio_transcript.delta：仅追加文本缓存 + notify，不打日志（节流）
          - 其余所有事件：打印日志 + 封装标准 payload + 触发 m_callback
        """
        try:
            event = json.loads(raw_message)
        except json.JSONDecodeError:
            logger.warning(f"[PIS] 收到非 JSON 消息：{raw_message[:120]}")
            return

        event_type = event.get("type", "")

        if event_type == "response.audio.delta":
            audio_b64 = event.get("delta", "")
            if audio_b64:
                try:
                    pcm_chunk = base64.b64decode(audio_b64)
                    with self._text_cond:
                        self._current_audio_buffer.extend(pcm_chunk)
                except Exception as e:
                    logger.warning(f"[PIS] 解码下行音频 Base64 失败：{e}")

        elif event_type != "response.audio_transcript.delta":
            logger.debug(f"[PIS] 收到消息：{event}")

        # ── 会话生命周期 ──
        if event_type == "session.created":
            logger.info("[PIS] 收到 session.created，连接就绪")
            self._session_ready.set()
            self._emit_callback("PISEvent", self._build_event_payload(event_type, event))

        elif event_type == "session.interrupt":
            logger.info("[PIS] 收到 session.interrupt，清空本轮缓存")
            self._on_interrupt()
            self._emit_callback("PISEvent", self._build_event_payload(event_type, event))

        elif event_type == "session.updated":
            logger.debug("[PIS] 收到 session.updated")
            self._emit_callback("PISEvent", self._build_event_payload(event_type, event))

        elif event_type == "session.destroyed":
            logger.info("[PIS] 收到 session.destroyed")
            self._ws_closed.set()
            self._emit_callback("PISEvent", self._build_event_payload(event_type, event))

        # ── ASR 结果 ──
        elif event_type == "response.input_audio_transcription.completed":
            asr_text = re.sub(r"[^\w\s]", "", event.get("transcript", ""))
            lang = event.get("language", "")
            self._current_asr = asr_text
            logger.info(f"[PIS] ASR 识别结果：{asr_text!r}")
            self._emit_callback("PISASRResult", {
                "source": "PIS",
                "type": "PISASRResult",
                "event": event_type,
                "asr": asr_text,
                "lang": lang,
                "data": event,
            })

        # ── 流式文本 delta（节流：仅累积 + notify，不打日志）──
        elif event_type == "response.audio_transcript.delta":
            delta = event.get("delta", "")
            with self._text_cond:
                self._current_text_buffer += delta
                self._text_cond.notify_all()
                self._emit_callback("ResponseTTSTemp", {
                    "source": "PIS",
                    "type": "ResponseTTSTemp",
                    "event": event_type,
                    "tts": self._current_text_buffer,
                    "data": event,
                })

        # LLM的最终回复的文本
        elif event_type == "response.audio_transcript.done":
            transcript = event.get("transcript", "")
            response_type = event.get("response_type", "")
            with self._text_cond:
                if transcript and not self._current_text_buffer:
                    self._current_text_buffer = transcript
                full_text = self._current_text_buffer
                self._text_cond.notify_all()
            self._emit_callback("ResponseTTS", {
                "source": "PIS",
                "type": "ResponseTTS",
                "event": event_type,
                "tts": full_text,
                "response_type": response_type,
                "data": event,
            })
            self._current_text_buffer = ""

        # ── 工具调用 ──
        elif event_type == "response.tool_call.info":
            item_id = event.get("item_id", "")
            tool_name = event.get("tool_name", "")
            tool_result = event.get("tool_result", "")
            self._current_tool_calls.append({
                "item_id": item_id,
                "tool_name": tool_name,
                "tool_result": tool_result,
            })
            logger.info(
                f"[PIS] 工具调用：tool_name={tool_name!r}, item_id={item_id}, "
                f"result={tool_result[:100]!r}"
            )
            self._emit_callback("PISToolCall", {
                "source": "PIS",
                "type": "PISToolCall",
                "event": event_type,
                "item_id": item_id,
                "tool_name": tool_name,
                "tool_result": tool_result,
                "data": event,
            })

        # ── 本轮结束 ──
        elif event_type == "response.done":
            if self._event_matches_filter(event_type, event):
                self._set_event_flag("response.done")
            resp_id = event.get("response", {}).get("id", "unknown_id")
            logger.info(f"[PIS] 收到 response.done (ID: {resp_id})，处理本段交互结束")
            self._on_response_done(event)

        # ── VAD 事件 ──
        elif event_type == "input_audio_buffer.speech_started":
            self._set_event_flag("input_audio_buffer.speech_started")
            self._emit_callback("PISEvent", self._build_event_payload(event_type, event))

        elif event_type == "input_audio_buffer.speech_stopped":
            self._set_event_flag("input_audio_buffer.speech_stopped")
            self._emit_callback("PISEvent", self._build_event_payload(event_type, event))

        # ── 服务端错误 ──
        elif event_type == "error":
            logger.error(f"[PIS] 服务端错误：{event.get('error', {})}")
            self._emit_callback("PISEvent", self._build_event_payload(event_type, event))

        # ── 其他事件 ──
        elif event_type == "response.audio.delta":
            logger.debug(f"[PIS] 收到音频流：{event_type}")
            self._set_event_flag(event_type)

        # ── 其余已知/未知事件：通用处理 ──
        elif event_type:
            logger.debug(f"[PIS] 收到事件：{event_type}")
            self._set_event_flag(event_type)
            self._emit_callback("PISEvent", self._build_event_payload(event_type, event))

    def _build_event_payload(self, event_type: str, event: dict) -> dict:
        """封装下行事件为标准回调格式（参考 parse_titan_result 结构）。"""
        return {
            "source": "PIS",
            "type": "PISEvent",
            "event": event_type,
            "data": event,
        }

    def _build_aibs_event_payload(self, status: int, result) -> dict:
        """封装 AIBS 回调为标准格式，供 m_callback 使用。"""
        event_map = {
            AIBSEngineStatusCode.STATUS_AIBS_SR_SPEECH_START: "PISAIBSSpeechStart",
            AIBSEngineStatusCode.STATUS_AIBS_SR_SPEECH_END: "PISAIBSSpeechEnd",
            AIBSEngineStatusCode.STATUS_AIBS_WAKEUP_UNIVERSAL_SUCCESS: "PISAIBSWakeup",
        }
        event_type = event_map.get(status, "PISAIBSEvent")
        payload = {"source": "PIS", "type": event_type, "status": status, "data": {}}

        if not result or not result.contents:
            return payload
        addr = result.contents.data
        if not addr:
            return payload
        # data 为 c_void_p，在 Python 中是整数地址，需用 string_at 读取
        try:
            raw = string_at(addr)
            _data = raw.decode("utf-8", errors="ignore").strip()
            if _data:
                payload["data"] = json.loads(_data)
        except Exception:
            pass
        return payload

    def _on_interrupt(self):
        """收到 session.interrupt：清空本轮缓存，通知等待中的 WAIT text=。"""
        with self._text_cond:
            self._current_text_buffer = ""
            self._current_audio_buffer.clear()  # 打断时清空被废弃的音频
            self._text_cond.notify_all()
        self._current_asr = ""
        self._current_tool_calls = []

    def _on_response_done(self, event: dict):
        """收到 response.done：落盘音频，汇总本轮数据打包为 PISFinalResponse 写入回调池。"""
        with self._text_cond:
            response_text = self._current_text_buffer
            pcm_data = bytes(self._current_audio_buffer) # 获取完整的音频字节
        
        # 将音频写出为 WAV 文件 (16kHz, 16bit, 单声道)；目录优先落在 suite_dir 下
        if pcm_data and self._suite_dir:
            save_dir = os.path.join(self._suite_dir, "pisa_downlink_audios")
            os.makedirs(save_dir, exist_ok=True)
            
            resp_id = event.get("response", {}).get("id", "unknown_resp")
            filename = f"downlink_turn{self._turn_id}_{resp_id}.wav"
            saved_audio_path = os.path.join(save_dir, filename)
            
            try:
                import wave
                with wave.open(saved_audio_path, 'wb') as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(24000)
                    wf.writeframes(pcm_data)
                logger.info(f"[PIS] ⬇️ 本段下行音频已保存至：{saved_audio_path}")
            except Exception as e:
                logger.error(f"[PIS] 保存下行音频失败：{e}")

    # ══════════════════════════════════════════════════════════
    # 内部工具方法
    # ══════════════════════════════════════════════════════════

    def _send_json(self, event: dict) -> int:
        """
        线程安全地向 WebSocket 发送 JSON 消息。
        通过 asyncio.run_coroutine_threadsafe 从主线程提交协程到事件循环并阻塞等待结果。
        """
        if not self._loop or self._loop.is_closed() or not self._ws_conn:
            logger.error("[PIS] _send_json 失败：连接未就绪")
            return -1
        try:
            future = asyncio.run_coroutine_threadsafe(
                self._ws_conn.send(json.dumps(event, ensure_ascii=False)),
                self._loop,
            )
            future.result(timeout=self._send_timeout)
            return 0
        except Exception as e:
            logger.error(f"[PIS] _send_json 发送失败：{e}")
            return -1

    def _close_ws(self):
        """从任意线程安全地关闭 WebSocket 连接。"""
        if self._loop and not self._loop.is_closed() and self._ws_conn:
            try:
                future = asyncio.run_coroutine_threadsafe(
                    self._ws_conn.close(),
                    self._loop,
                )
                future.result(timeout=5.0)
            except Exception:
                pass

    def _append_dialogue_event(self, callback_type: str, data: dict) -> None:
        """累积精简对话事件，供 STOP 时组装方案 B（不含 ResponseTTSTemp）。"""
        slim: Optional[Dict[str, Any]] = None
        data_payload = data.get("data", {}) if isinstance(data, dict) else {}
        if callback_type == "PISASRResult":
            slim = {"kind": "asr", "asr": data.get("asr", "")}
        elif callback_type == "ResponseTTS":
            slim = {
                "kind": "tts",
                "response_type": data.get("response_type", ""),
                "tts": data.get("tts", ""),
                "event_id": data_payload.get('event_id', ''),
                "response_id": data_payload.get("response_id", ""),
            }
        elif callback_type == "PISToolCall":
            slim = {
                "kind": "tool",
                "tool_name": data.get("tool_name", ""),
                "tool_result": data.get("tool_result", ""),
                "event_id": data_payload.get('event_id', ''),
                "response_id": data_payload.get("response_id", ""),
            }
        elif callback_type == "PISAVedioText":
            slim = {
                "kind": "vision",
                "image": data.get("image", ""),
                "image_text": data.get("image_text", ""),
                "event_id": data_payload.get('event_id', ''),
                "response_id": data_payload.get("response_id", ""),
            }
        if slim is None:
            return
        with self._dialogue_lock:
            self._dialogue_events.append(slim)

    @staticmethod
    def _build_pisa_dialogue_scheme_b(events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        方案 B：prelude + rounds。尾部未挂靠 ASR 的 vision 并入最后一轮 images（B-tail-1）；
        若尚无 round 仅有 pending_images，则追加 asr 为空的单轮。
        """
        prelude: List[Dict[str, Any]] = []
        rounds: List[Dict[str, Any]] = []
        pending_images: List[Dict[str, str]] = []
        current_round: Optional[Dict[str, Any]] = None

        for ev in events:
            k = ev.get("kind")
            if k == "vision":
                pending_images.append(
                    {
                        "image": ev.get("image", ""),
                        "image_text": ev.get("image_text", ""),
                    }
                )
            elif k == "asr":
                current_round = {
                    "round": len(rounds) + 1,
                    "images": list(pending_images),
                    "asr": ev.get("asr", ""),
                    "outputs": [],
                }
                pending_images = []
                rounds.append(current_round)
            elif k == "tts":
                item = {
                    "type": "tts",
                    "response_type": ev.get("response_type", ""),
                    "tts": ev.get("tts", ""),
                    "event_id": ev.get("event_id", ""),
                    "response_id": ev.get("response_id", ""),
                }
                if current_round is not None:
                    current_round["outputs"].append(item)
                else:
                    prelude.append(item)
            elif k == "tool":
                item = {
                    "type": "tool",
                    "tool_name": ev.get("tool_name", ""),
                    "tool_result": ev.get("tool_result", ""),
                    "event_id": ev.get("event_id", ""),
                    "response_id": ev.get("response_id", ""),
                }
                if current_round is not None:
                    current_round["outputs"].append(item)
                else:
                    prelude.append(item)

        if pending_images:
            if rounds:
                rounds[-1]["images"].extend(pending_images)
            else:
                rounds.append(
                    {
                        "round": 1,
                        "images": list(pending_images),
                        "asr": "",
                        "outputs": [],
                    }
                )

        return {"prelude": prelude, "rounds": rounds, "timestamp": datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')}

    def _emit_callback(self, callback_type: str, data: dict):
        """将回调数据写入 AssertionDataManager。"""
        self._append_dialogue_event(callback_type, data)
        if self.m_callback:
            try:
                self.m_callback(self.client_name, 0, data, "0", callback_type)
            except Exception as e:
                logger.error(f"[PIS] _emit_callback 写入失败：{e}")

    def _get_event_flag(self, event_type: str) -> threading.Event:
        """获取或创建指定事件类型的信号量（懒加载）。"""
        with self._event_lock:
            if event_type not in self._event_flags:
                self._event_flags[event_type] = threading.Event()
            return self._event_flags[event_type]

    def _event_matches_filter(self, event_type: str, event: dict) -> bool:
        """检查 event 是否满足当前 WAIT 的过滤条件。无过滤时返回 True。"""
        if not self._wait_event_filter or self._wait_event_filter.get("event") != event_type:
            return True
        resp = event.get("response", {})
        for key, expected in self._wait_event_filter.items():
            if key == "event":
                continue
            if resp.get(key) != expected:
                return False
        return True

    def _set_event_flag(self, event_type: str):
        """触发指定事件类型的信号量，唤醒 WAIT 阻塞的主线程。"""
        with self._event_lock:
            if event_type not in self._event_flags:
                self._event_flags[event_type] = threading.Event()
            self._event_flags[event_type].set()
