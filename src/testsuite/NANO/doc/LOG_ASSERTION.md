# NANO 日志断言系统说明文档

NANO测试套件提供了强大的日志断言功能，支持对日志文件进行多种模式的验证，包括关键字搜索、键值对匹配、JSON数据提取、正则表达式提取和时间差计算等。本文档详细介绍日志断言的使用方法、语法和最佳实践。

## 🎯 日志断言概述

### 核心特性
- **窗口锁定机制**: 基于Case级别的读取指针，确保每个Case只读取新增的日志内容
- **多种匹配模式**: 支持SEARCH、MATCH、DIFF三种主要模式
- **灵活的数据提取**: 支持KV键值对、JSON路径、正则表达式等多种提取方式
- **时间差计算**: 支持计算两个日志事件之间的时间差
- **智能指针管理**: 自动管理日志文件读取位置，防止重复计算

### 断言语法
```dsl
[EXP]LOG 文件名 模式 参数...
```

## 📋 断言模式详解

### SEARCH 模式 - 关键字搜索

SEARCH模式用于在日志窗口内统计关键字出现的次数，支持存在性、不存在性和数量比较。

#### 语法结构
```dsl
[EXP]LOG 文件名 SEARCH "关键字" [EXISTS|ABSENT|COUNT 操作符 数值]
```

#### 使用场景

| 场景描述 | DSL 语句示例 | 逻辑说明 |
|:---------|:-------------|:---------|
| 断言存在 | `[EXP]LOG app.log SEARCH "TagA" EXISTS` | 窗口内至少出现一次 "TagA" |
| 断言不存在 | `[EXP]LOG app.log SEARCH "Error" ABSENT` | 窗口内绝对不能出现 "Error" |
| 等于数量 | `[EXP]LOG app.log SEARCH "Retry" COUNT == 3` | 窗口内 "Retry" 必须正好出现 3 次 |
| 大于数量 | `[EXP]LOG app.log SEARCH "Login" COUNT > 0` | 等同于 EXISTS |
| 小于数量 | `[EXP]LOG app.log SEARCH "Warning" COUNT < 5` | 窗口内警告信息不得超过 5 条 |

#### 操作符说明
- `==`: 等于
- `!=`: 不等于
- `>`: 大于
- `<`: 小于
- `>=`: 大于等于
- `<=`: 小于等于
- `&&`: 且关系
- `||`: 或关系

#### 示例
```dsl
# 验证系统启动日志存在
[EXP]LOG test_app.log SEARCH "System Start" EXISTS

# 验证没有错误日志
[EXP]LOG test_app.log SEARCH "[ERROR]" ABSENT

# 验证重试操作发生了3次
[EXP]LOG test_app.log SEARCH "Retry connection" COUNT == 3

# 验证警告信息不超过5条
[EXP]LOG test_app.log SEARCH "[WARN]" COUNT < 5

# 且和或关系
[EXP]LOG test_app.log SEARCH "[WARN]"||"ASRResult" COUNT < 5
[EXP]LOG test_app.log SEARCH "[WARN]"&&"ASRResult" COUNT < 5
```

---

### MATCH 模式 - 精准匹配

MATCH模式用于查找包含指定关键字的最新日志行，并从中提取特定字段进行验证。支持三种提取方式：KV（键值对）、JSON（JSON路径）、EXTRACT（正则表达式）。

#### 语法结构
```dsl
[EXP]LOG 文件名 MATCH "关键字" [KV|JSON|EXTRACT] 提取参数 操作符 期望值
```

---

### MATCH + KV 模式 - 键值对提取

KV模式自动识别日志行中的键值对格式，支持多种分隔符（`:`、`=`、空格）。

#### 提取逻辑
- 自动识别 `:`、`=` 或 空格 作为分隔符
- 支持带引号和不带引号的值
- 兼容多种格式：`key:value`、`key=value`、`key value`

#### 使用场景

| 场景描述 | DSL 语句示例 | 逻辑说明 |
|:---------|:-------------|:---------|
| 等于数值 | `[EXP]LOG 123.log MATCH "add Client" KV "type" == 1` | 找到最新的一条，断言其 type 字段为 1 |
| 不等于数值 | `[EXP]LOG 123.log MATCH "add Client" KV "socket_fd" != -1` | 断言最新的 socket_fd 不是 -1 |
| 字符串匹配 | `[EXP]LOG 123.log MATCH "add Client" KV "filename" == "lcs.zip"` | 支持字符串全等校验 |
| 不规则格式 | `[EXP]LOG 123.log MATCH "Type:" KV "Type" == 2` | 兼容 Type:2 或 Type 2 等多种格式 |

