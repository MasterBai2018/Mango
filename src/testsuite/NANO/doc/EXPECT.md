# NANO DSL断言系统说明文档

NANO测试套件提供了强大而灵活的断言系统，支持对语音识别结果、API返回值、回调事件等进行自动化验证。本文档详细介绍断言的语法、类型、使用方法和最佳实践。

## 🎯 断言系统概述

### 核心特性
- **智能匹配**: 自动匹配回调结果与期望值
- **多通道支持**: 支持多通道场景的断言验证
- **字段匹配**: 支持对JSON数据的多字段精确匹配
- **比较操作**: 支持等值、大于、小于、包含等多种比较
- **实时验证**: 实时捕获和验证回调结果
- **超时等待**: 支持带超时的异步断言，使用信号量机制等待回调/结果到达
- **文件验证**: 支持文件存在性、大小、MD5值和JSON内容验证

### 断言语法
```dsl
[EXP]断言类型 [通道ID]期望字段1:期望值1;期望字段2:期望值2 <timeout=X>
```

## 📋 断言语法详解

### 基础语法结构

| 元素 | 说明 | 是否必需 | 示例 |
|:-----|------|----------|------|
| `[EXP]` | 断言指令标识 | ✅ 必需 | `[EXP]` |
| `[断言类型]` | 回调或API断言类型 | ✅ 必需 | `cloudASRResult` |
| `[通道ID]` | 指定通道编号 | ❌ 可选 | `[0]` |
| `期望字段` | 字段名:期望值 | ✅ 必需 | `asr:你好小白` |
| `<timeout=X>` | 超时等待时间（秒） | ❌ 可选 | `<timeout=5>` |

### 语法变体

#### 1. 立即断言（不等待）
```dsl
[EXP]断言类型 期望字段
```

#### 2. 带超时的等待断言
```dsl
[EXP]断言类型 期望字段 <timeout=5>      # 等待最多5秒
[EXP]断言类型 期望字段 <timeout=10>     # 等待最多10秒
[EXP]断言类型 期望字段 <timeout=-1>     # 无限等待，直到条件满足
```

#### 3. 多通道断言
```dsl
[EXP]断言类型 [0]期望字段    # 通道0
[EXP]断言类型 [1]期望字段    # 通道1
```

#### 4. 多字段断言
```dsl
[EXP]断言类型 字段1:值1;字段2:值2;字段3:值3
```

#### 5. 组合断言（多通道 + 超时）
```dsl
[EXP]断言类型 [0]字段1:值1;字段2:值2 <timeout=5>
```

## 🔊 回调断言类型

### ASR（语音识别）断言

#### cloudASRResult - 云端ASR识别结果
**触发条件**: 云端语音识别完成时

**常用字段**:

- `asr`: 识别文本
- `lang`: 识别语种
- `confidence`: 置信度
- `start`: 开始时间
- `end`: 结束时间

**使用示例**:
```dsl
# 基础文本断言
[EXP]cloudASRResult asr:今天天气怎么样

# 多字段断言
[EXP]cloudASRResult asr:播放音乐;lang:cmn

# 指定通道断言
[EXP]cloudASRResult [0]asr:你好小白
```

#### localASRResult - 本地ASR识别结果
**触发条件**: 本地语音识别完成时

**使用示例**:

```dsl
[EXP]localASRResult asr:打开空调
[EXP]localASRResult asr:关闭音乐;lang:cmn
```

#### ASRResult - 通用ASR识别结果
**触发条件**: ASR识别完成时（云端或本地）

**使用示例**:
```dsl
[EXP]ASRResult asr:天气查询
[EXP]ASRResult [1]asr:导航到家
```

#### ASRInputResult - ASR输入结果
**触发条件**: ASR输入处理完成时

**使用示例**:
```dsl
[EXP]ASRInputResult asr:语音输入测试
[EXP]ASRInputResult asr:文本转换;result:success
```

#### ASRResultTemp - ASR临时结果
**触发条件**: ASR识别过程中的中间结果

**使用示例**:
```dsl
[EXP]ASRResultTemp asr:你好
[EXP]ASRResultTemp asr:你好小白
```

#### ASRInputResultTemp - ASR输入临时结果
**触发条件**: ASR输入过程中的中间结果

**使用示例**:

```dsl
[EXP]ASRInputResultTemp asr:临时输入
```

### NLP（自然语言处理）断言

#### NLPResult - NLP意图识别结果
**触发条件**: 自然语言处理完成时

**常用字段**:
- `skill`: 技能领域
- `intention`: 意图类型
- `callback`: 回调信息
- `confidence`: 置信度

**使用示例**:
```dsl
# 基础意图断言
[EXP]NLPResult skill:WEATHER;intention:QUERY

# 包含回调信息
[EXP]NLPResult skill:MUSIC;intention:PLAY;callback:musicPlay

# 置信度断言
[EXP]NLPResult skill:NAVIGATION
```

### 声纹识别断言

#### startEnroll - 声纹注册开始
**触发条件**: 声纹注册流程开始时

**常用字段**:
- `userId`: 用户ID
- `result`: 操作结果
- `status`: 状态信息

**使用示例**:
```dsl
[EXP]startEnroll userId:user001;status:5
```

#### verifyVoiceprint - 声纹验证结果
**触发条件**: 声纹验证完成时

