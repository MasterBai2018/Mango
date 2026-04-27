# NANO DSL指令说明文档

本文档详细介绍NANO测试套件支持的所有DSL指令，包括语法、参数、使用示例和底层接口对应关系。

## 📋 指令总览

NANO测试套件共支持**100+个DSL指令**，分为以下几大类：

| 分类 | 指令数量 | 支持客户端 | 说明 |
|------|----------|------------|------|
| 基础指令 | 8个 | TSA/SET/VOI/OMS/TTS/NIS/NSE/HWK | 客户端生命周期管理 |
| 引擎控制 | 7个 | TSA/SET/VOI/OMS/TTS/NIS/NSE/HWK | 引擎状态控制 |
| 系统设置 | 6个 | TSA/SET/VOI/OMS/TTS/NIS/NSE/HWK | 系统参数配置 |
| 录音功能 | 2个 | TSA/VOI/HWK | 录音控制 |
| 语音输入 | 2个 | TSA/VOI/HWK | 语音输入功能 |
| 声纹功能 | 12个 | TSA/SET/NIS/NSE/HWK | 声纹识别相关 |
| 配置状态 | 5个 | TSA/SET/OMS/NIS/NSE | 配置查询 |
| 日志功能 | 3个 | TSA/SET/VOI/HWK | 日志记录 |
| 引擎参数 | 10个 | TSA/SET/VOI/NIS/NSE/HWK | 引擎参数设置 |
| 系统操作 | 10个 | SYS | 系统级操作 |
| 断言验证 | 5个 | EXP | 结果断言（含文件断言） |
| SpeechEngine专用 | 15个 | HWK | SpeechEngine引擎专用指令 |
| PSTT专用 | 4个 | PST | PSTT ASR服务专用指令 |
| TiTan专用 | 3个 | TIA | TiTan ASR服务专用指令 |
| CarPlay专用 | 2个 | CPL | CarPlay SDK专用指令 |
| PISA专用 | 8个 | PIS | PISA 大模型全双工 WebSocket 客户端 |
| TSR专用 | 9个 | TSR | Suite级别统计和报告 |

## 🎮 基础指令 (8个)

### CREATE - 创建客户端引擎
**语法**: `[客户端]CREATE language appid [config_file]`

**参数说明**:
- `language`: 语言代码 (`cmn`=中文, `eng`=英文, `yue`=粤语)
- `appid`: 应用标识符
- `config_file`: 配置文件路径（可选）

**底层接口**: `aibs_create_engine()`

**使用示例**:
```dsl
[TSA]CREATE cmn com.autoai.vr.service_vrassistant
[TSA]CREATE eng com.autoai.vr.service_vrassistant {CONFIGPATH}
[SET]CREATE cmn com.pachira.set
```

### START - 启动会话
**语法**: `[客户端]START channel_num`

**参数说明**:
- `channel_num`: 音频通道数（通常为1，支持多通道）

**底层接口**: `aibs_start_engine()`

**使用示例**:
```dsl
[TSA]START 1    # 单通道启动
[TSA]START 4    # 四通道启动
```

### STOP - 停止会话
**语法**: `[客户端]STOP`

**底层接口**: `aibs_stop_engine()`

**使用示例**:
```dsl
[TSA]STOP
[SET]STOP
```

### FREE - 释放客户端资源
**语法**: `[客户端]FREE`

**底层接口**: `aibs_free_engine()`

**使用示例**:
```dsl
[TSA]FREE
[SET]FREE
```

### DATA - 发送音频数据
**语法**: `[客户端]DATA audio_path [named_parameters...]`

**支持的命名参数**:

- `frame`: 帧大小（默认320字节）
- `range`: 时间范围（格式：`[start,end]`，-1表示到结尾）
- `delay`: 延时比例（0.0=无延时，1.0=真实速度）

**底层接口**: `aibs_process_data()`

**使用示例**:

```dsl
# 基础用法
[TSA]DATA {WORKPATH}/audio/weather.wav

# 指定帧大小
[TSA]DATA audio/test.wav frame=640

# 时间范围（0-2.3秒）
[TSA]DATA audio/test.wav range=[0,2.3]

# 音频速度控制
[TSA]DATA audio/test.wav delay=0.5

# 组合参数
[TSA]DATA audio/test.wav frame=640 range=[1.5,3.0] delay=0.5
```

### TEXT_DATA - 文本转音频并发送
**语法**: `[客户端]TEXT_DATA text [lang=cmn|eng|...] [engine=auto|volcano|edge_tts|index_tts|voxCpm] [frame=320] [delay=0] [range=[0,-1]] [abstime=0|1]`

**参数说明**:
- `text`: 待合成文本（必填）；支持 `text=...` 形式，也支持直接写在命令开头
- `lang`: 语种（可选，不传则自动识别）
- `engine`: 合成引擎（可选，默认 `auto`）
- `frame`/`delay`/`range`/`abstime`: 与 `DATA` 指令同义，合成完成后透传到内部 `DATA`

**执行行为**:
- 先将文本合成为音频（命中缓存则直接复用缓存音频）
- 再自动构造并执行同客户端的 `DATA` 指令

**使用示例**:
```dsl
# 直接文本（自动语种 + 自动引擎）
[TSA]TEXT_DATA 今天天气怎么样

# 显式 text= + 指定语种/引擎
[TSA]TEXT_DATA text="turn on the radio" lang=eng engine=edge_tts

# 合成后按 DATA 参数送流
[TSA]TEXT_DATA text="打开音乐" lang=cmn frame=320 delay=1 range=[0,-1] abstime=0
```

### EVENT - 发送事件
**语法**: `[客户端]EVENT json_event_data`

**参数说明**:
- `json_event_data`: JSON格式的事件数据

**底层接口**: `aibs_set_event()`

**使用示例**:
```dsl
[TSA]EVENT {"source":"TSA","type":"SetFullTimeOption","data":{"value":1}}
[TSA]EVENT {"source":"TSA","type":"VehicleInfo","data":{"vin":"TEST123","brand":"Lexus-2S"}}
```

### CANCEL - 取消操作
**语法**: `[客户端]CANCEL`

**底层接口**: `aibs_cancel_engine()`

**使用示例**:

```dsl
[TSA]CANCEL
[VOI]CANCEL
```

## 🔧 引擎控制指令 (7个)

### PAUSE - 暂停引擎
**语法**: `[客户端]PAUSE`

**底层接口**: `aibs_pause_engine()`

**使用示例**:

```dsl
[TSA]PAUSE
```

### RESUME - 恢复引擎
**语法**: `[客户端]RESUME`

**底层接口**: `aibs_resume_engine()`

**使用示例**:

```dsl
[TSA]RESUME
```

### GET_VERSION - 获取版本信息
**语法**: `[客户端]GET_VERSION`

**底层接口**: `aibs_get_engine_version()`

**使用示例**:
```dsl
[TSA]GET_VERSION
[SET]GET_VERSION
```

### FREEWAKEUP - 设置识别/唤醒模式
**语法**: `[客户端]FREEWAKEUP status`

**参数说明**:

- `status`: 模式状态（0=唤醒模式，1=识别模式）

**底层接口**: `aibs_set_event()` (通过SetFreeWakeup事件)

**使用示例**:
```dsl
# 设置唤醒模式
[TSA]FREEWAKEUP 0
# 设置识别模式
[TSA]FREEWAKEUP 1
```

### PARALLELSR - 设置并行模式
**语法**: `[客户端]PARALLELSR status`

**参数说明**:

- `status`: 模式状态（0=独立音区，1=并行模式,2=全时模式）

**底层接口**: `aibs_set_event()` (通过SetParallelSR事件)

**使用示例**:
```dsl
# 设置独立音区
[TSA]PARALLELSR 0
# 设置并行模式
[TSA]PARALLELSR 1
# 设置全时模式
[TSA]PARALLELSR 2
```

### TEXT - 文本输入
**语法**: `[客户端]TEXT text`

**参数说明**:
- `text`: 传入理解的文本内容

**底层接口**: `aibs_set_event()` (通过SetText事件)

**使用示例**:
```dsl
# 将“今天天气怎么样”的文本传入给引擎
[TSA]TEXT 今天天气怎么样
```

### STRATEGY - 策略模式
**语法**: `[客户端]STRATEGY status`

**参数说明**:
- `status`: 模式状态（0=离线模式，1=在线模式，2=混合仲裁模式）

**底层接口**: `aibs_set_event()` (通过SetStrategy事件)

**使用示例**:
```dsl
# 设置离线模式
[TSA]STRATEGY 0
# 设置在线模式
[TSA]STRATEGY 1
# 设置混合仲裁模式
[TSA]STRATEGY 2
```

### SETVRCONFIG - 设置VR配置
**语法**: `[客户端]SETVRCONFIG config_name config_value [language]`

**参数说明**:
- `config_name`: 配置项名称（详见下表）
- `config_value`: 配置值
- `language`: 语言代码（可选，部分配置需要）

**底层接口**: `aibs_set_vr_config()`

**支持的配置项**:

| 配置项名称 | 对应代码 | 数据类型 | 说明 | 示例 |
|---|-----|---|------------------|------|
| `VR_OPTION` | 0x01 | int | TSA助手开关 | `[SET]SETVRCONFIG VR_OPTION 1` |
| `SHOW_STYLE` | 0x02 | int | 显示风格设置 | `[SET]SETVRCONFIG SHOW_STYLE 1` |
| `WAKEUP_ALIAS` | 0x03 | JSON | 唤醒词别名设置 | `[SET]SETVRCONFIG WAKEUP_ALIAS 你好小白 cmn` |
| `DIALOGUE_STYLE` | 0x04 | int | 全时模式设置 | `[SET]SETVRCONFIG DIALOGUE_STYLE 1` |
| `DIALOGUE_LANGUAGE` | 0x05 | JSON | 语种设置 | `[SET]SETVRCONFIG DIALOGUE_LANGUAGE cmn/eng` |
| `SOUND_AREA_OPTION` | 0x06 | int | 音区设置 | `[SET]SETVRCONFIG SOUND_AREA_OPTION 1` |
| `WAKEUP_KEYWORD_OPTION` | 0x07 | int | 场景唤醒词开关 | `[SET]SETVRCONFIG WAKEUP_KEYWORD_OPTION 1` |
| `VOICE_WAKEUP_OPTION` | 0x08 | int | 语音唤醒开关 | `[SET]SETVRCONFIG VOICE_WAKEUP_OPTION 1` |
| `WAKEUP_ENABLE` | 0x09 | JSON | 唤醒词生效设置 | `[SET]SETVRCONFIG WAKEUP_ENABLE 你好丰田 cmn` |
| `SET_TTS_VOICE_TYPE` | 0x11 | string | TTS音色设置 | `[SET]SETVRCONFIG SET_TTS_VOICE_TYPE female` |
| `MULTI_DIALOGUE` | 0x12 | int | 多人对话设置 | `[SET]SETVRCONFIG MULTI_DIALOGUE 1` |
| `EXPERIENCE_IMPROVENMENT` | 0x13 | int | 用户体验改善计划 | `[SET]SETVRCONFIG EXPERIENCE_IMPROVENMENT 1` |
| `PERSONAL_SENSITIVE_AUTHORIZATION` | 0x14 | int | 个性化交互敏感信息授权 | `[SET]SETVRCONFIG PERSONAL_SENSITIVE_AUTHORIZATION 1` |
| `VOICE_SENSITIVE_AUTHORIZATION` | 0x15 | int | 声音敏感信息授权 | `[SET]SETVRCONFIG VOICE_SENSITIVE_AUTHORIZATION 1` |
| `ACTIVE_INTERACTION` | 0x17 | JSON | 主动交互列表 | `[SET]SETVRCONFIG ACTIVE_INTERACTION true cmn` |
| `SRE_SENSITIVE_EMPOWER_OPTION` | 0x18 | int | 声纹隐私设置开关 | `[SET]SETVRCONFIG SRE_SENSITIVE_EMPOWER_OPTION 1` |
| `SRE_FUNC_ENABLE_OPTION` | 0x19 | int | 声纹功能使能开关 | `[SET]SETVRCONFIG SRE_FUNC_ENABLE_OPTION 1` |
| `SERVER_CACHE_LANGUAGE` | 0x20 | string | 缓存语种修改 | `[SET]SETVRCONFIG SERVER_CACHE_LANGUAGE cmn` |
| `GPT_ENABLE_OPTION` | 0x21 | int | GPT功能开关 | `[SET]SETVRCONFIG GPT_ENABLE_OPTION 1` |
| `SRE_MEMORY` | 0x22 | int | 声纹记忆开关 | `[SET]SETVRCONFIG SRE_MEMORY 1` |
| `VEHICLE_MEMORY` | 0x23 | int | 车辆记忆开关 | `[SET]SETVRCONFIG VEHICLE_MEMORY 1` |

