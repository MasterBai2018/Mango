#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2025/10/14
# @Author  : huidong.bai
# @File    : config.py
# @Software: PyCharm
# @Mail    : MasterBai2018@outlook.com
import uuid
from src.utils.common import assert_key_value_config, uuid, get_timestamp, get_date

# API断言类型列表
AssertCodeTypeList = [
    # 普通C层接口断言
    'CREATE_RET',
    'START_RET',
    'STOP_RET',
    'FREE_RET',
    'DATA_RET',
    'EVENT_RET',
    'CANCEL_RET',
    'FREEWAKEUP_RET',
    'SETVRCONFIG_RET',
    'PAUSE_RET',
    'RESUME_RET',
    'GET_VERSION_RET',
    'CAR_TYPE_RET',
    'LOG_PATH_RET',
    'MIC_STATUS_RET',
    'VR_STATUS_RET',
    'LINK_TYPE_RET',
    'VREVENT_RET',
    'START_RECORD_RET',
    'STOP_RECORD_RET',
    'OPEN_VOICE_INPUT_RET',
    'CLOSE_VOICE_INPUT_RET',
    'CLEAR_VR_CONFIG_RET',
    'GET_FOTA_STATUS_RET',
    'SET_PARAM_RET',
    'UPDATE_PERSONALIZED_RET',
    'SET_TTS_STATE_RET',
    'SET_PAGE_INTENT_RET',
    'SET_LANGUAGE_MODE_RET',
    'SET_WAKEUP_WORD_RET',
    'SET_WAKEUP_ENABLE_RET',
    'GET_WAKEUP_WORD_RET',
    'SET_WORKMODE_RET',
    'GET_VR_CONFIG_RET',
    'START_SPEAKER_ENROLL_RET',
    'END_SPEAKER_ENROLL_RET',
    'RECOGNIZE_SPEAKER_RET',
    'VOICEPRINT_LOGIN_RET',
    'VERIFY_VOICEPRINT_RET',
    'CANCEL_VERIFY_VOICEPRINT_RET',
    'DELETE_SPEAKER_RET',
    'GET_SPEAKER_INFO_RET',
    'GET_SPEAKERS_RET',
    'GET_ENROLL_TEXT_RET',
    'SENSITIVE_WORD_CHECK_RET',
    'GET_CONFIG_ITEM_RET',
    'WRITE_LOG_RET',
    'CONFIG_VOICELOG_RET',
    'SET_VOICELOG_PATH_RET',


    # VRSETING 参数
    'VR_OPTION_RET',
    'SHOW_STYLE_RET',
    'WAKEUP_ALIAS_RET',
    'DIALOGUE_STYLE_RET',
    'DIALOGUE_LANGUAGE_RET',
    'SOUND_AREA_OPTION_RET',
    'WAKEUP_KEYWORD_OPTION_RET',
    'VOICE_WAKEUP_OPTION_RET',
    'WAKEUP_ENABLE_RET',
    'GET_WAKEUP_WORD_RET',
    'SET_TTS_VOICE_TYPE_RET',
    'MULTI_DIALOGUE_RET',
    'EXPERIENCE_IMPROVENMENT_RET',
    'PERSONAL_SENSITIVE_AUTHORIZATION_RET',
    'VOICE_SENSITIVE_AUTHORIZATION_RET',
    'ACTIVE_INTERACTION_RET',
    'SRE_SENSITIVE_EMPOWER_OPTION_RET',
    'SRE_FUNC_ENABLE_OPTION_RET',
    'SERVER_CACHE_LANGUAGE_RET',
    'GPT_ENABLE_OPTION_RET',
    'SRE_MEMORY_RET',
    'VEHICLE_MEMORY_RET',


    # SET_PARAM参数
    'AIBS_PARAM_SESSION_LINK_TYPE_RET',
    'AIBS_PARAM_SEAT_SIGNAL_RET',
    'AIBS_PARAM_FULL_VEHICLE_SPEECH_RET',
    'AIBS_PARAM_REAL_TIME_RESULT_RET',
    'AIBS_PARAM_PUNC_RESULT_RET',
    'AIBS_PARAM_DIGIT_CONVERT_RESULT_RET',
    'AIBS_PARAM_SILENCE_DURATION_RET',
    'AIBS_PARAM_SILENCE_TIMEOUT_RET',
    'AIBS_PARAM_SPEECH_TIMEOUT_RET',
    'AIBS_PARAM_SCENAROI_NAME_RET',
    'AIBS_PARAM_WAKEUP_SCENE_RET',
    'AIBS_PARAM_WAKEUP_DELAY_ONESHOT_DURATION_RET',
    'AIBS_PARAM_SOUND_EVENT_OPTION_RET',
    'AIBS_PARAM_DISABLE_BUTTON_WAKEUP_RET',
    'AIBS_PARAM_EMOTION_OPTION_RET',
    'AIBS_PARAM_SR_PTT_OPTION_RET',
    'AIBS_PARAM_SR_VOICE_WAKEUP_RET',
    'AIBS_PARAM_SR_WAKEUP_SCENE_ENABLE_RET',
    'AIBS_PARAM_SR_AUDIO_SPECTRAL_RET',
    'AIBS_PARAM_SR_RECORD_DEVICE_STATE_RET',

    # CarPlay相关断言（API返回值）
    'CARPLAY_CREATE_RET',
    'CARPLAY_FREE_RET',
]