**常用字段**:
- `userId`: 用户ID
- `result`: 验证结果（match/nomatch）
- `confidence`: 匹配度
- `score`: 评分

**使用示例**:

```dsl
[EXP]verifyVoiceprint userId:user001;result:match
```

#### VoiceDetectionResult - 声纹检测结果
**触发条件**: 声纹检测完成时

**使用示例**:

```dsl
[EXP]VoiceDetectionResult detected:true;userId:user001
[EXP]VoiceDetectionResult detected:false
```

## 🔧 API断言类型

### 基础API断言

#### GET_VERSION_RET - 版本信息返回
**触发条件**: 调用`GET_VERSION`指令后

**常用字段**:

- 无

**使用示例**:

```dsl
# 调用接口
[TSA]GET_VERSION

#断言接口返回
[EXP]GET_VERSION_RET 3.7.0
```

### VR配置相关断言

#### WAKEUP_ALIAS_RET - 唤醒词设置返回
**触发条件**: 调用`SETVRCONFIG WAKEUP_ALIAS`后

**使用示例**:
```dsl
# 调用设置自定义唤醒词
[SET]SETVRCONFIG WAKEUP_ALIAS 你好小白 cmn

# 断言接口返回
[EXP]WAKEUP_ALIAS_RET -27
```

#### ACTIVE_INTERACTION_RET - 主动交互设置返回
**触发条件**: 调用`SETVRCONFIG ACTIVE_INTERACTION`后

**使用示例**:

```dsl
# VR设置客户端，调用VR设置接口
[SET]SETVRCONFIG ACTIVE_INTERACTION true cmn

# 断言接口返回
[EXP]ACTIVE_INTERACTION_RET 0
```

#### VR_OPTION_RET - VR选项设置返回
**触发条件**: 调用`SETVRCONFIG VR_OPTION`后

**使用示例**:
```dsl
# VR设置客户端，调用VR设置接口
[SET]SETVRCONFIG VR_OPTION enable cmn

# 断言接口返回
[EXP]VR_OPTION_RET 0
```

#### GET_VR_CONFIG_RET - VR配置查询返回
**触发条件**: 调用`GET_VR_CONFIG`后

**使用示例**:
```dsl
# VR设置客户端获取VRCONFIG
[SET]GET_VR_CONFIG VR_OPTION

# 断言返回值
[EXP]GET_VR_CONFIG_RET value:enable;code:0
```

#### GET_WAKEUP_WORD_RET - 唤醒词查询返回
**触发条件**: 调用`GET_WAKEUP_WORD`后

**使用示例**:

```dsl
# TSA获取唤醒词列表
[TSA]GET_WAKEUP_WORD

# 断言唤醒词列表
[EXP]GET_WAKEUP_WORD_RET word:你好小白;threshold:0.8
```

### 参数设置断言

#### AIBS_PARAM_SILENCE_DURATION_RET - 静音时长参数设置返回
**触发条件**: 调用`SET_PARAM AIBS_PARAM_SILENCE_DURATION`后

**使用示例**:

```dsl
[TSA]SET_PARAM AIBS_PARAM_SILENCE_DURATION 5000
[EXP]AIBS_PARAM_SILENCE_DURATION_RET 0
```

#### AIBS_PARAM_SR_VOICE_WAKEUP_RET - 声纹唤醒参数设置返回
**触发条件**: 调用`SET_PARAM AIBS_PARAM_SR_VOICE_WAKEUP`后

**使用示例**:
```dsl
[TSA]SET_PARAM AIBS_PARAM_SR_VOICE_WAKEUP 1
[EXP]AIBS_PARAM_SR_VOICE_WAKEUP_RET 0
```

### 声纹功能断言

#### START_SPEAKER_ENROLL_RET - 开始声纹注册返回
**触发条件**: 调用`START_SPEAKER_ENROLL`后

**使用示例**:
```dsl
[SET]START_SPEAKER_ENROLL user001 测试文本 1 0
[EXP]START_SPEAKER_ENROLL_RET 5
```

#### END_SPEAKER_ENROLL_RET - 结束声纹注册返回
**触发条件**: 调用`END_SPEAKER_ENROLL`后

**使用示例**:
```dsl
[SET]END_SPEAKER_ENROLL
[EXP]END_SPEAKER_ENROLL_RET 0
```

#### VERIFY_VOICEPRINT_RET - 声纹验证返回
**触发条件**: 调用`VERIFY_VOICEPRINT`后

**使用示例**:
```dsl
[TSA]VERIFY_VOICEPRINT user001 你好小白 0
[EXP]VERIFY_VOICEPRINT_RET 0
```

#### DELETE_SPEAKER_RET - 删除声纹返回
**触发条件**: 调用`DELETE_SPEAKER`后

**使用示例**:
```dsl
[TSA]DELETE_SPEAKER user001
[EXP]DELETE_SPEAKER_RET -1
```

#### GET_SPEAKERS_RET - 获取声纹列表返回
**触发条件**: 调用`GET_SPEAKERS`后

**使用示例**:
```dsl
[TSA]GET_SPEAKERS
[EXP]GET_SPEAKERS_RET user:001
```

#### GET_SPEAKER_INFO_RET - 获取声纹信息返回
**触发条件**: 调用`GET_SPEAKER_INFO`后

**使用示例**:
```dsl
[TSA]GET_SPEAKER_INFO user001
[EXP]GET_SPEAKER_INFO_RET userId:user001
```