**使用示例**:
```dsl
# 设置唤醒词别名
[SET]SETVRCONFIG WAKEUP_ALIAS 你好小白 cmn
# 设置主动交互
[SET]SETVRCONFIG ACTIVE_INTERACTION true cmn  
# 设置VR选项
[SET]SETVRCONFIG VR_OPTION 1
```

## ⚙️ 系统设置指令 (6个)

### CAR_TYPE - 设置车型信息
**语法**: `[客户端]CAR_TYPE car_type_json`

**参数说明**:
- `car_type_json`: JSON格式的车型信息

**底层接口**: `aibs_set_car_type()`

**使用示例**:
```dsl
[TSA]CAR_TYPE {"brand":"0","device_name":"test_device"}
[TSA]CAR_TYPE {"brand":"Lexus-2S"}
```

### LOG_PATH - 设置日志路径
**语法**: `[客户端]LOG_PATH log_path`

**底层接口**: `aibs_client_set_log_path()`

**使用示例**:
```dsl
[TSA]LOG_PATH {LOGPATH}
[SET]LOG_PATH /tmp/logs
```

### MIC_STATUS - 设置麦克风状态
**语法**: `[客户端]MIC_STATUS status`

**参数说明**:
- `status`: 麦克风状态（0=关闭，1=开启）

**底层接口**: `aibs_set_mic_status()`

**使用示例**:
```dsl
[TSA]MIC_STATUS 1   # 开启麦克风
[TSA]MIC_STATUS 0   # 关闭麦克风
```

### VR_STATUS - 设置VR状态
**语法**: `[客户端]VR_STATUS status`

**参数说明**:
- `status`: VR状态（0=关闭，1=开启）

**底层接口**: `aibs_set_vr_status()`

**使用示例**:
```dsl
[TSA]VR_STATUS 1    # 开启VR
[TSA]VR_STATUS 0    # 关闭VR
```

### LINK_TYPE - 设置连接类型
**语法**: `[客户端]LINK_TYPE link_type`

**参数说明**:
- `link_type`: 连接类型代码（详见下表）

**底层接口**: `aibs_set_link_type()`

**支持的连接类型**:

| 连接类型 | 代码值 | 说明 |
|----------|--------|------|
| `NONE` | 0 | 无连接 |
| `CARPLAY` | 1 | CarPlay连接 |
| `HICAR` | 2 | CarLife连接 |
| `CARLIFE` | 3 | HiCar连接 |

**使用示例**:
```dsl
[SET]LINK_TYPE 0      # 设置为无连接
[SET]LINK_TYPE 1      # 设置为CarPlay连接
[SET]LINK_TYPE 2      # 设置为CarLife连接
[SET]LINK_TYPE 3      # 设置为HiCar连接
```

### VREVENT - 设置VR事件
**语法**: `[客户端]VREVENT event_data`

**底层接口**: `aibs_set_vr_event()`

**使用示例**:
```dsl
[TSA]VREVENT event_123
```

## 🎙️ 录音功能指令 (2个)

### START_RECORD - 开始录音
**语法**: `[客户端]START_RECORD record_path`

**参数说明**:
- `record_path`: 录音文件保存路径

**底层接口**: `aibs_start_record()`

**使用示例**:
```dsl
[TSA]START_RECORD {WORKPATH}/record/test.wav
[VOI]START_RECORD /tmp/voice_input.wav
```

### STOP_RECORD - 停止录音
**语法**: `[客户端]STOP_RECORD`

**底层接口**: `aibs_client_stop_record()`

**使用示例**:
```dsl
[TSA]STOP_RECORD
[VOI]STOP_RECORD
```

## 🗣️ 语音输入指令 (2个)

### OPEN_VOICE_INPUT - 开启语音输入
**语法**: `[客户端]OPEN_VOICE_INPUT param`

**参数说明**:
- `param`: 语音输入参数设置（JSON格式字符串或配置参数）

**底层接口**: `aibs_open_voice_input()`

**使用示例**:
```dsl
[TSA]OPEN_VOICE_INPUT {"mode":0,"channel":0}
[VOI]OPEN_VOICE_INPUT voice_input_config
```

### CLOSE_VOICE_INPUT - 关闭语音输入
**语法**: `[客户端]CLOSE_VOICE_INPUT`

**底层接口**: `aibs_client_close_voice_input()`

**使用示例**:
```dsl
[TSA]CLOSE_VOICE_INPUT
[VOI]CLOSE_VOICE_INPUT
```

## 🎤 声纹功能指令 (12个)

### START_SPEAKER_ENROLL - 开始声纹注册
**语法**: `[客户端]START_SPEAKER_ENROLL user_id text id channel_id`

**参数说明**:
- `user_id`: 用户ID字符串
- `text`: 注册文本内容
- `id`: 当前注册次数编号
- `channel_id`: 音频通道ID

**底层接口**: `aibs_start_speaker_enroll()`

**使用示例**:
```dsl
# 用户user001第1次注册，使用通道0
[SET]START_SPEAKER_ENROLL user001 你好雷克萨斯，登录我的个人中心 1 0
# 用户admin第3次注册，使用通道0  
[SET]START_SPEAKER_ENROLL admin 测试文本内容 3 0
```

### END_SPEAKER_ENROLL - 结束声纹注册
**语法**: `[客户端]END_SPEAKER_ENROLL`

**底层接口**: `aibs_client_end_speaker_enroll()`

**使用示例**:
```dsl
[TSA]END_SPEAKER_ENROLL
[SET]END_SPEAKER_ENROLL
```

### RECOGNIZE_SPEAKER - 声纹登录时系统调用接口
**语法**: `[VOI客户端]RECOGNIZE_SPEAKER channel_id start end`

**参数说明**:
- `channel_id`: 发话的音区
- `start`: 发话开始时间
- `end`: 发话结束时间

**底层接口**: `aibs_client_recognize_speaker()`

**使用示例**:
```dsl
[VOI]RECOGNIZE_SPEAKER 0 1230 3456
[VOI]RECOGNIZE_SPEAKER 1 3420 9203
```

### VOICEPRINT_LOGIN - 声纹登录
**语法**: `[客户端]VOICEPRINT_LOGIN audio_path [frame_size] [delay]`

**参数说明**:
- `audio_path`: 音频文件路径（必需）
- `frame_size`: 帧大小，默认320（可选）
- `delay`: 延时比例，默认0.0（可选）

**功能说明**:
- 发送音频数据进行声纹登录识别
- 自动等待回调事件（超时10秒）
- 如果识别成功且意图为"login"，则自动调用 `recognize_speaker` 识别用户
- 返回识别到的用户ID，失败返回None

**底层接口**: `voiceprint_login()`

**使用示例**:
```dsl
# 使用默认参数
[SET]VOICEPRINT_LOGIN {WORKPATH}/audio/login.wav

# 指定帧大小
[SET]VOICEPRINT_LOGIN {WORKPATH}/audio/login.wav 320

# 指定帧大小和延时
[SET]VOICEPRINT_LOGIN {WORKPATH}/audio/login.wav 320 0.0
```

### VERIFY_VOICEPRINT - 声纹验证
**语法**: `[客户端]VERIFY_VOICEPRINT user_id verify_text timeout_seconds`

**参数说明**:
- `user_id`: 要验证的用户ID
- `verify_text`: 验证文本
- `timeout_seconds`: 超时时间

**底层接口**: `aibs_client_verify_voiceprint()`

**使用示例**:
```dsl
[TSA]VERIFY_VOICEPRINT user001 你好小白 0
[SET]VERIFY_VOICEPRINT admin 验证文本 5
```

### CANCEL_VERIFY_VOICEPRINT - 取消声纹验证
**语法**: `[客户端]CANCEL_VERIFY_VOICEPRINT`

**底层接口**: `aibs_client_cancel_verify_voiceprint()`

**使用示例**:
```dsl
[TSA]CANCEL_VERIFY_VOICEPRINT
[SET]CANCEL_VERIFY_VOICEPRINT
```

### DELETE_SPEAKER - 删除声纹
**语法**: `[客户端]DELETE_SPEAKER user_id`

**参数说明**:
- `user_id`: 要删除的用户ID

**底层接口**: `aibs_client_delete_speaker()`

**使用示例**:
```dsl
[TSA]DELETE_SPEAKER user001
[SET]DELETE_SPEAKER test_user
```

### GET_SPEAKER_INFO - 获取声纹信息
**语法**: `[客户端]GET_SPEAKER_INFO user_id`

**参数说明**:
- `user_id`: 用户ID

**底层接口**: `aibs_client_get_speaker_info()`

**使用示例**:
```dsl
[TSA]GET_SPEAKER_INFO user001
[SET]GET_SPEAKER_INFO admin
```

### GET_SPEAKERS - 获取已注册声纹列表
**语法**: `[客户端]GET_SPEAKERS`

**底层接口**: `aibs_client_get_registered_speakers()`

**使用示例**:
```dsl
[TSA]GET_SPEAKERS
[SET]GET_SPEAKERS
```

### GET_ENROLL_TEXT - 获取注册文本
**语法**: `[客户端]GET_ENROLL_TEXT`

**底层接口**: `aibs_client_get_enroll_text()`

**使用示例**:
```dsl
[TSA]GET_ENROLL_TEXT
[VOI]GET_ENROLL_TEXT
```

### SENSITIVE_WORD_CHECK - 敏感词检测
**语法**: `[客户端]SENSITIVE_WORD_CHECK text`

**参数说明**:
- `text`: 要检测的文本

**底层接口**: `aibs_client_sensitive_word_check()`

**使用示例**:
```dsl
[TSA]SENSITIVE_WORD_CHECK 测试文本内容
[SET]SENSITIVE_WORD_CHECK 需要检查的语句
```

### REGISTER_VOICEPRINT_LIST - 批量注册声纹
**语法**: `[客户端]REGISTER_VOICEPRINT_LIST sre_user_files`

**参数说明**:
- `sre_user_files`: 声纹注册的用户列表，可以支持多个userid，按照userid分组

**数据格式**:
注册列表为JSON数组，每个元素包含以下字段：
- `audio_path`: 音频文件路径（支持环境变量）
- `user_id`: 用户ID字符串
- `text`: 注册文本内容
- `id`: 当前注册次数编号（整数）
- `channel_id`: 音频通道ID（整数）

**功能说明**:
- 批量注册多个用户的声纹信息，自动完成多次注册流程
- 会自动调用START_SPEAKER_ENROLL、DATA和END_SPEAKER_ENROLL接口

**底层接口**: `register_voiceprint_list()`

