# NANO DSL 客户端命令参考

本文档按客户端拆分 NANO DSL 的命令说明，用于 VSCode Hover、补全说明和人工查阅。

说明：

- 若同名命令在不同客户端下语义不同，这里分别写出各自说明。
- 若当前项目文档缺失，则保留 `文档待补充`，后续可继续完善。

## Client `TSA`

### Command `CREATE`

**作用**: 创建客户端引擎

**语法**: `[客户端]CREATE language appid [config_file]`

**参数说明**:
- `language`：语言代码 (`cmn`=中文, `eng`=英文, `yue`=粤语)
- `appid`：应用标识符
- `config_file`：配置文件路径（可选）

**示例**:

```dsl
[TSA]CREATE cmn com.autoai.vr.service_vrassistant
[TSA]CREATE eng com.autoai.vr.service_vrassistant {CONFIGPATH}
[SET]CREATE cmn com.pachira.set
[VOI]CREATE cmn com.agentservice.cn
```

### Command `START`

**作用**: 启动会话

**语法**: `[客户端]START channel_num`

**参数说明**:

- `channel_num`：音频通道数（通常为1，支持多通道）

**示例**:
```dsl
[TSA]START 1    # 单通道启动
[TSA]START 4    # 四通道启动
```

### Command `STOP`

**作用**: 停止会话

**语法**: `[客户端]STOP`

**参数说明**:
- 无特殊参数说明。

**示例**:
```dsl
[TSA]STOP
[SET]STOP
```

### Command `FREE`

**作用**: 释放客户端资源

**语法**: `[客户端]FREE`

**参数说明**:
- 无特殊参数说明。

**示例**:
```dsl
[TSA]FREE
[SET]FREE
```

### Command `DATA`

**作用**: 发送音频数据

**语法**: `[客户端]DATA audio_path [frame=320] [delay=0] [range=[0,-1]] [abstime=0]`

**参数说明**:

- frame：320/640/1280，对应单声道/双声道/4声道...
- delay: 0～1的fload类型，用于控制送音频速度
- range:  传入"[0,-1]"，表示音频的片段位置，单位s，-1表示音频结尾
- abstime：时间戳是否采用绝对，缺省时，该值默认为1

**示例**:

```dsl
# 基础用法
[TSA]DATA {WORKPATH}/audio/weather.wav
# 指定帧大小
[TSA]DATA audio/test.wav frame=640
# 指定送音频速度
[TSA]DATA audio/test.wav frame=320 delay=1 range=[0,-1]
# 时间戳改用相对时间戳
[TSA]DATA audio/test.wav frame=320 delay=1 range=[0,-1] abstime=0
```

### Command `TEXT_DATA`

**作用**: 发送文本，框架内部先合成音频，再按 `DATA` 流程送入对应客户端。

**语法**: `[客户端]TEXT_DATA text [lang=cmn|eng|...] [engine=auto|volcano|edge_tts|index_tts|voxCpm] [frame=320] [delay=0] [range=[0,-1]] [abstime=0|1]`

**参数说明**:
- `text`：必填，待合成文本。支持 `text=...`，也支持直接文本写法。
- `lang`：可选，语种；不传时自动识别。
- `engine`：可选，合成引擎；默认 `auto`。
- `frame`、`delay`、`range`、`abstime`：可选，含义与 `DATA` 一致，透传给内部 `DATA`。

**示例**:
```dsl
[TSA]TEXT_DATA 今天天气怎么样
[TSA]TEXT_DATA text="turn on the radio" lang=eng engine=edge_tts
[TSA]TEXT_DATA text="打开音乐" lang=cmn frame=320 delay=1 range=[0,-1] abstime=0
```

### Command `EVENT`

**作用**: 发送事件

**语法**: `[客户端]EVENT json_event_data`

**参数说明**:
- `json_event_data`：JSON格式的事件数据/JSON文件路径

**示例**:
```dsl
[TSA]EVENT TestCase/json/1.json
[TSA]EVENT {"source":"TSA","type":"SetFullTimeOption","data":{"value":1}}
[TSA]EVENT {"source":"TSA","type":"VehicleInfo","data":{"vin":"TEST123","brand":"Lexus-2S"}}
```

### Command `CANCEL`

**作用**: 取消操作

**语法**: `[客户端]CANCEL`

**参数说明**:
- 无特殊参数说明。

**示例**:
```dsl
[TSA]CANCEL
[VOI]CANCEL
```

### Command `FREEWAKEUP`

**作用**: 设置识别/唤醒模式

**语法**: `[客户端]FREEWAKEUP status`

**参数说明**:
- `status`：模式状态（0=唤醒模式，1=识别模式）

**示例**:
```dsl
# 设置唤醒模式
[TSA]FREEWAKEUP 0
# 设置识别模式
[TSA]FREEWAKEUP 1
```

### Command `PARALLELSR`

**作用**: 设置并行模式

**语法**: `[客户端]PARALLELSR status`

**参数说明**:
- `status`：模式状态（0=独立音区，1=并行模式,2=全时模式）

**示例**:
```dsl
# 设置独立音区
[TSA]PARALLELSR 0
# 设置并行模式
[TSA]PARALLELSR 1
```

### Command `SETVRCONFIG`

**作用**: 设置VR配置

**语法**: `[客户端]SETVRCONFIG config_name config_value`

**参数说明**:

- `config_name`：配置项名称，常用字段如下：
  - WAKEUP_ALIAS: 设置自定义唤醒词；
  - DIALOGUE_LANGUAGE：设置语种信息；
  - SOUND_AREA_OPTION：设置音区生效配比；
  - WAKEUP_KEYWORD_OPTION：设置场景唤醒词开关；
  - WAKEUP_ENABLE：设置生效唤醒词；
  - SRE_FUNC_ENABLE_OPTION：声纹使能开关；

- `config_value`：配置值

**示例**:
```dsl
# 设置唤醒词别名
[SET]SETVRCONFIG WAKEUP_ALIAS 你好小白 cmn
# 设置生效唤醒词
[SET]SETVRCONFIG WAKEUP_ENABLE 你好雷克萨斯 cmn
# 设置语种为中文
[SET]SETVRCONFIG DIALOGUE_LANGUAGE cmn
# 关闭声纹
[SET]SETVRCONFIG SRE_FUNC_ENABLE_OPTION 0
```

### Command `TEXT`

**作用**: 文本输入

**语法**: `[客户端]TEXT text`

**参数说明**:

- `text`：传入理解的文本内容

**示例**:

```dsl
# 将“今天天气怎么样”的文本传入给引擎
[TSA]TEXT 今天天气怎么样
```

### Command `STRATEGY`

**作用**: 策略模式

**语法**: `[客户端]STRATEGY status`

**参数说明**:
- `status`：模式状态（0=离线模式，1=在线模式，2=混合仲裁模式）

**示例**:
```dsl
# 设置离线模式
[TSA]STRATEGY 0
# 设置在线模式
[TSA]STRATEGY 1
```

### Command `PAUSE`

**作用**: 暂停引擎

**语法**: `[客户端]PAUSE`

**参数说明**:
- 无特殊参数说明。

**示例**:
```dsl
[TSA]PAUSE
```

### Command `RESUME`

**作用**: 恢复引擎

**语法**: `[客户端]RESUME`

**参数说明**:
- 无特殊参数说明。

**示例**:
```dsl
[TSA]RESUME
```

### Command `GET_VERSION`

**作用**: 获取版本信息

**语法**: `[客户端]GET_VERSION`

**参数说明**:
- 无特殊参数说明。

**示例**:
```dsl
[TSA]GET_VERSION
[SET]GET_VERSION
```

### Command `CAR_TYPE`

**作用**: 设置车型信息

**语法**: `[客户端]CAR_TYPE car_type_json`

**参数说明**:
- `car_type_json`：JSON格式的车型信息，brand：0/1/2（Lexus/T1/T2），devices_name：410D/450D/070D

**示例**:

```dsl
[TSA]CAR_TYPE {"brand":"0","device_name":"410D"}
```

### Command `LOG_PATH`

**作用**: 设置日志路径

**语法**: `[客户端]LOG_PATH log_path`

**参数说明**:
- log_path：日志路径

**示例**:

```dsl
[TSA]LOG_PATH {LOGPATH}
[SET]LOG_PATH /tmp/logs
```

### Command `MIC_STATUS`

**作用**: 设置麦克风状态

**语法**: `[客户端]MIC_STATUS status`

**参数说明**:
- `status`：麦克风状态（0=关闭，1=开启）

**示例**:
```dsl
[TSA]MIC_STATUS 1   # 开启麦克风
[TSA]MIC_STATUS 0   # 关闭麦克风
```

### Command `VR_STATUS`

**作用**: 设置VR状态

**语法**: `[客户端]VR_STATUS status`

**参数说明**:
- `status`：VR状态（0=关闭，1=开启）

**示例**:
```dsl
[TSA]VR_STATUS 1    # 开启VR
[TSA]VR_STATUS 0    # 关闭VR
```

### Command `LINK_TYPE`

**作用**: 设置CarPlay/HiCar/CarLink链接方式，该接口需配合CarPlay客户端（CPL）使用。

**语法**: `[客户端]LINK_TYPE link_type`

**参数说明**:

- `link_type`：连接类型代码（详见下表）

**示例**:

```dsl
[TSA]LINK_TYPE 0      # 设置为无连接
[TSA]LINK_TYPE 1      # 设置为CarPlay连接
[SET]LINK_TYPE 2      # 设置为CarLife连接
[OMS]LINK_TYPE 3      # 设置为HiCar连接
```

### Command `VREVENT`

**作用**: 设置给引擎事件，同EVENT接口

**语法**: `[客户端]VREVENT json_data`

**参数说明**:

- json_data：JSON串/JSON的文件路径

**示例**:
```dsl
[TSA]VREVENT {"type":"JSON","source":"TSA","data":123}
[TSA]VREVENT TestCase/json/1.json
```

### Command `START_RECORD`

**作用**: 开始录音

**语法**: `[客户端]START_RECORD`

**参数说明**:

- 无特殊参数说明。

**示例**:

```dsl
[TSA]START_RECORD
```

### Command `STOP_RECORD`

**作用**: 停止录音

**语法**: `[客户端]STOP_RECORD`

**参数说明**:
- 无特殊参数说明。

**示例**:

```dsl
[TSA]STOP_RECORD
```

### Command `OPEN_VOICE_INPUT`

**作用**: 开启语音输入，仅VOI客户端使用

**语法**: `[客户端]OPEN_VOICE_INPUT param`

**参数说明**:

- `param`：语音输入参数设置（JSON格式字符串或配置参数）
  - name：语音输入法场景，默认为poi
  - channelID：语音输入法开启的音区
  - mode：语音输入法模式：0 / 1/ 2
  - silDuration：语音输入法静音超时配置，单位ms


**示例**:

```dsl
[VOI]OPEN_VOICE_INPUT {"name":"poi","channelID":0,"mode":0,"silDuration":800}
```

### Command `CLOSE_VOICE_INPUT`

**作用**: 关闭语音输入，仅VOI客户端使用

**语法**: `[客户端]CLOSE_VOICE_INPUT`

**参数说明**:
- 无特殊参数说明。

**示例**:

```dsl
[VOI]CLOSE_VOICE_INPUT
```

### Command `START_SPEAKER_ENROLL`

**作用**: 开始声纹注册，仅SET客户端使用

**语法**: `[客户端]START_SPEAKER_ENROLL user_id text id channel_id`

**参数说明**:
- `user_id`：用户ID字符串
- `text`：注册文本内容
- `id`：当前注册次数编号
- `channel_id`：音频通道ID

**示例**:

```dsl
# 用户user001第1次注册，使用通道0
[SET]START_SPEAKER_ENROLL user001 你好雷克萨斯，登录我的个人中心 1 0
```

### Command `END_SPEAKER_ENROLL`

**作用**: 结束声纹注册

**语法**: `[客户端]END_SPEAKER_ENROLL`

**参数说明**:
- 无特殊参数说明。

**示例**:

```dsl
[SET]END_SPEAKER_ENROLL
```

### Command `RECOGNIZE_SPEAKER`

**作用**: 声纹登录时系统调用接口

**语法**: `[客户端]RECOGNIZE_SPEAKER channel_id start end`

**参数说明**:

- `channel_id`：发话的音区
- `start`：发话开始时间
- `end`：发话结束时间

**示例**:
```dsl
[TSA]RECOGNIZE_SPEAKER 0 1230 3456
```

### Command `VOICEPRINT_LOGIN`

**作用**: 声纹登录

**语法**: `[客户端]VOICEPRINT_LOGIN audio_path [frame_size] [delay]`

**参数说明**:
- `audio_path`：音频文件路径（必需）
- `frame`：帧大小，默认320（可选）
- `delay`：延时比例，默认0.0（可选）

**示例**:

```dsl
[SET]VOICEPRINT_LOGIN {WORKPATH}/audio/login.wav 320 frame=320 delay=1 range=[0,-1]
```

### Command `VERIFY_VOICEPRINT`

**作用**: 声纹验证

**语法**: `[客户端]VERIFY_VOICEPRINT user_id verify_text timeout_seconds`

**参数说明**:

- `user_id`：要验证的用户ID
- `verify_text`：验证文本
- `timeout_seconds`：超时时间

**示例**:
```dsl
[TSA]VERIFY_VOICEPRINT user001 你好小白 0
[SET]VERIFY_VOICEPRINT admin 验证文本 5
```

### Command `CANCEL_VERIFY_VOICEPRINT`

**作用**: 取消声纹验证

**语法**: `[客户端]CANCEL_VERIFY_VOICEPRINT`

**参数说明**:
- 无特殊参数说明。

**示例**:
```dsl
[TSA]CANCEL_VERIFY_VOICEPRINT
[SET]CANCEL_VERIFY_VOICEPRINT
```

### Command `DELETE_SPEAKER`

**作用**: 删除声纹

**语法**: `[客户端]DELETE_SPEAKER user_id`

**参数说明**:
- `user_id`：要删除的用户ID

**示例**:
```dsl
[TSA]DELETE_SPEAKER user001
[SET]DELETE_SPEAKER test_user
```

### Command `GET_SPEAKER_INFO`

**作用**: 获取声纹信息

**语法**: `[客户端]GET_SPEAKER_INFO user_id`

**参数说明**:
- `user_id`：用户ID

**示例**:
```dsl
[TSA]GET_SPEAKER_INFO user001
[SET]GET_SPEAKER_INFO admin
```

### Command `GET_SPEAKERS`

**作用**: 获取已注册声纹列表

**语法**: `[客户端]GET_SPEAKERS`