#### SENSITIVE_WORD_CHECK_RET - 敏感词检测返回
**触发条件**: 调用`SENSITIVE_WORD_CHECK`后

**使用示例**:
```dsl
[TSA]SENSITIVE_WORD_CHECK 测试文本
[EXP]SENSITIVE_WORD_CHECK_RET 0
```

### 配置查询断言

#### GET_CONFIG_ITEM_RET - 配置项查询返回
**触发条件**: 调用`GET_CONFIG_ITEM`后

**使用示例**:

```dsl
[TSA]GET_CONFIG_ITEM {CONFIGPATH} debug_mode
[EXP]GET_CONFIG_ITEM_RET 0
```

#### GET_FOTA_STATUS_RET - FOTA状态查询返回
**触发条件**: 调用`GET_FOTA_STATUS`后

**使用示例**:
```dsl
[TTS]GET_FOTA_STATUS
[EXP]GET_FOTA_STATUS_RET 0
```

#### CLEAR_VR_CONFIG_RET - 清除VR配置返回
**触发条件**: 调用`CLEAR_VR_CONFIG`后

**使用示例**:
```dsl
[TSA]CLEAR_VR_CONFIG
[EXP]CLEAR_VR_CONFIG_RET 0
```

## 🔢 字段比较操作

### 支持的比较操作符

| 操作符 | 含义 | 使用示例 | 说明 |
|--------|------|----------|------|
| `:` | 等于 | `asr:你好小白` | 精确匹配 |
| `:>` | 大于 | `confidence:>80` | 数值大于比较 |
| `:<` | 小于 | `confidence:<50` | 数值小于比较 |
| `:>=` | 大于等于 | `score:>=0.8` | 数值大于等于 |
| `:<=` | 小于等于 | `threshold:<=0.9` | 数值小于等于 |
| `:!=` | 不等于 | `result:!=error` | 值不相等 |
| `:~` | 包含 | `text:~天气` | 字符串包含 |
| `:*` | 模糊等于 | `text:今天天气*` | 模糊匹配 |

### 比较操作示例

#### 数值比较
```dsl
# 置信度大于80
[EXP]cloudASRResult asr:天气查询;confidence:>80

# 评分小于0.5
[EXP]verifyVoiceprint score:<0.5;result:nomatch

# 阈值范围检查
[EXP]GET_WAKEUP_WORD_RET threshold:>=0.6;threshold:<=0.9
```

#### 字符串比较
```dsl
# 精确匹配
[EXP]ASRResult asr:你好小白

# 包含匹配
[EXP]cloudASRResult asr:~音乐

# 模糊匹配
[EXP]NLPResult tts:今天天气*

# 不等于匹配
[EXP]NLPResult] result:!=error
```

#### 布尔值比较
```dsl
# 布尔真值
[EXP]VoiceDetectionResult detected:true

# 布尔假值
[EXP]SENSITIVE_WORD_CHECK_RET isSensitive:false
```

## ⏱️ 超时等待断言

### 超时断言机制

NANO测试套件支持带超时的异步断言，使用**信号量机制**等待回调数据或API结果到达，适用于需要等待异步回调的测试场景。

### 超时参数说明

| timeout值 | 行为 | 使用场景 |
|-----------|------|----------|
| **不写** | 立即断言，不等待 | 同步操作或已知数据已到达 |
| **timeout=0** | 立即断言（同不写） | 显式声明立即断言 |
| **timeout=正数** | 等待指定秒数 | 异步回调场景，如语音识别、声纹验证 |
| **timeout=-1** | 无限等待 | 确保必须收到回调才继续 |

### 工作原理

#### 立即断言（无timeout）
```
执行断言 → 立即检查已收集的数据 → 匹配成功/失败 → 继续执行
```

#### 超时等待断言（有timeout）
```
执行断言 → 检查数据
    ├─ 已存在 → 匹配成功 → 继续执行
    └─ 不存在 → 等待信号量
        ├─ 收到回调 → 信号触发 → 匹配检查 → 继续执行
        └─ 超时 → 断言失败 → 报告错误
```

### 适用范围

超时断言支持**所有断言类型**：
- ✅ **JSON回调断言**: cloudASRResult、NLPResult、verifyVoiceprint等
- ✅ **API返回值断言**: GET_VERSION_RET、START_RET、SETVRCONFIG_RET等
- ✅ **文件断言**: FILEEXIT、FILESIZE、FILEMD5、FILEDIF

### 超时断言使用示例

#### 示例1：语音识别异步断言
```dsl
>>> 1
# 发送音频后，等待最多5秒钟接收ASR回调
[TSA]CREATE cmn com.autoai.vr.service_vrassistant
[TSA]START 1
[TSA]DATA TestAudio/audio/weather_query.wav

# 等待5秒，直到cloudASRResult回调到达
[EXP]cloudASRResult asr:今天天气怎么样;confidence:>80 <timeout=5>

# 等待5秒，直到NLPResult回调到达
[EXP]NLPResult skill:WEATHER;intention:QUERY <timeout=5>

[TSA]STOP
[TSA]FREE
<<<
```