**使用示例**:
```dsl
# 方式1: 从JSON文件读取（推荐）
[SET]REGISTER_VOICEPRINT_LIST TestCase/caselist/haijin_female.txt

# 参数文件示例:
TestAudio/vp_multi_channel/haijin/zhu/66_你好小悦登录我的个人中心.wav	text:你好小悦，登录我的个人中心;channel:0;user_id:haijin;index:1
TestAudio/vp_multi_channel/haijin/zhu/71_你好小悦登录我的声纹记忆.wav	text:你好小悦，登录我的声纹记忆;channel:0;user_id:haijin;index:2
TestAudio/vp_multi_channel/haijin/zhu/77_你好小悦我要登录声纹账号.wav	text:你好小悦，我要登录声纹账号;channel:0;user_id:haijin;index:3
TestAudio/vp_multi_channel/haijin/zhu/84_你好小悦我要登录个人中心.wav	text:你好小悦，我要登录个人中心;channel:0;user_id:haijin;index:4
TestAudio/vp_multi_channel/haijin/zhu/86_你好小悦声纹登录个人中心.wav	text:你好小悦，声纹登录个人中心;channel:0;user_id:haijin;index:5


TestAudio/vp_multi_channel/haijin/zhu/66_你好小悦登录我的个人中心.wav	text:你好小悦，登录我的个人中心;channel:0;user_id:mingming;index:1
TestAudio/vp_multi_channel/haijin/zhu/71_你好小悦登录我的声纹记忆.wav	text:你好小悦，登录我的声纹记忆;channel:0;user_id:mingming;index:2
TestAudio/vp_multi_channel/haijin/zhu/77_你好小悦我要登录声纹账号.wav	text:你好小悦，我要登录声纹账号;channel:0;user_id:mingming;index:3
TestAudio/vp_multi_channel/haijin/zhu/84_你好小悦我要登录个人中心.wav	text:你好小悦，我要登录个人中心;channel:0;user_id:mingming;index:4
TestAudio/vp_multi_channel/haijin/zhu/86_你好小悦声纹登录个人中心.wav	text:你好小悦，声纹登录个人中心;channel:0;user_id:mingming;index:5


```

**注意事项**:
- 注册列表必须包含至少一个用户信息
- 每个用户信息必须包含所有必需的字段

## 📊 配置和状态指令 (5个)

### CLEAR_VR_CONFIG - 清除VR配置
**语法**: `[客户端]CLEAR_VR_CONFIG`

**底层接口**: `aibs_client_clear_vr_config()`

**使用示例**:
```dsl
[TSA]CLEAR_VR_CONFIG
[SET]CLEAR_VR_CONFIG
```

### GET_CONFIG_ITEM - 获取配置项
**语法**: `[客户端]GET_CONFIG_ITEM config_file config_key`

**参数说明**:
- `config_file`: 配置文件路径
- `config_key`: 配置键名

**底层接口**: `aibs_client_get_config_item()`

**使用示例**:
```dsl
[TSA]GET_CONFIG_ITEM {CONFIGPATH} debug_mode
[SET]GET_CONFIG_ITEM /tmp/config.conf language
```

### GET_FOTA_STATUS - 获取FOTA状态
**语法**: `[客户端]GET_FOTA_STATUS`

**底层接口**: `aibs_client_get_fota_status()`

**使用示例**:
```dsl
[TSA]GET_FOTA_STATUS
[OMS]GET_FOTA_STATUS
```

### GET_VR_CONFIG - 获取VR配置
**语法**: `[客户端]GET_VR_CONFIG config_name`

**参数说明**:
- `config_name`: 配置项名称

**底层接口**: `aibs_client_get_vr_config()`

**使用示例**:
```dsl
[TSA]GET_VR_CONFIG VR_OPTION
[SET]GET_VR_CONFIG WAKEUP_ALIAS
```

### GET_WAKEUP_WORD - 获取唤醒词
**语法**: `[客户端]GET_WAKEUP_WORD`

**底层接口**: `aibs_client_get_wakeup_word()`

**使用示例**:
```dsl
[TSA]GET_WAKEUP_WORD
[SET]GET_WAKEUP_WORD
```

## 📝 日志功能指令 (3个)

### WRITE_LOG - 写入日志
**语法**: `[客户端]WRITE_LOG log_path tag message log_level`

**参数说明**:
- `log_path`: 日志文件路径
- `tag`: 日志标签
- `message`: 日志消息
- `log_level`: 日志级别（1-5）

**底层接口**: `aibs_client_write_log()`

**使用示例**:
```dsl
[TSA]WRITE_LOG {LOGPATH}/test.log NANO 测试开始 1
[SET]WRITE_LOG /tmp/debug.log DEBUG 调试信息 2
```

### CONFIG_VOICELOG - 配置语音日志
**语法**: `[客户端]CONFIG_VOICELOG enable log_level`

**参数说明**:
- `enable`: 是否启用（true/false）
- `log_level`: 日志级别

**底层接口**: `aibs_client_config_voicelog()`

**使用示例**:
```dsl
[TSA]CONFIG_VOICELOG true 1
[SET]CONFIG_VOICELOG false 0
```

### SET_VOICELOG_PATH - 设置语音日志路径
**语法**: `[客户端]SET_VOICELOG_PATH log_path`

**参数说明**:
- `log_path`: 语音日志保存路径

**底层接口**: `aibs_client_set_voicelog_path()`

**使用示例**:
```dsl
[TSA]SET_VOICELOG_PATH {LOGPATH}/voicelog/
[SET]SET_VOICELOG_PATH /tmp/voice_logs/
```

## 🔧 引擎参数指令 (10个)

### SET_PARAM - 设置引擎参数
**语法**: `[客户端]SET_PARAM param_name param_value`

**参数说明**:
- `param_name`: 参数名称（详见下表）
- `param_value`: 参数值（支持int、float、string、bool类型）

**底层接口**: `set_aibs_param()`

**支持的引擎参数**:

| 参数名称 | 代码值 | 数据类型 | 说明 | 示例 |
|---------|--------|----------|------|------|
| `AIBS_PARAM_SESSION_LINK_TYPE` | 0x01 | int | 会话连接类型 | `[TSA]SET_PARAM AIBS_PARAM_SESSION_LINK_TYPE 1` |
| `AIBS_PARAM_SEAT_SIGNAL` | 0x02 | int | 座椅信号 | `[TSA]SET_PARAM AIBS_PARAM_SEAT_SIGNAL 1` |
| `AIBS_PARAM_FULL_VEHICLE_SPEECH` | 0x03 | int | 全车语音 | `[TSA]SET_PARAM AIBS_PARAM_FULL_VEHICLE_SPEECH 1` |
| `AIBS_PARAM_REAL_TIME_RESULT` | 0x04 | int | 实时结果开关 | `[TSA]SET_PARAM AIBS_PARAM_REAL_TIME_RESULT 1` |
| `AIBS_PARAM_PUNC_RESULT` | 0x05 | int | 标点符号结果 | `[TSA]SET_PARAM AIBS_PARAM_PUNC_RESULT 1` |
| `AIBS_PARAM_DIGIT_CONVERT_RESULT` | 0x06 | int | 数字转换结果 | `[TSA]SET_PARAM AIBS_PARAM_DIGIT_CONVERT_RESULT 1` |
| `AIBS_PARAM_SILENCE_DURATION` | 0x07 | int | 静音检测时长(ms) | `[TSA]SET_PARAM AIBS_PARAM_SILENCE_DURATION 5000` |
| `AIBS_PARAM_SILENCE_TIMEOUT` | 0x08 | int | 静音超时时长(ms) | `[TSA]SET_PARAM AIBS_PARAM_SILENCE_TIMEOUT 8000` |
| `AIBS_PARAM_SPEECH_TIMEOUT` | 0x09 | int | 语音超时时长(ms) | `[TSA]SET_PARAM AIBS_PARAM_SPEECH_TIMEOUT 15000` |
| `AIBS_PARAM_SCENAROI_NAME` | 0x0A | string | 场景名称 | `[TSA]SET_PARAM AIBS_PARAM_SCENAROI_NAME navigation` |
| `AIBS_PARAM_WAKEUP_SCENE` | 0x0B | int | 唤醒场景 | `[TSA]SET_PARAM AIBS_PARAM_WAKEUP_SCENE 1` |
| `AIBS_PARAM_WAKEUP_DELAY_ONESHOT_DURATION` | 0x0C | int | 唤醒延迟单次时长 | `[TSA]SET_PARAM AIBS_PARAM_WAKEUP_DELAY_ONESHOT_DURATION 3000` |
| `AIBS_PARAM_SOUND_EVENT_OPTION` | 0x0D | int | 声音事件选项 | `[TSA]SET_PARAM AIBS_PARAM_SOUND_EVENT_OPTION 1` |
| `AIBS_PARAM_DISABLE_BUTTON_WAKEUP` | 0x0E | int | 禁用按键唤醒 | `[TSA]SET_PARAM AIBS_PARAM_DISABLE_BUTTON_WAKEUP 0` |
| `AIBS_PARAM_EMOTION_OPTION` | 0x0F | int | 情感选项 | `[TSA]SET_PARAM AIBS_PARAM_EMOTION_OPTION 1` |
| `AIBS_PARAM_SR_PTT_OPTION` | 0x10 | int | 语音识别PTT选项 | `[TSA]SET_PARAM AIBS_PARAM_SR_PTT_OPTION 1` |
| `AIBS_PARAM_SR_VOICE_WAKEUP` | 0x12 | int | 声纹唤醒开关 | `[SET]SET_PARAM AIBS_PARAM_SR_VOICE_WAKEUP 1` |
| `AIBS_PARAM_SR_WAKEUP_SCENE_ENABLE` | 0x14 | int | 语音唤醒场景使能 | `[TSA]SET_PARAM AIBS_PARAM_SR_WAKEUP_SCENE_ENABLE 1` |
| `AIBS_PARAM_SR_AUDIO_SPECTRAL` | 0x15 | int | 声音能量获取开关 | `[TSA]SET_PARAM AIBS_PARAM_SR_AUDIO_SPECTRAL 1` |
| `AIBS_PARAM_SR_RECORD_DEVICE_STATE` | 0x16 | int | 录音设备状态获取开关 | `[TSA]SET_PARAM AIBS_PARAM_SR_RECORD_DEVICE_STATE 1` |

**使用示例**:
```dsl
# 设置静音检测时长为5秒
[TSA]SET_PARAM AIBS_PARAM_SILENCE_DURATION 5000
# 开启实时结果
[TSA]SET_PARAM AIBS_PARAM_REAL_TIME_RESULT 1
# 关闭声纹唤醒
[SET]SET_PARAM AIBS_PARAM_SR_VOICE_WAKEUP 0
# 设置场景名称
[TSA]SET_PARAM AIBS_PARAM_SCENAROI_NAME music_scene
```

### UPDATE_PERSONALIZED - 更新个性化信息
**语法**: `[客户端]UPDATE_PERSONALIZED personalized_info`

**参数说明**:
- `personalized_info`: 个性化信息数据

**底层接口**: `aibs_client_update_personalized_info()`

**使用示例**:
```dsl
[TSA]UPDATE_PERSONALIZED {"user":"admin","preferences":"music"}
```

### SET_TTS_STATE - 设置TTS状态
**语法**: `[客户端]SET_TTS_STATE state`

**参数说明**:
- `state`: TTS状态（true/false）

**底层接口**: `aibs_client_set_tts_state()`

**使用示例**:
```dsl
[TSA]SET_TTS_STATE true
[SET]SET_TTS_STATE false
```

### SET_PAGE_INTENT - 设置页面意图
**语法**: `[客户端]SET_PAGE_INTENT intent_info`

**参数说明**:
- `intent_info`: 页面意图信息

**底层接口**: `aibs_client_set_page_intent()`

**使用示例**:
```dsl
[TSA]SET_PAGE_INTENT {"page":"music","intent":"play"}
```

### SET_LANGUAGE_MODE - 设置语言模式
**语法**: `[客户端]SET_LANGUAGE_MODE language`

**参数说明**:

- `language`: 语言代码（cmn/eng/yue）

**底层接口**: `aibs_client_set_language_mode()`

**使用示例**:

```dsl
[TSA]SET_LANGUAGE_MODE cmn
[SET]SET_LANGUAGE_MODE eng
[VOI]SET_LANGUAGE_MODE yue
```

### SET_WAKEUP_WORD - 设置唤醒词
**语法**: `[客户端]SET_WAKEUP_WORD wakeup_word threshold`

**参数说明**:
- `wakeup_word`: 唤醒词内容
- `threshold`: 阈值（0.0-1.0）

**底层接口**: `aibs_client_set_wakeup_word()`

**使用示例**:
```dsl
[TSA]SET_WAKEUP_WORD 你好小白 0.8
[SET]SET_WAKEUP_WORD Hello 0.7
```

### SET_WAKEUP_ENABLE - 设置唤醒词启用状态
**语法**: `[客户端]SET_WAKEUP_ENABLE wakeup_word enable`

**参数说明**:
- `wakeup_word`: 唤醒词内容
- `enable`: 是否启用（true/false）