#### 示例
```dsl
# 日志示例: module=Auth user=admin id=1001 status=LoginSuccess
# 验证用户名为admin
[EXP]LOG test_app.log MATCH "LoginSuccess" KV "user" == "admin"

# 验证ID等于1001
[EXP]LOG test_app.log MATCH "LoginSuccess" KV "id" == 1001

# 日志示例: Event:NetworkChange Type:Reconnect Signal:Weak
# 验证Type字段
[EXP]LOG test_app.log MATCH "Event:NetworkChange" KV "Type" == "Reconnect"
```

---

### MATCH + JSON 模式 - JSON数据提取

JSON模式从日志行中提取JSON对象，并使用JSON路径提取嵌套字段。

#### 语法结构
```dsl
[EXP]LOG 文件名 MATCH "关键字" JSON "$.路径" 操作符 期望值
```

#### 路径格式
- 支持点号分隔的路径：`$.field.subfield`
- 路径必须以 `$.` 开头
- 支持深层嵌套结构

#### 使用场景

| 场景描述 | DSL 语句示例 | 逻辑说明 |
|:---------|:-------------|:---------|
| 简单路径 | `[EXP]LOG 123.log MATCH "setResult" JSON "$.source" == "SpeechEngine"` | 提取根目录下 source 字段 |
| 深层嵌套 | `[EXP]LOG 123.log MATCH "setResult" JSON "$.data.text" == "你好"` | 提取嵌套对象中的文本内容 |
| 数值比较 | `[EXP]LOG 123.log MATCH "setResult" JSON "$.data.confidence" > 0.4` | 对 JSON 里的浮点数进行比较 |

#### 示例
```dsl
# 日志示例: API_RESPONSE: {"code": 200, "data": {"items": [1, 2], "meta": {"total": 50}}}
# 提取嵌套的total字段
[EXP]LOG test_app.log MATCH "API_RESPONSE" JSON "$.data.meta.total" == 50

# 验证返回码
[EXP]LOG test_app.log MATCH "API_RESPONSE" JSON "$.code" == 200
```

---

### MATCH + EXTRACT 模式 - 正则表达式提取

EXTRACT模式使用正则表达式从日志行中提取值，支持捕获组。

#### 语法结构
```dsl
[EXP]LOG 文件名 MATCH "关键字" EXTRACT /正则表达式/ 操作符 期望值
```

#### 正则表达式格式
- 使用斜杠 `/` 包围正则表达式
- 支持捕获组，优先使用第一个捕获组的值
- 如果没有捕获组，使用整个匹配结果

#### 使用场景

| 场景描述 | DSL 语句示例 | 逻辑说明 |
|:---------|:-------------|:---------|
| 正则捕获 | `[EXP]LOG 123.log MATCH "User[" EXTRACT /User\[(\w+)\]/ == "admin"` | 使用括号中的捕获组进行比对 |

#### 示例
```dsl
# 日志示例: Task-A123 processing completed in 45ms.
# 提取任务ID（使用捕获组）
[EXP]LOG test_app.log MATCH "processing completed" EXTRACT /Task-([A-Z0-9]+)/ == "A123"

# 提取耗时数值（使用捕获组）
[EXP]LOG test_app.log MATCH "processing completed" EXTRACT /in (\d+)ms/ < 100
```

---

### DIFF 模式 - 时间差计算

DIFF模式用于计算两个日志事件之间的时间差，常用于性能测试和时序验证。

#### 语法结构
```dsl
[EXP]LOG 文件名 DIFF "开始关键字" "结束关键字" 操作符 时间阈值
```

#### 时间格式
- `500ms`: 500毫秒
- `1s`: 1秒
- `2.5s`: 2.5秒

#### 使用场景