#### 示例2：多通道超时断言
```dsl
>>> 1
[TSA]CREATE cmn com.autoai.vr.service_vrassistant
[TSA]START 4    # 启动4通道

[TSA]DATA TestAudio/audio/channel_4ch.wav

# 每个通道的断言都等待最多10秒
[EXP]cloudASRResult [0]asr:通道零测试 <timeout=10>
[EXP]cloudASRResult [1]asr:通道一测试 <timeout=10>
[EXP]cloudASRResult [2]asr:通道二测试 <timeout=10>
[EXP]cloudASRResult [3]asr:通道三测试 <timeout=10>

[TSA]STOP
[TSA]FREE
<<<
```

#### 示例3：无限等待断言
```dsl
>>> 1
# 声纹注册场景，必须等到注册完成回调
[SET]START_SPEAKER_ENROLL user001 测试文本 1 0
[TSA]DATA TestAudio/audio/enroll_voice.wav

# 无限等待，直到收到startEnroll回调
[EXP]startEnroll userId:user001;status:5 <timeout=-1>

[SET]END_SPEAKER_ENROLL
<<<
```

#### 示例4：API断言超时等待
```dsl
>>> 1
# API调用也支持超时断言
[TSA]CREATE cmn com.autoai.vr.service_vrassistant

# 等待3秒，确保CREATE返回
[EXP]CREATE_RET 0 <timeout=3>

[TSA]GET_VERSION
# 等待5秒，确保GET_VERSION返回
[EXP]GET_VERSION_RET 3.7.0 <timeout=5>

[TSA]FREE
<<<
```

#### 示例5：文件断言超时等待
```dsl
>>> 1
# 文件断言也支持超时等待（轮询检查）
[SYS]CMD wget http://example.com/lcs.zip -P {WORKPATH}

# 等待10秒，轮询检查文件是否下载完成
[EXP]FILEEXIT {WORKPATH}/lcs.zip 1 <timeout=10>

# 等待5秒，检查文件大小是否达到预期
[EXP]FILESIZE {WORKPATH}/lcs.zip > 1048576 <timeout=5>
<<<
```

### 超时断言最佳实践

#### ✅ 推荐做法

```dsl
# 1. 为异步操作设置合理的超时时间
[TSA]DATA audio.wav
[EXP]cloudASRResult asr:测试文本 <timeout=5>    # 语音识别通常3-5秒内完成

# 2. 关键场景使用无限等待确保不遗漏
[EXP]verifyVoiceprint result:match <timeout=-1>

# 3. API断言使用较短超时
[TSA]GET_VERSION
[EXP]GET_VERSION_RET 3.7.0 <timeout=2>          # API调用通常很快返回

# 4. 文件操作使用较长超时
[EXP]FILEEXIT {WORKPATH}/large_file.zip 1 <timeout=30>
```

#### ❌ 避免的做法

```dsl
# 1. 避免所有断言都使用超时（不必要的性能开销）
[EXP]START_RET 0 <timeout=10>                   # START立即返回，不需要超时

# 2. 避免超时时间过短导致误判
[TSA]DATA audio.wav
[EXP]cloudASRResult asr:测试 <timeout=0.5>      # 太短，可能来不及识别

# 3. 避免超时时间过长导致测试缓慢
[EXP]cloudASRResult asr:测试 <timeout=300>      # 5分钟太长，不合理
```

### 超时断言注意事项

1. **信号量机制**: 当回调到达时会立即触发信号，断言不必等到超时
2. **类型适用性**: 所有断言类型（JSON、API、FILE）都支持超时参数
3. **单位为秒**: timeout参数单位为秒，支持小数（如`<timeout=2.5>`表示2.5秒）
4. **性能考虑**: 只在异步场景使用超时断言，同步操作直接立即断言
5. **文件断言轮询**: 文件断言使用轮询机制（每0.2秒检查一次），适合等待文件生成/下载场景

## 📺 多通道断言

### 通道语法
```dsl
[EXP]断言类型 [通道ID]期望字段
```

### 通道使用场景
- **多麦克风阵列**: 不同方向的语音输入
- **立体声处理**: 左右声道分别处理
- **并发测试**: 同时测试多个音频流

### 多通道示例
```dsl
>>> 1
# 拉起本地服务
[SYS]PULL         AIBSServer cmn {"brand":"0"}
[SYS]PULL         LCSEngine cmn
[SYS]PULL         SpeechEngine cmn

# 多通道并发测试
[TSA]CREATE cmn com.autoai.vr.service_vrassistant
[TSA]START 4    # 启动4通道

# 发送不同通道的音频
[TSA]DATA TestAudio/audio/channel_4ch.wav

# 分别断言各通道结果
[EXP]cloudASRResult [0]asr:通道零测试
[EXP]cloudASRResult [1]asr:通道一测试
[EXP]cloudASRResult [2]asr:通道二测试
[EXP]cloudASRResult [3]asr:通道三测试

[TSA]STOP
[TSA]FREE
<<<
```

## 🧪 复合断言场景

### 场景1：完整语音识别流程断言
```dsl
>>> 1
# 拉起本地服务
[SYS]PULL         AIBSServer cmn {"brand":"0"}
[SYS]PULL         LCSEngine cmn
[SYS]PULL         SpeechEngine cmn

# 端到端语音识别断言
[TSA]CREATE cmn com.autoai.vr.service_vrassistant
[TSA]START 1

[TSA]DATA {WORKPATH}/audio/weather_query.wav

# ASR结果断言
[EXP]cloudASRResult asr:今天天气怎么样;lang:cmn;confidence:>85

# NLP意图断言
[EXP]NLPResult skill:WEATHER;intention:QUERY

[TSA]STOP
[TSA]FREE
<<<
```