**参数说明**:
- 无特殊参数说明。

**示例**:
```dsl
[TSA]GET_SPEAKERS
[SET]GET_SPEAKERS
```

### Command `GET_ENROLL_TEXT`

**作用**: 获取注册文本

**语法**: `[客户端]GET_ENROLL_TEXT`

**参数说明**:
- 无特殊参数说明。

**示例**:
```dsl
[TSA]GET_ENROLL_TEXT
[VOI]GET_ENROLL_TEXT
```

### Command `SENSITIVE_WORD_CHECK`

**作用**: 敏感词检测

**语法**: `[客户端]SENSITIVE_WORD_CHECK text`

**参数说明**:
- `text`：要检测的文本

**示例**:
```dsl
[TSA]SENSITIVE_WORD_CHECK 测试文本内容
[SET]SENSITIVE_WORD_CHECK 需要检查的语句
```

### Command `REGISTER_VOICEPRINT_LIST`

**作用**: 批量注册声纹

**语法**: `[客户端]REGISTER_VOICEPRINT_LIST sre_user_files`

**参数说明**:
- `sre_user_files`：声纹注册的用户列表，可以支持多个userid，按照userid分组

**示例**:
```dsl
# 方式1: 从JSON文件读取（推荐）
[SET]REGISTER_VOICEPRINT_LIST TestCase/caselist/haijin_female.txt
# 参数文件示例:
TestAudio/vp_multi_channel/haijin/zhu/66_你好小悦登录我的个人中心.wav	text:你好小悦，登录我的个人中心;channel:0;user_id:haijin;index:1
```

### Command `CLEAR_VR_CONFIG`

**作用**: 清除VR配置

**语法**: `[客户端]CLEAR_VR_CONFIG`

**参数说明**:
- 无特殊参数说明。

**示例**:

```dsl
[TSA]CLEAR_VR_CONFIG
[SET]CLEAR_VR_CONFIG
```

### Command `GET_CONFIG_ITEM`

**作用**: 获取配置项

**语法**: `[客户端]GET_CONFIG_ITEM config_file config_key`

**参数说明**:
- `config_file`：配置文件路径
- `config_key`：配置键名

**示例**:

```dsl
[TSA]GET_CONFIG_ITEM {CONFIGPATH} debug_mode
[SET]GET_CONFIG_ITEM /tmp/config.conf language
```

### Command `GET_FOTA_STATUS`

**作用**: 获取FOTA状态

**语法**: `[客户端]GET_FOTA_STATUS`

**参数说明**:
- 无特殊参数说明。

**示例**:
```dsl
[TSA]GET_FOTA_STATUS
[OMS]GET_FOTA_STATUS
```

### Command `WRITE_LOG`

**作用**: 写入日志

**语法**: `[客户端]WRITE_LOG log_path tag message log_level`

**参数说明**:
- `log_path`：日志文件路径
- `tag`：日志标签
- `message`：日志消息
- `log_level`：日志级别（1-5）

**示例**:
```dsl
[TSA]WRITE_LOG {LOGPATH}/test.log NANO 测试开始 1
[SET]WRITE_LOG /tmp/debug.log DEBUG 调试信息 2
```

### Command `CONFIG_VOICELOG`

**作用**: 配置语音日志

**语法**: `[客户端]CONFIG_VOICELOG enable log_level`

**参数说明**:
- `enable`：是否启用（true/false）
- `log_level`：日志级别

**示例**:
```dsl
[TSA]CONFIG_VOICELOG true 1
[SET]CONFIG_VOICELOG false 0
```

### Command `SET_VOICELOG_PATH`

**作用**: 设置语音日志路径

**语法**: `[客户端]SET_VOICELOG_PATH log_path`

**参数说明**:
- `log_path`：语音日志保存路径

**示例**:
```dsl
[TSA]SET_VOICELOG_PATH {LOGPATH}/voicelog/
[SET]SET_VOICELOG_PATH /tmp/voice_logs/
```

### Command `SET_PARAM`

**作用**: 设置引擎参数

**语法**: `[客户端]SET_PARAM param_name param_value`

**参数说明**:

- `param_name`：参数名称（详见下表）
- `param_value`：参数值（支持int、float、string、bool类型）

**示例**:
```dsl
# 设置静音检测时长为5秒
[TSA]SET_PARAM AIBS_PARAM_SILENCE_DURATION 5000
# 开启实时结果
[TSA]SET_PARAM AIBS_PARAM_REAL_TIME_RESULT 1
```

### Command `SET_TTS_STATE`

**作用**: 设置TTS状态

**语法**: `[客户端]SET_TTS_STATE state`

**参数说明**:
- `state`：TTS状态（true/false）

**示例**:
```dsl
[TSA]SET_TTS_STATE true
[SET]SET_TTS_STATE false
```

### Command `SET_LANGUAGE_MODE`

**作用**: 设置语言模式

**语法**: `[客户端]SET_LANGUAGE_MODE language`

**参数说明**:
- `language`：语言代码（cmn/eng/yue）

**示例**:
```dsl
[TSA]SET_LANGUAGE_MODE cmn
[SET]SET_LANGUAGE_MODE eng
[VOI]SET_LANGUAGE_MODE yue
```

### Command `SET_WORKMODE`

**作用**: 设置工作模式

**语法**: `[客户端]SET_WORKMODE mode`

**参数说明**:
- 无特殊参数说明。

**示例**:
```dsl
[TSA]SET_WORKMODE WAKEUP_ASR
[SET]SET_WORKMODE ASR_ONLY
```

### Command `UPDATE_PERSONALIZED`

**作用**: 更新个性化信息

**语法**: `[客户端]UPDATE_PERSONALIZED personalized_info`

**参数说明**:
- `personalized_info`：个性化信息数据

**示例**:
```dsl
[TSA]UPDATE_PERSONALIZED {"user":"admin","preferences":"music"}
```

### Command `SET_PAGE_INTENT`

**作用**: 设置页面意图

**语法**: `[客户端]SET_PAGE_INTENT intent_info`

**参数说明**:
- `intent_info`：页面意图信息

**示例**:
```dsl
[TSA]SET_PAGE_INTENT {"page":"music","intent":"play"}
```

### Command `GET_WAKEUP_WORD`

**作用**: 获取唤醒词

**语法**: `[客户端]GET_WAKEUP_WORD`

**参数说明**:
- 无特殊参数说明。

**示例**:
```dsl
[TSA]GET_WAKEUP_WORD
[SET]GET_WAKEUP_WORD
```

### Command `GET_VR_CONFIG`

**作用**: 获取VR配置

**语法**: `[客户端]GET_VR_CONFIG config_name`

**参数说明**:
- `config_name`：配置项名称

**示例**:
```dsl
[TSA]GET_VR_CONFIG VR_OPTION
[SET]GET_VR_CONFIG WAKEUP_ALIAS
```

### Command `INPUTEVENT`

**作用**: 发送输入事件，用于注入技能执行所需的外部上下文。

**语法**: `[TSA]INPUTEVENT event_name`

**参数说明**:

- `event_name`：事件名称，如 VehicleInfo、NaviLocationStatus、NavigateStatus。

**示例**:

```dsl
[TSA]INPUTEVENT VehicleInfo
[TSA]INPUTEVENT NaviLocationStatus
```

### Command `CALLBACK`

**作用**: 主动注入回调数据，常用于多轮对话、搜索结果、事件驱动测试等场景。

**语法**: `[TSA]CALLBACK callback_name [field_path:value ...]`

**参数说明**:

- `callback_name`：回调名称，常见为 default。
- `field_path:value`：可选，按字段路径注入返回值或文件数据。

**示例**:

```dsl
[TSA]CALLBACK default
[TSA]CALLBACK default data.result.code:0
```

## Client `SET`

### Command `CREATE`

**作用**: 创建客户端引擎

**语法**: `[客户端]CREATE language appid [config_file]`

**参数说明**:
- `language`：语言代码 (`cmn`=中文, `eng`=英文, `yue`=粤语)
- `appid`：应用标识符
- `config_file`：配置文件路径（可选）

**示例**:
```dsl
[TSA]CREATE cmn com.autoai.vr.service_vrassistant
[TSA]CREATE eng com.autoai.vr.service_vrassistant {CONFIGPATH}
[SET]CREATE cmn com.pachira.set
```

### Command `FREE`

**作用**: 释放客户端资源

**语法**: `[客户端]FREE`

**参数说明**:

- 无特殊参数说明。

**示例**:
```dsl
[TSA]FREE
[SET]FREE
```

### Command `EVENT`

**作用**: 发送事件

**语法**: `[客户端]EVENT json_event_data`

**参数说明**:
- `json_event_data`：JSON格式的事件数据

**示例**:
```dsl
[TSA]EVENT {"source":"TSA","type":"SetFullTimeOption","data":{"value":1}}
[TSA]EVENT {"source":"TSA","type":"VehicleInfo","data":{"vin":"TEST123","brand":"Lexus-2S"}}
```

### Command `FREEWAKEUP`

**作用**: 设置识别/唤醒模式

**语法**: `[客户端]FREEWAKEUP status`

**参数说明**:
- `status`：模式状态（0=唤醒模式，1=识别模式）

**示例**:
```dsl
# 设置唤醒模式
[TSA]FREEWAKEUP 0
# 设置识别模式
[TSA]FREEWAKEUP 1
```

### Command `SETVRCONFIG`

**作用**: 设置VR配置

**语法**: `[客户端]SETVRCONFIG config_name config_value [language]`

**参数说明**:
- `config_name`：配置项名称（详见下表）
- `config_value`：配置值
- `language`：语言代码（可选，部分配置需要）

**示例**:
```dsl
# 设置唤醒词别名
[SET]SETVRCONFIG WAKEUP_ALIAS 你好小白 cmn
# 设置主动交互
[SET]SETVRCONFIG ACTIVE_INTERACTION true cmn
```

### Command `PAUSE`

**作用**: 暂停引擎

**语法**: `[客户端]PAUSE`

**参数说明**:
- 无特殊参数说明。

**示例**:
```dsl
[TSA]PAUSE
```

### Command `RESUME`

**作用**: 恢复引擎

**语法**: `[客户端]RESUME`

**参数说明**:
- 无特殊参数说明。

**示例**:
```dsl
[TSA]RESUME
```

### Command `CAR_TYPE`

**作用**: 设置车型信息

**语法**: `[客户端]CAR_TYPE car_type_json`

**参数说明**:
- `car_type_json`：JSON格式的车型信息

**示例**:
```dsl
[TSA]CAR_TYPE {"brand":"0","device_name":"test_device"}
[TSA]CAR_TYPE {"brand":"Lexus-2S"}
```

### Command `SET_WORKMODE`

**作用**: 设置工作模式

**语法**: `[客户端]SET_WORKMODE mode`

**参数说明**:
- 无特殊参数说明。

**示例**:
```dsl
[TSA]SET_WORKMODE WAKEUP_ASR
[SET]SET_WORKMODE ASR_ONLY
```

### Command `GET_VR_CONFIG`

**作用**: 获取VR配置

**语法**: `[客户端]GET_VR_CONFIG config_name`

**参数说明**:
- `config_name`：配置项名称

**示例**:
```dsl
[TSA]GET_VR_CONFIG VR_OPTION
[SET]GET_VR_CONFIG WAKEUP_ALIAS
```

### Command `GET_WAKEUP_WORD`

**作用**: 获取唤醒词

**语法**: `[客户端]GET_WAKEUP_WORD`

**参数说明**:
- 无特殊参数说明。

**示例**:
```dsl
[TSA]GET_WAKEUP_WORD
[SET]GET_WAKEUP_WORD
```

### Command `GET_FOTA_STATUS`

**作用**: 获取FOTA状态

**语法**: `[客户端]GET_FOTA_STATUS`

**参数说明**:
- 无特殊参数说明。

**示例**:
```dsl
[TSA]GET_FOTA_STATUS
[OMS]GET_FOTA_STATUS
```

### Command `REGISTER_VOICEPRINT_LIST`

**作用**: 批量注册声纹

**语法**: `[客户端]REGISTER_VOICEPRINT_LIST sre_user_files`

**参数说明**:

- `sre_user_files`：声纹注册的用户列表，可以支持多个userid，按照userid分组

**示例**:
```dsl
# 方式1: 从JSON文件读取（推荐）
[SET]REGISTER_VOICEPRINT_LIST TestCase/caselist/haijin_female.txt
# 参数文件示例:
TestAudio/vp_multi_channel/haijin/zhu/66_你好小悦登录我的个人中心.wav	text:你好小悦，登录我的个人中心;channel:0;user_id:haijin;index:1
```

### Command `VOICEPRINT_LOGIN`

**作用**: 声纹登录

**语法**: `[客户端]VOICEPRINT_LOGIN audio_path [frame_size] [delay]`

**参数说明**:
- `audio_path`：音频文件路径（必需）
- `frame_size`：帧大小，默认320（可选）
- `delay`：延时比例，默认0.0（可选）

**示例**:
```dsl
# 使用默认参数
[SET]VOICEPRINT_LOGIN {WORKPATH}/audio/login.wav
# 指定帧大小
[SET]VOICEPRINT_LOGIN {WORKPATH}/audio/login.wav 320
```

### Command `START_SPEAKER_ENROLL`

**作用**: 开始声纹注册

**语法**: `[客户端]START_SPEAKER_ENROLL user_id text id channel_id`

**参数说明**:
- `user_id`：用户ID字符串
- `text`：注册文本内容
- `id`：当前注册次数编号
- `channel_id`：音频通道ID

**示例**:
```dsl
# 用户user001第1次注册，使用通道0
[SET]START_SPEAKER_ENROLL user001 你好雷克萨斯，登录我的个人中心 1 0
# 用户admin第3次注册，使用通道0
[SET]START_SPEAKER_ENROLL admin 测试文本内容 3 0
```

### Command `END_SPEAKER_ENROLL`

**作用**: 结束声纹注册

**语法**: `[客户端]END_SPEAKER_ENROLL`

**参数说明**:
- 无特殊参数说明。

**示例**:
```dsl
[TSA]END_SPEAKER_ENROLL
[SET]END_SPEAKER_ENROLL
```

### Command `RECOGNIZE_SPEAKER`

**作用**: 声纹登录时系统调用接口

**语法**: `[VOI客户端]RECOGNIZE_SPEAKER channel_id start end`

**参数说明**:
- `channel_id`：发话的音区
- `start`：发话开始时间
- `end`：发话结束时间

**示例**:
```dsl
[VOI]RECOGNIZE_SPEAKER 0 1230 3456
[VOI]RECOGNIZE_SPEAKER 1 3420 9203
```