# CarPlay回调断言类型列表（用于回调数据断言）
CarPlayCallbackTypeList = [
    'CarPlayWakeup',    # 唤醒词检测回调
    'CarPlayVad',       # VAD状态回调
    'CarPlayAudio',     # 音频数据回调
    'CarPlayStatus',    # CarPlay状态回调
]


# 文件断言指令列表
FILE_ASSERT_COMMANDS = [
    'FILEEXIT',  # 文件存在断言
    'FILESIZE',  # 文件大小断言
    'FILEMD5',   # 文件MD5断言
    'FILEDIF'   # 文件JSON内容断言
]


# DSL环境变量配置
# 定义所有支持的环境变量名称及其对应的获取方式
# 支持四种类型：
#   1. ('attribute', 'attr_name') - 从pytestconfig属性获取
#   2. ('getoption', '--option-name') - 从命令行参数获取
#   3. ('dynamic', function) - 动态生成（每次调用function()生成新值）
#   4. ('environ', 'ENV_VAR_NAME') - 从os.environ读取（由父进程注入）
ENVIRONMENT_VARIABLES = {
    # 路径相关变量 (7个)
    'WORKPATH': ('attribute', 'suite_dir'),           # Suite工作目录
    'ROOTPATH': ('getoption', '--mongo_root_dir'),    # 项目根目录
    'WORKSPACE': ('getoption', '--mongo_workspace'),  # 工作空间路径
    'BASEPATH': ('attribute', 'base_dir'),            # 并发时，每一个worker的路径
    'LIBPATH': ('attribute', 'lib_path'),             # 库文件路径
    'CASEPATH': ('attribute', 'case_dir'),            # 用例目录路径
    'LOGPATH': ('attribute', 'log_path'),             # 日志路径
    'SOCKETPATH': ('attribute', 'socket_path'),       # Socket端口文件路径
    
    # 配置相关变量 (4个)
    'CONFIGPATH': ('attribute', 'decoder_config'),    # 配置文件路径
    'CARPLAYCONFIG': ('attribute', 'carplay_config'), # CarPlay配置文件路径
    'LCSCONFIG': ('attribute', 'lcs_config'),         # LCS配置文件路径
    'CASELIST': ('getoption', '--mongo_case_list'),   # 用例文件路径
    'PARAMETERIZEDATA': ('getoption', '--mongo_parameterized_data'), # 参数化数据文件路径
    
    # 元数据变量 (3个)
    'SUITEID': ('getoption', '--mongo_suite_id'),     # Suite ID
    'SUITENAME': ('getoption', '--mongo_suite_name'), # Suite名称
    'CASEID': ('attribute', 'case_id'),               # Case ID（仅TEST Case注入）
    
    # 动态生成变量 (3个)
    'UUID': ('dynamic', uuid),                        # 随机UUID字符串
    'TIMESTAMP': ('dynamic', get_timestamp),          # 当前时间戳
    'NOW': ('dynamic', get_date),                     # 当前时间日期

    # Loop 相关变量 (3个)，由父进程通过 suite_env 注入子进程 os.environ
    'LOOP_INDEX': ('environ', 'LOOP_INDEX'),          # 当前Loop迭代索引（从0开始）
    'LOOP_VALUE': ('environ', 'LOOP_VALUE'),          # 当前Loop迭代的实际值
    'LOOP_TOTAL': ('environ', 'LOOP_TOTAL'),          # Loop总迭代次数
}