**底层接口**: `aibs_client_set_wakeup_word_enable()`

**使用示例**:
```dsl
[TSA]SET_WAKEUP_ENABLE 你好小白 true
[SET]SET_WAKEUP_ENABLE Hello false
```

### SET_WORKMODE - 设置工作模式
**语法**: `[客户端]SET_WORKMODE mode`

**常用模式**:
- `WAKEUP_ASR`: 唤醒+ASR模式
- `ASR_ONLY`: 仅ASR模式
- `WAKEUP_ONLY`: 仅唤醒模式

**底层接口**: `aibs_client_set_workmode()`

**使用示例**:
```dsl
[TSA]SET_WORKMODE WAKEUP_ASR
[SET]SET_WORKMODE ASR_ONLY
```

## 🖥️ 系统操作指令 (9个)

### PULL - 拉起服务
**语法**: `[SYS]PULL service_name language [car_type]`

**支持的服务**:
- `LCSEngine`: LCS语音处理引擎
- `SpeechEngine`: 语音识别引擎
- `AIBSServer`: AIBS服务器

**参数说明**:
- `service_name`: 服务名称
- `language`: 语言代码
- `car_type`: 车型信息（JSON格式，仅AIBSServer需要）

**使用示例**:
```dsl
[SYS]PULL LCSEngine cmn
[SYS]PULL SpeechEngine cmn
[SYS]PULL AIBSServer cmn {"brand":"0"}
```

### KILL - 终止服务
**语法**: `[SYS]KILL service_name`

**使用示例**:
```dsl
[SYS]KILL LCSEngine
[SYS]KILL SpeechEngine  
[SYS]KILL AIBSServer
```

### SLEEP - 睡眠等待
**语法**: `[SYS]SLEEP seconds`

**参数说明**:

- `seconds`: 睡眠时间（秒）

**使用示例**:
```dsl
[SYS]SLEEP 2        # 等待2秒
[SYS]SLEEP 0.5      # 等待0.5秒
```

### CMD - 执行系统命令
**语法**: `[SYS]CMD command`

**参数说明**:
- `command`: 要执行的系统命令

**使用示例**:
```dsl
[SYS]CMD mkdir -p {WORKPATH}/output
[SYS]CMD cp {CONFIGPATH} {WORKPATH}/backup.conf
[SYS]CMD echo "测试开始" > {LOGPATH}/test.log
```

### PRINT - 打印消息
**语法**: `[SYS]PRINT message`

**参数说明**:
- `message`: 要打印的消息内容

**使用示例**:

```dsl
[SYS]PRINT === 测试开始 ===
[SYS]PRINT 当前Suite: {SUITENAME}
[SYS]PRINT 工作目录: {WORKPATH}
```

### ENV - 设置环境变量
**语法**: `[SYS]ENV key=value`

**参数说明**:
- `key`: 环境变量名称
- `value`: 环境变量值（支持包含`=`号的值；支持双引号`"`或单引号`'`包裹，外层引号会被自动去除）

**功能说明**:
- 设置系统环境变量，子进程可通过 `getenv()` 获取
- 环境变量会被后续 `[SYS]PULL` 拉起的服务进程继承

**使用示例**:
```dsl
# 设置简单环境变量
[SYS]ENV ro.vendor-iauto.unityversion=313

# 设置路径类型环境变量
[SYS]ENV MY_CONFIG_PATH=/data/test/config

# 使用双引号包裹含空格或特殊字符的 value
[SYS]ENV MY_PATH="/data/test/config path"

# 使用单引号包裹
[SYS]ENV MY_CONFIG='key=value&other=123'
```

**注意事项**:
- 环境变量需要在 `[SYS]PULL` 拉起服务**之前**设置，否则子进程无法获取
- C++ 侧需使用 `getenv("key")` 获取
- key 不能为空，value 可以为空字符串
- value 若用双引号或单引号包裹，执行时会自动去除外层引号

### UPLOAD - 更新文件内容
**语法**: `[SYS]UPLOAD upload_type file_path [params...]`

**参数说明**:
- `upload_type`: 上传类型（JSON、LINE、REPLACE、DELETE）
- `file_path`: 目标文件路径（支持环境变量）
- `params`: 根据类型不同的额外参数

**支持的三种类型**:

#### 1. JSON类型 - 更新JSON文件字段
**语法**: `[SYS]UPLOAD JSON file_path field_path new_value`

**参数说明**:
- `file_path`: JSON文件路径
- `field_path`: 字段路径，支持嵌套路径和数组索引
  - 嵌套路径: `data.text.start`
  - 数组索引: `data.[0].text.start`
- `new_value`: 新值，支持字符串、数字、布尔值等，自动类型转换

**类型转换规则**:
- 数字字符串自动转换为int或float
- "true"/"false"、"yes"/"no"、"1"/"0"转换为布尔值
- 其他保持为字符串

**使用示例**:
```dsl
# 更新嵌套字段（数字）
[SYS]UPLOAD JSON {WORKPATH}/daemon_tag.json data.text.start 320

# 更新嵌套字段（字符串）
[SYS]UPLOAD JSON {WORKPATH}/config.json app.name "MyApp"

# 更新数组元素字段
[SYS]UPLOAD JSON {WORKPATH}/config.json data.[0].text.start 320

# 更新布尔值字段
[SYS]UPLOAD JSON {WORKPATH}/config.json app.enabled true

# 更新浮点数字段
[SYS]UPLOAD JSON {WORKPATH}/config.json threshold 0.85
```

#### 2. LINE类型 - 更新配置文件行
**语法**: `[SYS]UPLOAD LINE file_path key new_value`

**参数说明**:
- `file_path`: 配置文件路径
- `key`: 配置项的键名（用于匹配行）
- `new_value`: 新值，支持字符串和数字，自动类型转换

**匹配规则**:
- 支持 `=` 和 `:` 分隔符
- 保持原有格式（缩进、注释等）
- 自动匹配包含键名的行

**使用示例**:
```dsl
# 更新数字配置
[SYS]UPLOAD LINE {WORKPATH}/decoder.conf ASK_SIL_DURATION 540

# 更新字符串配置
[SYS]UPLOAD LINE {WORKPATH}/decoder.conf LANGUAGE cmn

# 更新布尔值配置
[SYS]UPLOAD LINE {WORKPATH}/config.conf DEBUG_MODE true
```

#### 3. REPLACE类型 - 全局字符串替换
**语法**: `[SYS]UPLOAD REPLACE file_path old_value new_value`

**参数说明**:
- `file_path`: 目标文件路径
- `old_value`: 要替换的旧字符串
- `new_value`: 替换后的新字符串

**使用示例**:
```dsl
# 全局字符串替换
[SYS]UPLOAD REPLACE {WORKPATH}/decoder.conf AAA BBB

# 替换路径
[SYS]UPLOAD REPLACE {WORKPATH}/config.conf /old/path /new/path

# 替换配置值
[SYS]UPLOAD REPLACE {WORKPATH}/template.conf PLACEHOLDER actual_value
```

#### 4. DELETE类型 - 删除某个配置项
**语法**: `[SYS]UPLOAD DELETE {CONFIGPATH} key1`

**参数说明**:
- `{CONFIGPATH}`: 目标配置文件路径
- `key1`: 配置项Key

**使用示例**:
```dsl
# 删除某个key的配置项
[SYS]UPLOAD DELETE {CONFIGPATH} FREETALK_TIMEOUT
```

**注意事项**:
- JSON类型：文件必须是有效的JSON格式，路径必须存在
- LINE类型：如果键名不存在，会记录警告但不添加新行
- REPLACE类型：替换所有出现的字符串，包括注释和配置值
- DELETE类型：仅支持删除配置文件，如果文件中原本不存在该Key，则跳过，如果存在重复Key，则报错

### ALLURE - 添加Allure报告附件
**语法**: `[SYS]ALLURE attachment_type file_path`

**参数说明**:
- `attachment_type`: 附件类型（TEXT、CSV、JSON等）
- `file_path`: 要添加的文件路径（支持环境变量）

**支持的附件类型**:
- `TEXT`: 文本类型附件
- `CSV`: CSV表格类型附件
- `JSON`: JSON数据类型附件（自动识别）
- 其他类型默认按TEXT处理

**使用示例**:
```dsl
# 添加配置文件到报告（TEXT类型）
[SYS]ALLURE TEXT {WORKPATH}/decoder.conf

# 添加CSV报告到Allure
[SYS]ALLURE CSV {WORKPATH}/asr_report.csv

# 添加JSON配置文件到报告
[SYS]ALLURE JSON {WORKPATH}/config.json

# 添加日志文件到报告
[SYS]ALLURE TEXT {LOGPATH}/test.log
```

**应用场景**:
- 将测试过程中修改的配置文件添加到报告，便于问题追踪
- 将测试结果文件（CSV、日志等）添加到报告，便于结果分析
- 将关键的中间数据文件保存到报告中

### FOTA_RANDOM_ZIP - FOTA动态压缩包支持
**语法**: `[SYS]FOTA_RANDOM_ZIP source_dir target_zip count [zip_root] [mode]`

**参数说明**:
- `source_dir`: 源目录路径（支持环境变量）
- `target_zip`: 目标zip文件路径（支持环境变量）
- `count`: 随机选取的文件数量（整数）
- `zip_root`: zip包内的根目录名（可选，`None`或`.`表示无根目录）
- `mode`: 打包模式（可选，默认为`normal`）
  - `normal`: 普通模式，从源目录随机选取文件
  - `lcs`: LCS模式，仅从`TSAPResource`目录选取文件，并自动生成`checksum.list`文件

**功能说明**:
- 从指定源目录中随机选取指定数量的文件，打包成zip压缩包
- 支持设置zip包内的根目录结构
- LCS模式专用于FOTA测试场景，会自动处理`TSAPResource`目录结构
- LCS模式会根据文件中的语种（cmn/eng）自动生成对应的`checksum.list`文件
- 如果源目录中文件数量少于指定数量，会选取所有可用文件

**使用示例**:
```dsl
# 普通模式：随机选取10个文件打包
[SYS]FOTA_RANDOM_ZIP {WORKPATH}/resources {WORKPATH}/output/random.zip 10

# 指定zip包内根目录
[SYS]FOTA_RANDOM_ZIP {WORKPATH}/resources {WORKPATH}/output/random.zip 10 myroot

# LCS模式：从TSAPResource目录随机选取文件
[SYS]FOTA_RANDOM_ZIP {WORKPATH}/lcs_resources {WORKPATH}/output/lcs.zip 20 . lcs

# 使用环境变量指定路径
[SYS]FOTA_RANDOM_ZIP {WORKSPACE}/source {WORKPATH}/fota.zip 15
```

**注意事项**:
- 源目录必须存在，否则打包失败
- LCS模式下，如果源目录中不存在`TSAPResource`子目录，会失败
- 目标zip文件的父目录会自动创建（如果不存在）
- 文件路径支持环境变量替换（如`{WORKPATH}`、`{WORKSPACE}`等）

## 🚗 CarPlay客户端指令 (CPL客户端)

CarPlay客户端当前在 DSL 层只开放 `CREATE` 和 `FREE` 两个指令；唤醒词、VAD、状态等结果通过统一回调池暴露，使用 `[EXP]CarPlayWakeup`、`[EXP]CarPlayVad`、`[EXP]CarPlayStatus` 等断言进行验证。

### CREATE - 创建CarPlay引擎
**语法**: `[CPL]CREATE mode lang config_path`

**参数说明**:

- `mode`: 工作模式
  - `0`: 无模式
  - `1`: 唤醒词数据模式
  - `2`: VAD信息模式
  - `3`: 音频数据模式
- `lang`: 语言代码（cmn/eng）
- `config_path`: 配置文件路径

**底层接口**: `create_carplay_link()`

**使用示例**:

```dsl
# 基本创建（KAD唤醒词模式）
[CPL]CREATE 1 cmn {CARPLAYCONFIG}

# VAD模式
[CPL]CREATE 2 cmn {CARPLAYCONFIG}
```

### FREE - 释放CarPlay引擎
**语法**: `[CPL]FREE`