### Command `VERIFY_VOICEPRINT`

**作用**: 声纹验证

**语法**: `[客户端]VERIFY_VOICEPRINT user_id verify_text timeout_seconds`

**参数说明**:
- `user_id`：要验证的用户ID
- `verify_text`：验证文本
- `timeout_seconds`：超时时间

**示例**:
```dsl
[TSA]VERIFY_VOICEPRINT user001 你好小白 0
[SET]VERIFY_VOICEPRINT admin 验证文本 5
```

### Command `CANCEL_VERIFY_VOICEPRINT`

**作用**: 取消声纹验证

**语法**: `[客户端]CANCEL_VERIFY_VOICEPRINT`

**参数说明**:
- 无特殊参数说明。

**示例**:
```dsl
[TSA]CANCEL_VERIFY_VOICEPRINT
[SET]CANCEL_VERIFY_VOICEPRINT
```

### Command `DELETE_SPEAKER`

**作用**: 删除声纹

**语法**: `[客户端]DELETE_SPEAKER user_id`

**参数说明**:
- `user_id`：要删除的用户ID

**示例**:
```dsl
[TSA]DELETE_SPEAKER user001
[SET]DELETE_SPEAKER test_user
```

### Command `GET_SPEAKER_INFO`

**作用**: 获取声纹信息

**语法**: `[客户端]GET_SPEAKER_INFO user_id`

**参数说明**:
- `user_id`：用户ID

**示例**:
```dsl
[TSA]GET_SPEAKER_INFO user001
[SET]GET_SPEAKER_INFO admin
```

### Command `GET_SPEAKERS`

**作用**: 获取已注册声纹列表

**语法**: `[客户端]GET_SPEAKERS`

**参数说明**:
- 无特殊参数说明。

**示例**:
```dsl
[TSA]GET_SPEAKERS
[SET]GET_SPEAKERS
```

### Command `GET_ENROLL_TEXT`

**作用**: 获取注册文本

**语法**: `[客户端]GET_ENROLL_TEXT`

**参数说明**:
- 无特殊参数说明。

**示例**:
```dsl
[TSA]GET_ENROLL_TEXT
[VOI]GET_ENROLL_TEXT
```

### Command `SENSITIVE_WORD_CHECK`

**作用**: 敏感词检测

**语法**: `[客户端]SENSITIVE_WORD_CHECK text`

**参数说明**:
- `text`：要检测的文本

**示例**:
```dsl
[TSA]SENSITIVE_WORD_CHECK 测试文本内容
[SET]SENSITIVE_WORD_CHECK 需要检查的语句
```

## Client `VOI`

### Command `CREATE`

**作用**: 创建客户端引擎

**语法**: `[客户端]CREATE language appid [config_file]`

**参数说明**:
- `language`：语言代码 (`cmn`=中文, `eng`=英文, `yue`=粤语)
- `appid`：应用标识符
- `config_file`：配置文件路径（可选）

**示例**:
```dsl
[TSA]CREATE cmn com.autoai.vr.service_vrassistant
[TSA]CREATE eng com.autoai.vr.service_vrassistant {CONFIGPATH}
[SET]CREATE cmn com.pachira.set
```

### Command `FREE`

**作用**: 释放客户端资源

**语法**: `[客户端]FREE`

**参数说明**:
- 无特殊参数说明。

**示例**:
```dsl
[TSA]FREE
[SET]FREE
```

### Command `EVENT`

**作用**: 发送事件

**语法**: `[客户端]EVENT json_event_data`

**参数说明**:
- `json_event_data`：JSON格式的事件数据

**示例**:
```dsl
[TSA]EVENT {"source":"TSA","type":"SetFullTimeOption","data":{"value":1}}
[TSA]EVENT {"source":"TSA","type":"VehicleInfo","data":{"vin":"TEST123","brand":"Lexus-2S"}}
```

### Command `OPEN_VOICE_INPUT`

**作用**: 开启语音输入

**语法**: `[客户端]OPEN_VOICE_INPUT param`

**参数说明**:
- `param`：语音输入参数设置（JSON格式字符串或配置参数）

**示例**:
```dsl
[TSA]OPEN_VOICE_INPUT {"mode":0,"channel":0}
[VOI]OPEN_VOICE_INPUT voice_input_config
```

### Command `CLOSE_VOICE_INPUT`

**作用**: 关闭语音输入

**语法**: `[客户端]CLOSE_VOICE_INPUT`

**参数说明**:
- 无特殊参数说明。

**示例**:
```dsl
[TSA]CLOSE_VOICE_INPUT
[VOI]CLOSE_VOICE_INPUT
```

## Client `OMS`

### Command `CREATE`

**作用**: 创建客户端引擎

**语法**: `[客户端]CREATE language appid [config_file]`

**参数说明**:
- `language`：语言代码 (`cmn`=中文, `eng`=英文, `yue`=粤语)
- `appid`：应用标识符
- `config_file`：配置文件路径（可选）

**示例**:
```dsl
[TSA]CREATE cmn com.autoai.vr.service_vrassistant
[TSA]CREATE eng com.autoai.vr.service_vrassistant {CONFIGPATH}
[SET]CREATE cmn com.pachira.set
```

### Command `FREE`

**作用**: 释放客户端资源

**语法**: `[客户端]FREE`

**参数说明**:
- 无特殊参数说明。

**示例**:
```dsl
[TSA]FREE
[SET]FREE
```

### Command `EVENT`

**作用**: 发送事件

**语法**: `[客户端]EVENT json_event_data`

**参数说明**:
- `json_event_data`：JSON格式的事件数据

**示例**:
```dsl
[TSA]EVENT {"source":"TSA","type":"SetFullTimeOption","data":{"value":1}}
[TSA]EVENT {"source":"TSA","type":"VehicleInfo","data":{"vin":"TEST123","brand":"Lexus-2S"}}
```

## Client `TTS`

### Command `CREATE`

**作用**: 创建客户端引擎

**语法**: `[客户端]CREATE language appid [config_file]`

**参数说明**:
- `language`：语言代码 (`cmn`=中文, `eng`=英文, `yue`=粤语)
- `appid`：应用标识符
- `config_file`：配置文件路径（可选）

**示例**:
```dsl
[TSA]CREATE cmn com.autoai.vr.service_vrassistant
[TSA]CREATE eng com.autoai.vr.service_vrassistant {CONFIGPATH}
[SET]CREATE cmn com.pachira.set
```

### Command `FREE`

**作用**: 释放客户端资源

**语法**: `[客户端]FREE`

**参数说明**:
- 无特殊参数说明。

**示例**:
```dsl
[TSA]FREE
[SET]FREE
```

### Command `EVENT`

**作用**: 发送事件

**语法**: `[客户端]EVENT json_event_data`

**参数说明**:
- `json_event_data`：JSON格式的事件数据

**示例**:
```dsl
[TSA]EVENT {"source":"TSA","type":"SetFullTimeOption","data":{"value":1}}
[TSA]EVENT {"source":"TSA","type":"VehicleInfo","data":{"vin":"TEST123","brand":"Lexus-2S"}}
```

### Command `GET_FOTA_STATUS`

**作用**: 获取FOTA状态

**语法**: `[客户端]GET_FOTA_STATUS`

**参数说明**:

- 无特殊参数说明。

**示例**:

```dsl
[TSA]GET_FOTA_STATUS
[OMS]GET_FOTA_STATUS
```

## Client `HWK`

SpeechEngine 客户端（`HWK`）用于离线识别、唤醒词检测、声纹等相关能力测试；命令语义与 `COMMAND.md` 中 HWK 章节一致。下列语法与示例均以 `[HWK]` 为前缀。

### Command `CREATE`

**作用**: 创建 SpeechEngine 引擎实例。

**语法**: `[HWK]CREATE`

**参数说明**: 无需参数

**示例**:

```dsl
[HWK]CREATE
```

### Command `START`

**作用**: 启动会话。

**语法**: `[HWK]START [channel_num]`

**参数说明**:

- `channel_num`：可选，音频通道数；省略时运行器按单通道（1）处理。

**示例**:

```dsl
[HWK]START
[HWK]START 1
```

### Command `STOP`

**作用**: 停止会话。

**语法**: `[HWK]STOP`

**参数说明**:

- 无特殊参数说明。

**示例**:

```dsl
[HWK]STOP
```

### Command `FREE`

**作用**: 释放引擎资源。

**语法**: `[HWK]FREE`

**参数说明**:

- 无特殊参数说明。

**示例**:

```dsl
[HWK]FREE
```

### Command `DATA`

**作用**: 发送音频数据（命名参数与 TSA 的 DATA 用法一致）。

**语法**: `[HWK]DATA audio_path [frame=320] [delay=0.0] [range=[0,-1]]`

**参数说明**:

- `audio_path`：音频文件路径。
- `frame`、`delay`、`range`：可选命名参数，含义同 TSA 的 DATA 指令。

**示例**:

```dsl
[HWK]DATA {WORKPATH}/audio/test.wav
[HWK]DATA audio/test.wav frame=640 delay=0.5
```

### Command `CANCEL`

**作用**: 取消当前操作。

**语法**: `[HWK]CANCEL`

**参数说明**:

- 无特殊参数说明。

**示例**:

```dsl
[HWK]CANCEL
```

### Command `SET_PARAM`

**作用**: 设置 SpeechEngine 引擎参数（参数码为 `SPEECH_ENGINE_*` 枚举名，而非 AIBS 参数名）。

**语法**: `[HWK]SET_PARAM param_code param_value`

**参数说明**:

- `param_code`：参数代码字符串，例如 `SPEECH_ENGINE_PARAM_LINK_TYPE`、`SPEECH_ENGINE_PARAM_REAL_TIME_RESULT`、`SPEECH_ENGINE_PARAM_SILENCE_DURATION` 等（完整列表见 `COMMAND.md` HWK 的 SET_PARAM 小节）。
- `param_value`：参数值（整型、浮点、字符串或布尔，由运行器按类型转换）。

**示例**:

```dsl
[HWK]SET_PARAM SPEECH_ENGINE_PARAM_REAL_TIME_RESULT 1
[HWK]SET_PARAM SPEECH_ENGINE_PARAM_SILENCE_DURATION 5000
```

### Command `INIT_DECODE`

**作用**: 初始化解码器。

**语法**: `[HWK]INIT_DECODE`

**参数说明**:

- 无特殊参数说明。

**示例**:

```dsl
[HWK]INIT_DECODE
```

### Command `SET_DATA_TYPE`

**作用**: 设置数据类型。

**语法**: `[HWK]SET_DATA_TYPE data_type`

**参数说明**:

- `data_type`：数据类型，0: 单声道；1：降噪后多声道，2：降噪前带参考的多声道

**示例**:

```dsl
[HWK]SET_DATA_TYPE 1
```

### Command `SET_WORK_MODE`

**作用**: 设置工作模式。

**语法**: `[HWK]SET_WORK_MODE mode`

**参数说明**:

- `mode`：工作模式代码。0：唤醒；1：识别；2：唤醒+识别

**示例**:

```dsl
# 设置唤醒模式
[HWK]SET_WORK_MODE 0
```

### Command `SET_TTS_STATE`

**作用**: 设置 TTS 状态。

**语法**: `[HWK]SET_TTS_STATE state`

**参数说明**:

- `state`：TTS 状态（`true` / `false` / `1` / `0`）。

**示例**:

```dsl
[HWK]SET_TTS_STATE true
```

### Command `SET_FREETALK_STATE`

**作用**: 设置自由对话状态。

**语法**: `[HWK]SET_FREETALK_STATE state`

**参数说明**:

- `state`：自由对话状态（`true` / `false` / `1` / `0`）。

**示例**:

```dsl
[HWK]SET_FREETALK_STATE true
```

### Command `ADD_WAKEUP_WORD`

**作用**: 添加唤醒词。

**语法**: `[HWK]ADD_WAKEUP_WORD wakeup_word threshold`

**参数说明**:

- `wakeup_word`：唤醒词内容。
- `threshold`：阈值（0.0～1.0）。

**示例**:

```dsl
[HWK]ADD_WAKEUP_WORD 你好小白 0.8
```

### Command `GET_WAKEUP_TERM`

**作用**: 获取当前配置的唤醒词列表。

**语法**: `[HWK]GET_WAKEUP_TERM`

**参数说明**:

- 无特殊参数说明。

**示例**:

```dsl
[HWK]GET_WAKEUP_TERM
```

### Command `SET_WAKEUP_ENABLE`

**作用**: 设置指定唤醒词是否启用。

**语法**: `[HWK]SET_WAKEUP_ENABLE wakeup_word enable`

**参数说明**:

- `wakeup_word`：唤醒词内容。
- `enable`：是否启用（`true` / `false` / `1` / `0`）。

**示例**:

```dsl
[HWK]SET_WAKEUP_ENABLE 你好小白 true
```

### Command `SET_VOICE_WAKEUP_OPTION`

**作用**: 设置语音唤醒选项。

**语法**: `[HWK]SET_VOICE_WAKEUP_OPTION option`

**参数说明**:

- `option`：语音唤醒选项值。

**示例**:

```dsl
[HWK]SET_VOICE_WAKEUP_OPTION 1
```

### Command `SET_SRE_REQUEST`

**作用**: 设置声纹（SRE）请求数据。

**语法**: `[HWK]SET_SRE_REQUEST request_data`

**参数说明**:

- `request_data`：声纹请求数据（JSON 字符串）。

**示例**:

```dsl
[HWK]SET_SRE_REQUEST {"user_id":"test","text":"你好"}
```

### Command `SET_SRE_ENABLE_OPTION`

**作用**: 设置声纹使能选项。

**语法**: `[HWK]SET_SRE_ENABLE_OPTION option`

**参数说明**:

- `option`：声纹使能选项值。

**示例**:

```dsl
[HWK]SET_SRE_ENABLE_OPTION 1
```

### Command `SET_LANGUAGE_INFO`

**作用**: 设置语言信息。

**语法**: `[HWK]SET_LANGUAGE_INFO language_info`

**参数说明**:

- `language_info`：语言信息（JSON 字符串）。

**示例**:

```dsl
[HWK]SET_LANGUAGE_INFO {"lang":"cmn"}
```

### Command `SET_VR_SILENCE_TIMEOUT`

**作用**: 设置 VR 静音超时时间。

**语法**: `[HWK]SET_VR_SILENCE_TIMEOUT timeout_ms`

**参数说明**:

- `timeout_ms`：静音超时（毫秒）。

**示例**:

```dsl
[HWK]SET_VR_SILENCE_TIMEOUT 5000
```

### Command `HMI`

**作用**: 设置 HMI 上下文信息。