### 场景2：声纹注册验证完整流程
```dsl
>>> 1
# 拉起本地服务
[SYS]PULL         AIBSServer cmn {"brand":"0"}
[SYS]PULL         LCSEngine cmn
[SYS]PULL         SpeechEngine cmn

# 声纹功能完整测试
[TSA]CREATE cmn com.autoai.vr.service_vrassistant
[SET]CREATE cmn com.pachira.set

[TSA]EVENT        {"source":"TSA","type":"VehicleInfo","data":{"vin":"589CC5478CDA4439BF3F2EA6F8BC837DMongo","brand":"Lexus-2S","model":"T0001","originImei":"","imei":"","mmVersion":"","tsaVersion":"Mongo2.0.0"}}

# 第一次注册声纹
[SET]START_SPEAKER_ENROLL user001 你好雷克萨斯，登录我的个人中心 1 0
[TSA]DATA         TestAudio/你好雷克萨斯登录我的个人中心.wav frame=320 delay=1
[EXP]startEnroll  status:5;channelId:0

# 第二次注册声纹
[SET]START_SPEAKER_ENROLL user001 你好雷克萨斯，登录我的声纹记忆 2 0
[TSA]DATA         TestAudio/你好雷克萨斯登录我的声纹记忆.wav frame=320 delay=1
[EXP]startEnroll  status:5;channelId:0

# 第三次注册声纹
[SET]START_SPEAKER_ENROLL user001 你好雷克萨斯，我要登录声纹账号 3 0
[TSA]DATA         TestAudio/你好雷克萨斯我要登录声纹账号.wav frame=320 delay=1
[EXP]startEnroll  status:5;channelId:0

# 第四次注册声纹
[SET]START_SPEAKER_ENROLL user001 你好雷克萨斯，我要登录个人中心 4 0    # 注册用户声纹
[TSA]DATA         TestAudio/你好雷克萨斯我要登录个人中心.wav frame=320 delay=1
[EXP]startEnroll  status:5;channelId:0

# 第五次注册声纹
[SET]START_SPEAKER_ENROLL user001 你好雷克萨斯，声纹登录个人中心 5 0    # 注册用户声纹
[TSA]DATA         TestAudio/你好雷克萨斯声纹登录个人中心.wav frame=320 delay=1
[EXP]startEnroll  status:5;channelId:0

# 调用结束声纹接口
[SET]END_SPEAKER_ENROLL

# 等待2秒
[SYS]SLEEP 2

# 调用验证声纹接口
[SET]VERIFY_VOICEPRINT user001 你好雷克萨斯，登录我的个人中心 0

# 获取声纹列表接口
[SET]GET_SPEAKERS

# 发生声纹列表事件
[SET]VREVENT {"source":"TSA","type":"VoiceAccountList","data":{"voiceAccountList":[{"voicePrintId":"10001","nickname":"晓红"}]}}

# 发送音频
[TSA]DATA         TestAudio/SDK/Sre_Audio/audio_new/user01/single_audio/你好雷克萨斯登录我的个人中心.wav frame=320 delay=1

# 停止引擎
[TSA]STOP

# 杀死服务
[SYS]KILL   LCSEngine
[SYS]KILL   SpeechEngine
[SYS]KILL   AIBSServer
<<<
```

### 场景3：多API连续调用断言
```dsl
>>> 1
# 系统状态检查
[TSA]CREATE cmn com.autoai.vr.service_vrassistant

# 获取版本
[TSA]GET_VERSION
[EXP]GET_VERSION_RET 3.7.0

# 设置参数
[TSA]SET_PARAM AIBS_PARAM_SILENCE_DURATION 3000
[EXP]AIBS_PARAM_SILENCE_DURATION_RET 0

# 配置VR
[TSA]SETVRCONFIG VR_OPTION enable cmn
[EXP]VR_OPTION_RET 0

# 查询配置
[TSA]GET_VR_CONFIG VR_OPTION
[EXP]GET_VR_CONFIG_RET 0

[TSA]FREE
<<<
```

## 🧹 断言上下文管理

### CLEAR_ASSERT - 清空断言上下文

在Case执行过程中，如果存在多个相同类型的操作（如连续播放多个音频），可能会导致断言匹配顺序混乱。`CLEAR_ASSERT` 命令用于在关键节点清空断言上下文，确保后续断言不会匹配到之前的历史数据。

**语法**: `[SYS]CLEAR_ASSERT [类型]`

| 参数 | 说明 | 示例 |
|------|------|------|
| 无参数/`ALL` | 清空所有断言数据（回调+API） | `[SYS]CLEAR_ASSERT` |
| `CALLBACK` | 只清空回调数据 | `[SYS]CLEAR_ASSERT CALLBACK` |
| `API` | 只清空API数据 | `[SYS]CLEAR_ASSERT API` |
| `<具体类型>` | 清空指定类型的数据 | `[SYS]CLEAR_ASSERT ASRResult` |