**底层接口**: `destroy_carplay_link()`

**使用示例**:

```dsl
[CPL]FREE
```

### CarPlay回调断言

CarPlay客户端支持以下回调断言类型：

| 断言类型 | 触发条件 | 可用字段 |
|----------|----------|----------|
| `CarPlayWakeup` | 唤醒词检测 | text, kadStart, kadEnd, duration |
| `CarPlayVad` | VAD状态变化 | state, vadStart, vadEnd |
| `CarPlayAudio` | 音频数据回传 | length, channelNum, timestamp |
| `CarPlayStatus` | CarPlay状态变化 | code, text |

**断言示例**:
```dsl
# 唤醒词断言
[EXP]CarPlayWakeup text:你好小白 <timeout=5>

# VAD状态断言
[EXP]CarPlayVad state:1 <timeout=3>

# CarPlay状态断言
[EXP]CarPlayStatus code:0
```

### CarPlay完整测试示例

```dsl
>>> SETUP
# 启动服务
[SYS]PULL AIBSServer cmn {"brand":"0"}
[SYS]SLEEP 2

# 创建TSA客户端
[TSA]CREATE cmn com.autoai.vr.service_vrassistant
<<<

>>>
# CarPlay唤醒测试
[TSA]START 1

# 创建CarPlay引擎（KAD唤醒词模式，并保存音频）
[CPL]CREATE 1 cmn {CARPLAYCONFIG}

# 发送音频数据
[TSA]DATA {WORKPATH}/audio/wakeup_test.wav

# 断言唤醒词检测结果
[EXP]CarPlayWakeup text:你好小白 <timeout=5>

# 断言VAD状态
[EXP]CarPlayVad state:1 <timeout=3>

# 释放CarPlay引擎
[CPL]FREE
[TSA]STOP
<<<

>>> TEARDOWN
[TSA]FREE
[SYS]KILL AIBSServer
<<<
```

## 🔍 断言指令 (EXP客户端)

### EXP - 执行断言
**语法**: `[EXP]assertion_type [channel]expected_fields`

**参数说明**:

- `assertion_type`: 断言类型（如cloudASRResult、NLPResult等）
- `channel`: 通道ID（可选，默认为0）
- `expected_fields`: 期望字段（格式：字段1:值1;字段2:值2）

**使用示例**:
```dsl
# 立即断言
[EXP]cloudASRResult asr:你好小白

# 不同声道结果断言
[EXP]cloudASRResult] [1]asr:天气查询;confidence:>80

# 多字段断言
[EXP]NLPResult skill:WEATHER;intention:QUERY

# API断言
[EXP]GET_VERSION_RET code:0
```

## 📁 文件断言指令 (EXP客户端)

NANO测试套件新增了4个文件断言指令，用于验证文件存在性、大小、MD5值和JSON内容。这些指令支持环境变量，可以在测试过程中对文件状态进行验证。

### FILEEXIT - 文件存在性断言
**语法**: `[EXP]FILEEXIT file_path [expected_exists]`

**参数说明**:
- `file_path`: 文件路径（支持环境变量，如`{WORKPATH}`、`{WORKSPACE}`等）
- `expected_exists`: 期望存在状态（`1`=存在，`0`=不存在，默认为`1`）

**功能说明**:
- 检查指定文件是否存在
- 如果文件存在性与期望值匹配则Pass，否则Fail

**使用示例**:
```dsl
# 断言文件存在
[EXP]FILEEXIT {WORKPATH}/lcs.zip 1

# 断言文件不存在
[EXP]FILEEXIT {WORKPATH}/temp.log 0

# 使用默认值（默认为1，即期望存在）
[EXP]FILEEXIT {WORKSPACE}/result.json
```

### FILESIZE - 文件大小断言
**语法**: `[EXP]FILESIZE file_path operator expected_size`

**参数说明**:
- `file_path`: 文件路径（支持环境变量）
- `operator`: 比较操作符（`>`大于、`<`小于、`=`等于）
- `expected_size`: 期望的文件大小（字节）

**功能说明**:
- 检查文件大小是否符合期望
- 支持大于、小于、等于三种比较方式
- 如果文件不存在则Fail

**使用示例**:
```dsl
# 断言文件大小大于1230字节
[EXP]FILESIZE {WORKPATH}/lcs.zip > 1230

# 断言文件大小小于300字节
[EXP]FILESIZE {WORKPATH}/small.txt < 300

# 断言文件大小等于1024字节
[EXP]FILESIZE {WORKSPACE}/data.bin = 1024
```

### FILEMD5 - 文件MD5值断言
**语法**: `[EXP]FILEMD5 file_path = expected_md5`

**参数说明**:
- `file_path`: 文件路径（支持环境变量）
- `expected_md5`: 期望的MD5值（字符串，不区分大小写）

**功能说明**:
- 计算文件的MD5哈希值并与期望值比较
- 如果文件不存在则Fail
- MD5比较不区分大小写

**使用示例**:
```dsl
# 断言文件MD5值
[EXP]FILEMD5 {WORKPATH}/lcs.zip = 1921u2u192u1921212

# MD5值不区分大小写
[EXP]FILEMD5 {WORKSPACE}/binary.dat = ABC123DEF456

# 验证下载文件的完整性
[EXP]FILEMD5 {WORKPATH}/download.zip = 5d41402abc4b2a76b9719d911017c592
```

### FILEDIF - 文件内容断言（JSON）
**语法**: `[EXP]FILEDIF JSON file_path json_path_expr`

**参数说明**:
- `file_path`: JSON文件路径（支持环境变量）
- `json_path_expr`: JSON路径表达式（格式：`path.to.field=expected_value`，支持数组索引）

**功能说明**:
- 检查JSON文件中指定路径的值是否等于期望值
- 支持嵌套对象路径（使用`.`分隔）
- 支持数组索引（使用`[index]`）
- 自动进行数值类型转换（整数、浮点数）
- 目前仅支持JSON格式文件

**JSON路径表达式说明**:
- 对象键访问：`data.status` - 访问data对象的status字段
- 数组索引访问：`data.items[0]` - 访问data对象的items数组的第一个元素
- 嵌套路径：`data.shsh[0].txt.status` - 访问嵌套对象和数组的字段
- 值比较：使用`=`指定期望值，如`data.status=0`

**使用示例**:
```dsl
# 断言简单字段值
[EXP]FILEDIF JSON {WORKPATH}/config.json app.enabled=true

# 断言数组元素字段
[EXP]FILEDIF JSON {WORKPATH}/daemon_tag.json data.shsh[0].txt.status=0

# 断言数字字段
[EXP]FILEDIF JSON {WORKSPACE}/result.json data.score=100

# 断言嵌套路径
[EXP]FILEDIF JSON {WORKPATH}/settings.json config.audio.volume=80

# 断言字符串字段
[EXP]FILEDIF JSON {WORKPATH}/info.json user.name="test_user"
```

**注意事项**:
- 文件路径支持环境变量，会在解析时自动替换
- 如果文件不存在，断言会Fail
- JSON路径必须存在，否则断言会Fail
- 数值比较会自动进行类型转换（整数、浮点数）
- 字符串比较区分大小写

**文件断言应用场景**:
```dsl
>>> 1
# 验证下载的文件是否存在
[EXP]FILEEXIT {WORKPATH}/lcs.zip 1

# 验证文件大小是否符合预期
[EXP]FILESIZE {WORKPATH}/lcs.zip > 1000000

# 验证文件MD5确保完整性
[EXP]FILEMD5 {WORKPATH}/lcs.zip = abc123def456

# 修改配置文件后验证修改是否生效
[SYS]UPLOAD JSON {WORKPATH}/config.json data.timeout 5000
[EXP]FILEDIF JSON {WORKPATH}/config.json data.timeout=5000

# 验证配置文件中的状态值
[EXP]FILEDIF JSON {WORKPATH}/daemon_tag.json data.shsh[0].txt.status=0
<<<
```

## 📋 指令兼容性表

| 指令类别 | TSA | SET | VOI | OMS | TTS | SYS | EXP |
|----------|-----|-----|-----|-----|-----|-----|-----|
| 基础指令 | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| 引擎控制 | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| 系统设置 | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| 录音功能 | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| 语音输入 | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| 声纹功能 | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 配置状态 | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ |
| 日志功能 | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| 引擎参数 | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| 系统操作 | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| 断言验证 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| 文件断言 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |

**注意**: 系统操作指令中的UPLOAD和ALLURE用于文件操作和报告管理，是测试流程中非常有用的辅助工具。

## 🎯 最佳实践

### 1. 客户端选择原则
- **TSA**: 主要用于语音识别、声纹、TTS等核心功能测试
- **SET**: 用于系统设置和配置相关测试  
- **VOI**: 专用于语音输入功能测试
- **OMS**: 用于OMS相关功能测试
- **TTS**: 专用于文本转语音功能测试
- **SYS**: 用于系统级操作（服务管理、文件操作、报告管理等）
- **EXP**: 专用于结果断言验证（包括回调断言、API断言和文件断言）

### 2. 指令执行顺序
```dsl
# 推荐的指令执行顺序
[SYS]PULL AIBSServer cmn {"brand":"0"}       # 1. 启动服务
[SYS]SLEEP 2                                 # 2. 等待服务启动
# 可选：修改配置文件
[SYS]UPLOAD JSON {WORKPATH}/config.json param.value 100
[SYS]UPLOAD LINE {WORKPATH}/decoder.conf TIMEOUT 5000
[TSA]CREATE cmn com.autoai.vr.service_vrassistant   # 3. 创建客户端
[TSA]START 1                                # 4. 启动会话
[TSA]DATA audio.wav                         # 5. 发送数据
[EXP]cloudASRResult asr:期望结果 <timeout=3> # 6. 断言验证
# 可选：将关键文件添加到报告
[SYS]ALLURE TEXT {WORKPATH}/decoder.conf
[SYS]ALLURE CSV {WORKPATH}/result.csv
[TSA]STOP                                   # 7. 停止会话
[TSA]FREE                                   # 8. 释放资源
[SYS]KILL AIBSServer                        # 9. 清理服务
```

### 3. 错误处理
- 使用合适的超时时间进行断言
- 在测试结束后及时清理资源
- 使用环境变量提高用例可移植性
- 添加必要的延时确保操作完成

### 4. 调试技巧
- 使用`[SYS]PRINT`输出调试信息
- 利用日志功能记录关键操作
- 合理设置断言超时时间
- 在GDB模式下进行深度调试

---

## 🎙️ SpeechEngine客户端指令 (HWK客户端)

SpeechEngine客户端（HWK）用于测试SpeechEngine语音识别引擎，支持离线识别、唤醒词检测、声纹识别等功能。

### CREATE - 创建SpeechEngine引擎
**语法**: `[HWK]CREATE decoder_config log_path`

**参数说明**:

- `decoder_config`: 解码器配置文件路径
- `log_path`: 日志文件保存路径

**底层接口**: `speech_create_engine()`

**使用示例**:
```dsl
[HWK]CREATE {CONFIGPATH} {LOGPATH}
```

### START - 启动会话
**语法**: `[HWK]START`

**底层接口**: `speech_start_engine()`

**使用示例**:
```dsl
[HWK]START
```

### STOP - 停止会话
**语法**: `[HWK]STOP`

**底层接口**: `speech_stop_engine()`

**使用示例**:
```dsl
[HWK]STOP
```

### FREE - 释放引擎资源
**语法**: `[HWK]FREE`

**底层接口**: `speech_free_engine()`

**使用示例**:
```dsl
[HWK]FREE
```

### DATA - 发送音频数据
**语法**: `[HWK]DATA audio_path [frame=320] [delay=0.0] [range=[0,-1]]`

**参数说明**: 与TSA客户端的DATA指令相同，支持命名参数

**底层接口**: `speech_process_data()`

**使用示例**:
```dsl
[HWK]DATA {WORKPATH}/audio/test.wav
[HWK]DATA audio/test.wav frame=640 delay=0.5
```

### CANCEL - 取消操作
**语法**: `[HWK]CANCEL`

**底层接口**: `speech_cancel_engine()`

**使用示例**:
```dsl
[HWK]CANCEL
```