**语法**: `[HWK]HMI hmi_data_or_file`

**参数说明**:

- `hmi_data_or_file`：HMI 数据（JSON 字符串或 JSON 文件路径）。

**示例**:

```dsl
[HWK]HMI {"page":"music","app":"player"}
[HWK]HMI {WORKPATH}/hmi_config.json
```

## Client `PST`

PSTT 客户端（`PST`）用于在线 ASR（PSTT）服务测试，支持单条音频与批量测试集处理；命令语义与 `COMMAND.md` 中 PST 章节一致。下列语法与示例均以 `[PST]` 为前缀。

### Command `CREATE`

**作用**: 加载 PSTT 配置并初始化服务（构建 `pstt_client` 启动参数等）。

**语法**: `[PST]CREATE config_path`

**参数说明**:

- `config_path`：PSTT 配置文件路径（文档惯例可写 `{CONFIGPATH}/pstt.conf` 等形式）。

**说明**: 若 DSL 中省略路径参数，当前 NANO 运行器会使用运行配置中的默认配置文件路径（与 `{CONFIGPATH}` 同源）作为回退。

**示例**:

```dsl
[PST]CREATE {CONFIGPATH}/pstt.conf
```

### Command `FREE`

**作用**: 释放 PSTT 服务相关资源并从客户端管理器移除实例。

**语法**: `[PST]FREE`

**参数说明**:

- 无特殊参数说明。

**示例**:

```dsl
[PST]FREE
```

### Command `DATA`

**作用**: 处理单个音频文件并输出识别过程/结果（由 `pstt_client` 执行）。

**语法**: `[PST]DATA audio_path [delay=0.0]`

**参数说明**:

- `audio_path`：音频文件路径。
- `delay`：延时比例（可选，默认 `0.0`）。

**示例**:

```dsl
[PST]DATA {WORKPATH}/audio/test.wav
[PST]DATA audio/test.wav delay=0.5
```

### Command `HMI`

**作用**: 设置 PSTT 服务的 HMI 上下文信息。

**语法**: `[PST]HMI hmi_data_or_file`

**参数说明**:

- `hmi_data_or_file`：HMI 数据（JSON 字符串或 JSON 文件路径）。

**示例**:

```dsl
[PST]HMI {"page":"music","app":"player"}
[PST]HMI {WORKPATH}/hmi.json
```

### Command `DATA_QUEUE`

**作用**: 调用 `pstt_client_qa` 按音频列表批量跑测试集。

**语法**: `[PST]DATA_QUEUE case=caselist_path model=model_name bref=testset_name [thread=<n>]`

**参数说明**:

- `case`：音频列表文件路径（必填）。
- `model`：模型名（必填）。
- `bref`：测试集标识（必填，用于结果文件名）。
- `thread`：可选，线程数；传入后会写回配置中的 `THREAD_NUM`。

**数据格式**: 音频列表为 scp 风格文本，每行一个音频路径；以 `#` 或 `//` 开头的注释行会被跳过。

**示例**:

```dsl
[PST]DATA_QUEUE case=audio_list.txt model=cmn bref=testset_a
[PST]DATA_QUEUE case=audio_list.txt model=default bref=testset_a thread=10
```

**音频列表文件示例**:

```
# 音频列表文件
TestAudio/weather/weather_001.wav
TestAudio/weather/weather_002.wav
// 注释行会被跳过
TestAudio/navigation/navi_001.wav
```

## Client `TIA`

TiTan 客户端（`TIA`）用于 TiTan WebSocket ASR 服务测试，支持单文件与批量列表；语义与 `COMMAND.md` 中 TIA 章节一致。

### Command `CREATE`

**作用**: 加载 TiTan 配置并初始化 WebSocket 连接。

**语法**: `[TIA]CREATE config_path`

**参数说明**:

- `config_path`：TiTan 配置文件路径（INI 格式，支持无 section 的键值对）。

**说明**: 若 DSL 中省略路径，当前 NANO 运行器会使用运行配置中的默认配置文件路径（与 `{CONFIGPATH}` 同源）作为回退。

**示例**:

```dsl
[TIA]CREATE {CONFIGPATH}/titan.ini
```

**配置文件示例**（与 `COMMAND.md` 一致）:

```ini
url=ws://example.com/asr
language=cmn
realTimeSilStep=10
```

### Command `FREE`

**作用**: 释放 TiTan 客户端实例（从管理器移除，无额外 teardown 时可直接结束）。

**语法**: `[TIA]FREE`

**参数说明**:

- 无特殊参数说明。

**示例**:

```dsl
[TIA]FREE
```

### Command `DATA`

**作用**: 通过 WebSocket 处理单个音频文件并返回识别结果。

**语法**: `[TIA]DATA audio_path [delay=0.0]`

**参数说明**:

- `audio_path`：音频文件路径。
- `delay`：延时比例（可选，默认 `0.0`）。

**示例**:

```dsl
[TIA]DATA {WORKPATH}/audio/test.wav
[TIA]DATA audio/test.wav delay=0.5
```

### Command `CASELIST`

**作用**: 按列表文件批量处理音频，支持并发 WebSocket。

**语法**: `[TIA]CASELIST caselist_path [delay=0.0] [thread=1]`

**参数说明**:

- `caselist_path`：音频列表文件路径（每行一个音频路径）。
- `delay`：延时比例（可选，默认 `0.0`）。
- `thread`：并发数（可选，默认 `1`）。

**数据格式**: 文本列表，每行一个路径；以 `#` 或 `//` 开头的行为注释。

**示例**:

```dsl
[TIA]CASELIST {WORKPATH}/audio_list.txt
[TIA]CASELIST audio_list.txt delay=0.0 thread=10
```

## Client `CPL`

CarPlay 客户端（`CPL`）在 DSL 层主要提供 `CREATE` / `FREE`；唤醒词、VAD、状态等通过回调池与 `[EXP]CarPlayWakeup`、`[EXP]CarPlayVad`、`[EXP]CarPlayStatus` 等断言验证（与 `COMMAND.md` 一致）。

### Command `CREATE`

**作用**: 创建 CarPlay 引擎。

**语法**: `[CPL]CREATE mode lang config_path`

**参数说明**:

- `mode`：工作模式：`0` 无模式；`1` 唤醒词数据；`2` VAD 信息；`3` 音频数据。
- `lang`：语言代码（如 `cmn` / `eng`）。
- `config_path`：CarPlay 配置文件路径（惯例可用 `{CARPLAYCONFIG}`）。

**说明**: 若 DSL 中仅提供 `mode` 与 `lang` 两个参数，运行器会自动追加运行配置中的 CarPlay 配置文件路径作为第三段参数。

**示例**:

```dsl
[CPL]CREATE 1 cmn {CARPLAYCONFIG}
[CPL]CREATE 2 cmn {CARPLAYCONFIG}
```

### Command `FREE`

**作用**: 释放 CarPlay 引擎资源。

**语法**: `[CPL]FREE`

**参数说明**:

- 无特殊参数说明。

**示例**:

```dsl
[CPL]FREE
```

## Client `ENR`

ECNR 客户端（`ENR`），与 `COMMAND.md` 中「ECNR客户端指令」一致：多通道降噪流水线、VEC/MD5/SNR 等断言与 `ANALYZE_AUDIO_DATA` 分析。

### Command `SET_DOWNLINK`

**作用**: 在 `CREATE` 之前设置上下行模式；首次调用时可由运行器自动创建 ENR 客户端占位实例。`0`=普通 ECNR（上行），`1`=LineIn 下行模式。

**语法**: `[ENR]SET_DOWNLINK downLink`（`downLink` 为 `0` 或 `1`）

**示例**:

```dsl
[ENR]SET_DOWNLINK 0
```

### Command `AMP_TYPE`

**作用**: 在 `CREATE` 之前通过 CarInfo 模拟车机默认功放类型，`n` 取值约 `0`～`8`（与库及车型配置一致）。

**语法**: `[ENR]AMP_TYPE n`

**示例**:

```dsl
[ENR]AMP_TYPE 3
```

### Command `ECNR_TYPE`

**作用**: 在 `CREATE` 之前通过 CarInfo 设置默认 ECNR 类型字符串: 410D/450D/695D。

**语法**: `[ENR]ECNR_TYPE 410D`

**示例**:

```dsl
[ENR]ECNR_TYPE 410D
```

### Command `CREATE`

**作用**: 创建 PNR 引擎。DSL 参数为**一个**字符串，内部用分号 `;` 连接多段 `键:值`（解析逻辑见 `ECNRClient.create` / `parse_params`）。

**语法**: `[ENR]CREATE device:设备标识;micNum:麦克风路数;refNum:参考通道数;micDistance:间距毫米`

**参数说明**:

- **`device`**
  - 设备类型`lexus_2S`。

- **`micNum`**
  - 麦克风路数

- **`refNum`** 
  - 参考通道数

- **`micDistance`**
  - 麦克风间距，单位：mm

**示例**:

```dsl
[ENR]CREATE device:lexus_2S;micNum:4;refNum:7;micDistance:560
```

### Command `SET_WORKMODE`

**作用**: 设置工作模式与采样率（及 LineIn 下的 spectrum 等）。

**语法**: `[ENR]SET_WORKMODE workMode:X;sampleRate:16000[;spectrum:8000|16000|...]`

**书写格式**: 与 `CREATE` 相同，整段写在 `params` 第一段里，用 `;` 连接多对 `键:值`（`parse_params`）。

**参数说明**:

- **`workMode`**：工作模式枚举（整型）。实现中允许取值为 `0`～`11` 或 `21`，超出会报错；具体语义以 `libNR_dynamic.so` / 项目标定为准。  
- **`sampleRate`**：处理采样率（Hz），常用 `16000`。省略时默认 `16000`。  
- **`spectrum`**（可选）：仅在 **`SET_DOWNLINK` 为 `1`（LineIn 下行）** 时传入，作为 `set_linein_pnr_work_mode` 的第三参，表示输出侧谱线/采样相关配置（如 `8000`、`16000`、`24000` 等），需与设备可用向量匹配；普通上行 ECNR 时底层只使用 `workMode` 与 `sampleRate` 两参，**仍可写 `spectrum`，但不上行分支不会传给库**。省略时默认 `8000`。

**示例**:

```dsl
[ENR]SET_WORKMODE workMode:0;sampleRate:16000
```

### Command `START`

**作用**: 按通道掩码与合成方法启动引擎。

**语法**: `[ENR]START channelMask:mask;synthMethod:method`

**书写格式**: 与 `CREATE` 相同，首段字符串内 `channelMask:...;synthMethod:...`（`parse_params`）。

**参数说明**:

- **`channelMask`**：通道掩码（整型，按位表示要打开的**输出**通道）。实现里用其二进制中 `1` 的个数作为输出通道数 `m_outputChannelNum`（例如 `15` 即 `0b1111`，为 4 路输出），并原样传给 `start_pnr_engine` / `start_linein_pnr_engine`。需与后续 `DATA` 写盘长度、断言通道等一致。省略时默认 `15`。  
- **`synthMethod`**：合成/处理策略编号（整型），由底层 NR 库解释，与 `channelMask` 一并传入启动接口。省略时默认 `1`；具体取值含义以 `libNR_dynamic.so` 文档或项目标定为准。

**示例**:

```dsl
[ENR]START channelMask:15;synthMethod:2
```

### Command `STOP`

**作用**: 停止 ECNR 会话。

**语法**: `[ENR]STOP`

**示例**:

```dsl
[ENR]STOP
```

### Command `DATA`

**作用**: 送入多通道 PCM/WAV，生成降噪后数据并参与后续 `ECNR` 类断言。

**语法**: `[ENR]DATA audio_path`

**示例**:

```dsl
[ENR]DATA {WORKPATH}/input_11ch_16k.pcm
```

### Command `ANALYZE_AUDIO_DATA`

**作用**: 对前置 `DATA` 产生的输出在指定时间段内做 dBFS/RMS 等分析，供 `[EXP]ECNR` 断言使用。

**语法**: `[ENR]ANALYZE_AUDIO_DATA channel:N;start:秒;end:秒`

**参数说明**:

- `channel`：通道索引。
- `start` / `end`：时间窗口（秒），必填。

**示例**:

```dsl
[ENR]ANALYZE_AUDIO_DATA channel:0;start:1.78;end:3
```

### Command `SET_PNR_MIC_MUTE_OPTION`

**作用**: 设置麦克风静音开关（PNR）。

**语法**: `[ENR]SET_PNR_MIC_MUTE_OPTION option:0|1`（`parse_params`，`0`/`1` 以外会报错；省略时按实现默认 `0`。）

### Command `SET_PNR_ENABLE_OPTION`

**作用**: 设置 PNR 算法总开关。

**语法**: `[ENR]SET_PNR_ENABLE_OPTION option:0|1`（规则同上。）

### Command `SET_PNR_AUDIO_QUALITY`

**作用**: 设置音质 / 降噪效果档位。

**语法**: `[ENR]SET_PNR_AUDIO_QUALITY quality:整型`（档位含义以 `libNR_dynamic.so` 为准；省略时实现默认 `0`。）

### Command `GET_PNR_VERSION`

**作用**: 读取 NR 库版本字符串。

**语法**: `[ENR]GET_PNR_VERSION`（无参，需已 `CREATE` 且引擎有效；结果在指令返回信息中体现。）

### Command `GET_PNR_HFT_PARAM`

**作用**: 查询 HFT 场景下 PNR 参数配置（库返回字符串）。

**语法**: `[ENR]GET_PNR_HFT_PARAM`（无参。）

### Command `GET_PNR_MVR_PARAM`

**作用**: 查询 MVR 场景下 PNR 参数配置。

**语法**: `[ENR]GET_PNR_MVR_PARAM`（无参。）

### Command `GET_PNR_GEN_PARAM`

**作用**: 查询通用（Gen）场景下 PNR 参数配置。

**语法**: `[ENR]GET_PNR_GEN_PARAM`（无参。）

### Command `FREE`

**作用**: 释放 ECNR 引擎并从客户端管理器移除实例。

**语法**: `[ENR]FREE`

**示例**:

```dsl
[ENR]FREE
```

## Client `PIS`

PISA 大模型全双工 WebSocket 客户端（`PIS`），用于语音输入、视觉理解（指令名为 `VEDIO`）、会话配置等；语义与 `COMMAND.md` 中 PIS 章节一致。**依赖**：`pip install websockets`。音频送流经 AIBS（`libAIBS_dynamic.so`），需在 `[PIS]CREATE` 之后按顺序完成 AIBS 初始化，再 `[PIS]START` 建立 WebSocket。

### Command `CREATE`

