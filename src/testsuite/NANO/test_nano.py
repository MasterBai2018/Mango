#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2025/09/28
# @Author  : Claude Code
# @File    : test_nano.py
# @Software: PyCharm
# @Mail    : noreply@anthropic.com
import os
import pytest
import json
from html import escape
import allure
from loguru import logger
from src.core.Reporter import Reporter
from src.utils.jsonUtil import JsonUtil
from src.utils.common import color_template, print_streaming_line
from src.core.BaseTestCase import BaseTestCase
from src.testsuite.NANO.dsl_engine import DSLCase
from src.testsuite.NANO.runner.NANORunner import NANORunner
from src.testsuite.NANO.assertion.AssertionDataManager import AssertionDataManager
suite_dir = os.environ.get("MONGO_SUITE_DIR")


class TestNANO(BaseTestCase):
    """NANO测试套件 - 基于DSL语言驱动的测试框架"""

    SuiteName = "NANO"
    SuiteSummary = "DSL自定义语言测试Suite"

    # 回调结果收集器
    assert_data = AssertionDataManager()
    
    # DSL指令执行器
    nano_runner: NANORunner = None

    # 识别结果保存文件
    asr_report = Reporter(report_dir=suite_dir, report_name="asr", report_type="csv")
    asr_report.set_header(["voice", "result", "type", "channel", "start", "end", "audiotime", "confidence", "lang"])

    # 唤醒结果保存文件
    wakeup_report = Reporter(report_dir=suite_dir, report_name="wakeup", report_type="csv", delimiter=",")
    wakeup_report.set_header(["audio", "result", "start", "end", "channel"])

    # 全量回调数据保存文件（整个session共用，记录所有非污染数据）
    callback_report = Reporter(report_dir=suite_dir, report_name="callback", report_type="jsonl")

    # PIS 大模型对话汇总（每 DSL Case 一行，[PIS]STOP 时由客户端回调 PISDialogueSummary，此处写入 case.index）
    pisa_llm_dialogue_report = Reporter(report_dir=suite_dir, report_name="pisa_llm_result", report_type="jsonl")

    # 当前执行的 DSL Case index，供 PISDialogueSummary 写入 jsonl 时合并
    _current_pisa_case_index = None

    @pytest.fixture(scope="function", autouse=True)
    def nano_case_setup_fixture(self, pytestconfig, request, base_session_fixture):
        all_case_list = pytestconfig.shared_case_list
        case_setup_case = next((case for case in all_case_list if case.is_case_setup()), None)
        if case_setup_case:
            self.__class__.nano_runner.execute_case("CASE_SETUP", case_setup_case.commands)
        yield

        case_teardown_case = next((case for case in all_case_list if case.is_case_teardown()), None)
        if case_teardown_case:
            self.__class__.nano_runner.execute_case("CASE_TEARDOWN", case_teardown_case.commands)
    
    @pytest.fixture(scope="session", autouse=True)
    def nano_class_fixture(self, pytestconfig, request, base_session_fixture):
        # 创建执行器
        self.__class__.nano_runner = NANORunner(pytestconfig, self.__class__.assert_data, self.assert_config)
        
        # 注册各种客户端回调
        self.__class__.nano_runner.client_manager.set_client_callback(
            aibs_callback=self.aibs_client_callback,
            nissan_callback=self.nissan_client_callback,
            speech_callback=self.speech_client_callback,
            pstt_callback=self.pstt_client_callback,
            titan_callback=self.titan_client_callback,
            carplay_callback=self.carplay_client_callback,
            pis_callback=self.pis_client_callback,
            tss_callback=self.tss_client_callback,
        )

        # 查找并执行SETUP
        all_case_list = pytestconfig.shared_case_list
        setup_case = next((case for case in all_case_list if case.is_setup()), None)
        if setup_case:
            # SETUP阶段不注入CASEID，避免误用到非TEST流程
            pytestconfig.case_id = None
            self.__class__.nano_runner.execute_case("CLASS_SETUP", setup_case.commands)
            self.__class__.assert_data.clear_case_data()

        yield

        # 查找并执行TEARDOWN
        teardown_case = next((case for case in all_case_list if case.is_teardown()), None)
        if teardown_case:
            # TEARDOWN阶段不注入CASEID，避免沿用上一个TEST Case值
            pytestconfig.case_id = None
            self.__class__.nano_runner.execute_case("CLASS_TEARDOWN", teardown_case.commands)
        
        # 清理资源
        if self.__class__.nano_runner:
            self.__class__.nano_runner.cleanup()

    @classmethod
    def _write_callback_jsonl(cls, client_name: str, status: int, callback_type: str, result_data: dict):
        """将回调数据包装元数据后写入jsonl文件"""
        try:
            record = {
                "client": client_name,
                "status": status,
                "callback_type": callback_type,
                "data": result_data
            }
            cls.callback_report.write_json_row(record)
        except Exception as e:
            logger.error(f"写入回调jsonl失败: {e}, client_name:{client_name}, callback_type:{callback_type}")

    @classmethod
    def setup_class(cls, **kwargs):
        """测试套件初始化 - NANO使用独立的客户端架构"""
        # NANO套件不需要传统的回调参数，使用独立的架构
        super().setup_class()

    @classmethod
    def teardown_class(cls):
        """测试套件清理 - NANO使用独立清理机制"""
        # 刷新report缓冲区
        cls.asr_report.flush()
        cls.wakeup_report.flush()
        cls.callback_report.flush()
        cls.pisa_llm_dialogue_report.flush()
        logger.info("NANO测试套件清理完成")
    
    @classmethod
    def parse_asr_result(cls, callback_type: str, result_data: dict, channel: str = "", audio_path: str = "") -> str:
        try:
            # 解析识别文本
            text = JsonUtil.parse(result_data, cls.assert_config[callback_type].get('asr'))
            start_time = JsonUtil.parse(result_data, cls.assert_config[callback_type].get('start'))
            start_time_seconds = str(round(float(int(start_time) / 1000), 2))
            end_time = JsonUtil.parse(result_data, cls.assert_config[callback_type].get('end'))
            end_time_seconds = str(round(float(int(end_time) / 1000), 2))
            # 获取音频进度单位: s
            audiotime = result_data.get('audiotime', '')
            confidence = JsonUtil.parse(result_data, cls.assert_config[callback_type].get('confidence'))
            lang = JsonUtil.parse(result_data, cls.assert_config[callback_type].get('lang'))
            row = [str(audio_path), str(text), callback_type, str(channel), start_time_seconds, end_time_seconds, audiotime, confidence, lang]
            cls.asr_report.write_row(row)
            return text
        except Exception as e:
            logger.error(f"保存ASR结果失败: {e}, callback_type={callback_type}")
            return ""

    @classmethod
    def parse_wakeup_result(cls, callback_type: str, result_data: dict, channel: str = "", audio_path: str = "") -> str:
        try:
            # 解析唤醒文本
            text = JsonUtil.parse(result_data, cls.assert_config[callback_type].get('text'))
            # 解析开始时间戳（毫秒）
            start_time_ms = JsonUtil.parse(result_data, cls.assert_config[callback_type].get('start'))
            # 解析结束时间戳（毫秒）
            end_time_ms = JsonUtil.parse(result_data, cls.assert_config[callback_type].get('end'))
            
            # 检查时间戳是否有效（JsonUtil.parse失败时返回字符串"None"）
            if start_time_ms is None or start_time_ms == "None" or str(start_time_ms).strip() == "":
                logger.warning(f"唤醒结果开始时间戳无效: {start_time_ms}, callback_type={callback_type}")
                start_time_ms = 0
            if end_time_ms is None or end_time_ms == "None" or str(end_time_ms).strip() == "":
                logger.warning(f"唤醒结果结束时间戳无效: {end_time_ms}, callback_type={callback_type}")
                end_time_ms = 0
            
            base_timestamp_str = os.environ.get("AUDIO_BASE_TIMESTAMP")
            logger.debug(f"解析基准时间, base_timestamp_str: {base_timestamp_str}")
            # 检查环境变量是否有效（可能是None对象、字符串"None"或空字符串）
            if base_timestamp_str is None or base_timestamp_str == "None" or str(base_timestamp_str).strip() == "":
                base_timestamp_str = "0"
            base_timestamp = int(base_timestamp_str)
            # 计算相对时间（秒）：(绝对时间戳 - 基准时间戳) / 1000
            start_time_seconds = round((int(start_time_ms) - base_timestamp) / 1000.0, 2)
            end_time_seconds = round((int(end_time_ms) - base_timestamp) / 1000.0, 2)
            # 写入CSV行：["audio", "result", "start", "end", "channel"]
            row = [str(audio_path), str(text), str(start_time_seconds), str(end_time_seconds), str(channel)]
            cls.wakeup_report.write_row(row)
            return result_data
        except Exception as e:
            logger.error(f"保存唤醒结果失败: {e}, callback_type={callback_type}")
            return result_data

    @classmethod
    def speech_client_callback(cls, client_name: str, status: int, result_data: dict):
        """
        SpeechEngineClient回调处理
        Args:
            client_name: 客户端名称 (HWK)
            status: 回调状态码
            result_data: 回调数据字典
        """
        try:
            audio_path = result_data.get('audio', 'NULL')
            callback_type = JsonUtil.parse(result_data, 'type')
            channel = JsonUtil.parse(result_data, 'channelId')
            color = color_template.get(client_name, None)
            cls._write_callback_jsonl(client_name, status, callback_type, result_data)
            if callback_type in ["SpeechASRResultTemp", "SpeechASRResult"]:
                callback_msg = cls.parse_asr_result(callback_type, result_data, channel, audio_path)
                cls.assert_data.add_callback_data(client_name, status, result_data, channel, callback_type)
                logger.success(color % f"[{client_name}] [>>>回调>>>] [{channel}][{callback_type}] {callback_msg}")
            elif callback_type in ["SpeechEngineWakeup"]:
                callback_msg = cls.parse_wakeup_result(callback_type, result_data, channel, audio_path)
                cls.assert_data.add_callback_data(client_name, status, result_data, channel, callback_type)
                logger.success(color % f"[{client_name}] [>>>回调>>>] [{channel}][{callback_type}] {callback_msg}")
            else:
                callback_msg = json.dumps(result_data, ensure_ascii=False, separators=(',', ':'))
                logger.success(color % f"[{client_name}] [>>>回调>>>] [{channel}][{callback_type}] {callback_msg}")
        except Exception as e:
            logger.error(f"SpeechEngineClient回调处理异常: {e}, result_data:{result_data}, client_name:{client_name}, status:{status}")

    @classmethod
    def pstt_client_callback(cls, client_name: str, status: int, result_data: dict):
        """
        PSTTClient回调处理
        Args:
            client_name: 客户端名称 (PST)
            status: 回调状态码
            result_data: 回调数据字典
        """
        try:
            audio_path = result_data.get('audio', '')
            callback_type = JsonUtil.parse(result_data, 'type')
            channel = JsonUtil.parse(result_data, 'channelId')
            color = color_template.get(client_name, None)
            cls._write_callback_jsonl(client_name, status, callback_type, result_data)
            if callback_type in ["PSTTASRResultTemp", "PSTTASRResult"]:
                callback_msg = cls.parse_asr_result(callback_type, result_data, channel, audio_path)
                cls.assert_data.add_callback_data(client_name, status, result_data, channel, callback_type)
                logger.success(color % f"[{client_name}] [>>>回调>>>] [{channel}][{callback_type}] {callback_msg}")
            else:
                callback_msg = json.dumps(result_data, ensure_ascii=False, separators=(',', ':'))
                logger.success(color % f"[{client_name}] [>>>回调>>>] [{channel}][{callback_type}] {callback_msg}")
        except Exception as e:
            logger.error(f"PSTTClient回调处理异常: {e}, result_data:{result_data}, client_name:{client_name}, status:{status}")

    @classmethod
    def titan_client_callback(cls, client_name: str, status: int, result_data: dict):
        """
        PSTTClient回调处理
        Args:
            client_name: 客户端名称 (TIA)
            status: 回调状态码
            result_data: 回调数据字典
        """
        try:
            audio_path = result_data.get('audio', '')
            callback_type = JsonUtil.parse(result_data, 'type')
            channel = JsonUtil.parse(result_data, 'channelId')
            color = color_template.get(client_name, None)
            cls._write_callback_jsonl(client_name, status, callback_type, result_data)
            if callback_type in ["TiTanASRResultTemp", "TiTanASRResult"]:
                callback_msg = cls.parse_asr_result(callback_type, result_data, channel, audio_path)
                cls.assert_data.add_callback_data(client_name, status, result_data, channel, callback_type)
                logger.success(color % f"[{client_name}] [>>>回调>>>] [{channel}][{callback_type}] {callback_msg}")
            else:
                callback_msg = json.dumps(result_data, ensure_ascii=False, separators=(',', ':'))
                logger.success(color % f"[{client_name}] [>>>回调>>>] [{channel}][{callback_type}] {callback_msg}")
        except Exception as e:
            logger.error(f"TitanClient回调处理异常: {e}, result_data:{result_data}, client_name:{client_name}, status:{status}")

    @classmethod
    def aibs_client_callback(cls, client_name: str, status: int, result_data: dict):
        """
        AIBSClient专用的客户端回调处理函数
        处理NANO客户端的回调，与传统的TestBaseSuite回调分离
        支持彩色输出和结果收集，便于测试断言和调试
        Args:
            client_name: 客户端名称 (TSA, TTS, SET, VOI, OMS等)
            status: 回调状态码
            result_data: 回调数据字典
        """
        try:
            # 获取回调数据中的类型字段
            audio_path = result_data.get('audio', 'NULL')
            callback_type = JsonUtil.parse(result_data, 'type')
            skill, intention = None, None # 初始化skill和intention

            # 优先处理NLPResult，并过滤污染数据
            if callback_type == "NLPResult":
                skill = JsonUtil.parse(result_data, 'data.skill')
                intention = JsonUtil.parse(result_data, 'data.intention')
                text = JsonUtil.parse(result_data, 'data.asr.text')
                channel = JsonUtil.parse(result_data, cls.assert_config[callback_type].get('channelId'))

                # 如果channelID是-1说明不是正常数据，也过滤
                if str(channel) == "-1":
                    logger.debug(f"[{client_name}] 过滤污染数据: channelID=-1")
                    return  # 不再处理此回调

                # 过滤污染数据
                if skill in ["VPA_ACTION"] or intention in ["VPA_ACTION", "SceneSleep", "ignore"]:
                    logger.debug(f"[{client_name}] 过滤污染数据: skill=VPA_ACTION/Sleep/ignore, intention=VPA_ACTION/SceneSleep/ignore")
                    return  # 不再处理此回调
                
                # 记录声纹登录的通道ID、开始时间和结束时间
                if skill == "VoicePrint" and intention == "login":
                    channel = JsonUtil.parse(result_data, cls.assert_config[callback_type].get('channelId'))
                    start = JsonUtil.parse(result_data, cls.assert_config[callback_type].get('start'))
                    end = JsonUtil.parse(result_data, cls.assert_config[callback_type].get('end'))
                    os.environ["VOICE_LOGIN_NLP"] = f"{channel} {start} {end}"

            if callback_type in cls.assert_config:
                # 非TSA客户端的LCSInit回调，不记录在断言结果集中
                if callback_type == "LCSInit" and client_name != "TSA":
                    return
                if callback_type == "LCSInit":
                    result_data.update({"channelId": 0})

                channel = JsonUtil.parse(result_data, cls.assert_config[callback_type].get('channelId'))
                # 获取客户端对应的颜色，默认为None（无颜色显示）
                color = color_template.get(client_name, None)
                # JSON格式收集回调结果
                cls.assert_data.add_callback_data(client_name, status, result_data, channel, callback_type)
                cls._write_callback_jsonl(client_name, status, callback_type, result_data)

                callback_msg = ""
                # 解析回调数据并格式化打印
                if callback_type in ["ASRResult", "cloudASRResult", "localASRResult", "ASRInputResult", "ASRInputResultTemp", "ASRResultTemp"]:
                    callback_msg = cls.parse_asr_result(callback_type, result_data, channel, audio_path)
                elif callback_type in ["SpeechWakeup"]:
                    callback_msg = cls.parse_wakeup_result(callback_type, result_data, channel, audio_path)
                elif callback_type in ["NLPResult"]:
                    text = JsonUtil.parse(result_data, 'data.asr.text')
                    dirCallback = JsonUtil.parse(result_data, cls.assert_config[callback_type].get('dirCallbackType'))
                    dirCallbackId = JsonUtil.parse(result_data, cls.assert_config[callback_type].get('dirCallbacketId'))
                    tts = JsonUtil.parse(result_data, cls.assert_config[callback_type].get('tts'))
                    callback_msg = f"skill:{skill}  intention:{intention}  text:{text}  dirCallback:{dirCallback}  dirCallbackId:{dirCallbackId}  tts:{tts}"
                elif callback_type in ["HICARWakeup", "startEnroll"]:
                    callback_msg = json.dumps(result_data, ensure_ascii=False, separators=(',', ':'))
                else:
                    callback_msg = json.dumps(result_data, ensure_ascii=False, separators=(',', ':'))

                logger.success(color % f"[{client_name}] [>>>回调>>>] [{channel}][{callback_type}] {callback_msg}")

        except Exception as e:
            logger.error(f"NANO客户端回调处理异常: {e}, assert_data:{result_data}")
    

    @classmethod
    def nissan_client_callback(cls, client_name: str, status: int, result_data: dict):
        """
        NissanAIBSClient专用的客户端回调处理函数
        Args: client_name: 客户端名称 (NIS) status: 回调状态码
        result_data: 回调数据字典
        """
        try:
            # 获取回调数据中的类型字段
            audio_path = result_data.get('audio', 'NULL')
            callback_type = JsonUtil.parse(result_data, 'type')
            skill, intention = None, None # 初始化skill和intention

            # 优先处理NLPResult，并过滤污染数据
            if callback_type == "NLPResult":
                skill = JsonUtil.parse(result_data, 'data.skill')
                intention = JsonUtil.parse(result_data, 'data.intention')
                text = JsonUtil.parse(result_data, 'data.asr.text')
                channel = JsonUtil.parse(result_data, cls.assert_config[callback_type].get('channelId'))

                # 如果channelID是-1说明不是正常数据，也过滤
                if str(channel) == "-1":
                    logger.debug(f"[{client_name}] 过滤污染数据: channelID=-1")
                    return  # 不再处理此回调

                # 过滤污染数据
                if skill in ["VPA_ACTION"] or intention in ["VPA_ACTION", "SceneSleep"]:
                    logger.debug(f"[{client_name}] 过滤污染数据: skill=VPA_ACTION/Sleep/ignore, intention=VPA_ACTION/SceneSleep/ignore")
                    return  # 不再处理此回调
                
                # 记录声纹登录的通道ID、开始时间和结束时间
                if skill == "VoicePrint" and intention == "login":
                    channel = JsonUtil.parse(result_data, cls.assert_config[callback_type].get('channelId'))
                    start = JsonUtil.parse(result_data, cls.assert_config[callback_type].get('start'))
                    end = JsonUtil.parse(result_data, cls.assert_config[callback_type].get('end'))
                    os.environ["VOICE_LOGIN_NLP"] = f"{channel} {start} {end}"

            if callback_type in cls.assert_config:
                channel = JsonUtil.parse(result_data, cls.assert_config[callback_type].get('channelId'))
                # 获取客户端对应的颜色，默认为None（无颜色显示）
                color = color_template.get(client_name, None)
                # JSON格式收集回调结果
                cls.assert_data.add_callback_data(client_name, status, result_data, channel, callback_type)
                cls._write_callback_jsonl(client_name, status, callback_type, result_data)

                callback_msg = ""
                # 解析回调数据并格式化打印
                if callback_type in ["ASRResult", "cloudASRResult", "localASRResult", "ASRInputResult", "ASRInputResultTemp", "ASRResultTemp"]:
                    callback_msg = cls.parse_asr_result(callback_type, result_data, channel, audio_path)
                elif callback_type in ["SpeechWakeup"]:
                    callback_msg = cls.parse_wakeup_result(callback_type, result_data, channel, audio_path)
                elif callback_type in ["NLPResult"]:
                    text = JsonUtil.parse(result_data, 'data.asr.text')
                    dirCallback = JsonUtil.parse(result_data, cls.assert_config[callback_type].get('dirCallbackType'))
                    dirCallbackId = JsonUtil.parse(result_data, cls.assert_config[callback_type].get('dirCallbacketId'))
                    tts = JsonUtil.parse(result_data, cls.assert_config[callback_type].get('tts'))
                    callback_msg = f"skill:{skill}  intention:{intention}  text:{text}  dirCallback:{dirCallback}  dirCallbackId:{dirCallbackId}  tts:{tts}"
                elif callback_type in ["HICARWakeup", "startEnroll"]:
                    callback_msg = json.dumps(result_data, ensure_ascii=False, separators=(',', ':'))
                else:
                    callback_msg = json.dumps(result_data, ensure_ascii=False, separators=(',', ':'))

                logger.success(color % f"[{client_name}] [>>>回调>>>] [{channel}][{callback_type}] {callback_msg}")

        except Exception as e:
            import traceback
            traceback.print_exc()
            logger.error(f"NANO客户端回调处理异常: {e}, assert_data:{result_data}")

    @classmethod
    def carplay_client_callback(cls, client_name: str, callback_type: str, result_data: dict):
        """
        CarPlayClient专用的客户端回调处理函数
        处理CarPlay SDK的各种回调：唤醒词检测、VAD状态、音频数据、状态变化
        
        Args:
            client_name: 客户端名称 (CPL)
            callback_type: 回调类型 (CarPlayWakeup, CarPlayVad, CarPlayAudio, CarPlayStatus)
            result_data: 回调数据字典
        """
        try:
            # 获取客户端对应的颜色
            color = color_template.get(client_name, None)
            cls._write_callback_jsonl(client_name, 0, callback_type, result_data)

            # CarPlay回调数据格式化
            if callback_type == "CarPlayWakeup":
                # 唤醒词检测回调
                text = result_data.get('text', '')
                kad_start = result_data.get('kadStart', 0)
                kad_end = result_data.get('kadEnd', 0)
                duration = result_data.get('duration', 0)
                callback_msg = f"text:{text}  kadStart:{kad_start}  kadEnd:{kad_end}  duration:{duration}"
                cls.assert_data.add_callback_data(client_name, 0, result_data, 0, callback_type)
                logger.success(color % f"[{client_name}] [>>>回调>>>] [0][{callback_type}] {callback_msg}")
                
            elif callback_type.startswith("CarPlayVad"):
                # VAD状态回调
                state = result_data.get('state', -1)
                timestamp = result_data.get('timestamp', None)
                state_str = "开始" if state == 0 else "结束"
                callback_msg = f"state:{state}({state_str})  timestamp:{timestamp}"
                cls.assert_data.add_callback_data(client_name, 0, result_data, 0, callback_type)
                logger.success(color % f"[{client_name}] [>>>回调>>>] [0][{callback_type}] {callback_msg}")
                
            elif callback_type == "CarPlayStatus":
                # CarPlay状态回调
                code = result_data.get('code', -1)
                text = result_data.get('text', '')
                callback_msg = f"code:{code}  text:{text}"
                cls.assert_data.add_callback_data(client_name, 0, result_data, 0, callback_type)
                logger.success(color % f"[{client_name}] [>>>回调>>>] [0][{callback_type}] {callback_msg}")

        except Exception as e:
            logger.error(f"CarPlayClient回调处理异常: {e}, callback_type:{callback_type}, result_data:{result_data}")

    @classmethod
    def pis_client_callback(cls, client_name: str, status: int, result_data: dict, channel: str, callback_type: str):
        """
        PISALLMClient 回调处理函数（全双工大模型 WebSocket 客户端）。

        签名对齐 AssertionDataManager.add_callback_data：
            (client_name, status, result_data, channel, callback_type)

        回调类型：
            PISASRResult       — 用户语音识别结果
            PISToolCall        — 大模型工具调用结果（车控等）
            PISDialogueSummary — [PIS]STOP 时本 Case 对话方案 B 汇总（prelude / rounds），无 case 元信息
        """
        try:
            color = color_template.get(client_name, None)
            cls._write_callback_jsonl(client_name, status, callback_type, result_data)

            if callback_type == "PISDialogueSummary":
                row = dict(result_data)
                idx = cls._current_pisa_case_index
                if idx is not None:
                    row["case"] = {"index": idx}
                try:
                    cls.pisa_llm_dialogue_report.write_json_row(row)
                except Exception as e:
                    logger.error(f"写入 pisa_llm_result.jsonl 失败: {e}")
                logger.info(
                    f"[{client_name}] PISDialogueSummary 已写入 pisa_llm_result.jsonl "
                    f"(case.index={idx})"
                )
                return

            if callback_type == "PISASRResult":
                text = result_data.get("asr", "")
                cls.assert_data.add_callback_data(client_name, status, result_data, channel, callback_type)
                logger.success(color % f"[{client_name}] [>>>回调>>>] [{channel}][{callback_type}] {text}")
            
            elif callback_type == "ResponseTTSTemp":
                tts_tmp = result_data.get("tts", "")
                cls.assert_data.add_callback_data(client_name, status, result_data, channel, callback_type)
                prefix = f"[{client_name}] [>>>回调>>>] [{channel}][{callback_type}] "
                print_streaming_line(prefix, tts_tmp, color, newline=False)
            
            elif callback_type == "ResponseTTS":
                tts = result_data.get("tts", "")
                response_type = result_data.get("response_type", "")
                cls.assert_data.add_callback_data(client_name, status, result_data, channel, callback_type)
                prefix = f"[{client_name}] [>>>回调>>>] [{channel}][{callback_type}] "
                print_streaming_line(prefix, f"[{response_type}]: {tts}", color, newline=True)

            elif callback_type == "PISToolCall":
                tool_result = result_data.get("tool_result", "")
                item_id = result_data.get("item_id", "")
                tool_name = result_data.get("tool_name", "")
                cls.assert_data.add_callback_data(client_name, status, result_data, channel, callback_type)
                logger.success(color % f"[{client_name}] [>>>回调>>>] [{channel}][{callback_type}] tool_name={tool_name} {tool_result}")

            elif callback_type == "PISAVedioText":
                image = result_data.get("image", "")
                image_text = result_data.get("image_text", "")
                cls.assert_data.add_callback_data(client_name, status, result_data, channel, callback_type)
                logger.success(color % f"[{client_name}] [>>>回调>>>] [{channel}][{callback_type}] {image}: {image_text}")

            elif callback_type == "PISAIBSEvent":
                cls.assert_data.add_callback_data(client_name, status, result_data, channel, callback_type)
                logger.success(color % f"[{client_name}] [>>>回调>>>] [{channel}][{callback_type}] {result_data}")

            else:
                callback_msg = json.dumps(result_data, ensure_ascii=False, separators=(',', ':'))
                logger.debug(color % f"[{client_name}] [>>>回调>>>] [{callback_type}] {callback_msg}")

        except Exception as e:
            logger.error(f"PISALLMClient回调处理异常: {e}, callback_type={callback_type}, result_data={result_data}")

    @classmethod
    def tss_client_callback(cls, client_name: str, status: int, result_data: dict, channel: str, callback_type: str):
        """TSSClient 回调处理函数。"""
        try:
            callback_type = JsonUtil.parse(result_data, 'type')
            audio_path = result_data.get('audio', 'NULL')
            color = color_template.get(client_name, color_template.get("TSS"))
            cls._write_callback_jsonl(client_name, status, callback_type, result_data)
            cls.assert_data.add_callback_data(client_name, status, result_data, channel, callback_type)
            if callback_type in ["TSSAIBSWakeup"]:
                callback_msg = cls.parse_wakeup_result(callback_type, result_data, channel, audio_path)
                logger.success(color % f"[{client_name}] [>>>回调>>>] [{channel}][{callback_type}] {callback_msg}")
            else:
                callback_msg = json.dumps(result_data, ensure_ascii=False, separators=(',', ':'))
                logger.success(color % f"[{client_name}] [>>>回调>>>] [{channel}][{callback_type}] {callback_msg}")
        except Exception as e:
            logger.error(f"TSSClient回调处理异常: {e}, callback_type={callback_type}, result_data={result_data}")

    def test_nano(self, pytestconfig, testcase: DSLCase):
        # 始终展示 Case 基础信息；如果是参数化 Case，再附加参数表格
        
        case_info_rows = [
            ("Case简介(Bref)", testcase.comment or "-"),
            ("Case文件(-a)", testcase.casefile or "-"),
            ("Case行范围(-F)", testcase.case_line_range or "-"),
            ("参数化文件(-P)", pytestconfig.getoption('--mongo_parameterized_data')),
            ("参数化行范围(-PF)", testcase.param_line_range or "-"),
        ]

        case_info_html = "".join(f"<tr><td><b>{escape(str(key))}</b></td><td>{escape(str(value))}</td></tr>" for key, value in case_info_rows)
        html = (
            "<table border='1' cellpadding='4' cellspacing='0'>"
            "<tr><th>参数</th><th>说明</th></tr>"
            f"{case_info_html}"
            "</table>"
        )

        allure.dynamic.description_html(html)

        # 清理之前的回调结果
        self.__class__.assert_data.clear_case_data()
        self.__class__.nano_runner.assertion_engine.clear_assertion_results()

        self.__class__._current_pisa_case_index = testcase.index

        # 获取用例信息
        pytestconfig.case_dir = os.path.join(str(pytestconfig.suite_dir), str(testcase.index))
        # 仅在真正TEST Case执行时注入CASEID，值来源于case.unique_id
        pytestconfig.case_id = testcase.unique_id
        case_name = f"{testcase.casefile}[{testcase.index}]"

        # NANO执行器已在fixture中创建和管理
        if not self.__class__.nano_runner:
            pytest.fail("NANO Runner未初始化，请检查Class Fixture")

        # 执行DSL用例
        self.__class__.nano_runner.execute_case(case_name, testcase.commands, dsl_case=testcase)
        
        # 每个Case运行结束后，如果存在TSA客户端，则清除会话历史
        try:
            if self.__class__.nano_runner.client_manager.has_client("TSA"):
                tsa_client = self.__class__.nano_runner.client_manager.get_client("TSA")
                tsa_client.internal_vr_event({"source":"TSA","type":"ClearContext","data":{}})
                logger.debug(f"[NANO] Case执行完成，已清除TSA会话历史: {case_name}")
        except Exception as e:
            logger.warning(f"[NANO] 清除TSA会话历史失败: {e}")
        
        assertion_stats = self.__class__.nano_runner.assertion_engine.get_assertion_stats()

        assert assertion_stats['all_passed']