### SET_PARAM - 设置引擎参数
**语法**: `[HWK]SET_PARAM param_code param_value`

**支持的参数**:
- `SPEECH_ENGINE_PARAM_LINK_TYPE`: 连接类型
- `SPEECH_ENGINE_PARAM_SEAT_SIGNAL`: 座椅信号
- `SPEECH_ENGINE_FULL_VEHICLE_SPEECH`: 全车语音
- `SPEECH_ENGINE_PARAM_REAL_TIME_RESULT`: 实时结果
- `SPEECH_ENGINE_PARAM_PUNC_RESULT`: 标点符号结果
- `SPEECH_ENGINE_PARAM_SILENCE_DURATION`: 静音检测时长
- `SPEECH_ENGINE_PARAM_SILENCE_TIMEOUT`: 静音超时时长
- `SPEECH_ENGINE_PARAM_SPEECH_TIMEOUT`: 语音超时时长
- `SPEECH_ENGINE_PARAM_SCENAROI_NAME`: 场景名称
- `SPEECH_ENGINE_PARAM_WAKEUP_SCENE`: 唤醒场景
- `SPEECH_ENGINE_PARAM_SR_VOICE_WAKEUP`: 声纹唤醒开关
- `SPEECH_ENGINE_PARAM_SR_WAKEUP_SCENE_ENABLE`: 语音唤醒场景使能

**使用示例**:
```dsl
[HWK]SET_PARAM SPEECH_ENGINE_PARAM_REAL_TIME_RESULT 1
[HWK]SET_PARAM SPEECH_ENGINE_PARAM_SILENCE_DURATION 5000
```

### INIT_DECODE - 初始化解码器
**语法**: `[HWK]INIT_DECODE`

**功能说明**: 初始化SpeechEngine解码器

**使用示例**:
```dsl
[HWK]INIT_DECODE
```

### SET_DATA_TYPE - 设置数据类型
**语法**: `[HWK]SET_DATA_TYPE data_type`

**参数说明**:
- `data_type`: 数据类型代码

**使用示例**:
```dsl
[HWK]SET_DATA_TYPE 1
```

### SET_WORK_MODE - 设置工作模式
**语法**: `[HWK]SET_WORK_MODE mode`

**参数说明**:
- `mode`: 工作模式代码

**使用示例**:
```dsl
[HWK]SET_WORK_MODE 1
```

### SET_TTS_STATE - 设置TTS状态
**语法**: `[HWK]SET_TTS_STATE state`

**参数说明**:
- `state`: TTS状态（true/false/1/0）

**使用示例**:
```dsl
[HWK]SET_TTS_STATE true
```

### SET_FREETALK_STATE - 设置自由对话状态
**语法**: `[HWK]SET_FREETALK_STATE state`

**参数说明**:
- `state`: 自由对话状态（true/false/1/0）

**使用示例**:
```dsl
[HWK]SET_FREETALK_STATE true
```

### ADD_WAKEUP_WORD - 添加唤醒词
**语法**: `[HWK]ADD_WAKEUP_WORD wakeup_word threshold`

**参数说明**:
- `wakeup_word`: 唤醒词内容
- `threshold`: 阈值（0.0-1.0）

**使用示例**:
```dsl
[HWK]ADD_WAKEUP_WORD 你好小白 0.8
```

### GET_WAKEUP_TERM - 获取唤醒词
**语法**: `[HWK]GET_WAKEUP_TERM`

**功能说明**: 获取当前配置的唤醒词列表

**使用示例**:
```dsl
[HWK]GET_WAKEUP_TERM
```

### SET_WAKEUP_ENABLE - 设置唤醒词使能
**语法**: `[HWK]SET_WAKEUP_ENABLE wakeup_word enable`

**参数说明**:
- `wakeup_word`: 唤醒词内容
- `enable`: 是否启用（true/false/1/0）

**使用示例**:
```dsl
[HWK]SET_WAKEUP_ENABLE 你好小白 true
```

### SET_VOICE_WAKEUP_OPTION - 设置语音唤醒选项
**语法**: `[HWK]SET_VOICE_WAKEUP_OPTION option`

**参数说明**:
- `option`: 语音唤醒选项值

**使用示例**:
```dsl
[HWK]SET_VOICE_WAKEUP_OPTION 1
```

### SET_SRE_REQUEST - 设置声纹请求
**语法**: `[HWK]SET_SRE_REQUEST request_data`

**参数说明**:
- `request_data`: 声纹请求数据（JSON格式）

**使用示例**:
```dsl
[HWK]SET_SRE_REQUEST {"user_id":"test","text":"你好"}
```

### SET_SRE_ENABLE_OPTION - 设置声纹使能选项
**语法**: `[HWK]SET_SRE_ENABLE_OPTION option`

**参数说明**:
- `option`: 声纹使能选项值

**使用示例**:
```dsl
[HWK]SET_SRE_ENABLE_OPTION 1
```

### SET_LANGUAGE_INFO - 设置语言信息
**语法**: `[HWK]SET_LANGUAGE_INFO language_info`

**参数说明**:
- `language_info`: 语言信息（JSON格式）

**使用示例**:
```dsl
[HWK]SET_LANGUAGE_INFO {"lang":"cmn"}
```

### SET_VR_SILENCE_TIMEOUT - 设置VR静音超时
**语法**: `[HWK]SET_VR_SILENCE_TIMEOUT timeout_ms`

**参数说明**:
- `timeout_ms`: 静音超时时间（毫秒）

**使用示例**:
```dsl
[HWK]SET_VR_SILENCE_TIMEOUT 5000
```

### HMI - 设置HMI信息
**语法**: `[HWK]HMI hmi_data_or_file`

**参数说明**:
- `hmi_data_or_file`: HMI数据（JSON字符串或JSON文件路径）

**使用示例**:
```dsl
[HWK]HMI {"page":"music","app":"player"}
[HWK]HMI {WORKPATH}/hmi_config.json
```

### SpeechEngine回调断言

SpeechEngine客户端支持以下回调断言类型：

| 断言类型 | 触发条件 | 可用字段 |
|----------|----------|----------|
| `SpeechASRResult` | ASR识别结果 | asr, start, end, confidence, lang |
| `SpeechASRResultTemp` | ASR临时结果 | asr, start, end, confidence |
| `SpeechEngineWakeup` | 唤醒词检测 | text, start, end |
| `SpeechNluResult` | NLU理解结果 | skill, intention, text |
| `VoiceDetectionResult` | 语音检测结果 | state, start, end |

**断言示例**:
```dsl
# ASR结果断言
[EXP]SpeechASRResult asr:你好小白 <timeout=5>

# 唤醒词断言
[EXP]SpeechEngineWakeup text:你好小白 <timeout=3>

# NLU结果断言
[EXP]SpeechNluResult skill:WEATHER;intention:QUERY <timeout=5>
```

## 📡 PSTT客户端指令 (PST客户端)

PSTT客户端用于测试PSTT在线ASR服务，支持单音频处理和批量音频处理。

### CREATE - 创建PSTT服务
**语法**: `[PST]CREATE config_path`

**参数说明**:
- `config_path`: PSTT配置文件路径

**功能说明**: 加载PSTT配置并初始化服务

**使用示例**:
```dsl
[PST]CREATE {CONFIGPATH}/pstt.conf
```

### FREE - 释放PSTT服务
**语法**: `[PST]FREE`

**功能说明**: 释放PSTT服务资源

**使用示例**:
```dsl
[PST]FREE
```

### DATA - 处理单个音频文件
**语法**: `[PST]DATA audio_path [delay=0.0]`

**参数说明**:
- `audio_path`: 音频文件路径
- `delay`: 延时比例（可选，默认0.0）

**功能说明**: 处理单个音频文件，返回识别结果

**底层接口**: `process_single_audio()`

**使用示例**:
```dsl
# 基础用法
[PST]DATA {WORKPATH}/audio/test.wav

# 指定延时
[PST]DATA audio/test.wav delay=0.5
```

### HMI - 设置HMI信息
**语法**: `[PST]HMI hmi_data_or_file`

**参数说明**:
- `hmi_data_or_file`: HMI数据（JSON字符串或JSON文件路径）

**功能说明**: 设置PSTT服务的HMI上下文信息

**使用示例**:
```dsl
[PST]HMI {"page":"music","app":"player"}
[PST]HMI {WORKPATH}/hmi.json
```

### DATA_QUEUE - 批量处理测试集（pstt_client_qa）
**语法**: `[PST]DATA_QUEUE case=caselist_path model=model_name bref=testset_name [thread=<n>]`

**参数说明**:
- `case`: 音频列表文件路径（必填参数）
- `model`: 传入模型名（必填参数）
- `bref`: 测试集标识（必填，用于结果文件名）
- `thread`: 线程数（可选，传入后会写回配置 `THREAD_NUM`）

**结果文件说明**:
- 结果文件由框架内部固定写入 `{WORKPATH}/result_file/`
- 为避免同名 `bref` 覆盖，框架会附加用例唯一标识（优先 CASEID）
- `RESULT_FILE`: `{bref}__{unique_tag}_full.txt`
- `REC_RES_FILE`: `{bref}__{unique_tag}_testset.txt`

**功能说明**: 调用 `pstt_client_qa -f conf` 批量处理测试集

**数据格式**: 音频列表文件为scp文本，每行一个音频绝对/相对路径

**使用示例**:
```dsl
# 必填参数：case + bref
[PST]DATA_QUEUE case=audio_list.txt model=cmn bref=testset_a

# 覆盖线程数
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

### PSTT回调断言

PSTT客户端支持以下回调断言类型：

| 断言类型 | 触发条件 | 可用字段 |
|----------|----------|----------|
| `PSTTASRResult` | PSTT ASR最终结果 | asr, start, end, confidence, lang |
| `PSTTASRResultTemp` | PSTT ASR临时结果 | asr, start, end, confidence |

**断言示例**:
```dsl
# PSTT ASR结果断言
[EXP]PSTTASRResult asr:今天天气怎么样 <timeout=5>
```

## 🤖 TiTan客户端指令 (TIA客户端)

TiTan客户端用于测试TiTan WebSocket ASR服务，支持单音频处理和批量音频处理。

### CREATE - 创建TiTan服务
**语法**: `[TIA]CREATE config_path`

**参数说明**:
- `config_path`: TiTan配置文件路径（INI格式）

**功能说明**: 加载TiTan配置并初始化WebSocket连接

**配置文件格式**: INI格式，支持无section格式

**使用示例**:
```dsl
[TIA]CREATE {CONFIGPATH}/titan.ini
```

**配置文件示例**:
```ini
url=ws://example.com/asr
language=cmn
realTimeSilStep=10
```

### DATA - 处理单个音频文件
**语法**: `[TIA]DATA audio_path [delay=0.0]`

**参数说明**:
- `audio_path`: 音频文件路径
- `delay`: 延时比例（可选，默认0.0）

**功能说明**: 通过WebSocket连接处理单个音频文件，返回识别结果

**底层接口**: `process_single_audio()`

**使用示例**:
```dsl
# 基础用法
[TIA]DATA {WORKPATH}/audio/test.wav

# 指定延时
[TIA]DATA audio/test.wav delay=0.5
```

### CASELIST - 批量处理音频列表
**语法**: `[TIA]CASELIST caselist_path [delay=0.0] [thread=1]`

**参数说明**:
- `caselist_path`: 音频列表文件路径（每行一个音频路径）
- `delay`: 延时比例（可选，默认0.0）
- `thread`: 并发处理数（可选，默认1）

**功能说明**: 批量处理音频列表文件中的音频，支持并发WebSocket连接

**数据格式**: 音频列表文件为文本文件，每行一个音频路径，支持注释（以`#`或`//`开头）

**使用示例**:
```dsl
# 单线程处理
[TIA]CASELIST {WORKPATH}/audio_list.txt

# 并发处理（10个线程）
[TIA]CASELIST audio_list.txt delay=0.0 thread=10
```

### TiTan回调断言

TiTan客户端支持以下回调断言类型：

| 断言类型 | 触发条件 | 可用字段 |
|----------|----------|----------|
| `TiTanASRResult` | TiTan ASR最终结果 | asr, start, end, confidence, lang, emotion, gender, age |
| `TiTanASRResultTemp` | TiTan ASR临时结果 | asr, start, end, confidence |