**作用**: 解析 WebSocket / Video 服务端等连接参数，不建立长连接。

**语法**: `[PIS]CREATE key=value [key=value ...]`

**参数说明**（常用键）：

- `url`：Realtime WebSocket 地址
- `client_id`：客户端标识
- `video_url`：可选，Video LLM 服务地址

**示例**：

```dsl
[PIS]CREATE url=ws://192.168.128.32:8765/realtime client_id=test_device
[PIS]CREATE url=ws://192.168.128.32:8765/realtime video_url=http://192.168.128.32:8057 client_id=test_device
```

### Command `START`

**作用**: 建立 WebSocket 长连接并等待会话就绪（与 TSA 的 `START channel` 无关）。

**语法**: `[PIS]START`

**示例**：

```dsl
[PIS]START
```

### Command `STOP`

**作用**: 关闭 WebSocket 连接。

**语法**: `[PIS]STOP`

**示例**：

```dsl
[PIS]STOP
```

### Command `FREE`

**作用**: 释放 PIS 客户端资源并从管理器移除实例。

**语法**: `[PIS]FREE`

**示例**：

```dsl
[PIS]FREE
```

### Command `DATA`

**作用**: 主线程同步推流；音频经 AIBS 处理后转发到 WebSocket。

**语法**: `[PIS]DATA audio_path [frame=320] [delay=...] [range=[0,-1]] ...`

**参数说明**: 命名参数含义与 TSA 的 `DATA` 类似（帧长、延时、时间片等），以 `PISALLMClient` 实现为准。

**示例**：

```dsl
[PIS]DATA {WORKPATH}/audio/test.wav
[PIS]DATA audio/test.wav frame=320 delay=1.0 range=[0,-1]
```

### Command `VEDIO`

**作用**: 上传图片到 Video LLM；成功后结果进入上下文栈，后续 `DATA` 可一并带上。

**语法**: `[PIS]VEDIO image=path [lat=纬度] [lon=经度] [nlat=下一纬度] [nlon=下一经度]`

**参数说明**: `image` 必填；`lat`/`lon` 为空表示前置摄像头；`nlat`/`nlon` 为下一位置坐标。

**示例**：

```dsl
[PIS]VEDIO image={WORKPATH}/frame_001.png
[PIS]VEDIO image=road.jpg lat=39.9 lon=116.4
[PIS]VEDIO image=intersection.png lat=39.9 lon=116.4 nlat=39.91 nlon=116.41
```

### Command `WAIT`

**作用**: 主线程阻塞直到匹配事件/文本或超时（默认超时见实现，可用 `timeout=` 覆盖）。

**语法**:

- `[PIS]WAIT type=事件类型 [键=值 ...] [timeout=N]`
- `[PIS]WAIT text=关键词 [timeout=N]`

DSL 行末也可使用全局超时写法 `<timeout=N>`（与用例风格一致）。

**示例**：

```dsl
[PIS]WAIT type=response.done <timeout=5>
[PIS]WAIT type=response.done response_type=query <timeout=3>
[PIS]WAIT text=北京 <timeout=10>
[PIS]WAIT type=input_audio_buffer.speech_started <timeout=2>
[PIS]WAIT type=response.input_audio_transcription.completed <timeout=5>
```

### Command `UPDATE`

**作用**: 发送 `session.update`（JSON 文件、清空上下文或系统指令等）。

**语法**:

- `[PIS]UPDATE path/to/session.json`
- `[PIS]UPDATE quit=true`
- `[PIS]UPDATE instructions="系统人设文本"`

**示例**：

```dsl
[PIS]UPDATE {WORKPATH}/session_config.json
[PIS]UPDATE quit=true
[PIS]UPDATE instructions="你是一个简洁的车载语音助手"
```

## Client `TSS`
### Command `START_SERVICE`

**作用**: 启动 AIBS 语音服务进程（`start_aibs_service`），使用运行配置中的 decoder 路径与给定语言。

**语法**: `[TSS]START_SERVICE lang`

**参数说明**:

- `lang`：语言代码，常用 `cmn`、`eng`、`yue`；省略时实现侧常默认 `cmn`。

**示例**:

```dsl
[TSS]START_SERVICE cmn
```

### Command `SET_CARTYPE`

**作用**: 调用 `set_aibs_engine_device_type`，**必须在 `[TSS]CREATE` 之前**执行。

**语法**: `[TSS]SET_CARTYPE "车型字符串"`

**示例**:

```dsl
[TSS]SET_CARTYPE "KAICHENG_TWO"
```

### Command `CREATE`

**作用**: 调用 `create_aibs_client` 创建 AIBS 客户端并阻塞等待 init 成功回调。

**语法**: `[TSS]CREATE lang`

**参数说明**:

- `lang`：与 `START_SERVICE` 一致的语言代码；省略时实现常默认 `cmn`。配置文件来自 pytest 的 `-C` / `{CONFIGPATH}`。

**示例**:

```dsl
[TSS]CREATE cmn
```

### Command `SET_WORK_MODE`

**作用**: 调用 `set_engine_work_mode`，设置 AIBS 工作模式（`0`～`7`）。

**语法**: `[TSS]SET_WORK_MODE mode`

**示例**:

```dsl
[TSS]SET_WORK_MODE 1
```

### Command `START`

**作用**: 调用 `start_aibs_engine` 启动会话并等待 start 成功回调。

**语法**: `[TSS]START`（无参数，与 TSA 的 `START channel` 不同。）

**示例**:

```dsl
[TSS]START
```

### Command `STOP`

**作用**: 停止当前 AIBS 会话（`stop_aibs_engine`）。

**语法**: `[TSS]STOP`

**示例**:

```dsl
[TSS]STOP
```

### Command `DATA`

**作用**: 按帧将音频送入 AIBS（支持命名参数，语义见上文「DATA 参数细节」）。

**语法**: `[TSS]DATA audio_path [frame=320] [delay=1.0] [range=[0,-1]]`

**示例**:

```dsl
[TSS]DATA {WORKPATH}/audio/test.wav frame=320 delay=1.0 range=[0,-1]
```

### Command `SET_PARAM`

**作用**: 调用 `set_aibs_engine_param` 设置单个引擎参数。

**语法**: `[TSS]SET_PARAM key value`

**参数说明**:

- `key`：`AIBSEngineParam` 中的枚举名（如 `ENGINE_PARAM_SR_REAL_TIME_RESULT`）。
- `value`：由底层接口消费的标量或指针兼容值；多组参数可写多条 `SET_PARAM`。

**示例**:

```dsl
[TSS]SET_PARAM ENGINE_PARAM_SR_REAL_TIME_RESULT 1
```

### Command `SET_LANGUAGE_MODE`

**作用**: 切换识别/交互语言模式。

**语法**: `[TSS]SET_LANGUAGE_MODE cmn|eng|yue`

**示例**:

```dsl
[TSS]SET_LANGUAGE_MODE cmn
```

### Command `SET_WAKEUP_WORD`

**作用**: 设置唤醒词及阈值。

**语法**: `[TSS]SET_WAKEUP_WORD word threshold`

**示例**:

```dsl
[TSS]SET_WAKEUP_WORD 你好小白 0.8
```

### Command `SET_WAKEUP_ENABLE`

**作用**: 设置指定唤醒词是否在线启用。

**语法**: `[TSS]SET_WAKEUP_ENABLE word true|false`

**示例**:

```dsl
[TSS]SET_WAKEUP_ENABLE 你好小白 true
```

### Command `GET_WAKEUP_WORD`

**作用**: 获取当前唤醒词列表（成功时结果会进入断言池，回调类型标记为 `TSS`）。

**语法**: `[TSS]GET_WAKEUP_WORD`

**示例**:

```dsl
[TSS]GET_WAKEUP_WORD
```

### Command `FREE`

**作用**: 释放 AIBS 引擎并停止服务，移除客户端实例。

**语法**: `[TSS]FREE`

**示例**:

```dsl
[TSS]FREE
```

## Client `SYS`

### Command `PULL`

**作用**: 拉起服务

**语法**: `[SYS]PULL service_name language [car_type]`

**参数说明**:
- `service_name`：服务名称
- `language`：语言代码
- `car_type`：车型信息（JSON格式，仅AIBSServer需要）

**示例**:
```dsl
[SYS]PULL LCSEngine cmn
[SYS]PULL SpeechEngine cmn
[SYS]PULL AIBSServer cmn {"brand":"0"}
```

### Command `KILL`

**作用**: 终止服务

**语法**: `[SYS]KILL service_name`

**参数说明**:
- 无特殊参数说明。

**示例**:
```dsl
[SYS]KILL LCSEngine
[SYS]KILL SpeechEngine
[SYS]KILL AIBSServer
```

### Command `SLEEP`

**作用**: 睡眠等待

**语法**: `[SYS]SLEEP seconds`

**参数说明**:
- `seconds`：睡眠时间（秒）

**示例**:
```dsl
[SYS]SLEEP 2        # 等待2秒
[SYS]SLEEP 0.5      # 等待0.5秒
```

### Command `CMD`

**作用**: 执行系统命令

**语法**: `[SYS]CMD command`

**参数说明**:
- `command`：要执行的系统命令

**示例**:
```dsl
[SYS]CMD mkdir -p {WORKPATH}/output
[SYS]CMD cp {CONFIGPATH} {WORKPATH}/backup.conf
[SYS]CMD echo "测试开始" > {LOGPATH}/test.log
```

### Command `PRINT`

**作用**: 打印消息

**语法**: `[SYS]PRINT message`

**参数说明**:
- `message`：要打印的消息内容

**示例**:
```dsl
[SYS]PRINT === 测试开始 ===
[SYS]PRINT 当前Suite: {SUITENAME}
[SYS]PRINT 工作目录: {WORKPATH}
```

### Command `ENV`

**作用**: 设置环境变量

**语法**: `[SYS]ENV key=value`

**参数说明**:
- `key`：环境变量名称
- `value`：环境变量值（支持包含`=`号的值；支持双引号`"`或单引号`'`包裹，外层引号会被自动去除）

**示例**:
```dsl
# 设置简单环境变量
[SYS]ENV ro.vendor-iauto.unityversion=313
# 设置路径类型环境变量
[SYS]ENV MY_CONFIG_PATH=/data/test/config
```

### Command `UPLOAD`

**作用**: 更新文件内容

**语法**: `[SYS]UPLOAD upload_type file_path [params...]`

**参数说明**:
- `upload_type`：上传类型（JSON、LINE、REPLACE）
- `file_path`：目标文件路径（支持环境变量）
- `params`：根据类型不同的额外参数

**示例**:

```dsl
# 更新嵌套字段（数字）
[SYS]UPLOAD JSON {WORKPATH}/daemon_tag.json data.text.start 320
# 更新嵌套字段（字符串）
[SYS]UPLOAD JSON {WORKPATH}/config.json app.name "MyApp"
```

### Command `ALLURE`

**作用**: 添加Allure报告附件

**语法**: `[SYS]ALLURE attachment_type file_path`

**参数说明**:
- `attachment_type`：附件类型（TEXT、CSV、JSON等）
- `file_path`：要添加的文件路径（支持环境变量）

**示例**:
```dsl
# 添加配置文件到报告（TEXT类型）
[SYS]ALLURE TEXT {WORKPATH}/decoder.conf
# 添加CSV报告到Allure
[SYS]ALLURE CSV {WORKPATH}/asr_report.csv
```

### Command `FOTA_RANDOM_ZIP`

**作用**: FOTA动态压缩包支持

**语法**: `[SYS]FOTA_RANDOM_ZIP source_dir target_zip count [zip_root] [mode]`

**参数说明**:
- `source_dir`：源目录路径（支持环境变量）
- `target_zip`：目标zip文件路径（支持环境变量）
- `count`：随机选取的文件数量（整数）
- `zip_root`：zip包内的根目录名（可选，`None`或`.`表示无根目录）
- `mode`：打包模式（可选，默认为`normal`）
- `normal`：普通模式，从源目录随机选取文件
- `lcs`：LCS模式，仅从`TSAPResource`目录选取文件，并自动生成`checksum.list`文件

**示例**:
```dsl
# 普通模式：随机选取10个文件打包
[SYS]FOTA_RANDOM_ZIP {WORKPATH}/resources {WORKPATH}/output/random.zip 10
# 指定zip包内根目录
[SYS]FOTA_RANDOM_ZIP {WORKPATH}/resources {WORKPATH}/output/random.zip 10 myroot
```

### Command `BREF`

**作用**: 写入分段说明文本，常用于报告或日志中的步骤标记。

**语法**: `[SYS]BREF text`

**参数说明**:
- `text`：分段标题或说明文本。

**示例**:
```dsl
[SYS]BREF "1. 基础关键字搜索 (SEARCH Mode)"
```

### Command `CLEAR_ASSERT`

**作用**: 清空断言上下文，防止历史回调或 API 结果污染后续断言。

**语法**: `[SYS]CLEAR_ASSERT [type]`

**参数说明**:
- `type`：可选。支持 ALL、CALLBACK、API 或具体断言类型名。

**示例**:
```dsl
[SYS]CLEAR_ASSERT
[SYS]CLEAR_ASSERT CALLBACK
[SYS]CLEAR_ASSERT cloudASRResult
```

## Client `TSR`

TSR（Test Suite Report）用于 **Suite  teardown** 阶段的统计与报告（准确率、时延、VAD、唤醒、时间边界、大模型评测、PSTT 汇总等）。实现位于 `src/testsuite/NANO/tools/tsr/`，由装饰器注册；**完整字段说明、输入文件格式、终端 Summary 与命令行用法** 见同目录文档 **`TSR.md`**。下列 DSL 与 `TSR.md` / `COMMAND.md` 中 TSR 章节一致。

**使用建议**：写在 `>>> SUITE_TEARDOWN` … `<<<` 中；参数为命名形式 `key=value`，多参数在同一行用空格分隔；路径支持 `{WORKPATH}`、`{ROOTPATH}`、`{SUITEID}` 等占位符。

### Command `ASR_ACCURACY`

**作用**: 对比识别结果 CSV 与参考答案 CSV，计算句准率、字准率、插入/删除/替换率、空结果率等，并生成 Excel。

**语法**: `[TSR]ASR_ACCURACY result=<识别结果.csv> ref=<参考答案.csv> [output=<报告.xlsx>]`

**参数说明**:

- `result=`：必填。识别结果 CSV（含 `voice`、`result`、`type` 等；仅统计 `*ASRResult` 最终结果类型）。
- `ref=`：必填。参考答案 CSV（音频路径列与文本列名见 `TSR.md`）。
- `output=`：可选。报告路径；默认 `{WORKPATH}/asr_accuracy.xlsx`。