**使用示例**:
```dsl
>>> 1
# 场景：多音频连续播放，确保断言匹配正确

# 第一段音频测试
[TSA]DATA TestAudio/audio1.wav
[EXP]cloudASRResult asr:你好 <timeout=5>

# 清空断言上下文，防止干扰后续断言
[SYS]CLEAR_ASSERT

# 第二段音频测试
[TSA]DATA TestAudio/audio2.wav
[EXP]cloudASRResult asr:天气 <timeout=5>

# 只清空ASR类型的回调数据
[SYS]CLEAR_ASSERT cloudASRResult

# 第三段音频测试
[TSA]DATA TestAudio/audio3.wav
[EXP]cloudASRResult asr:导航 <timeout=5>
<<<
```

**适用场景**:
- Case中有多个相同类型的操作，需要阶段性隔离
- 调试时想重新开始断言匹配
- 防止历史数据污染后续断言

---

## 🛠️ 调试和故障排除

### 常见断言错误

#### 1. 超时错误
**现象**: 断言超时，未收到期望的回调
**原因**:

- 音频文件路径错误
- 服务未正常启动
- 期望值不匹配

**解决方案**:
```dsl
# 增加调试信息
[SYS]PRINT 开始语音识别测试
[TSA]DATA {WORKPATH}/audio/test.wav
[SYS]PRINT 等待ASR结果
[EXP]cloudASRResult asr:测试文本
[SYS]PRINT ASR断言完成
```

#### 2. 字段不匹配
**现象**: 收到回调但字段值不匹配
**原因**:
- 期望值拼写错误
- 大小写不匹配
- 数值类型错误

**解决方案**:
```dsl
# 使用包含匹配降低匹配要求
[EXP]cloudASRResult asr:~关键词

# 或使用不等于排除错误值
[EXP]cloudASRResult asr:!=打开车窗
```

#### 3. 通道错误
**现象**: 多通道场景下通道不匹配
**解决方案**:

```dsl
# 明确指定通道
[EXP]cloudASRResult [0]asr:通道0结果 <timeout=3>
[EXP]cloudASRResult [1]asr:通道1结果 <timeout=3>
```

### 调试技巧

#### 1. 使用宽松断言进行调试
```dsl
# 先使用宽松条件确认收到回调
[EXP]cloudASRResult lang:cmn    # 只检查语种

# 再逐步收紧条件
[EXP]cloudASRResult asr:~关键词;lang:cmn

# 最后使用精确匹配
[EXP]cloudASRResult asr:完整的期望文本;lang:cmn
```

#### 2. 分步验证
```dsl
# 分别验证不同阶段的结果
[TSA]DATA audio.wav
[EXP]cloudASRResult lang:cmn          # 先验证有ASR结果
[EXP]NLPResult skill:WEATHER         # 再验证NLP处理
```

## 📊 断言最佳实践

### 1. ✅ 推荐做法
```dsl
# 使用多级断言确保准确性
[EXP]cloudASRResult asr:天气查询;confidence:>80;lang:cmn

# API断言立即检查
[TSA]GET_VERSION
[EXP]GET_VERSION_RET 3.7.0

# 合理使用包含匹配
[EXP]cloudASRResult asr:~关键词      # 降低匹配要求
```

### 2. ❌ 避免的做法
```dsl
# 避免过于严格的匹配
[EXP]cloudASRResult asr:完整的很长的期望文本并且包含标点符号

# 避免在没有触发条件的情况下断言
[EXP]cloudASRResult asr:结果         # 没有发送音频就断言

# 避免不清理资源
[TSA]START 1
[EXP]cloudASRResult asr:结果

# 忘记调用STOP和FREE
```

## 📚 断言类型速查表

### 🎤 识别回调断言类型
| 断言类型 | 触发条件 | 可用字段 | 字段说明 |
|----------|----------|----------|----------|
| `ASRResult` | 最终识别结果 | source, type, asr, start, end, channelId, lang | asr=识别文本, lang=语种, start/end=时间戳 |
| `cloudASRResult` | 云端识别完成 | source, type, asr, start, end, channelId, lang | 同ASRResult |
| `localASRResult` | 本地识别完成 | source, type, asr, start, end, channelId, lang | 同ASRResult |
| `ASRResultTemp` | 临时识别结果 | asr, type, start, end, channelId, location, text | 中间识别结果，实时更新 |
| `ASRInputResult` | 语音输入最终结果 | type, asr, start, end, lang, channelId | 语音输入法专用 |
| `ASRInputResultTemp` | 语音输入临时结果 | type, asr, start, end, lang, channelId | 语音输入法实时结果 |

### 🧠 理解回调断言类型  
| 断言类型 | 触发条件 | 可用字段 | 字段说明 |
|----------|----------|----------|----------|
| `NLPResult` | NLP理解完成 | text, skill, intention, tts, start, end, channelId, dirCallbackType等等. | skill=技能名称, intention=意图名称, text=识别文本, directives相关字段=指令信息 |

### 👋 HiCar唤醒检测回调断言类型
| 断言类型 | 触发条件 | 可用字段 | 字段说明 |
|----------|----------|----------|----------|
| `HICARWakeup` | 唤醒词检测成功 | source, type, text, lang, channelId, keywordType | text=唤醒词文本, keywordType=唤醒词类型 |

### 👤 声纹识别回调断言类型
| 断言类型 | 触发条件 | 可用字段 | 字段说明 |
|----------|----------|----------|----------|
| `startEnroll` | 声纹注册开始 | type, status, user_id, message, channelId | user_id=用户ID, status=注册状态 |
| `verifyVoiceprint` | 声纹验证完成 | type, status, user_id, message, channelId | user_id=用户ID, status=验证结果 |

