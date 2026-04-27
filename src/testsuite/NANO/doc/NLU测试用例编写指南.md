# 📚 NANO NLU 测试用例编写指南

本文档详细介绍如何编写NANO框架的NLU（自然语言理解）测试用例，包括MGO格式规范、DSL语法、断言系统、Fixture机制以及最佳实践。

---

## 📖 目录

1. [概述](#1-概述)
2. [文件格式说明](#2-文件格式说明)
3. [测试用例结构](#3-测试用例结构)
4. [DSL指令详解](#4-dsl指令详解)
5. [断言系统](#5-断言系统)
6. [Fixture系统](#6-fixture系统)
7. [YAML到MGO转换](#7-yaml到mgo转换)
8. [编写最佳实践](#8-编写最佳实践)
9. [完整示例](#9-完整示例)

---

## 1. 概述

### 1.1 什么是NANO NLU测试

NANO NLU测试用于验证语音SDK的自然语言理解能力，通过发送文本指令并断言NLP返回结果来验证技能（skill）和意图（intention）的正确性。

### 1.2 测试场景

NLU测试覆盖多种技能领域：

| 技能领域 | 说明 | 示例 |
|---------|------|------|
| NAVI | 导航技能 | 导航回家、导航去天安门 |
| WEATHER | 天气查询 | 今天天气怎么样 |
| Calculate | 计算器 | 1加1等于几 |
| Media | 媒体播放 | 播放周杰伦的歌 |
| Phone | 电话拨打 | 打电话给张三 |
| AppControl | 应用控制 | 打开系统设置 |
| Schedule | 日程管理 | 创建日程 |
| VoicePrint | 声纹识别 | 声纹注册 |

### 1.3 目录结构

```
TestCase/nano/24MM/NLU/
├── cmn/                          # 中文测试用例
│   ├── Calculate/                # 计算器技能
│   │   └── Calculate_Offline.mgo
│   ├── Media/                    # 媒体技能
│   ├── NAVI/                     # 导航技能
│   ├── QueryWeather/             # 天气技能
│   ├── Voiceprint/               # 声纹技能
│   └── SmokeCase_text.mgo        # 冒烟测试
└── eng/                          # 英文测试用例
    └── ...
```

---

## 2. 文件格式说明

### 2.1 MGO文件格式

NANO测试用例使用`.mgo`后缀的DSL文件，特点如下：

- **声明式语法**：易于阅读和维护
- **Block结构**：使用`>>>`和`<<<`标记代码块
- **客户端标识**：使用`[XXX]`标识不同客户端

### 2.2 文件结构

```dsl
######################################################################
# 文件头注释
# 描述测试用例的用途、语言、Case数量等
######################################################################

>>> SETUP
# 前置初始化操作（启动服务、创建客户端等）
<<<

>>> TEARDOWN
# 后置清理操作（释放客户端、杀死服务等）
<<<

# Case 1: 测试用例名称
>>>
# 测试指令
<<<

# Case 2: 另一个测试用例
>>>
# 测试指令
<<<
```

---

## 3. 测试用例结构

### 3.1 单个Case的标准结构

每个NLU测试用例遵循以下结构：

```dsl
# Case N: 用例描述
>>>
[TSA]START        1                    # 启动引擎（1表示单通道）
[TSA]FREEWAKEUP   1                    # 释放唤醒状态
[TSA]STRATEGY     0                    # 设置策略（0=离线, 1=在线, 2=纯在线）
[TSA]INPUTEVENT   VehicleInfo          # 发送输入事件（可选）
[TSA]TEXT         今天天气怎么样        # 发送文本输入
[EXP]NLPResult    skill:WEATHER;intention:queryWeather    <timeout=2>  # 断言NLP结果
[TSA]STOP                              # 停止引擎
<<<
```

### 3.2 多轮对话结构

多轮对话需要依次发送文本和CALLBACK：

```dsl
>>>
[TSA]START        1
[TSA]FREEWAKEUP   1
[TSA]STRATEGY     1
[TSA]INPUTEVENT   NaviLocationStatus

# 第一轮：用户说"导航去天安门"
[TSA]TEXT         导航去天安门
[EXP]NLPResult    skill:NAVI;intention:naviPlanRouteToDest    <timeout=2>

# 模拟搜索结果回调
[TSA]CALLBACK     default    data.result.searchData.poiList:TestCase/.../poiList_Num3.json
[EXP]NLPResult    skill:NAVI;intention:keywordSearchCallback    <timeout=2>

# 第二轮：用户选择"第一个"
[TSA]TEXT         第一个
[EXP]NLPResult    skill:NAVI;intention:naviTextSelectedByIndex    <timeout=2>

# 模拟规划路线回调
[TSA]CALLBACK     default
[EXP]NLPResult    skill:NAVI;intention:naviPlanRouteCallback    <timeout=2>

[TSA]STOP
<<<
```

---

## 4. DSL指令详解

### 4.1 客户端类型

| 客户端 | 标识 | 说明 |
|--------|------|------|
| TSA | `[TSA]` | 语音助手客户端（主要NLU测试客户端） |
| SET | `[SET]` | VR设置客户端 |
| SYS | `[SYS]` | 系统操作客户端 |
| EXP | `[EXP]` | 断言客户端 |
| VOI | `[VOI]` | 声纹客户端 |
| TTS | `[TTS]` | TTS客户端 |

### 4.2 核心TSA指令

#### 4.2.1 CREATE - 创建客户端

```dsl
[TSA]CREATE       cmn com.autoai.vr.service_vrassistant
```

**参数说明**：
- `cmn/eng`：语言代码（中文/英文）
- `appid`：应用标识

#### 4.2.2 START - 启动引擎

```dsl
[TSA]START        1
```

**参数说明**：
- 数字：通道数（1=单通道, 4=四通道）

#### 4.2.3 STRATEGY - 设置策略

```dsl
[TSA]STRATEGY     0
```

**策略值说明**：
| 值 | 含义 |
|----|------|
| 0 | 离线模式 |
| 1 | 在线模式（先在线后离线） |
| 2 | 纯在线模式 |

#### 4.2.4 FREEWAKEUP - 释放唤醒

```dsl
[TSA]FREEWAKEUP   1
```

- `1`：释放唤醒状态，允许直接输入

#### 4.2.5 INPUTEVENT - 发送输入事件

```dsl
[TSA]INPUTEVENT   VehicleInfo
[TSA]INPUTEVENT   NaviLocationStatus
[TSA]INPUTEVENT   NavigateStatus
```

**常用事件类型**：
| 事件 | 说明 |
|------|------|
| VehicleInfo | 车辆信息事件 |
| NaviLocationStatus | 导航位置状态 |
| NavigateStatus | 导航状态 |
| NaviHomeStatus | 家地址状态 |
| PhoneBluetooth | 蓝牙电话状态 |
| PhoneBook | 电话簿事件 |
| MediaStatus | 媒体状态 |
| HiCarStatus | HiCar状态 |
| AppStatus | 应用状态 |
| TypeList | 类型列表 |

#### 4.2.6 TEXT - 发送文本

```dsl
[TSA]TEXT         今天天气怎么样
```

**说明**：模拟用户语音输入的文本，触发NLU理解流程

#### 4.2.7 CALLBACK - 发送回调

```dsl
# 默认回调
[TSA]CALLBACK     default

# 带数据的回调
[TSA]CALLBACK     default    data.result.code:0

# 引用JSON文件的回调
[TSA]CALLBACK     default    data.result.searchData.poiList:TestCase/caselist/MongoCase/events/Public/poiList_Num3.json
```

**用途**：模拟外部系统（如导航App）返回的callback事件

#### 4.2.8 STOP / FREE - 停止和释放

```dsl
[TSA]STOP    # 停止当前会话
[TSA]FREE    # 释放客户端资源
```

### 4.3 系统指令 [SYS]

#### 4.3.1 PULL - 拉起服务

```dsl
[SYS]PULL         AIBSServer cmn {"brand":"0"}
[SYS]PULL         LCSEngine cmn
[SYS]PULL         SpeechEngine cmn
```

#### 4.3.2 KILL - 杀死服务

```dsl
[SYS]KILL   SpeechEngine
[SYS]KILL   LCSEngine
[SYS]KILL   AIBSServer
```

#### 4.3.3 SLEEP - 等待

```dsl
[SYS]SLEEP 2    # 等待2秒
```

#### 4.3.4 CLEAR_ASSERT - 清空断言上下文

```dsl
[SYS]CLEAR_ASSERT              # 清空所有断言数据
[SYS]CLEAR_ASSERT CALLBACK     # 只清空回调数据
[SYS]CLEAR_ASSERT NLPResult    # 清空指定类型数据
```

### 4.4 VR设置指令 [SET]

```dsl
[SET]CREATE       cmn com.autoai.vrsetting
[SET]SETVRCONFIG  DIALOGUE_LANGUAGE cmn    # 设置对话语言
[SET]FREE
```

---

## 5. 断言系统

### 5.1 断言语法

```dsl
[EXP]断言类型 期望字段1:期望值1;期望字段2:期望值2 <timeout=X>
```

### 5.2 NLPResult断言

NLPResult是NLU测试的核心断言类型：

```dsl
# 基础断言
[EXP]NLPResult    skill:WEATHER;intention:queryWeather    <timeout=2>

# 多字段断言
[EXP]NLPResult    skill:NAVI;intention:naviPlanRouteToDest;directivesType:NaviDIR.keywordSearch    <timeout=2>

# 带TTS断言
[EXP]NLPResult    skill:NAVI;intention:currentLocationCallback;tts:当前位于*    <timeout=2>

# 模糊匹配
[EXP]NLPResult    skill:WEATHER;intention:queryWeather;tts:北京*    <timeout=2>
```

### 5.3 常用断言字段

| 字段 | 说明 | 示例 |
|------|------|------|
| `skill` | 技能名称 | `skill:NAVI` |
| `intention` | 意图名称 | `intention:queryWeather` |
| `text` | 识别文本 | `text:今天天气怎么样` |
| `tts` | TTS播报文本 | `tts:北京今天晴*` |
| `ttsID` | TTS模板ID | `ttsID:Weather001` |
| `directivesType` | 指令类型 | `directivesType:NaviDIR.naviPlanRoute` |
| `dirCallbackType` | 回调类型 | `dirCallbackType:NaviDIRCallback.naviPlanRoute` |
| `displayNotify` | 显示通知 | `displayNotify:*` |
| `displayType` | 显示类型 | `displayType:GuiUI.TextCard3` |

### 5.4 比较操作符

| 操作符 | 含义 | 示例 |
|--------|------|------|
| `:` | 等于 | `skill:NAVI` |
| `:>` | 大于 | `confidence:>80` |
| `:<` | 小于 | `score:<0.5` |
| `:>=` | 大于等于 | `threshold:>=0.6` |
| `:<=` | 小于等于 | `threshold:<=0.9` |
| `:!=` | 不等于 | `result:!=error` |
| `:~` | 包含 | `tts:~天气` |
| `:*` | 模糊匹配 | `tts:北京*` |

### 5.5 超时参数

```dsl
# 等待2秒
[EXP]NLPResult    skill:WEATHER;intention:queryWeather    <timeout=2>

# 等待5秒
[EXP]NLPResult    skill:NAVI;intention:naviPlanRouteCallback    <timeout=5>

# 无限等待
[EXP]NLPResult    skill:VoicePrint;intention:register    <timeout=-1>
```

**推荐超时时间**：
- 简单NLP请求：2秒
- 需要网络的请求：5秒
- 复杂场景：10秒

---

## 6. Fixture系统

### 6.1 SETUP块

在所有Case执行前运行一次，用于初始化环境：

```dsl
>>> SETUP
# 拉起服务
[SYS]PULL         AIBSServer cmn {"brand":"0"}
[SYS]PULL         LCSEngine cmn
[SYS]PULL         SpeechEngine cmn

# 创建客户端
[TSA]CREATE       cmn com.autoai.vr.service_vrassistant
[SET]CREATE       cmn com.autoai.vrsetting

# 配置设置
[SET]SETVRCONFIG  DIALOGUE_LANGUAGE cmn
<<<
```

### 6.2 TEARDOWN块

在所有Case执行后运行一次，用于清理资源：

```dsl
>>> TEARDOWN
# 释放客户端
[TSA]FREE
[SET]FREE

# 杀死服务
[SYS]KILL   SpeechEngine
[SYS]KILL   LCSEngine
[SYS]KILL   AIBSServer
<<<
```

### 6.3 注意事项

1. **SETUP和TEARDOWN必须成对出现**
2. 每个文件最多一个SETUP块和一个TEARDOWN块
3. 在SETUP中创建的客户端，在TEARDOWN中释放
4. 服务的PULL和KILL操作放在Fixture中，避免每个Case重复执行

---

## 7. YAML到MGO转换

### 7.1 工具介绍

`yaml2mgo_converter.py`是一个将老版本YAML格式测试用例转换为MGO格式的工具。

### 7.2 使用方法

```bash
# 单文件转换
python3 yaml2mgo_converter.py input.yaml output.mgo

# 指定语言和AppID
python3 yaml2mgo_converter.py input.yaml output.mgo --lang cmn --appid com.autoai.vr.service_vrassistant

# 批量转换
python3 yaml2mgo_converter.py input_dir/ output_dir/ --batch
```

### 7.3 YAML格式说明

老版本YAML格式示例：

```yaml
@DEFAULT_CHANNEL: 0
@DEFAULT_MSGTYPE: NLP
@CASE_BREF: 天气查询测试用例

# 查询天气
*inputEvent:[VehicleInfo];text:今天天气怎么样    strategy:1;dialog:start
skill:WEATHER;intention:queryWeather;tts:*

*callbackEvent:[default]    dialog:end
skill:WEATHER;intention:queryWeatherCallback;tts:北京*
```

---

## 8. 编写最佳实践

### 8.1 Case设计原则

1. **单一职责**：每个Case只测试一个场景
2. **独立性**：Case之间相互独立，不依赖执行顺序
3. **可重复性**：相同条件下执行结果一致
4. **清晰命名**：Case注释说明测试目的

### 8.2 断言最佳实践

```dsl
# ✅ 推荐：验证关键字段
[EXP]NLPResult    skill:NAVI;intention:naviPlanRouteToDest    <timeout=2>

# ✅ 推荐：使用模糊匹配处理动态内容
[EXP]NLPResult    skill:WEATHER;intention:queryWeather;tts:北京*    <timeout=2>

# ❌ 避免：过于严格的TTS匹配
[EXP]NLPResult    tts:北京今天晴转多云，气温15到25度，空气质量良好    <timeout=2>

# ❌ 避免：没有设置超时
[EXP]NLPResult    skill:WEATHER;intention:queryWeather
```

### 8.3 多轮对话最佳实践

```dsl
# 多轮对话示例：导航搜索并选择
>>>
[TSA]START        1
[TSA]FREEWAKEUP   1
[TSA]STRATEGY     1
[TSA]INPUTEVENT   NaviLocationStatus

# 第一轮：搜索
[TSA]TEXT         导航去天安门
[EXP]NLPResult    skill:NAVI;intention:naviPlanRouteToDest    <timeout=2>

# 清空断言上下文，避免干扰
[SYS]CLEAR_ASSERT

# 模拟回调
[TSA]CALLBACK     default    data.result.searchData.poiList:TestCase/.../poiList_Num3.json
[EXP]NLPResult    skill:NAVI;intention:keywordSearchCallback    <timeout=2>

# 第二轮：选择
[TSA]TEXT         第一个
[EXP]NLPResult    skill:NAVI;intention:naviTextSelectedByIndex    <timeout=2>

[TSA]STOP
<<<
```

### 8.4 常见错误避免

1. **忘记STOP**：每个Case结束前必须调用`[TSA]STOP`
2. **超时过短**：网络请求建议至少2秒超时
3. **断言过于严格**：TTS文本可能随版本变化，使用模糊匹配
4. **缺少事件**：某些技能需要特定的INPUTEVENT

---

## 9. 完整示例

### 9.1 简单NLU测试（计算器）

```dsl
######################################################################
# 计算器技能测试
# 语言: cmn
# Case数量: 3
######################################################################

>>> SETUP
[SYS]PULL         AIBSServer cmn {"brand":"0"}
[SYS]PULL         LCSEngine cmn
[SYS]PULL         SpeechEngine cmn
[TSA]CREATE       cmn com.autoai.vr.service_vrassistant
[SET]CREATE       cmn com.autoai.vrsetting
[SET]SETVRCONFIG  DIALOGUE_LANGUAGE cmn
<<<

>>> TEARDOWN
[TSA]FREE
[SET]FREE
[SYS]KILL   SpeechEngine
[SYS]KILL   LCSEngine
[SYS]KILL   AIBSServer
<<<

# Case 1: 加法计算
>>>
[TSA]START        1
[TSA]FREEWAKEUP   1
[TSA]STRATEGY     0
[TSA]INPUTEVENT   VehicleInfo
[TSA]TEXT         1加1等于几
[EXP]NLPResult    skill:Calculate;intention:calculate;tts:一加一等于2    <timeout=2>
[TSA]STOP
<<<

# Case 2: 乘法计算
>>>
[TSA]START        1
[TSA]FREEWAKEUP   1
[TSA]STRATEGY     0
[TSA]INPUTEVENT   VehicleInfo
[TSA]TEXT         八的八次方是多少
[EXP]NLPResult    skill:Calculate;intention:calculate;tts:八的八次方等于*    <timeout=2>
[TSA]STOP
<<<

# Case 3: 圆周率查询
>>>
[TSA]START        1
[TSA]FREEWAKEUP   1
[TSA]STRATEGY     0
[TSA]INPUTEVENT   VehicleInfo
[TSA]TEXT         圆周率是多少
[EXP]NLPResult    skill:Calculate;intention:calculate    <timeout=2>
[TSA]STOP
<<<
```

### 9.2 多轮对话测试（导航）

```dsl
######################################################################
# 导航技能多轮对话测试
# 语言: cmn
# Case数量: 1
######################################################################

>>> SETUP
[SYS]PULL         AIBSServer cmn {"brand":"0"}
[SYS]PULL         LCSEngine cmn
[SYS]PULL         SpeechEngine cmn
[TSA]CREATE       cmn com.autoai.vr.service_vrassistant
[SET]CREATE       cmn com.autoai.vrsetting
[SET]SETVRCONFIG  DIALOGUE_LANGUAGE cmn
<<<

>>> TEARDOWN
[TSA]FREE
[SET]FREE
[SYS]KILL   SpeechEngine
[SYS]KILL   LCSEngine
[SYS]KILL   AIBSServer
<<<

# Case 1: 导航到某地并开始导航
>>>
[TSA]START        1
[TSA]FREEWAKEUP   1
[TSA]STRATEGY     1
[TSA]INPUTEVENT   NaviLocationStatus
[TSA]INPUTEVENT   NavigateStatus

# 第一轮：用户说"导航去人民大学"
[TSA]TEXT         导航去人民大学
[EXP]NLPResult    skill:NAVI;intention:naviPlanRouteToDest;directivesType:NaviDIR.keywordSearch    <timeout=2>

# 模拟搜索结果回调（3个结果）
[TSA]CALLBACK     default    data.result.searchData.poiList:TestCase/caselist/MongoCase/events/Public/poiList_Num3.json
[EXP]NLPResult    skill:NAVI;intention:keywordSearchCallback;tts:找到3个去人民大学的结果*    <timeout=2>

# 第二轮：用户选择"第一个"
[TSA]TEXT         第一个
[EXP]NLPResult    skill:NAVI;intention:naviTextSelectedByIndex;directivesType:NaviDIR.naviPlanRoute    <timeout=2>

# 模拟路线规划回调
[TSA]CALLBACK     default
[EXP]NLPResult    skill:NAVI;intention:naviPlanRouteCallback;tts:去北京市*    <timeout=2>

# 第三轮：用户确认开始导航
[TSA]TEXT         开始导航
[EXP]NLPResult    skill:NAVI;intention:*;directivesType:NaviDIR.startNavi    <timeout=2>

[TSA]CALLBACK     default
[EXP]NLPResult    skill:NAVI;intention:startNaviCallback;tts:好的，为您开始导航*    <timeout=2>

[TSA]STOP
<<<
```

### 9.3 天气查询测试

```dsl
######################################################################
# 天气查询技能测试
# 语言: cmn
# Case数量: 2
######################################################################

>>> SETUP
[SYS]PULL         AIBSServer cmn {"brand":"0"}
[SYS]PULL         LCSEngine cmn
[SYS]PULL         SpeechEngine cmn
[TSA]CREATE       cmn com.autoai.vr.service_vrassistant
[SET]CREATE       cmn com.autoai.vrsetting
[SET]SETVRCONFIG  DIALOGUE_LANGUAGE cmn
<<<

>>> TEARDOWN
[TSA]FREE
[SET]FREE
[SYS]KILL   SpeechEngine
[SYS]KILL   LCSEngine
[SYS]KILL   AIBSServer
<<<

# Case 1: 查询北京天气
>>>
[TSA]START        1
[TSA]FREEWAKEUP   1
[TSA]STRATEGY     1
[TSA]TEXT         请问北京今天天气如何
[EXP]NLPResult    skill:WEATHER;intention:queryWeather;tts:北京*    <timeout=2>
[TSA]STOP
<<<

# Case 2: 追问天气（上海呢）
>>>
[TSA]START        1
[TSA]FREEWAKEUP   1
[TSA]STRATEGY     1
[TSA]TEXT         请问北京今天天气如何
[EXP]NLPResult    skill:WEATHER;intention:queryWeather;tts:北京*    <timeout=2>
[TSA]TEXT         上海呢
[EXP]NLPResult    skill:WEATHER;intention:queryWeatherAgain;tts:上海*    <timeout=2>
[TSA]STOP
<<<
```

---

## 📌 附录

### A. 技能与意图参考

| 技能 | 常用意图 |
|------|---------|
| NAVI | naviPlanRouteToDest, naviToHome, currentLocation, stopNavi, zoomMap |
| WEATHER | queryWeather, queryWeatherAgain, queryWeatherAgainII |
| Calculate | calculate |
| Media | listenToMusicByQuery, playRadio, pausePlay, continuePlay |
| Phone | callPhone, callPhoneNum |
| AppControl | openApp, closeApp |
| Schedule | addSchedule, querySchedule, deleteSchedule, modifySchedule |
| VoicePrint | register |
| Search | searchAll, searchType |

### B. 相关文档

- [COMMAND.md](../../src/testsuite/NANO/doc/COMMAND.md) - DSL指令完整说明
- [EXPECT.md](../../src/testsuite/NANO/doc/EXPECT.md) - 断言系统详解
- [FIXTURE.md](../../src/testsuite/NANO/doc/FIXTURE.md) - Fixture系统说明
- [README.md](../../src/testsuite/NANO/doc/README.md) - NANO框架概述

---

**编写者**: NANO测试团队  
**最后更新**: 2026-01-30