**示例**:

```dsl
[TSR]ASR_ACCURACY result={WORKPATH}/asr.csv ref=TestCase/ref/cmn_answer.csv output={WORKPATH}/asr_accuracy.xlsx
```

### Command `ASR_LANGUAGE`

**作用**: 统计识别结果中 **语种** 与期望语种是否一致。

**语法**: `[TSR]ASR_LANGUAGE result=<识别结果.csv> ref=<期望语种代码> [output=<报告.xlsx>]`

**参数说明**:

- `result=`：必填。CSV 需含 `lang` 等字段（规则同 `TSR.md`）。
- `ref=`：必填。期望语种，如 `cmn`、`en`、`yue`。
- `output=`：可选。默认 `{WORKPATH}/asr_language.xlsx`。

**示例**:

```dsl
[TSR]ASR_LANGUAGE result={WORKPATH}/asr.csv ref=cmn output={WORKPATH}/lang_report.xlsx
```

### Command `DELAY`

**作用**: 根据卡拉 OK 式标注与 `callback.jsonl`，分析 **实时上屏**（`type` 以 `Temp` 结尾）或 **最终结果** 上屏时延。

**语法**: `[TSR]DELAY ref=<标注文件> result=<callback.jsonl> type=<回调类型> [output=<报告.xlsx>]`

**参数说明**:

- `ref=`：必填。卡拉 OK 式标注（格式见 `TSR.md`）。
- `result=`：必填。回调 JSONL。
- `type=`：必填。与 JSONL 中 `callback_type` 完全一致；`Temp` 结尾为实时模式。
- `output=`：可选。默认 `{WORKPATH}/delay.xlsx`。

**示例**:

```dsl
[TSR]DELAY ref=TestCase/ref/label.txt result={WORKPATH}/callback.jsonl type=PSTTASRResultTemp output={WORKPATH}/delay.xlsx
```

### Command `WAKEUP_ACCURACY`

**作用**: 对比唤醒结果 CSV 与无表头参考唤醒文件，统计唤醒率、FA、FR、关键词错误、断句/连句及可选 channel 音区检测。

**语法**: `[TSR]WAKEUP_ACCURACY result=<唤醒结果.csv> ref=<参考唤醒.csv> [output=<报告.xlsx>]`

**参数说明**:

- `result=`：必填。有表头 CSV（`audio`、`result`、`start`、`end`，可选 `channel`）。
- `ref=`：必填。无表头：`音频,关键词,开始(s),结束(s)[,channel]`。
- `output=`：可选。默认 `{WORKPATH}/wakeup_accuracy.xlsx`。

**示例**:

```dsl
[TSR]WAKEUP_ACCURACY result={WORKPATH}/wakeup.csv ref=TestCase/ref/wakeup_ref.csv output={WORKPATH}/wakeup_report.xlsx
```

### Command `VAD_ACCURACY`

**作用**: VAD 段级 FA / FR 统计（无关键词，时间重叠即匹配）。

**语法**: `[TSR]VAD_ACCURACY result=<result_txt> ref=<ref_txt> [output=<报告.xlsx>]`

**参数说明**: `result` / `ref` 为同格式空格分隔无表头文本（见 `TSR.md`）。

**示例**:

```dsl
[TSR]VAD_ACCURACY result={WORKPATH}/vad.txt ref=TestCase/ref/vad_ref.txt
```

### Command `VAD_PRECISION`

**作用**: 在已匹配段上统计 VAD **起止时间边界误差** 及分位容忍值。

**语法**: `[TSR]VAD_PRECISION result=<result_txt> ref=<ref_txt> [output=<报告.xlsx>]`

**参数说明**: 输入格式与 `VAD_ACCURACY` 相同。

**示例**:

```dsl
[TSR]VAD_PRECISION result={WORKPATH}/vad.txt ref=TestCase/ref/vad_ref.txt
```

### Command `TIME_BOUNDARY_ACCURACY`

**作用**: 统计起止时间误差；支持纯文本边界文件或 `callback.jsonl`，可选端云对比。

**语法**: `[TSR]TIME_BOUNDARY_ACCURACY result=<结果文件> ref=<参考txt> [output=<路径>] [threshold=<秒>] [type=<类型>]`

**参数说明**:

- `result=`：必填。`txt` 或 `.jsonl`（字段要求见 `TSR.md`）。
- `ref=`：必填。参考时间 txt（`00h_S` 段等）。
- `output=`：可选。
- `threshold=`：可选。秒，默认 `0.3`；超阈值在报告中高亮。
- `type=`：可选。`ASRResult` / `localASRResult` / `cloudASRResult` / `both` 等。

**示例**:

```dsl
[TSR]TIME_BOUNDARY_ACCURACY result={WORKPATH}/callback.jsonl ref=TestCase/ref/timelist.txt output={WORKPATH}/tb.xlsx threshold=0.3 type=both
```

### Command `LLM`

**作用**: 读取待评测 CSV，按 Prompt 模板并发请求大模型，生成 Excel/HTML 报告（需环境变量 `DEEPSEEK_API_KEY` 等，见 `TSR.md`）。

**语法**: `[TSR]LLM result=<csv> prompt=<模板文件> [output=<路径>] [batch=<条数>]`

**参数说明**:

- `result=`、`prompt=`：必填。
- `output=`：可选。默认 `{WORKPATH}/mango_report/llm_eval.xlsx`（以 `TSR.md` 为准）。
- `batch=`：可选。每批请求条数，默认 `10`。

**示例**:

```dsl
[TSR]LLM result={WORKPATH}/nlu_result.csv prompt=TestCase/eval_prompts.txt output={WORKPATH}/llm_report.xlsx batch=20
```

### Command `PSTT_ACCURACY`

**作用**: 对 `pstt_client_qa` 生成的 `*_full.txt`（或结果目录）与 ref 标注做 **ASR / 语种 / 性别年龄情绪 / GPU 时延** 等综合统计；`type` 可取 `asr`、`lang`、`sex`、`age`、`emotion`、`gpu`、`gae`、`auto` 及组合（见 `pstt_accuracy.py`）。

**语法**: `[TSR]PSTT_ACCURACY result=<*_full.txt 或目录/> ref=<ref 文件或目录/> type=<维度列表> [output=<xlsx>]`

**参数说明**:

- `result=`：必填。单个 `*_full.txt` 或结果目录（按 bref 匹配多测试集，规则见工具文件头注释）。
- `ref=`：必填。标注 TSV/CSV 等；`AUDIOPATH` 必须，其余列随 `type` 选填。
- `type=`：必填。如 `asr,lang,gpu` 或目录模式下 `auto`。
- `output=`：可选。默认套件目录下 `pstt_accuracy.xlsx`（以实现为准）。

**示例**:

```dsl
[TSR]PSTT_ACCURACY result={WORKPATH}/result_file/C1__tag_full.txt ref=TestCase/ref/C1_ref.tsv type=asr,lang,gpu
[TSR]PSTT_ACCURACY result={WORKPATH}/result_file/ ref=TestCase/ref_dir/ type=auto
```

## Client `NIS`

### Command `CREATE`

**作用**: 创建客户端引擎

**语法**: `[客户端]CREATE language appid [config_file]`

**参数说明**:
- `language`：语言代码 (`cmn`=中文, `eng`=英文, `yue`=粤语)
- `appid`：应用标识符
- `config_file`：配置文件路径（可选）

**示例**:
```dsl
[TSA]CREATE cmn com.autoai.vr.service_vrassistant
[TSA]CREATE eng com.autoai.vr.service_vrassistant {CONFIGPATH}
[SET]CREATE cmn com.pachira.set
```

### Command `START`

**作用**: 启动会话

**语法**: `[客户端]START channel_num`

**参数说明**:
- `channel_num`：音频通道数（通常为1，支持多通道）

**示例**:
```dsl
[TSA]START 1    # 单通道启动
[TSA]START 4    # 四通道启动
```

### Command `STOP`

**作用**: 停止会话

**语法**: `[客户端]STOP`

**参数说明**:
- 无特殊参数说明。

**示例**:
```dsl
[TSA]STOP
[SET]STOP
```

### Command `FREE`

**作用**: 释放客户端资源

**语法**: `[客户端]FREE`

**参数说明**:
- 无特殊参数说明。

**示例**:
```dsl
[TSA]FREE
[SET]FREE
```

### Command `DATA`

**作用**: 发送音频数据

**语法**: `[客户端]DATA audio_path [named_parameters...]`

**参数说明**:
- 无特殊参数说明。

**示例**:
```dsl
# 基础用法
[TSA]DATA {WORKPATH}/audio/weather.wav
# 指定帧大小
[TSA]DATA audio/test.wav frame=640
```

### Command `TEXT_DATA`

**作用**: 发送文本并内部转为 `DATA` 执行（NIS 语义与 TSA 一致）。

**语法**: `[客户端]TEXT_DATA text [lang=cmn|eng|...] [engine=auto|volcano|edge_tts|index_tts|voxCpm] [frame=320] [delay=0] [range=[0,-1]] [abstime=0|1]`

**参数说明**:
- `text`：必填，待合成文本。
- 其他参数语义与 TSA 的 `TEXT_DATA` 相同。

**示例**:
```dsl
[NIS]TEXT_DATA 打开空调
[NIS]TEXT_DATA text="close the window" lang=eng engine=auto frame=320 delay=1 range=[0,-1]
```

### Command `EVENT`

**作用**: 发送事件

**语法**: `[客户端]EVENT json_event_data`

**参数说明**:
- `json_event_data`：JSON格式的事件数据

**示例**:
```dsl
[TSA]EVENT {"source":"TSA","type":"SetFullTimeOption","data":{"value":1}}
[TSA]EVENT {"source":"TSA","type":"VehicleInfo","data":{"vin":"TEST123","brand":"Lexus-2S"}}
```

### Command `CANCEL`

**作用**: 取消操作

**语法**: `[客户端]CANCEL`

**参数说明**:
- 无特殊参数说明。

**示例**:
```dsl
[TSA]CANCEL
[VOI]CANCEL
```

### Command `FREEWAKEUP`

**作用**: 设置识别/唤醒模式

**语法**: `[客户端]FREEWAKEUP status`

**参数说明**:
- `status`：模式状态（0=唤醒模式，1=识别模式）

**示例**:
```dsl
# 设置唤醒模式
[TSA]FREEWAKEUP 0
# 设置识别模式
[TSA]FREEWAKEUP 1
```

### Command `SETVRCONFIG`

**作用**: 设置VR配置

**语法**: `[客户端]SETVRCONFIG config_name config_value [language]`

**参数说明**:
- `config_name`：配置项名称（详见下表）
- `config_value`：配置值
- `language`：语言代码（可选，部分配置需要）

**示例**:
```dsl
# 设置唤醒词别名
[SET]SETVRCONFIG WAKEUP_ALIAS 你好小白 cmn
# 设置主动交互
[SET]SETVRCONFIG ACTIVE_INTERACTION true cmn
```

### Command `TEXT`

**作用**: 文本输入

**语法**: `[客户端]TEXT text`

**参数说明**:
- `text`：传入理解的文本内容

**示例**:
```dsl
# 将“今天天气怎么样”的文本传入给引擎
[TSA]TEXT 今天天气怎么样
```

### Command `STRATEGY`

**作用**: 策略模式

**语法**: `[客户端]STRATEGY status`

**参数说明**:
- `status`：模式状态（0=离线模式，1=在线模式，2=混合仲裁模式）

**示例**:
```dsl
# 设置离线模式
[TSA]STRATEGY 0
# 设置在线模式
[TSA]STRATEGY 1
```

### Command `OPEN_VOICE_INPUT`

**作用**: 开启语音输入

**语法**: `[客户端]OPEN_VOICE_INPUT param`

**参数说明**:
- `param`：语音输入参数设置（JSON格式字符串或配置参数）

**示例**:
```dsl
[TSA]OPEN_VOICE_INPUT {"mode":0,"channel":0}
[VOI]OPEN_VOICE_INPUT voice_input_config
```

### Command `CLOSE_VOICE_INPUT`

**作用**: 关闭语音输入

**语法**: `[客户端]CLOSE_VOICE_INPUT`

**参数说明**:
- 无特殊参数说明。

**示例**:
```dsl
[TSA]CLOSE_VOICE_INPUT
[VOI]CLOSE_VOICE_INPUT
```

### Command `START_SPEAKER_ENROLL`

**作用**: 开始声纹注册

**语法**: `[客户端]START_SPEAKER_ENROLL user_id text id channel_id`

**参数说明**:
- `user_id`：用户ID字符串
- `text`：注册文本内容
- `id`：当前注册次数编号
- `channel_id`：音频通道ID

**示例**:
```dsl
# 用户user001第1次注册，使用通道0
[SET]START_SPEAKER_ENROLL user001 你好雷克萨斯，登录我的个人中心 1 0
# 用户admin第3次注册，使用通道0
[SET]START_SPEAKER_ENROLL admin 测试文本内容 3 0
```

### Command `END_SPEAKER_ENROLL`

**作用**: 结束声纹注册

**语法**: `[客户端]END_SPEAKER_ENROLL`

**参数说明**:
- 无特殊参数说明。

**示例**:
```dsl
[TSA]END_SPEAKER_ENROLL
[SET]END_SPEAKER_ENROLL
```

### Command `RECOGNIZE_SPEAKER`

**作用**: 声纹登录时系统调用接口

**语法**: `[VOI客户端]RECOGNIZE_SPEAKER channel_id start end`

**参数说明**:
- `channel_id`：发话的音区
- `start`：发话开始时间
- `end`：发话结束时间

**示例**:
```dsl
[VOI]RECOGNIZE_SPEAKER 0 1230 3456
[VOI]RECOGNIZE_SPEAKER 1 3420 9203
```

### Command `VOICEPRINT_LOGIN`

**作用**: 声纹登录

**语法**: `[客户端]VOICEPRINT_LOGIN audio_path [frame_size] [delay]`

**参数说明**:
- `audio_path`：音频文件路径（必需）
- `frame_size`：帧大小，默认320（可选）
- `delay`：延时比例，默认0.0（可选）

**示例**:
```dsl
# 使用默认参数
[SET]VOICEPRINT_LOGIN {WORKPATH}/audio/login.wav
# 指定帧大小
[SET]VOICEPRINT_LOGIN {WORKPATH}/audio/login.wav 320
```

### Command `VERIFY_VOICEPRINT`

**作用**: 声纹验证

**语法**: `[客户端]VERIFY_VOICEPRINT user_id verify_text timeout_seconds`