| 场景描述 | DSL 语句示例 | 逻辑说明 |
|:---------|:-------------|:---------|
| 小于最大耗时 | `[EXP]LOG 123.log DIFF "Req" "Resp" < 500ms` | A 到 B 的时间差必须在 500 毫秒内 |
| 大于最小耗时 | `[EXP]LOG 123.log DIFF "Start" "End" > 1s` | 验证某个过程至少持续了 1 秒 |
| 逻辑顺序校验 | `[EXP]LOG 123.log DIFF "StepA" "StepB" >= 0ms` | 验证 A 必须发生在 B 之前（差值为正则顺序对） |

#### 查找逻辑
1. 从日志窗口末尾开始，倒序查找包含"结束关键字"的最新日志行
2. 提取该行的时间戳 T2
3. 继续倒序查找，找到在 T2 之前出现的包含"开始关键字"的日志行
4. 提取该行的时间戳 T1
5. 计算时间差：T2 - T1
6. 与阈值进行比较

#### 超时机制
如果在窗口内找到了"结束日志"但找不到"开始日志"，程序会报错：
```
Error: Log A not found before Log B
```

#### 示例
```dsl
# 验证请求到响应的耗时小于500毫秒
# Start: [REQ] /api/v1/login
# End:   [RESP] /api/v1/login 200 OK
[EXP]LOG test_app.log DIFF "[REQ]" "[RESP]" < 500ms

# 验证异步任务至少执行了1秒
[EXP]LOG test_app.log DIFF "AsyncJob Start" "AsyncJob Finish" > 1s
```

---

## 🔧 核心解析流程

日志断言的核心执行流程如下：

### 1. 指令拆解
解析DSL语句，提取：
- 文件名
- 动作模式（SEARCH/MATCH/DIFF）
- 参数列表
- 预期值

### 2. 窗口锁定
- 读取该文件当前的偏移量（Last_Pointer）
- 只读取该点之后的日志内容
- 确保每个Case只处理新增的日志

### 3. 倒序读取
- 从文件末尾开始读取日志行
- 对于MATCH和DIFF模式，优先查找最新的匹配行

### 4. 分支处理

#### IF SEARCH:
- 统计所有行中包含关键字的次数
- 根据操作符（EXISTS/ABSENT/COUNT）返回结果

#### IF MATCH:
- 找到第一条符合特征的行，停止读取
- **IF KV**: 调用 `smart_kv_extract(line, key)` 提取键值对
- **IF JSON**: 调用 `json_path_extract(line, path)` 提取JSON字段
- **IF EXTRACT**: 使用正则表达式提取值（去掉斜杠分隔符）

#### IF DIFF:
- 找到最新 B 行时间 T2
- 继续找最近 A 行时间 T1（必须在T2之前）
- 计算 T2 - T1
- 与阈值进行比较

### 5. 更新指针
- 将此文件当前的"已读水位线"更新到临时指针
- Case结束时，将临时指针提交为永久指针
- 防止下次断言重复计算

---

## 💡 最佳实践

### 1. 文件路径
- 支持相对路径和绝对路径
- 相对路径默认在当前工作目录查找
- 建议使用环境变量：`{WORKPATH}/logs/app.log`

### 2. 关键字选择
- 选择唯一且稳定的关键字，避免误匹配
- 对于时间戳等动态内容，使用正则表达式提取
- 避免使用过于通用的关键字（如 "log"、"error"）

### 3. 窗口管理
- SEARCH模式会统计整个窗口内的所有匹配
- MATCH模式只查找最新的匹配行
- DIFF模式需要确保开始和结束日志都在窗口内

### 4. 时间戳格式
DIFF模式支持以下时间戳格式：
- `YYYY-MM-DD HH:MM:SS.mmm`
- `YYYY/MM/DD HH:MM:SS.mmm`
- `HH:MM:SS.mmm`（自动补全当前日期）

### 5. 错误处理
- 文件不存在：返回 FAILED 状态，错误信息为"日志文件不存在"
- 关键字未找到：返回 FAILED 状态，错误信息为"未找到包含关键字的日志"
- 提取失败：返回 FAILED 状态，显示具体的提取错误信息
- 时间解析失败：返回 FAILED 状态，提示无法解析时间戳

---

## 📝 完整示例