**断言示例**:
```dsl
# TiTan ASR结果断言
[EXP]TiTanASRResult asr:今天天气怎么样 <timeout=5>

# 断言情感识别结果
[EXP]TiTanASRResult emotion:happy <timeout=5>
```

## 📊 TSR客户端指令 (TSR客户端)

TSR (Test Suite Report) 客户端用于 Suite 级别的统计和报告生成。当前代码实际支持的 DSL 指令如下，推荐写在 `SUITE_TEARDOWN` 中执行：

| 指令 | 说明 | 常见输入 |
|------|------|----------|
| `ASR_ACCURACY` | ASR 准确率统计 | `result=<asr.csv> ref=<答案CSV>` |
| `ASR_LANGUAGE` | 语种识别统计 | `result=<asr.csv> ref=cmn` |
| `DELAY` | 实时/最终结果时延统计 | `ref=<标注文件> result=<callback.jsonl> type=<回调类型>` |
| `WAKEUP_ACCURACY` | 唤醒 FA/FR 统计 | `result=<wakeup.csv> ref=<参考CSV>` |
| `VAD_ACCURACY` | VAD FA/FR 统计 | `result=<vad.txt> ref=<参考txt>` |
| `VAD_PRECISION` | VAD 边界精度统计 | `result=<vad.txt> ref=<参考txt>` |
| `TIME_BOUNDARY_ACCURACY` | 起止时间边界误差统计 | `result=<txt/jsonl> ref=<参考txt>` |
| `LLM` | 大模型批量评测 | `result=<csv> prompt=<模板文件>` |
| `PSTT_ACCURACY` | PSTT 测试集综合统计 | `result=<*_full.txt或目录> ref=<ref文件或目录> type=<asr/lang/...>` |

### TSR使用示例

```dsl
>>> SUITE_TEARDOWN
# ASR 结果准确率
[TSR]ASR_ACCURACY result={WORKPATH}/asr.csv ref=TestCase/ref/cmn_answer.csv output={WORKPATH}/asr_accuracy.xlsx

# 实时上屏时延
[TSR]DELAY ref=TestCase/ref/label.txt result={WORKPATH}/callback.jsonl type=PSTTASRResultTemp output={WORKPATH}/delay.xlsx

# 唤醒统计
[TSR]WAKEUP_ACCURACY result={WORKPATH}/wakeup.csv ref=TestCase/ref/wakeup_ref.csv output={WORKPATH}/wakeup_accuracy.xlsx
<<<
```

## 🚗 NIS客户端指令 (NIS客户端)

NIS (Nissan AIBS) 客户端是专为日产项目定制的AIBS客户端，指令与TSA客户端完全相同，请参考TSA客户端指令说明。

**支持的指令**: 与TSA客户端完全一致，包括：
- 基础指令：CREATE, START, STOP, FREE, DATA, TEXT_DATA, EVENT, CANCEL等
- 引擎控制：PAUSE, RESUME, GET_VERSION等
- 声纹功能：START_SPEAKER_ENROLL, VOICEPRINT_LOGIN等
- 配置状态：GET_VR_CONFIG, GET_WAKEUP_WORD等

**使用示例**:
```dsl
[NIS]CREATE cmn com.autoai.vr.service_vrassistant
[NIS]START 1
[NIS]DATA {WORKPATH}/audio/test.wav
[EXP]NLPResult skill:WEATHER;intention:QUERY <timeout=5>
[NIS]STOP
[NIS]FREE
```

## ⚙️ NSE客户端指令 (NSE客户端)

NSE (Nissan SET) 客户端是专为日产项目定制的SET客户端，指令与SET客户端完全相同，请参考SET客户端指令说明。

**支持的指令**: 与SET客户端完全一致，包括：

- 基础指令：CREATE, START, STOP, FREE, DATA, TEXT_DATA, EVENT等
- 声纹功能：REGISTER_VOICEPRINT_LIST, VOICEPRINT_LOGIN等
- 配置状态：GET_VR_CONFIG, SET_WAKEUP_WORD等

**使用示例**:
```dsl
[NSE]CREATE cmn com.pachira.set
[NSE]START 1
[NSE]SETVRCONFIG VR_OPTION 1
[NSE]STOP
[NSE]FREE
```

## 🎙️ ECNR客户端指令(ECNR客户端)
**命令前缀**：`[ENR]`
**支持的指令**:

- **基础控制**  
  - `SET_DOWNLINK downLink`：设置上下行模式，`0`=普通ECNR，`1`=LineIn下行模式  
  - `AMP_TYPE 0`：设置车机AMP类型，可选范围：0～8；
  - `ECNR_TYPE 450D`：设置ECNR_TYPE。
  - `CREATE device:xxx;micNum:N;refNum:M;micDistance:D`：创建ECNR引擎  
  - `SET_WORKMODE workMode:X;sampleRate:16000[;spectrum:8000|16000|24000|32000|48000]`：设置工作模式及采样率。LineIn 模式下 `spectrum` 为输出采样率，需与设备可用向量匹配（如 16k→16k 用 spectrum:16000）  
  - `START channelMask:mask;synthMethod:method`：启动引擎，`channelMask` 决定输出通道数  
  - `DATA /path/to/audio.(pcm|wav)`：送入多通道音频数据，生成NR后的单/多通道PCM  
  - `ANALYZE_AUDIO_DATA channel:0;start:1.78;end:3`：分析前置 `DATA` 生成的输出音频在时间段 `[start,end]` 内各指标（dBFS/幅值），用于后续 `EXP` 断言  
    - `channel`：取哪一路麦克风/输出通道（与 DATA/START 生成的通道一致）  
    - `start/end`：时间（单位：秒），**必填**，用于切片分析，缺省会直接报错  
  - `FREE`：释放ECNR引擎资源  
- **开关类控制**  
  - `SET_PNR_MIC_MUTE_OPTION option:0|1`：MIC静音开关  
  - `SET_PNR_ENABLE_OPTION option:0|1`：PNR算法总开关  
  - `SET_PNR_AUDIO_QUALITY quality:0|1|2...`：音质/降噪效果档位  
- **查询类指令**  
  - `GET_VERSION`：获取库版本号  
  - `GET_PNR_HFT_PARAM` / `GET_PNR_MVR_PARAM` / `GET_PNR_GEN_PARAM`：获取不同场景下的参数配置  
  - `GET_PNR_FRAME_SIZE` / `GET_LINEIN_PNR_FRAME_SIZE`：获取处理一帧所需采样点数  

**使用示例（典型流程）**:

```dsl
[ENR]AMP_TYPE  3          # 模拟车机设置ECNR_TYPE
[ENR]ECNR_TYPE 410D       # 模拟车机设置AMP_TYPE
[ENR]SET_DOWNLINK 0       # 设置上下行模式 0: 上行   1:下行
[ENR]CREATE       device:lexus_2S;micNum:4;refNum:7;micDistance:560     # 创建引擎
[ENR]SET_WORKMODE workMode:0;sampleRate:16000                           # 设置工作模式
[ENR]START        channelMask:15;synthMethod:2                          # 开始会话
[ENR]DATA         /data1/.../input_11ch_16k.pcm
[EXP]ECNR vec:dl_lexus410D_fm1388_vec_1mic_2ref_DL16Kto16K        # 断言选择的VEC Name
[EXP]ECNR md5:6cd211c989d4d10571606116c50fc5e4                    # 断言降噪后的音频md5

[ENR]ANALYZE_AUDIO_DATA channel:0;start:1.78;end:3       # 音频分析器，取channel0的第1.78s到3s的数据进行分析
[EXP]ECNR snr:>20                                        # 断言SNR大于20dB                           
[EXP]ECNR maxRms:<10                                     # 断言最大RMS小于10dB
[EXP]ECNR minRms:>-20                                    # 断言最小RMS大于-20dB
[EXP]ECNR avgRms:>5                                      # 断言平均RMS大于5dB
[ENR]FREE
```

## 🤖 PISA大模型客户端指令 (PIS客户端)

PISA 客户端用于测试 PISA 大模型全双工 WebSocket 服务，支持语音输入、视觉理解（VEDIO）、会话配置等。**依赖**：`pip install websockets`。音频送流经 AIBS 降噪引擎（libAIBS_dynamic.so），需在 CREATE 后完成 AIBSServer、AIBS_CREATE、AIBS_START 初始化。

**命令前缀**：`[PIS]`

| 指令 | 说明 |
|------|------|
| CREATE | 初始化连接参数（url=, client_id=, video_url=），不建立连接 |
| AIBSServer | 启动 AIBS 语音服务（使用 decoder.conf，需 -C 传入配置） |
| AIBS_SET_CARTYPE | 设置 AIBS 设备类型，**需在 AIBS_CREATE 前调用** |
| AIBS_SET_WORK_MODE | 设置 AIBS 工作模式（0=NORMAL, 1=WAKEUP, 2=ASR 等） |
| AIBS_CREATE | 创建 AIBS 客户端（接入 libAIBS_dynamic.so） |
| AIBS_START | 启动 AIBS 会话 |
| AIBS_STOP | 停止 AIBS 会话 |
| START | 建立 WebSocket 长连接，等待 session.created |
| DATA | 同步发送音频，经 AIBS 降噪后转发到 WebSocket |
| VEDIO | 上传图片到 Video LLM，获取视觉理解结果（详见下文） |
| WAIT | 阻塞等待事件或流式文本（详见下文） |
| UPDATE | 发送 session.update，更新会话配置（详见下文） |
| STOP | 关闭 WebSocket 连接 |
| FREE | 释放资源 |

### AIBS 引擎指令（libAIBS_dynamic.so）

PISA 客户端集成 AIBS 降噪引擎，音频经 AIBS 处理后转发到 WebSocket。需在 CREATE 之后、START 之前完成 AIBS 初始化。

**语法**：
- `[PIS]AIBSServer cmn` — 启动 AIBS 服务，使用 `{CONFIGPATH}`（decoder.conf）
- `[PIS]AIBS_SET_CARTYPE "车型标识"` — 设置设备类型，**必须在 AIBS_CREATE 前调用**
- `[PIS]AIBS_SET_WORK_MODE 模式` — 设置工作模式，支持数值或名称
- `[PIS]AIBS_CREATE cmn` — 创建 AIBS 客户端
- `[PIS]AIBS_START` — 启动 AIBS 会话
- `[PIS]AIBS_STOP` — 停止 AIBS 会话

**工作模式**：`0`=NORMAL, `1`=WAKEUP, `2`=ASR, `3`=NLU, `4`=NLG, `5`=ONE_SHOT, `6`=SMART_LINK, `7`=FREE_TALK

**示例**：
```dsl
# 完整 AIBS 初始化流程
[PIS]CREATE url=ws://192.168.128.32:8765/realtime client_id=test_device
[PIS]AIBSServer cmn
[PIS]AIBS_SET_CARTYPE "KAICHENG_TWO"
[PIS]AIBS_CREATE cmn
[PIS]AIBS_SET_WORK_MODE 1
[PIS]AIBS_START
[PIS]START
[PIS]DATA {WORKPATH}/audio/test.wav
[PIS]AIBS_STOP
[PIS]STOP
[PIS]FREE
```

**说明**：`DATA` 将原始 PCM 送入 AIBS，由 AIBS 回调返回 NR 输出、speech_start、speech_end，再转发到 WebSocket。AIBS 回调 `PISAIBSSpeechStart`、`PISAIBSSpeechEnd`、`PISAIBSWakeup` 会写入断言池。

### VEDIO - 上传图片到 Video LLM

**语法**：`[PIS]VEDIO image=path [lat=纬度] [lon=经度] [nlat=下一纬度] [nlon=下一经度]`

**参数**：`image` 必填；`lat`/`lon` 为空表示前置摄像头；`nlat`/`nlon` 为下一位置坐标。

**说明**：成功后图片理解结果加入 `video_info_stack`，后续 DATA 推流时会作为上下文一并发送；并回调 `PISAVedioText`。