**参数说明**:
- `user_id`：要验证的用户ID
- `verify_text`：验证文本
- `timeout_seconds`：超时时间

**示例**:
```dsl
[TSA]VERIFY_VOICEPRINT user001 你好小白 0
[SET]VERIFY_VOICEPRINT admin 验证文本 5
```

### Command `CANCEL_VERIFY_VOICEPRINT`

**作用**: 取消声纹验证

**语法**: `[客户端]CANCEL_VERIFY_VOICEPRINT`

**参数说明**:
- 无特殊参数说明。

**示例**:
```dsl
[TSA]CANCEL_VERIFY_VOICEPRINT
[SET]CANCEL_VERIFY_VOICEPRINT
```

### Command `DELETE_SPEAKER`

**作用**: 删除声纹

**语法**: `[客户端]DELETE_SPEAKER user_id`

**参数说明**:
- `user_id`：要删除的用户ID

**示例**:
```dsl
[TSA]DELETE_SPEAKER user001
[SET]DELETE_SPEAKER test_user
```

### Command `GET_SPEAKER_INFO`

**作用**: 获取声纹信息

**语法**: `[客户端]GET_SPEAKER_INFO user_id`

**参数说明**:
- `user_id`：用户ID

**示例**:
```dsl
[TSA]GET_SPEAKER_INFO user001
[SET]GET_SPEAKER_INFO admin
```

### Command `GET_SPEAKERS`

**作用**: 获取已注册声纹列表

**语法**: `[客户端]GET_SPEAKERS`

**参数说明**:
- 无特殊参数说明。

**示例**:
```dsl
[TSA]GET_SPEAKERS
[SET]GET_SPEAKERS
```

### Command `GET_ENROLL_TEXT`

**作用**: 获取注册文本

**语法**: `[客户端]GET_ENROLL_TEXT`

**参数说明**:
- 无特殊参数说明。

**示例**:
```dsl
[TSA]GET_ENROLL_TEXT
[VOI]GET_ENROLL_TEXT
```

### Command `SENSITIVE_WORD_CHECK`

**作用**: 敏感词检测

**语法**: `[客户端]SENSITIVE_WORD_CHECK text`

**参数说明**:
- `text`：要检测的文本

**示例**:
```dsl
[TSA]SENSITIVE_WORD_CHECK 测试文本内容
[SET]SENSITIVE_WORD_CHECK 需要检查的语句
```

### Command `REGISTER_VOICEPRINT_LIST`

**作用**: 批量注册声纹

**语法**: `[客户端]REGISTER_VOICEPRINT_LIST sre_user_files`

**参数说明**:
- `sre_user_files`：声纹注册的用户列表，可以支持多个userid，按照userid分组

**示例**:
```dsl
# 方式1: 从JSON文件读取（推荐）
[SET]REGISTER_VOICEPRINT_LIST TestCase/caselist/haijin_female.txt
# 参数文件示例:
TestAudio/vp_multi_channel/haijin/zhu/66_你好小悦登录我的个人中心.wav	text:你好小悦，登录我的个人中心;channel:0;user_id:haijin;index:1
```

### Command `INPUTEVENT`

**作用**: 发送输入事件，用于注入技能执行所需的外部上下文。

**语法**: `[TSA]INPUTEVENT event_name`

**参数说明**:

- `event_name`：事件名称，如 VehicleInfo、NaviLocationStatus、NavigateStatus。

**示例**:

```dsl
[TSA]INPUTEVENT VehicleInfo
[TSA]INPUTEVENT NaviLocationStatus
```

### Command `CALLBACK`

**作用**: 主动注入回调数据，常用于多轮对话、搜索结果、事件驱动测试等场景。

**语法**: `[TSA]CALLBACK callback_name [field_path:value ...]`

**参数说明**:

- `callback_name`：回调名称，常见为 default。
- `field_path:value`：可选，按字段路径注入返回值或文件数据。

**示例**:

```dsl
[TSA]CALLBACK default
[TSA]CALLBACK default data.result.code:0
```

## Client `NSE`

### Command `CREATE`

**作用**: 创建客户端引擎

**语法**: `[客户端]CREATE language appid [config_file]`

**参数说明**:
- `language`：语言代码 (`cmn`=中文, `eng`=英文, `yue`=粤语)
- `appid`：应用标识符
- `config_file`：配置文件路径（可选）

**示例**:
```dsl
[TSA]CREATE cmn com.autoai.vr.service_vrassistant
[TSA]CREATE eng com.autoai.vr.service_vrassistant {CONFIGPATH}
[SET]CREATE cmn com.pachira.set
```

### Command `FREE`

**作用**: 释放客户端资源

**语法**: `[客户端]FREE`

**参数说明**:
- 无特殊参数说明。

**示例**:
```dsl
[TSA]FREE
[SET]FREE
```

### Command `EVENT`

**作用**: 发送事件

**语法**: `[客户端]EVENT json_event_data`

**参数说明**:
- `json_event_data`：JSON格式的事件数据

**示例**:
```dsl
[TSA]EVENT {"source":"TSA","type":"SetFullTimeOption","data":{"value":1}}
[TSA]EVENT {"source":"TSA","type":"VehicleInfo","data":{"vin":"TEST123","brand":"Lexus-2S"}}
```

### Command `SETVRCONFIG`

**作用**: 设置VR配置

**语法**: `[客户端]SETVRCONFIG config_name config_value [language]`

**参数说明**:
- `config_name`：配置项名称（详见下表）
- `config_value`：配置值
- `language`：语言代码（可选，部分配置需要）

**示例**:

```dsl
# 设置唤醒词别名
[SET]SETVRCONFIG WAKEUP_ALIAS 你好小白 cmn
# 设置主动交互
[SET]SETVRCONFIG ACTIVE_INTERACTION true cmn
```

## Client `EXP`

**断言客户端**：从回调池/结果数据中匹配指定类型的记录，并对 **字段键值** 做校验。字段名及与 JSON 的映射关系以仓库 **`conf/assert_key_value.yaml`** 为准（本节的「可断言字段」表与该文件各顶层键一致）。

**通用语法**（与 `COMMAND.md` 断言章节一致，可在此基础上加超时）：

`[EXP]<断言类型> [[通道号]]字段1:期望值1[;字段2:期望值2...] [<timeout=秒>]`

- **断言类型**：与回调 `type` / 处理器注册的名称一致（大小写敏感）。
- **`[[通道号]]`**：可选，整型通道，如 `[0]`、`[1]`。
- **多字段**：英文分号 `;` 分隔；数值型字段可配合比较符（如 `confidence:>80`，具体以断言引擎支持为准）。
- **完整字段清单**：除下文明示外，凡 `assert_key_value.yaml` 中该断言类型下的 **左列键名** 均可作为 DSL 字段名使用。

---

### Command `NLPResult`

**作用**: 理解结果 / NLU-NLP 综合回调断言（配置节「理解结果回调信息」）。

**语法**: `[EXP]NLPResult [[ch]]字段:期望[;字段:期望...] [<timeout=N>]`

**可断言字段**: `NLPResult` 节点下字段极多（含 `skill`、`intention`、`asr`、`directives`、`display`、天气/日程/多媒体等）。**完整键名与 YAML 路径以 `assert_key_value.yaml` → `NLPResult` 为准**；下表仅列常用项：

| 字段名 | 说明（摘自配置注释） |
|--------|----------------------|
| `text` / `asr` | `data.asr.text` |
| `skill` | `data.skill` |
| `intention` | `data.intention` |
| `TTS` / `tts` | `data.tts.text` |
| `directivesType` | `directives[0].type` |
| `dirCallbackType` | `directives[0].callback.type` |

**示例**:

```dsl
[EXP]NLPResult skill:WEATHER;intention:QUERY <timeout=5>
[EXP]NLPResult [0]asr:打开空调 <timeout=5>
```

### Command `ASRInputResult`

**作用**: 语音输入法 **最终** 识别结果回调断言。

**语法**: `[EXP]ASRInputResult [[ch]]字段:期望[;...] [<timeout=N>]`

**可断言字段**（`assert_key_value.yaml` → `ASRInputResult`）:

| 字段名 | 说明 |
|--------|------|
| `type` | 类型 |
| `asr` | `data.result.text` |
| `start` / `end` | `data.result.startMts` / `data.result.endMts` |
| `lang` | `data.lang` |
| `channelId` | `data.channelId` |
| `confidence` | `data.result.confidence` |

**示例**:

```dsl
[EXP]ASRInputResult asr:你好;confidence:>90 <timeout=5>
```

### Command `ASRInputResultTemp`

**作用**: 语音输入法 **中间** 识别结果回调断言。

**语法**: `[EXP]ASRInputResultTemp [[ch]]字段:期望[;...] [<timeout=N>]`

**可断言字段**: 与 `ASRInputResult` 相同（见 `ASRInputResultTemp` 节）。

**示例**:

```dsl
[EXP]ASRInputResultTemp asr:你 <timeout=3>
```

### Command `HICARWakeup`

**作用**: HiCar 唤醒结果回调断言。

**语法**: `[EXP]HICARWakeup [[ch]]字段:期望[;...] [<timeout=N>]`

**可断言字段**（`HICARWakeup`）:

| 字段名 | 说明 |
|--------|------|
| `text` | `data.text` |
| `lang` | `data.lang` |
| `channelId` | `data.channelId` |
| `keywordType` | `data.keywordType` |

**示例**:

```dsl
[EXP]HICARWakeup text:你好小德 <timeout=5>
```

### Command `ASRResultTemp`

**作用**: **临时** ASR 识别结果回调断言。

**语法**: `[EXP]ASRResultTemp [[ch]]字段:期望[;...] [<timeout=N>]`

**可断言字段**（`ASRResultTemp`）:

| 字段名 | 说明 |
|--------|------|
| `asr` | `data.result.text` |
| `type` | `type` / `data.type`（配置中均映射 type） |
| `start` / `end` | `data.result.startMts` / `data.result.endMts` |
| `channelId` | `data.channelId` |
| `text` | `data.text` |
| `lang` | `data.lang` |
| `confidence` | `data.result.confidence` |

**示例**:

```dsl
[EXP]ASRResultTemp asr:打开 <timeout=3>
```

### Command `ASRResult`

**作用**: **最终** ASR 识别结果回调断言。

**语法**: `[EXP]ASRResult [[ch]]字段:期望[;...] [<timeout=N>]`

**可断言字段**（`ASRResult`）:

| 字段名 | 说明 |
|--------|------|
| `asr` | `data.result.text` |
| `start` / `end` | `data.result.startMts` / `data.result.endMts` |
| `channelId` | `data.channelId` |
| `lang` | `data.lang` |
| `confidence` | `data.result.confidence` |

**示例**:

```dsl
[EXP]ASRResult asr:打开车窗 <timeout=5>
```

### Command `cloudASRResult`

**作用**: **云端** ASR 最终结果回调断言。

**语法**: `[EXP]cloudASRResult [[ch]]字段:期望[;...] [<timeout=N>]`

**可断言字段**: 与 `ASRResult` 结构一致（`cloudASRResult` 节）。

**示例**:

```dsl
[EXP]cloudASRResult asr:你好小白 <timeout=5>
[EXP]cloudASRResult [1]asr:天气查询;confidence:>80 <timeout=5>
```

### Command `localASRResult`

**作用**: **本地** ASR 最终结果回调断言。

**语法**: `[EXP]localASRResult [[ch]]字段:期望[;...] [<timeout=N>]`

**可断言字段**: 与 `ASRResult` 结构一致（`localASRResult` 节）。

**示例**:

```dsl
[EXP]localASRResult asr:打开空调 <timeout=5>
```

### Command `startEnroll`

**作用**: 声纹 **注册过程** 回调信号断言。

**语法**: `[EXP]startEnroll [[ch]]字段:期望[;...] [<timeout=N>]`

**可断言字段**（`startEnroll`）:

| 字段名 | 说明 |
|--------|------|
| `status` | 状态 |
| `user_id` | `data.user_id` |
| `channelId` | `data.channel` |

**示例**:

```dsl
[EXP]startEnroll status:0 <timeout=10>
```

### Command `verifyVoiceprint`

**作用**: 声纹 **验证** 回调信号断言。

**语法**: `[EXP]verifyVoiceprint [[ch]]字段:期望[;...] [<timeout=N>]`

**可断言字段**（`verifyVoiceprint`）:

| 字段名 | 说明 |
|--------|------|
| `type` | 类型 |
| `status` | 状态 |
| `user_id` | `data.user_id` |
| `message` | 消息 |
| `channelId` | `data.channel` |

**示例**:

```dsl
[EXP]verifyVoiceprint status:0;user_id:user001 <timeout=10>
```

### Command `SpeechWakeup`

**作用**: 通用 **唤醒信号** 回调断言。

**语法**: `[EXP]SpeechWakeup [[ch]]字段:期望[;...] [<timeout=N>]`

**可断言字段**（`SpeechWakeup`）:

| 字段名 | 说明 |
|--------|------|
| `type` | 类型 |
| `text` | `data.text` |
| `keywordType` | `data.keywordType` |
| `channelId` | `data.channelId` |
| `lang` | `data.lang` |
| `start` / `end` | `data.startMts` / `data.endMts` |
| `dialect` | `data.dialect` |
| `confidence` | `data.confidence` |
| `user_id` | `data.voiceDetection.voicePrint.voicePrintId` |

**示例**:

```dsl
[EXP]SpeechWakeup text:你好小白 <timeout=5>
```

### Command `LCSInit`

**作用**: LCS **初始化成功** 信号（版本号等）断言。

**语法**: `[EXP]LCSInit [[ch]]字段:期望[;...] [<timeout=N>]`

**可断言字段**（`LCSInit`）:

| 字段名 | 说明 |
|--------|------|
| `lcs_res_version` | `data.lcs_res_version` |
| `lcsVersion` | `data.lcsVersion` |
| `speechEngineVersion` | `data.speechEngineVersion` |
| `carPlayVersion` | `data.carPlayVersion` |

**示例**:

```dsl
[EXP]LCSInit lcsVersion:1.0.0 <timeout=30>
```

### Command `SpeechASRResultTemp`

**作用**: **SpeechEngine（HWK）** 本地临时 ASR 结果断言。

**语法**: `[EXP]SpeechASRResultTemp [[ch]]字段:期望[;...] [<timeout=N>]`

**可断言字段**（`SpeechASRResultTemp`）:

| 字段名 | 说明 |
|--------|------|
| `asr` | `result.text` |
| `start` / `end` | `result.startMts` / `result.endMts` |
| `channelId` | `channelId` |
| `lang` | `lang` |
| `confidence` | `result.confidence` |

**示例**:

