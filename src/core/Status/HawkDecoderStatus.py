#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/5/29 13:51
# @Author  : liutianwei
# @File    : HawkDecoderStatus.py
# @Software: PyCharm

from ctypes import c_int


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


class SpeechEngineParam:
    SPEECH_ENGINE_PARAM_LINK_TYPE = c_int(0x01)
    SPEECH_ENGINE_PARAM_SEAT_SIGNAL = c_int(0x02)
    SPEECH_ENGINE_FULL_VEHICLE_SPEECH = c_int(0x03)
    SPEECH_ENGINE_PARAM_REAL_TIME_RESULT = c_int(0x04)
    SPEECH_ENGINE_PARAM_PUNC_RESULT = c_int(0x05)
    SPEECH_ENGINE_PARAM_DIGIT_CONVERT_RESULT = c_int(0x06)
    SPEECH_ENGINE_PARAM_SILENCE_DURATION = c_int(0x07)
    SPEECH_ENGINE_PARAM_SILENCE_TIMEOUT = c_int(0x08)
    SPEECH_ENGINE_PARAM_SPEECH_TIMEOUT = c_int(0x09)
    SPEECH_ENGINE_PARAM_SCENAROI_NAME = c_int(0x0A)
    SPEECH_ENGINE_PARAM_WAKEUP_SCENE = c_int(0x0B)
    SPEECH_ENGINE_PARAM_WAKEUP_DELAY_ONESHOT_DURATION = c_int(0x0C)
    SPEECH_ENGINE_PARAM_SOUND_EVENT_OPTION = c_int(0x0D)
    SPEECH_ENGINE_PARAM_EMOTION_OPTION = c_int(0x0F)
    SPEECH_ENGINE_PARAM_HMI_CONTEXT = c_int(0x51)
    SPEECH_ENGINE_PARAM_SR_PTT_OPTION = c_int(0x18)
    SPEECH_ENGINE_PARAM_SR_REALTIME_RESULT = c_int(0x11)
    SPEECH_ENGINE_PARAM_SR_VOICE_WAKEUP = c_int(0x12)
    SPEECH_ENGINE_PARAM_FULLTIME_OPTION = c_int(0x13)
    SPEECH_ENGINE_PARAM_SR_WAKEUP_SCENE_ENABLE = c_int(0x14)


class SpeechEngineWorkMode:
    engine_mode_WAKEUP = c_int(0x00)    # when only switching to wakeup
    engine_mode_ASR = c_int(0x01)       # when only switching to asr
    engine_mode_WAKEUP_ASR = c_int(0x02)    # when switching to wakeup, asr, nlp


class MongoCode:
    STATUS_MONGO_ASSERT = 999             # 断言信号
    STATUS_MONGO_FINISH = 1000            # 最终断言信号