### ⚙️ API调用断言类型

#### 基础API断言
| 断言类型 | 触发指令 | 断言值说明 |
|----------|----------|----------|
| `CREATE_RET` | CREATE | 返回码：0=成功，非0=失败 |
| `START_RET` | START | 返回码：0=成功，非0=失败 |
| `STOP_RET` | STOP | 返回码：0=成功，非0=失败 |
| `FREE_RET` | FREE | 返回码：0=成功，非0=失败 |
| `DATA_RET` | DATA | 返回码：0=成功，非0=失败 |
| `EVENT_RET` | EVENT | 返回码：0=成功，非0=失败 |
| `CANCEL_RET` | CANCEL | 返回码：0=成功，非0=失败 |
| `GET_VERSION_RET` | GET_VERSION | 返回值：版本信息 |

#### 语音引擎控制API断言
| 断言类型 | 触发指令 | 断言值说明 |
|----------|----------|----------|
| `PAUSE_RET` | PAUSE | 返回码：0=成功，非0=失败 |
| `RESUME_RET` | RESUME | 返回码：0=成功，非0=失败 |
| `START_RECORD_RET` | START_RECORD | 返回码：0=成功，非0=失败 |
| `STOP_RECORD_RET` | STOP_RECORD | 返回码：0=成功，非0=失败 |

#### 配置相关API断言  
| 断言类型 | 触发指令 | 断言值说明 |
|----------|----------|----------|
| `SETVRCONFIG_RET` | SETVRCONFIG | 返回码：设置VR设置项返回值 |
| `CLEAR_VR_CONFIG_RET` | CLEAR_VR_CONFIG | 返回码：0=成功，非0=失败 |
| `GET_VR_CONFIG_RET` | GET_VR_CONFIG | 返回值：VRConfig Json字符串 |
| `GET_CONFIG_ITEM_RET` | GET_CONFIG_ITEM | 返回值：VRConfig Json字符串 |
| `SET_PARAM_RET` | SET_PARAM | 返回码：0=成功，非0=失败 |

#### 唤醒词相关API断言
| 断言类型 | 触发指令 | 断言值说明 |
|----------|----------|----------|
| `SET_WAKEUP_WORD_RET` | SET_WAKEUP_WORD | 返回码：设置唤醒词状态码 |
| `SET_WAKEUP_ENABLE_RET` | SET_WAKEUP_ENABLE | 返回码：设置唤醒词状态码 |
| `GET_WAKEUP_WORD_RET` | GET_WAKEUP_WORD | 返回值：唤醒词列表 |

#### 声纹相关API断言
| 断言类型 | 触发指令 | 断言值说明 |
|----------|----------|----------|
| `START_SPEAKER_ENROLL_RET` | START_SPEAKER_ENROLL | 返回码：0=成功，非0=失败 |
| `END_SPEAKER_ENROLL_RET` | END_SPEAKER_ENROLL | 返回码：0=成功，非0=失败 |
| `RECOGNIZE_SPEAKER_RET` | RECOGNIZE_SPEAKER | 返回值：声纹验证UserID |
| `VERIFY_VOICEPRINT_RET` | VERIFY_VOICEPRINT | 返回码：0=成功，非0=失败 |
| `CANCEL_VERIFY_VOICEPRINT_RET` | CANCEL_VERIFY_VOICEPRINT | 返回码：0=成功，非0=失败 |
| `DELETE_SPEAKER_RET` | DELETE_SPEAKER | 返回码：0=成功，非0=失败 |
| `GET_SPEAKER_INFO_RET` | GET_SPEAKER_INFO | 返回值：接口返回字符串 |
| `GET_SPEAKERS_RET` | GET_SPEAKERS | 返回码：接口返回字符串 |
| `GET_ENROLL_TEXT_RET` | GET_ENROLL_TEXT | 返回码：接口返回字符串 |
| `SENSITIVE_WORD_CHECK_RET` | SENSITIVE_WORD_CHECK | 返回码：接口返回状态码 |

#### VR设置相关API断言
| 断言类型 | VR配置项 | 断言值说明 |
|----------|----------|----------|
| `VR_OPTION_RET` | VR_OPTION | 返回码：VR状态码 |
| `WAKEUP_ALIAS_RET` | WAKEUP_ALIAS | 返回码：设置自定义唤醒词返回状态码 |
| `DIALOGUE_LANGUAGE_RET` | DIALOGUE_LANGUAGE | 返回码：设置语种接口 |
| `VOICE_WAKEUP_OPTION_RET` | VOICE_WAKEUP_OPTION | 返回码：0=成功，非0=失败 |
| `WAKEUP_ENABLE_RET` | WAKEUP_ENABLE | 返回码：设置唤醒词生效状态码 |

## 📁 文件断言类型

NANO测试套件新增了4种文件断言类型，用于验证文件的状态和内容。这些断言类型不依赖回调或API调用，直接对文件系统进行操作。

### FILEEXIT - 文件存在性断言
**语法**: `[EXP]FILEEXIT file_path [expected_exists]`

**说明**: 
- 检查文件是否存在
- `expected_exists`: `1`表示期望存在，`0`表示期望不存在（默认值为`1`）

**使用示例**:
```dsl
# 验证文件存在
[EXP]FILEEXIT {WORKPATH}/lcs.zip 1

# 验证文件不存在
[EXP]FILEEXIT {WORKPATH}/temp.log 0

# 使用默认值（默认为1，即期望存在）
[EXP]FILEEXIT {WORKSPACE}/result.json
```