```dsl
[EXP]SpeechASRResultTemp asr:你好 <timeout=5>
```

### Command `SpeechASRResult`

**作用**: **SpeechEngine（HWK）** 本地最终 ASR 结果断言。

**语法**: `[EXP]SpeechASRResult [[ch]]字段:期望[;...] [<timeout=N>]`

**可断言字段**: 与 `SpeechASRResultTemp` 相同（`SpeechASRResult` 节）。

**示例**:

```dsl
[EXP]SpeechASRResult asr:你好小白 <timeout=5>
```

### Command `SpeechEngineWakeup`

**作用**: **SpeechEngine（HWK）** 本地唤醒断言。

**语法**: `[EXP]SpeechEngineWakeup [[ch]]字段:期望[;...] [<timeout=N>]`

**可断言字段**（`SpeechEngineWakeup`）:

| 字段名 | 说明 |
|--------|------|
| `text` | 文本 |
| `keywordType` | 关键词类型 |
| `channelId` | 通道 |
| `lang` | 语种 |
| `start` / `end` | `startMts` / `endMts` |
| `confidence` | 置信度 |
| `user_id` | `voiceDetection.voicePrint.voicePrintId` |

**示例**:

```dsl
[EXP]SpeechEngineWakeup text:你好小白 <timeout=3>
```

### Command `TSSAIBSWakeup`

**作用**: **TSS / AIBS** 唤醒回调断言。

**语法**: `[EXP]TSSAIBSWakeup [[ch]]字段:期望[;...] [<timeout=N>]`

**可断言字段**（`TSSAIBSWakeup`）:

| 字段名 | 说明 |
|--------|------|
| `source` | 来源 |
| `type` | 类型 |
| `text` | `data.text` |
| `start` / `end` | `data.start_time` / `data.end_time` |

**示例**:

```dsl
[EXP]TSSAIBSWakeup text:你好小白 <timeout=5>
```

### Command `TiTanASRResultTemp`

**作用**: **TiTan（TIA）** 临时 ASR 结果断言。

**语法**: `[EXP]TiTanASRResultTemp [[ch]]字段:期望[;...] [<timeout=N>]`

**可断言字段**（`TiTanASRResultTemp`）:

| 字段名 | 说明 |
|--------|------|
| `source` | 来源 |
| `type` | 类型 |
| `asr` | `asr` |
| `start` / `end` | `start` / `end` |
| `channelId` | `channelId` |
| `lang` | `lang` |
| `confidence` | `confidence` |
| `emotion` | `emotion` |
| `gender` | `gender` |
| `age` | `ages`（配置键为 `age`，映射 `ages`） |

**示例**:

```dsl
[EXP]TiTanASRResultTemp asr:今天天气 <timeout=5>
```

### Command `TiTanASRResult`

**作用**: **TiTan（TIA）** 最终 ASR 结果断言。

**语法**: `[EXP]TiTanASRResult [[ch]]字段:期望[;...] [<timeout=N>]`

**可断言字段**: 与 `TiTanASRResultTemp` 相同（`TiTanASRResult` 节）。

**示例**:

```dsl
[EXP]TiTanASRResult asr:今天天气怎么样;emotion:happy <timeout=5>
```

### Command `PSTTASRResultTemp`

**作用**: **PSTT（PST）** 临时 ASR 结果断言。

**语法**: `[EXP]PSTTASRResultTemp [[ch]]字段:期望[;...] [<timeout=N>]`

**可断言字段**: 与 `TiTanASRResultTemp` 列相同（`PSTTASRResultTemp` 节）。

**示例**:

```dsl
[EXP]PSTTASRResultTemp asr:打 <timeout=5>
```

### Command `PSTTASRResult`

**作用**: **PSTT（PST）** 最终 ASR 结果断言。

**语法**: `[EXP]PSTTASRResult [[ch]]字段:期望[;...] [<timeout=N>]`

**可断言字段**: 与 `PSTTASRResultTemp` 相同（`PSTTASRResult` 节）。

**示例**:

```dsl
[EXP]PSTTASRResult asr:打开车窗 <timeout=5>
```

### Command `VRConfig`

**作用**: VR 配置项 / GET_VR_CONFIG 类结果断言。

**语法**: `[EXP]VRConfig [[ch]]字段:期望[;...] [<timeout=N>]`

**可断言字段**（`VRConfig`）:

| 字段名 | 映射（YAML 右值） |
|--------|-------------------|
| `SreMemory` | `SreMemory` |
| `deviceInfo` | `deviceInfo.brand` |
| `vrOption` | `vrOption` |
| `showStyle` | `showStyle` |
| `wakeupAlias` | `wakeupAlias.name` |
| `setVRWakeupAliasCode` | `setVRWakeupAliasCode` |
| `dialogueStyle` | `dialogueStyle` |
| `dialogueLanguage` | `dialogueLanguage` |
| `SoundAreaOption` | `SoundAreaOption` |
| `WakupKeyWordOption` | `WakupKeyWordOption` |
| `VoiceWakeupOption` | `VoiceWakeupOption` |
| `WakeupEnable` | `WakeupEnable` |
| `wakeupWordList` | `wakeupWordList` |
| `wakeupWordListAll` | `wakeupWordListAll` |
| `wakeupWordMain` | `wakeupWordMain` |
| `wakeupRecomTrue` | `wakeupRecomTrue` |
| `wakeupRecomFalse` | `wakeupRecomFalse` |
| `SetTtsVoiceType` | `SetTtsVoiceType` |
| `MultiDialogue` | `MultiDialogue` |
| `ExperienceImprovenment` | `ExperienceImprovenment` |
| `PersonalSensitiveAuthorization` | `PersonalSensitiveAuthorization` |
| `VoiceSensitiveAuthorization` | `VoiceSensitiveAuthorization` |

**示例**:

```dsl
[EXP]VRConfig vrOption:1 <timeout=5>
```

### Command `CarPlayWakeup`

**作用**: **CarPlay（CPL）** 唤醒词检测回调断言。

**语法**: `[EXP]CarPlayWakeup [[ch]]字段:期望[;...] [<timeout=N>]`

**可断言字段**（`CarPlayWakeup`）:

| 字段名 | 说明 |
|--------|------|
| `type` | 类型 |
| `text` | 唤醒文本 |
| `kadStart` / `kadEnd` | KAD 起止 |
| `duration` | 持续时长 |

**示例**:

```dsl
[EXP]CarPlayWakeup text:你好小白 <timeout=5>
```

### Command `CarPlayVadStart`

**作用**: **CarPlay** VAD **开始** 状态回调断言（与 `CarPlayVadEnd` 成对）。

**语法**: `[EXP]CarPlayVadStart [[ch]]字段:期望[;...] [<timeout=N>]`

**可断言字段**（`CarPlayVadStart`）:

| 字段名 | 说明 |
|--------|------|
| `type` | 类型 |
| `state` | VAD 状态 |
| `timestamp` | 时间戳 |

**示例**:

```dsl
[EXP]CarPlayVadStart state:1 <timeout=3>
```

### Command `CarPlayVadEnd`

**作用**: **CarPlay** VAD **结束** 状态回调断言。

**语法**: `[EXP]CarPlayVadEnd [[ch]]字段:期望[;...] [<timeout=N>]`

**可断言字段**: 与 `CarPlayVadStart` 相同（`CarPlayVadEnd` 节）。

**示例**:

```dsl
[EXP]CarPlayVadEnd state:0 <timeout=3>
```

### Command `CarPlayStatus`

**作用**: **CarPlay** 状态变化回调断言。

**语法**: `[EXP]CarPlayStatus [[ch]]字段:期望[;...] [<timeout=N>]`

**可断言字段**（`CarPlayStatus`）:

| 字段名 | 说明 |
|--------|------|
| `type` | 类型 |
| `code` | 状态码 |
| `text` | 文本描述 |

**示例**:

```dsl
[EXP]CarPlayStatus code:0 <timeout=5>
```

### Command `PISASRResult`

**作用**: **PISA（PIS）** 用户语音识别结果断言（`response.input_audio_transcription.completed` 对应数据）。

**语法**: `[EXP]PISASRResult [[ch]]字段:期望[;...] [<timeout=N>]`

**可断言字段**（`PISASRResult`）:

| 字段名 | 说明 |
|--------|------|
| `type` | 类型 |
| `asr` | 用户语音识别文本 |
| `lang` | 发话语种 |

**示例**:

```dsl
[EXP]PISASRResult asr:导航去公司 <timeout=5>
```

### Command `ResponseTTS`

**作用**: **PISA** 大模型回复 TTS 文本断言。

**语法**: `[EXP]ResponseTTS [[ch]]字段:期望[;...] [<timeout=N>]`

**可断言字段**（`ResponseTTS`）:

| 字段名 | 说明 |
|--------|------|
| `tts` | 大模型回复文本 |

**示例**:

```dsl
[EXP]ResponseTTS tts:今天晴天 <timeout=10>
```

### Command `PISAVedioText`

**作用**: **PISA** 图片理解（VEDIO）结果文本断言。

**语法**: `[EXP]PISAVedioText [[ch]]字段:期望[;...] [<timeout=N>]`

**可断言字段**（`PISAVedioText`）:

| 字段名 | 说明 |
|--------|------|
| `image_text` | 图片理解文本 |

**示例**:

```dsl
[EXP]PISAVedioText image_text:前方有行人 <timeout=10>
```

### Command `PISToolCall`

**作用**: **PISA** 工具调用结果断言（`response.tool_call.info` 等）。

**语法**: `[EXP]PISToolCall [[ch]]字段:期望[;...] [<timeout=N>]`

**可断言字段**（`PISToolCall`）:

| 字段名 | 说明 |
|--------|------|
| `type` | 类型 |
| `item_id` | 模型输入或输出 id |
| `tool_name` | 工具名（如 `get_weather`） |
| `tool_result` | 工具结果 JSON 字符串 |

**示例**:

```dsl
[EXP]PISToolCall tool_name:get_weather <timeout=10>
```

### Command `TSS`

**作用**: **TSS** 客户端专用回调池条目断言（当前配置仅 `wakeup_list`）。

**语法**: `[EXP]TSS [[ch]]字段:期望[;...] [<timeout=N>]`

**可断言字段**（`TSS`）:

| 字段名 | 说明 |
|--------|------|
| `wakeup_list` | `result` |

**示例**:

```dsl
[EXP]TSS wakeup_list:期望子串或结构 <timeout=5>
```

### Command `ECNR`

**作用**: **ECNR（ENR）** 降噪结果断言（VEC、音频 md5、RMS/SNR 等，与 `[ENR]ANALYZE_AUDIO_DATA` 写入数据一致）。

**语法**: `[EXP]ECNR [[ch]]字段:期望[;...] [<timeout=N>]`

**可断言字段**（`ECNR`）:

| 字段名 | 说明 |
|--------|------|
| `vec` | VEC 名称 |
| `md5` | 降噪后音频 md5 |
| `snr` | `rms.total_rms_dbfs`（总 RMS dBFS，配置键名 `snr`） |
| `maxRms` | `rms.max_rms_dbfs` |
| `minRms` | `rms.min_rms_dbfs` |
| `avgRms` | `rms.avg_rms_dbfs` |
| `peakAmplitude` | `rms.peak_amplitude` |

**示例**:

```dsl
[EXP]ECNR vec:dl_lexus410D_fm1388_vec_1mic_2ref_DL16Kto16K <timeout=5>
[EXP]ECNR snr:>20;maxRms:<10 <timeout=5>
```

### Command `FILEEXIT`

**作用**: 文件存在性断言

**语法**: `[EXP]FILEEXIT file_path [expected_exists]`

**参数说明**:
- `file_path`：文件路径（支持环境变量，如`{WORKPATH}`、`{WORKSPACE}`等）
- `expected_exists`：期望存在状态（`1`=存在，`0`=不存在，默认为`1`）

**示例**:
```dsl
# 断言文件存在
[EXP]FILEEXIT {WORKPATH}/lcs.zip 1
# 断言文件不存在
[EXP]FILEEXIT {WORKPATH}/temp.log 0
```

### Command `FILESIZE`

**作用**: 文件大小断言

**语法**: `[EXP]FILESIZE file_path operator expected_size`

**参数说明**:
- `file_path`：文件路径（支持环境变量）
- `operator`：比较操作符（`>`大于、`<`小于、`=`等于）
- `expected_size`：期望的文件大小（字节）

**示例**:
```dsl
# 断言文件大小大于1230字节
[EXP]FILESIZE {WORKPATH}/lcs.zip > 1230
# 断言文件大小小于300字节
[EXP]FILESIZE {WORKPATH}/small.txt < 300
```

### Command `FILEMD5`

**作用**: 文件MD5值断言

**语法**: `[EXP]FILEMD5 file_path = expected_md5`

**参数说明**:
- file_path：文件路径

**示例**:
```dsl
[EXP]FILEMD5 {WORKPATH}/lcs.zip = 19s3ms928skan203md
```

### Command `FILEDIF`

**作用**: 文件内容断言（JSON）

**语法**: `[EXP]FILEDIF JSON file_path json_path_expr`

**参数说明**:
- `file_path`：JSON文件路径（支持环境变量）
- `json_path_expr`：JSON路径表达式（格式：`path.to.field=expected_value`，支持数组索引）

**示例**:
```dsl
# 断言简单字段值
[EXP]FILEDIF JSON {WORKPATH}/config.json app.enabled=true
# 断言数组元素字段
[EXP]FILEDIF JSON {WORKPATH}/daemon_tag.json data.shsh[0].txt.status=0
```

### Command `LOG`

**作用**: 日志断言入口，支持 SEARCH、MATCH、DIFF 三种模式。

**语法**: `[EXP]LOG file mode args...`

**参数说明**:
- `file`：日志文件名或路径。
- `mode`：SEARCH、MATCH 或 DIFF。
- `args`：各模式对应的参数组合。

**示例**:
```dsl
[EXP]LOG app.log SEARCH "TagA" EXISTS
[EXP]LOG app.log MATCH "LoginSuccess" KV "user" == "admin"
[EXP]LOG app.log DIFF "Req" "Resp" < 500ms
```

### Command `SUM`

**作用**: 统计某类回调在指定通道内出现的次数，并进行数量断言。

**语法**: `[EXP]SUM [channel]callbackType COUNT operator value`

**参数说明**:
- `channel`：可选，支持单通道或多通道列表。
- `callbackType`：回调类型，如 ASRResult。
- `operator value`：数量比较条件，如 == 1。

**示例**:
```dsl
[EXP]SUM [0]ASRResult COUNT == 1
[EXP]SUM ASRResult COUNT == 1
```