```dsl
>>> SETUP
# 初始化环境，生成日志
[SYS]CMD echo "开始生成日志"
<<<

>>> 
[SYS]BREF "1. 基础关键字搜索 (SEARCH Mode)"
# 验证系统启动日志是否存在
[EXP]LOG test_app.log SEARCH "System Start" EXISTS

# 验证整个窗口内没有出现 Error 级别的日志
[EXP]LOG test_app.log SEARCH "[ERROR]" ABSENT

# 验证重试操作发生了正好 3 次
[EXP]LOG test_app.log SEARCH "Retry connection" COUNT == 3

# 验证警告信息不超过 5 条
[EXP]LOG test_app.log SEARCH "[WARN]" COUNT < 5
<<<

>>> 
[SYS]BREF "2. 键值对精准匹配 (MATCH KV Mode)"
# 日志示例: module=Auth user=admin id=1001 status=LoginSuccess
# 场景：找到包含 "LoginSuccess" 的最新日志，断言其 user 字段为 admin
[EXP]LOG test_app.log MATCH "LoginSuccess" KV "user" == "admin"

# 场景：同上，断言其 id 字段等于 1001 (数值比较)
[EXP]LOG test_app.log MATCH "LoginSuccess" KV "id" == 1001

# 场景：支持冒号格式 "Type:Reconnect"
# 日志示例: Event:NetworkChange Type:Reconnect Signal:Weak
[EXP]LOG test_app.log MATCH "Event:NetworkChange" KV "Type" == "Reconnect"
<<<

>>> 
[SYS]BREF "3. JSON 数据深度提取 (MATCH JSON Mode)"
# 日志示例: API_RESPONSE: {"code": 200, "data": {"items": [1, 2], "meta": {"total": 50}}}
# 场景：提取嵌套的 total 字段并断言
[EXP]LOG test_app.log MATCH "API_RESPONSE" JSON "$.data.meta.total" == 50

# 场景：断言数组长度或特定值
[EXP]LOG test_app.log MATCH "API_RESPONSE" JSON "$.code" == 200
<<<

>>> 
[SYS]BREF "4. 正则表达式提取 (MATCH EXTRACT Mode)"
# 日志示例: Task-A123 processing completed in 45ms.
# 场景：提取任务ID (捕获组1)
[EXP]LOG test_app.log MATCH "processing completed" EXTRACT /Task-([A-Z0-9]+)/ == "A123"

# 场景：提取耗时数值
[EXP]LOG test_app.log MATCH "processing completed" EXTRACT /in (\d+)ms/ < 100
<<<

>>> 
[SYS]BREF "5. 时序与性能分析 (DIFF Mode)"
# 场景：验证请求到响应的耗时小于 500毫秒
# Start: [REQ] /api/v1/login
# End:   [RESP] /api/v1/login 200 OK
[EXP]LOG test_app.log DIFF "[REQ]" "[RESP]" < 500ms

# 场景：验证某个异步任务至少执行了 1秒 (防止过快结束)
[EXP]LOG test_app.log DIFF "AsyncJob Start" "AsyncJob Finish" > 1s
<<<

>>> TEARDOWN
[SYS]CMD echo "结束"
<<<
```

---

## 🔍 技术实现细节

### 指针管理机制
- **永久指针** (`log_file_pointers`): 记录上一个Case结束时的文件位置，Case之间隔离
- **临时指针** (`temp_log_pointers`): 记录当前Case执行过程中读到的最大位置，Case内部共享
- **提交机制**: Case结束时，将临时指针提交为永久指针，供下一个Case使用

### 文件读取策略
- 使用二进制模式打开文件，支持大文件读取
- 使用 `errors='ignore'` 防止编码错误中断
- 支持文件截断检测，自动重置指针

### 正则表达式处理
- EXTRACT模式会自动去掉正则表达式两边的斜杠 `/`
- 优先使用第一个捕获组的值
- 如果没有捕获组，使用整个匹配结果

### 时间戳解析
- 支持多种时间格式
- 自动补全日期（如果只有时分秒）
- 使用 `datetime` 对象进行精确计算

---

## 📚 相关文档

- [断言系统总览](EXPECT.md) - 了解其他断言类型
- [指令系统](COMMAND.md) - 了解如何生成日志
- [环境变量](ENV.md) - 了解如何在日志路径中使用环境变量

---

**Updated 2025/12/30 - 新增日志断言功能：支持SEARCH、MATCH、DIFF三种模式，提供强大的日志验证能力**