**应用场景**:
- 验证下载的文件是否成功
- 验证生成的文件是否存在
- 验证临时文件是否已清理

### FILESIZE - 文件大小断言
**语法**: `[EXP]FILESIZE file_path operator expected_size`

**说明**:
- 检查文件大小是否符合期望
- `operator`: 比较操作符（`>`大于、`<`小于、`=`等于）
- `expected_size`: 期望的文件大小（字节）

**使用示例**:
```dsl
# 验证文件大小大于1MB
[EXP]FILESIZE {WORKPATH}/lcs.zip > 1000000

# 验证文件大小小于1KB
[EXP]FILESIZE {WORKPATH}/small.txt < 1024

# 验证文件大小等于特定值
[EXP]FILESIZE {WORKSPACE}/data.bin = 2048
```

**应用场景**:
- 验证文件下载是否完整
- 验证压缩文件大小是否合理
- 验证日志文件大小是否超限

### FILEMD5 - 文件MD5值断言
**语法**: `[EXP]FILEMD5 file_path = expected_md5`

**说明**:
- 计算文件的MD5哈希值并与期望值比较
- MD5比较不区分大小写
- 文件不存在则断言失败

**使用示例**:
```dsl
# 验证文件MD5值
[EXP]FILEMD5 {WORKPATH}/lcs.zip = 1921u2u192u1921212

# MD5值不区分大小写
[EXP]FILEMD5 {WORKSPACE}/binary.dat = ABC123DEF456

# 验证下载文件的完整性
[EXP]FILEMD5 {WORKPATH}/download.zip = 5d41402abc4b2a76b9719d911017c592
```

**应用场景**:
- 验证文件完整性（确保文件未被损坏）
- 验证文件版本一致性
- 验证文件是否被修改

### FILEDIF - 文件内容断言（JSON）
**语法**: `[EXP]FILEDIF JSON file_path json_path_expr`

**说明**:
- 检查JSON文件中指定路径的值是否等于期望值
- 支持嵌套对象路径（使用`.`分隔）
- 支持数组索引（使用`[index]`）
- 自动进行数值类型转换（整数、浮点数）
- 目前仅支持JSON格式文件

**JSON路径表达式格式**:
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

**应用场景**:
- 验证配置文件修改是否生效
- 验证JSON配置中的状态值
- 验证测试结果文件中的字段值
- 与`[SYS]UPLOAD`指令配合使用，验证配置更新结果

**文件断言完整示例**:
```dsl
>>> 1
# 1. 验证下载的文件存在
[EXP]FILEEXIT {WORKPATH}/lcs.zip 1

# 2. 验证文件大小符合预期（大于1MB）
[EXP]FILESIZE {WORKPATH}/lcs.zip > 1048576

# 3. 验证文件MD5确保完整性
[EXP]FILEMD5 {WORKPATH}/lcs.zip = abc123def456789

# 4. 修改配置文件
[SYS]UPLOAD JSON {WORKPATH}/config.json data.timeout 5000

# 5. 验证配置文件修改是否生效
[EXP]FILEDIF JSON {WORKPATH}/config.json data.timeout=5000

# 6. 验证嵌套数组字段
[EXP]FILEDIF JSON {WORKPATH}/daemon_tag.json data.shsh[0].txt.status=0

# 7. 验证文件不存在（清理验证）
[EXP]FILEEXIT {WORKPATH}/temp.log 0
<<<
```

**文件断言注意事项**:
1. **环境变量支持**: 所有文件路径都支持环境变量（如`{WORKPATH}`、`{WORKSPACE}`等），会在解析时自动替换
2. **文件不存在处理**: 如果文件不存在，FILESIZE、FILEMD5、FILEDIF都会失败，并给出明确的错误信息
3. **路径有效性**: JSON路径必须存在，否则断言会失败
4. **类型转换**: FILEDIF会自动进行数值类型转换（整数、浮点数），但字符串比较区分大小写
5. **性能考虑**: FILEMD5需要读取整个文件计算哈希值，大文件可能耗时较长

---

### SUM - 查找回调信息匹配个数
**语法**: `[EXP]SUM [通道数(可以省略)]回调对应的关键字 count == 1`
```
**应用场景**:
- 查找对应字段个数

**支持类型**:
- 计算比较类支持符号[==，>=,<=]
- 回调支持填写参数 ASRResult localASRResult ，NLPResult, SpeechWakeup

### 实例
**语法**: `[EXP]SUM [0]ASRResult count == 1`
          `[EXP]SUM ASRResult count == 1 (通道省略)`
          `[EXP]SUM [0,1,2,3]ASRResult count == 1 `
```

**NANO断言系统为语音SDK测试提供了强大而灵活的验证能力，正确使用断言是确保测试质量的关键！**

**Write By Baihuidong 2025/10/20**
**Updated 2025/11/07 - 新增超时断言功能：支持 `<timeout=X>` 语法，使用信号量机制等待异步回调，适用于所有断言类型**
**Updated 2025/10/27 - 新增文件断言类型：FILEEXIT、FILESIZE、FILEMD5、FILEDIF**
**Updated 2026/01/20 - 新增断言上下文管理：`[SYS]CLEAR_ASSERT` 命令，用于清空断言数据，防止匹配混乱**