CLIENT_COMMANDS = {
    # TSA客户端指令
    'TSA': [
        # 基础指令
        'CREATE', 'START', 'STOP', 'FREE', 'DATA', 'TEXT_DATA', 'EVENT', 'CANCEL', 'FREEWAKEUP', 'PARALLELSR', 'SETVRCONFIG', 'TEXT', 'STRATEGY',
        # 扩展指令 - 引擎控制
        'PAUSE', 'RESUME', 'GET_VERSION',
        # 扩展指令 - 系统设置
        'CAR_TYPE', 'LOG_PATH', 'MIC_STATUS', 'VR_STATUS', 'LINK_TYPE', 'VREVENT',
        # 扩展指令 - 录音功能
        'START_RECORD', 'STOP_RECORD',
        # 扩展指令 - 语音输入
        'OPEN_VOICE_INPUT', 'CLOSE_VOICE_INPUT',
        # 扩展指令 - 声纹功能
        'START_SPEAKER_ENROLL', 'END_SPEAKER_ENROLL', 'RECOGNIZE_SPEAKER', 'VOICEPRINT_LOGIN', 
        'VERIFY_VOICEPRINT', 'CANCEL_VERIFY_VOICEPRINT', 'DELETE_SPEAKER', 'GET_SPEAKER_INFO', 'GET_SPEAKERS',
        'GET_ENROLL_TEXT', 'SENSITIVE_WORD_CHECK', 'REGISTER_VOICEPRINT_LIST',
        # 扩展指令 - 配置和状态
        'CLEAR_VR_CONFIG', 'GET_CONFIG_ITEM', 'GET_FOTA_STATUS',
        # 扩展指令 - 日志功能  
        'WRITE_LOG', 'CONFIG_VOICELOG', 'SET_VOICELOG_PATH',
        # 新增扩展指令 - 参数和模式设置
        'SET_PARAM', 'SET_TTS_STATE', 'SET_LANGUAGE_MODE', 'SET_WORKMODE',
        'UPDATE_PERSONALIZED', 'SET_PAGE_INTENT',
        'GET_WAKEUP_WORD', 'GET_VR_CONFIG',
        # NLU测试专用指令 - 事件管理
        'INPUTEVENT', 'CALLBACK'
    ],
    'SET': [
        'CREATE', 'START', 'STOP', 'FREE', 'DATA', 'TEXT_DATA', 'EVENT', 'CANCEL', 'FREEWAKEUP', 'TEXT', 'STRATEGY', 'SETVRCONFIG',
        'PAUSE', 'RESUME', 'CAR_TYPE', 'LOG_PATH', 'MIC_STATUS', 'VR_STATUS', 'LINK_TYPE', 'VREVENT',
        'CLEAR_VR_CONFIG', 'GET_CONFIG_ITEM', 'SET_TTS_STATE', 'SET_LANGUAGE_MODE', 'SET_WORKMODE',
        'GET_VR_CONFIG', 'GET_WAKEUP_WORD', 'SET_WAKEUP_WORD', 'SET_WAKEUP_ENABLE', 'GET_FOTA_STATUS',
        # 扩展指令 - 声纹功能
        'REGISTER_VOICEPRINT_LIST', 'VOICEPRINT_LOGIN', 
        'START_SPEAKER_ENROLL', 'END_SPEAKER_ENROLL', 'RECOGNIZE_SPEAKER', 'VERIFY_VOICEPRINT', 
        'CANCEL_VERIFY_VOICEPRINT', 'DELETE_SPEAKER', 'GET_SPEAKER_INFO', 'GET_SPEAKERS',
        'GET_ENROLL_TEXT', 'SENSITIVE_WORD_CHECK',
    ],
    'VOI': [
        'CREATE', 'START', 'STOP', 'FREE', 'DATA', 'TEXT_DATA', 'EVENT', 'CANCEL', 'FREEWAKEUP', 'TEXT', 'STRATEGY', 'SETVRCONFIG',
        'PAUSE', 'RESUME', 'OPEN_VOICE_INPUT', 'CLOSE_VOICE_INPUT', 'GET_ENROLL_TEXT', 'RECOGNIZE_SPEAKER',
        'SENSITIVE_WORD_CHECK', 'SET_LANGUAGE_MODE', 'SET_WORKMODE'
    ],
    'OMS': [
        'CREATE', 'START', 'STOP', 'FREE', 'DATA', 'TEXT_DATA', 'EVENT', 'CANCEL', 'FREEWAKEUP', 'TEXT', 'STRATEGY', 'SETVRCONFIG',
        'GET_FOTA_STATUS'
    ],
    'TTS': [
        'CREATE', 'START', 'STOP', 'FREE', 'DATA', 'EVENT', 'CANCEL', 'FREEWAKEUP', 'TEXT', 'STRATEGY', 'SETVRCONFIG',
        'GET_FOTA_STATUS'
    ],

    # HWK客户端指令
    'HWK': [
        # 基础指令
        'CREATE', 'START', 'STOP', 'FREE', 'DATA', 'TEXT_DATA', 'CANCEL',
        # 参数设置
        'SET_PARAM', 'INIT_DECODE', 'SET_DATA_TYPE',
        # 引擎控制
        'UPDATE_PERSONALIZED', 'SET_WORK_MODE', 'SET_TTS_STATE', 'SET_FREETALK_STATE',
        # 唤醒词管理
        'ADD_WAKEUP_WORD', 'GET_WAKEUP_TERM', 'SET_WAKEUP_ENABLE', 'SET_VOICE_WAKEUP_OPTION',
        # 声纹功能
        'SET_SRE_REQUEST', 'SET_SRE_ENABLE_OPTION',
        # 语音输入
        'OPEN_VOICE_INPUT', 'CLOSE_VOICE_INPUT',
        # 语言设置
        'SET_LANGUAGE_INFO',
        # 语音日志
        'CONFIG_VOICELOG', 'SET_VOICELOG_PATH',
        # VR设置
        'SET_VR_SILENCE_TIMEOUT',
        # 系统设置
        'SET_LINK_TYPE', 'SET_MIC_STATUS', 'SET_CAR_TYPE',
        # 录音功能
        'START_RECORD', 'STOP_RECORD',
        # 敏感词检测
        'SENSITIVE_WORD_CHECK',
        # 设置HMI
        'HMI'
    ],

    # PSTT客户端指令
    'PST': [
        'CREATE', 'FREE', 'DATA', 'TEXT_DATA', 'HMI', 'DATA_QUEUE'
    ],

    # TiTan客户端指令
    'TIA': [
        'CREATE', 'DATA', 'TEXT_DATA', 'CASELIST'
    ],

    # CarPlay客户端指令
    'CPL': [
        'CREATE',           # 创建CarPlay引擎
        'FREE',             # 释放CarPlay引擎
    ],

    # ECNR客户端指令
    'ENR': [
        'SET_DOWNLINK',     # 设置下行链接
        'AMP_TYPE',         # CarInfo 默认功放类型（setDefaultAmpType，CREATE 前）
        'ECNR_TYPE',        # CarInfo 默认 ECNR 类型（setDefaultEcnrType，CREATE 前）
        'CREATE',           # 创建ECNR引擎
        'START',            # 启动ECNR引擎
        'STOP',             # 停止ECNR引擎
        'FREE',             # 释放ECNR引擎
        'SET_WORKMODE',     # 设置ECNR工作模式
        'DATA',             # 发送音频数据
        'GET_VERSION',        # 获取ECNR版本
        'SET_PNR_MIC_MUTE_OPTION',    # 设置ECNR麦克风静音选项
        'SET_PNR_ENABLE_OPTION',      # 设置ECNR启用选项
        'SET_PNR_AUDIO_QUALITY',      # 设置ECNR音频质量
        'GET_PNR_VERSION',            # 获取ECNR版本
        'GET_PNR_HFT_PARAM',          # 获取ECNRHFT参数
        'GET_PNR_MVR_PARAM',          # 获取ECNRMVR参数
        'GET_PNR_GEN_PARAM',          # 获取ECNRGEN参数
        'ANALYZE_AUDIO_DATA'          # 分析音频数据
    ],

    # PISA 大模型全双工 WebSocket 客户端指令
    'PIS': [
        'CREATE',       # 初始化连接参数（不建立连接）
        'AIBSServer',   # 启动 AIBS 语音服务（start_aibs_service）
        'AIBS_SET_CARTYPE',  # 设置车参（set_aibs_engine_device_type，需在 create 前调用）
        'AIBS_SET_WORK_MODE',  # 设置工作模式（set_engine_work_mode）
        'AIBS_CREATE',  # 创建 AIBS 客户端（create_aibs_client）
        'AIBS_START',   # 启动 AIBS 会话（start_aibs_engine）
        'AIBS_STOP',    # 停止 AIBS 会话（stop_aibs_engine）
        'START',        # 建立 WebSocket 长连接，等待 session.created
        'STOP',         # 关闭 WebSocket 连接
        'FREE',         # 清理所有资源
        'DATA',         # 发送音频到 AIBS，由 AIBS 回调转发到 WebSocket
        'TEXT_DATA',    # 发送文本（内部转音频后送DATA）
        'VEDIO',        # 异步VedioLLM请求指令
        'WAIT',         # 流控阻塞：等待 事件类型 或 response.done 条件满足
        'UPDATE',       # 发送 session.update（更新会话配置/清空上下文）
    ],

    'TSS': [
        'START_SERVICE',       # 创建TSS服务端
        'START',  # 启动TSS服务
        'SET_CARTYPE',    # 设置车参
        'STOP',           # 停止TSS引擎
        'CREATE',  # 创建TSS客户端
        'DATA',           # 发送音频到TSS，由TSS回调转发到WebSocket
        'TEXT_DATA',      # 发送文本（内部转音频后送DATA）
        'SET_PARAM', # 设置AIBS引擎参数
        'SET_LANGUAGE_MODE', # 设置AIBS语言模式
        'SET_WAKEUP_WORD', # 设置AIBS唤醒词
        'SET_WAKEUP_ENABLE', # 设置AIBS唤醒词启用状态
        'GET_WAKEUP_WORD', # 获取AIBS唤醒词
        'FREE'            # 释放TSS客户端资源
    ],

    # 系统指令
    'SYS': ['PULL', 'KILL', 'SLEEP', 'CMD', 'PRINT', 'ENV', 'UPLOAD', 'ALLURE', 'FOTA_RANDOM_ZIP', 'BREF', 'CLEAR_ASSERT'],

    # TSR (Test Suite Report) 客户端指令 - Suite级别统计和报告
    # 使用装饰器自动注册机制，新增指令只需在 tools/tsr/ 目录下添加文件并使用 @register_tsr_command 装饰器
    'TSR': ['ASR_ACCURACY', 'ASR_LANGUAGE', 'DELAY', 'WAKEUP_ACCURACY', 'VAD_ACCURACY', 'VAD_PRECISION', 'TIME_BOUNDARY_ACCURACY', 'LLM', 'PSTT_ACCURACY'],
    # NISSAN日产测试客户端指令
    'NIS': [
        # 基础指令
        'CREATE', 'START', 'STOP', 'FREE', 'DATA', 'TEXT_DATA', 'EVENT', 'CANCEL', 'FREEWAKEUP', 'SETVRCONFIG', 'TEXT', 'STRATEGY',
        # 扩展指令 - 引擎控制
        'PAUSE', 'RESUME', 'GET_VERSION',
        # 扩展指令 - 系统设置
        'CAR_TYPE', 'LOG_PATH', 'MIC_STATUS', 'VR_STATUS', 'LINK_TYPE', 'VREVENT',
        # 扩展指令 - 录音功能
        'START_RECORD', 'STOP_RECORD',
        # 扩展指令 - 语音输入
        'OPEN_VOICE_INPUT', 'CLOSE_VOICE_INPUT',
        # 扩展指令 - 声纹功能
        'START_SPEAKER_ENROLL', 'END_SPEAKER_ENROLL', 'RECOGNIZE_SPEAKER', 'VOICEPRINT_LOGIN', 
        'VERIFY_VOICEPRINT', 'CANCEL_VERIFY_VOICEPRINT', 'DELETE_SPEAKER', 'GET_SPEAKER_INFO', 'GET_SPEAKERS',
        'GET_ENROLL_TEXT', 'SENSITIVE_WORD_CHECK', 'REGISTER_VOICEPRINT_LIST',
        # 扩展指令 - 配置和状态
        'CLEAR_VR_CONFIG', 'GET_CONFIG_ITEM', 'GET_FOTA_STATUS',
        # 扩展指令 - 日志功能  
        'WRITE_LOG', 'CONFIG_VOICELOG', 'SET_VOICELOG_PATH',
        # 新增扩展指令 - 参数和模式设置
        'SET_PARAM', 'SET_TTS_STATE', 'SET_LANGUAGE_MODE', 'SET_WORKMODE',
        'UPDATE_PERSONALIZED', 'SET_PAGE_INTENT',
        'GET_WAKEUP_WORD', 'GET_VR_CONFIG',
        # NLU测试专用指令 - 事件管理
        'INPUTEVENT', 'CALLBACK'
    ],

    # NISSAN日产语音设置&声纹识别客户端指令
    'NSE': [
        'CREATE', 'START', 'STOP', 'FREE', 'DATA', 'TEXT_DATA', 'EVENT', 'CANCEL', 'FREEWAKEUP', 'TEXT', 'STRATEGY', 'SETVRCONFIG',
        'PAUSE', 'RESUME', 'CAR_TYPE', 'LOG_PATH', 'MIC_STATUS', 'VR_STATUS', 'LINK_TYPE', 'VREVENT',
        'CLEAR_VR_CONFIG', 'GET_CONFIG_ITEM', 'SET_TTS_STATE', 'SET_LANGUAGE_MODE', 'SET_WORKMODE',
        'GET_VR_CONFIG', 'GET_WAKEUP_WORD', 'SET_WAKEUP_WORD', 'SET_WAKEUP_ENABLE',
        # 扩展指令 - 声纹功能
        'REGISTER_VOICEPRINT_LIST', 'VOICEPRINT_LOGIN', 
        'START_SPEAKER_ENROLL', 'END_SPEAKER_ENROLL', 'RECOGNIZE_SPEAKER', 'VERIFY_VOICEPRINT', 
        'CANCEL_VERIFY_VOICEPRINT', 'DELETE_SPEAKER', 'GET_SPEAKER_INFO', 'GET_SPEAKERS',
        'GET_ENROLL_TEXT', 'SENSITIVE_WORD_CHECK',
    ],

    # EXP断言指令
    'EXP': AssertCodeTypeList + list(assert_key_value_config.keys()) + FILE_ASSERT_COMMANDS + ['LOG','SUM']
}