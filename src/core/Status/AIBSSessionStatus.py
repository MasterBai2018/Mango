#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2023/8/2 14:08
# @Author  : huidong.bai
# @File    : AIBSSessionStatus.py
# @Software: PyCharm
# @Mail    : MasterBai2018@outlook.com

from ctypes import c_int


class AIBSStatusCode:
    STATUS_AIBS_INIT_SUCCESS = 1           # 初始化成功
    STATUS_AIBS_INIT_FAILED = 2            # 初始化失败
    STATUS_AIBS_SESSION_START_SUCCESS = 3  # 开始会话成功
    STATUS_AIBS_SESSION_START_FAILED = 4   # 开始会话失败
    STATUS_AIBS_EVENT = 16                 # 事件信息
    STATUS_AIBS_AUDIO_ENERGY = 17          # 音频能量
    STATUS_AIBS_SESSION_FINISH = 32       # 会话结束事件，SessionEnd, 需要解析返回Status
    STATUS_AIBS_SRE_EVENT = 48             # 声纹回调事件
    STATUS_AIBS_VR_CLOSED = 49             # 助手关闭状态回调


class MongoCode:
    STATUS_MONGO_ASSERT = 999             # 断言信号
    STATUS_MONGO_FINISH = 1000            # 最终断言信号


class AIBSParam:
    AIBS_PARAM_SESSION_LINK_TYPE = c_int(0x01)
    AIBS_PARAM_SEAT_SIGNAL = c_int(0x02)
    AIBS_PARAM_FULL_VEHICLE_SPEECH = c_int(0x03)
    AIBS_PARAM_REAL_TIME_RESULT = c_int(0x04)
    AIBS_PARAM_PUNC_RESULT = c_int(0x05)
    AIBS_PARAM_DIGIT_CONVERT_RESULT = c_int(0x06)
    AIBS_PARAM_SILENCE_DURATION = c_int(0x07)
    AIBS_PARAM_SILENCE_TIMEOUT = c_int(0x08)
    AIBS_PARAM_SPEECH_TIMEOUT = c_int(0x09)
    AIBS_PARAM_SCENAROI_NAME = c_int(0x0A)
    AIBS_PARAM_WAKEUP_SCENE = c_int(0x0B)
    AIBS_PARAM_WAKEUP_DELAY_ONESHOT_DURATION = c_int(0x0C)
    AIBS_PARAM_SOUND_EVENT_OPTION = c_int(0x0D)
    AIBS_PARAM_EMOTION_OPTION = c_int(0x0F)
    AIBS_PARAM_DISABLE_BUTTON_WAKEUP = c_int(0x0E)
    AIBS_PARAM_SR_PTT_OPTION = c_int(0x10)
    AIBS_PARAM_SR_VOICE_WAKEUP = c_int(0x12)
    AIBS_PARAM_SR_WAKEUP_SCENE_ENABLE = c_int(0x14)


class AIBSWorkMode:
    aibs_mode_WAKEUP = c_int(0x00)  # 仅唤醒模式
    aibs_mode_ASR = c_int(0x01)  # 仅识别模式
    aibs_mode_WAKEUP_ASR = c_int(0x02)  # 唤醒识别模式
    aibs_mode_SMART_LINK = c_int(0x03)  # 智能联协模式


class AIBSVRConfigCode:
    AIBS_SETTING_DEVICE_INFO = c_int(0x00)                       # 设备信息
    AIBS_SETTING_VR_OPTION = c_int(0x01)                         # TSA助手开关
    AIBS_SETTING_SHOW_STYLE = c_int(0x02)                        # 设置显示风格
    AIBS_SETTING_WAKEUP_ALIAS = c_int(0x03)                      # 设置唤醒词
    AIBS_SETTING_DIALOGUE_STYLE = c_int(0x04)                    # 设置全时模式
    AIBS_SETTING_DIALOGUE_LANGUAGE = c_int(0x05)                 # 设置语种
    AIBS_SETTING_SOUND_AREA_OPTION = c_int(0x06)                 # 设置音区
    AIBS_SETTING_WAKEUP_KEYWORD_OPTION = c_int(0x07)             # 设置场景唤醒词开关
    AIBS_SETTING_VOICE_WAKEUP_OPTION = c_int(0x08)               # 设置语音唤醒开关
    AIBS_SETTING_WAKEUP_ENABLE = c_int(0x09)                     # 设置唤醒词生效
    AIBS_SETTING_GET_WAKEUP_WORD = c_int(0x10)                   # vrConfig获取唤醒词
    AIBS_SETTING_SET_TTS_VOICE_TYPE = c_int(0x11)                # 设置TTS音色
    AIBS_SETTING_MULTI_DIALOGUE = c_int(0x12)                    # 设置多人对话
    AIBS_SETTING_EXPERIENCE_IMPROVENMENT = c_int(0x13)           # 用户体验改善计划
    AIBS_SETTING_PERSONAL_SENSITIVE_AUTHORIZATION = c_int(0x14)  # 个性化交互敏感信息授权
    AIBS_SETTING_VOICE_SENSITIVE_AUTHORIZATION = c_int(0x15)     # 声音敏感信息授权
    AIBS_SETTING_ACTIVE_INTERACTION = c_int(0x17)                # 语音助手主动交互列表
    AIBS_SETTING_SRE_SENSITIVE_EMPOWER_OPTION = c_int(0x18)      # 声纹隐私设置开关
    AIBS_SETTING_SRE_FUNC_ENABLE_OPTION = c_int(0x19)            # 声纹使能开关
    AIBS_SETTING_SERVER_CACHE_LANGUAGE = c_int(0x20)             # 修改缓存语种
    AIBS_SETTING_GPT_ENABLE_OPTION = c_int(0x21)                 # enable gpt option
    AIBS_SETTING_SRE_MEMORY = c_int(0x22)                        # 声纹记忆开关
    AIBS_SETTING_VEHICLE_MEMORY = c_int(0x23)                    # 车辆记忆开关