**示例**：
```dsl
# 仅上传图片（前置摄像头）
[PIS]VEDIO image={WORKPATH}/frame_001.png

# 带 GPS 坐标（后视/环视场景）
[PIS]VEDIO image=road.jpg lat=39.9 lon=116.4

# 带当前位置和下一位置（导航场景）
[PIS]VEDIO image=intersection.png lat=39.9 lon=116.4 nlat=39.91 nlon=116.41

# 多图场景：先 VEDIO 再 DATA，图片会作为上下文
[PIS]VEDIO image=scene1.png
[PIS]VEDIO image=scene2.png
[PIS]DATA {WORKPATH}/audio/问这是什么.wav
```

### WAIT - 阻塞等待

**语法**：
- 等待事件：`[PIS]WAIT type=事件类型 [过滤键=值] [timeout=N]`
- 等待流式文本：`[PIS]WAIT text=关键词 [timeout=N]`

**说明**：主线程阻塞直到条件满足或超时。超时默认 10 秒，`timeout=` 可覆盖。

**示例**：
```dsl
# 等待 response.done（本轮回复结束）
[PIS]WAIT type=response.done <timeout=5>

# 等待 response.done 且 response_type=query
[PIS]WAIT type=response.done response_type=query <timeout=3>

# 等待流式输出中出现某关键词
[PIS]WAIT text=北京 <timeout=10>

# 等待 VAD 开始说话
[PIS]WAIT type=input_audio_buffer.speech_started <timeout=2>

# 等待 ASR 完成（可断言 PISASRResult）
[PIS]WAIT type=response.input_audio_transcription.completed <timeout=5>
```

### UPDATE - 更新会话配置

**语法**：
- JSON 文件：`[PIS]UPDATE path/to/session.json`
- 清空上下文：`[PIS]UPDATE quit=true`
- 系统指令：`[PIS]UPDATE instructions="你是车载助手，请简洁回答"`

**示例**：
```dsl
# 从 JSON 文件加载完整 session 配置
[PIS]UPDATE {WORKPATH}/session_config.json

# 清空对话上下文（开始新轮次）
[PIS]UPDATE quit=true

# 设置系统指令/人设
[PIS]UPDATE instructions="你是一个简洁的车载语音助手"

# 组合：先清空再设指令
[PIS]UPDATE quit=true
[PIS]UPDATE instructions="请用一句话回答"
```

**回调断言类型**：`PISASRResult`、`PISToolCall`、`PISAVedioText`、`PISFinalResponse`、`PISEvent`、`ResponseTTS`、`ResponseTTSTemp`、`PISAIBSSpeechStart`、`PISAIBSSpeechEnd`、`PISAIBSWakeup`

**典型流程（经 AIBS 降噪）**：
```dsl
[PIS]CREATE url=ws://192.168.128.32:8765/realtime video_url=http://192.168.128.32:8057
[PIS]AIBSServer cmn
[PIS]AIBS_SET_CARTYPE "KAICHENG_TWO"
[PIS]AIBS_CREATE cmn
[PIS]AIBS_SET_WORK_MODE 1
[PIS]AIBS_START
[PIS]START
[PIS]VEDIO image={WORKPATH}/frame_001.png
[PIS]DATA {WORKPATH}/audio/test.wav
[PIS]WAIT type=response.done timeout=5
[EXP]PISASRResult asr:期望识别结果 <timeout=3>
[PIS]AIBS_STOP
[PIS]STOP
[PIS]FREE
```

**说明**：当前 DATA 送音频需经 AIBS 降噪，请按上述流程完整执行 AIBSServer → AIBS_CREATE → AIBS_START。需通过 `-C {CONFIGPATH}` 传入 decoder.conf，并通过 `--mongo_lib_path=lib/pisa` 指定 libAIBS_dynamic.so 所在目录。

## 🎛️ TSS客户端使用说明 (电信智慧屏)

`TSSClient`,用于电信智慧屏项目， 对应实现文件：`src/testsuite/NANO/client/TSSClient.py`，主要用于直接驱动 `libAIBS_dynamic.so` 完成会话启动、音频推流、唤醒词与语言配置等能力。

**命令前缀**：`[TSS]`

### 快速上手（推荐顺序）

```dsl
# 1) 启动服务（依赖 -C 传入 decoder.conf）
[TSS]START_SERVICE cmn

# 2) 设置车型（必须在 AIBS_CREATE 前）
[TSS]SET_CARTYPE "KAICHENG_TWO"

# 3) 创建客户端
[TSS]CREATE cmn

# 4) 可选：设置工作模式（0=NORMAL,1=WAKEUP,2=ASR...）
[TSS]SET_WORK_MODE 1

# 5) 启动会话
[TSS]START

# 6) 可选：设置引擎参数（支持分号批量）
[TSS]SET_PARAM ENGINE_PARAM_SR_REAL_TIME_RESULT 1

# 7) 送音频（支持 frame/delay/range）
[TSS]DATA {WORKPATH}/audio/test.wav frame=320 delay=1.0 range=[0,-1]

# 8) 停止会话并释放资源
[TSS]STOP
[TSS]FREE
```

### 指令说明（TSS专用）

| 指令 | 语法 | 说明 |
|------|------|------|
| `START_SERVICE` | `[TSS]START_SERVICE lang` | 启动 AIBS 服务，`lang` 常用 `cmn/eng/yue` |
| `SET_CARTYPE` | `[TSS]SET_CARTYPE "car_type"` | 设置设备类型，建议在 `CREATE` 前调用 |
| `CREATE` | `[TSS]CREATE lang` | 创建 AIBS 客户端并等待 init 成功回调 |
| `SET_WORK_MODE` | `[TSS]SET_WORK_MODE mode` | 设置工作模式，支持 0~7 |
| `START` | `[TSS]START` | 启动会话并等待 start 成功回调 |
| `STOP` | `[TSS]STOP` | 停止当前会话 |
| `DATA` | `[TSS]DATA audio [frame=320] [delay=1.0] [range=[0,-1]]` | 分帧送入音频；`delay=1.0` 为近实时推流 |
| `SET_PARAM` | `[TSS]SET_PARAM key value` | 设置 AIBS 参数（按 `AIBSEngineParam` 枚举名） |
| `SET_LANGUAGE_MODE` | `[TSS]SET_LANGUAGE_MODE cmn|eng|yue` | 切换语言模式 |
| `SET_WAKEUP_WORD` | `[TSS]SET_WAKEUP_WORD word threshold` | 设置唤醒词和阈值 |
| `SET_WAKEUP_ENABLE` | `[TSS]SET_WAKEUP_ENABLE word true|false` | 设置指定唤醒词是否启用 |
| `GET_WAKEUP_WORD` | `[TSS]GET_WAKEUP_WORD` | 获取当前唤醒词列表 |
| `FREE` | `[TSS]FREE` | 释放客户端并停止服务 |

### DATA 参数细节

- `frame`：每次送入 `process_data` 的字节数，默认 `320`（16k/16bit/单通道约 10ms）。
- `delay`：推流速度系数，`1.0` 为近实时，`0` 近似无延时全速发送。
- `range=[start,end]`：按秒切片发送，`end=-1` 表示发到音频末尾。

### 回调与断言关注点

`TSSClient` 会透出以下关键回调类型（通过统一回调池）：

- `SpeechStart`
- `SpeechEnd`
- `TSSAIBSWakeup`

其中 payload 会携带：

- `audio`：当前送测音频路径；
- `audiotime`：当前推流时间（秒，字符串）；
- `channel`：由 `speaker` 映射的通道号（`01h~04h` -> `0~3`）。

### 常见问题

- `CREATE 超时 / START 超时`：优先检查服务是否启动成功、配置文件路径是否正确。
- `DATA 无回调`：检查音频格式、`frame` 取值和 `range` 是否裁剪为空。
- `SET_ENGINE_PARAM 失败`：确认参数名与 `TSSClient.py` 中 `AIBSEngineParam` 枚举完全一致。

## 📋 指令兼容性表

| 指令类别 | TSA | SET | VOI | OMS | TTS | HWK | PST | TIA | CPL | PIS | NIS | NSE | SYS | EXP | TSR |
|----------|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|
| 基础指令 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| 引擎控制 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ |
| 系统设置 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ |
| 录音功能 | ✅ | ❌ | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| 语音输入 | ✅ | ❌ | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| 声纹功能 | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ |
| 配置状态 | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ |
| 日志功能 | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| 引擎参数 | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| SpeechEngine专用 | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| PSTT专用 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| TiTan专用 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| CarPlay专用 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| PISA专用 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 系统操作 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| 断言验证 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| TSR专用 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |

**注意**: 

- **HWK**: SpeechEngine客户端，支持离线识别和唤醒词检测
- **PST**: PSTT在线ASR服务客户端，支持单音频和批量处理
- **TIA**: TiTan WebSocket ASR服务客户端，支持并发处理
- **CPL**: CarPlay SDK客户端，支持唤醒词检测和VAD状态
- **PIS**: PISA 大模型全双工 WebSocket 客户端，支持语音+视觉多模态
- **NIS**: 日产项目AIBS客户端，指令与TSA相同
- **NSE**: 日产项目SET客户端，指令与SET相同
- **TSR**: Suite级别统计和报告生成，用于TEARDOWN阶段

## 🎯 最佳实践

### 1. 客户端选择原则
- **TSA**: 主要用于语音识别、声纹、TTS等核心功能测试
- **SET**: 用于系统设置和配置相关测试  
- **VOI**: 专用于语音输入功能测试
- **OMS**: 用于OMS相关功能测试
- **TTS**: 专用于文本转语音功能测试
- **HWK**: 用于SpeechEngine离线识别和唤醒词测试
- **PST**: 用于PSTT在线ASR服务测试
- **TIA**: 用于TiTan WebSocket ASR服务测试
- **CPL**: 用于CarPlay SDK功能测试
- **PIS**: 用于 PISA 大模型端到端测试（语音+视觉）
- **NIS**: 日产项目AIBS功能测试
- **NSE**: 日产项目SET功能测试
- **ENR**: ECNR降噪功能测试
- **TSS**: 电信智慧屏测试
- **SYS**: 用于系统级操作（服务管理、文件操作、报告管理等）
- **EXP**: 专用于结果断言验证（包括回调断言、API断言和文件断言）
- **TSR**: 用于Suite级别统计和报告生成

### 2. 指令执行顺序
```dsl
# 推荐的指令执行顺序
[SYS]PULL AIBSServer cmn {"brand":"0"}       # 1. 启动服务
[SYS]SLEEP 2                                # 2. 等待服务启动
# 可选：修改配置文件
[SYS]UPLOAD JSON {WORKPATH}/config.json param.value 100
[SYS]UPLOAD LINE {WORKPATH}/decoder.conf TIMEOUT 5000
[TSA]CREATE cmn com.autoai.vr.service_vrassistant   # 3. 创建客户端
[TSA]START 1                                # 4. 启动会话
[TSA]DATA audio.wav                         # 5. 发送数据
[EXP]cloudASRResult asr:期望结果 <timeout=3> # 6. 断言验证
# 可选：将关键文件添加到报告
[SYS]ALLURE TEXT {WORKPATH}/decoder.conf
[SYS]ALLURE CSV {WORKPATH}/result.csv
[TSA]STOP                                   # 7. 停止会话
[TSA]FREE                                   # 8. 释放资源
[SYS]KILL AIBSServer                        # 9. 清理服务
```

### 3. 错误处理
- 使用合适的超时时间进行断言
- 在测试结束后及时清理资源
- 使用环境变量提高用例可移植性
- 添加必要的延时确保操作完成

### 4. 调试技巧
- 使用`[SYS]PRINT`输出调试信息
- 利用日志功能记录关键操作
- 合理设置断言超时时间
- 在GDB模式下进行深度调试

---

**Write By Baihuidong 2025/10/20**
**Updated 2025/11/1 - 新增UPLOAD和ALLURE指令**
**Updated 2025/11/1 - 新增文件断言指令：FILEEXIT、FILESIZE、FILEMD5、FILEDIF**
**Updated 2025/12/20 - 新增HWK、PST、TIA、TSR、NIS、NSE客户端指令说明**
**Updated 2026/03/17 - 新增PIS（PISA大模型）客户端指令说明**