# NANO DSL环境变量说明文档

NANO测试套件的DSL语言支持强大的环境变量系统，允许在测试用例中使用动态路径和运行时信息，大大提高测试用例的可移植性和灵活性。

## 🎯 功能概述

### 核心特性
- **动态替换**: 使用`{VARIABLE_NAME}`格式在DSL中引用环境变量
- **运行时求值**: 在指令执行时动态获取变量值
- **跨平台兼容**: 自动处理路径分隔符差异
- **错误容错**: 对未定义变量进行友好处理
- **丰富类型**: 支持路径、配置、元数据、服务等多种变量类型
- **Case隔离**: `{CASEID}` 仅在 TEST Case 执行阶段可用

### 语法格式
```dsl
{VARIABLE_NAME}
{EVAL:expression}
```

- **环境变量**:
  - 必须全大写，使用花括号包围，如 `{WORKPATH}`
  - 支持在指令参数、JSON数据中使用

- **动态表达式**:
  - 格式为 `{EVAL:python_expression}`
  - 支持 Python 语法，可调用内置函数和工具库
  - 示例: `{EVAL:get_date(1)}`, `{EVAL:random.randint(1,100)}`

## 📋 支持的环境变量

### 🗂️ 路径相关变量 (8个)

| 变量名 | 描述 | 变量来源 | 示例值 |
|--------|------|----------|--------|
| `{WORKPATH}` | Suite工作目录 | `pytestconfig.suite_dir` | `/workspace/solution_filter/FILTER/1` |
| `{ROOTPATH}` | 项目根目录 | `pytest --mongo_root_dir` | `/data1/baihuidong/ProjectWorkSpace/mango` |
| `{WORKSPACE}` | 工作空间路径 | `pytest --mongo_workspace` | `/workspace` |
| `{BASEPATH}` | Worker基础路径 | `pytestconfig.base_dir` | `/workspace/solution_filter/FILTER/1` |
| `{LIBPATH}` | 库文件路径 | `pytestconfig.lib_path` | `/workspace/solution_filter/FILTER/1/lib` |
| `{CASEPATH}` | Case目录路径 | `pytestconfig.case_dir` | `/workspace/solution_filter/FILTER/1/3` |
| `{LOGPATH}` | 日志路径 | `pytestconfig.log_path` | `/workspace/solution_filter/FILTER/1/log` |
| `{SOCKETPATH}` | Socket端口文件路径 | `pytestconfig.socket_path` | `/workspace/solution_filter/FILTER/1/ports` |

**使用示例**:
```dsl
# 文件操作中使用路径变量
[SYS]CMD mkdir -p {WORKPATH}/output
[SYS]CMD cp source.txt {WORKPATH}/backup/target.txt
[TSA]DATA {WORKPATH}/audio/weather_query.wav
[TSA]START_RECORD {LOGPATH}/record.wav
```

### ⚙️ 配置相关变量 (5个)

| 变量名 | 描述 | 变量来源 | 示例值 |
|--------|------|----------|--------|
| `{CONFIGPATH}` | 配置文件路径 | `pytestconfig.decoder_config` | `/workspace/solution_filter/FILTER/1/decoder.conf` |
| `{CARPLAYCONFIG}` | CarPlay配置文件路径 | `pytestconfig.carplay_config` | `/workspace/config/carplay.conf` |
| `{LCSCONFIG}` | LCS配置文件路径 | `pytestconfig.lcs_config` | `/workspace/config/lcs.conf` |
| `{CASELIST}` | 用例文件路径 | `pytest --mongo_case_list` | `/TestCase/caselist/Mongo/routine/routine.txt` |
| `{PARAMETERIZEDATA}` | 参数化CSV文件路径 | `pytest --mongo_parameterized_data` | `/TestCase/data/case_data.csv` |

**使用示例**:
```dsl
# 配置文件操作
[SYS]CMD cp {CONFIGPATH} {WORKPATH}/config_backup.conf
[TSA]CREATE cmn com.autoai.vr.service_vrassistant {CONFIGPATH}
[TSA]GET_CONFIG_ITEM {CONFIGPATH} debug_mode
```

### 📊 元数据变量 (3个)

| 变量名 | 描述 | 变量来源 | 示例值 |
|--------|------|----------|--------|
| `{SUITEID}` | Suite ID | `pytest --mongo_suite_id` | `FILTER` |
| `{SUITENAME}` | Suite名称 | `pytest --mongo_suite_name` | `NANO` |
| `{CASEID}` | Case唯一标识（TEST Case） | `pytestconfig.case_id` | `/workspace/FILTER_1_3` |

**使用示例**:
```dsl
# 信息输出
[SYS]PRINT === Suite: {SUITENAME} (ID: {SUITEID}) ===
[SYS]PRINT 当前CaseID: {CASEID}
```

> **CASEID 作用域说明**
> - `{CASEID}` 仅在 `test_nano` 执行真正 `TEST` Case 时注入，值来源于 `case.unique_id`。
> - `SETUP/TEARDOWN/SUITE_TEARDOWN` 阶段不注入 `{CASEID}`，使用时会保持原样并输出告警日志。

### 📅 动态生成变量 (3个)

| 变量名 | 描述 | 对应函数 | 示例值 |
|--------|------|----------|--------|
| `{UUID}` | 随机UUID | `common.uuid` | `9B7C8D...` |
| `{TIMESTAMP}` | 当前时间戳(ms) | `common.get_timestamp` | `1697767890123` |
| `{NOW}` | 当前日期 | `common.get_date` | `2023-10-20` |

> **提示**: `{NOW}` 等价于 `{EVAL:get_date()}`，如果需要日期偏移，请使用 `{EVAL:get_date(days)}`。

> **说明**: 当前实现中不提供 `LCSPATH/SPEECHPATH/AIBSPATH/CLIENTPATH/LANG/APPID` 这类环境变量，
> 若 DSL 中直接使用，会按未定义变量处理（保持原样并记录日志）。

### 🧮 动态求值表达式 (EVAL)

NANO DSL 支持使用 `{EVAL:expression}` 语法执行 Python 表达式，实现更复杂的动态逻辑。

#### 1. 可用上下文环境
在 EVAL 表达式中，可以直接使用以下模块和对象：

- **标准库**: `datetime`, `time`, `random`, `uuid`, `json`, `math`, `os`, `re`
- **配置对象**: `config` (当前的 pytest 配置对象)
- **工具函数**: `src.utils.common` 中的所有函数 (如 `get_date`, `get_timestamp` 等)

#### 2. 常用功能示例

| 功能 | 表达式示例 | 结果示例 |
|------|-----------|----------|
| **日期计算** | `{EVAL:get_date(1)}` | `2023-10-28` (明天) |
| **日期偏移** | `{EVAL:get_date(-7)}` | `2023-10-20` (上周) |
| **时间格式化** | `{EVAL:datetime.now().strftime('%H:%M:%S')}` | `14:30:05` |
| **随机数** | `{EVAL:random.randint(1000, 9999)}` | `5678` |
| **UUID截取** | `{EVAL:str(uuid.uuid4())[:8]}` | `a1b2c3d4` |
| **数学运算** | `{EVAL:math.floor(10.5) + 5}` | `15` |

#### 3. 注意事项
- 表达式必须是合法的 Python 表达式。
- 如果表达式执行失败，将保留原字符串 `{EVAL:...}` 并记录错误日志。
- `get_date(offset)` 函数返回的是格式化后的日期字符串 (`%Y-%m-%d %H:%M:%S.%f`)。

## 💡 使用场景和示例

### 🚀 场景1：基础语音识别测试
```dsl
>>> 1
# 使用环境变量的语音识别测试
[SYS]PULL AIBSServer cmn {"brand":"0"}
[SYS]SLEEP 2

[TSA]CREATE cmn com.autoai.vr.service_vrassistant
[TSA]START 1

# 使用工作路径中的音频文件
[TSA]DATA {WORKPATH}/audio/weather_query.wav

# 期望识别结果断言
[EXP]cloudASRResult [0]asr:今天天气怎么样;lang:cmn <timeout=3>

[TSA]STOP
[TSA]FREE
[SYS]KILL AIBSServer
<<<
```

### 🔄 场景2：批量测试环境管理
```dsl
>>> 1
# 为每个Suite创建独立的工作环境
[SYS]CMD mkdir -p {WORKPATH}/results/{SUITEID}
[SYS]CMD mkdir -p {WORKPATH}/logs/{SUITENAME}
[SYS]CMD mkdir -p {WORKPATH}/audio_backup

# 复制配置和音频文件
[SYS]CMD cp {CONFIGPATH} {WORKPATH}/config_{SUITEID}.conf
[SYS]CMD cp -r {ROOTPATH}/TestCase/audio/* {WORKPATH}/audio_backup/

# 输出环境信息到日志
[SYS]CMD echo "Suite: {SUITENAME}" > {LOGPATH}/env_info.log
[SYS]CMD echo "ID: {SUITEID}" >> {LOGPATH}/env_info.log
[SYS]CMD echo "CaseID: {CASEID}" >> {LOGPATH}/env_info.log
[SYS]CMD echo "WorkPath: {WORKPATH}" >> {LOGPATH}/env_info.log
<<<
```

### 🎤 场景3：声纹功能测试
```dsl
>>> 1
# 声纹注册和验证测试
[SET]CREATE cmn com.autoai.vr.service_vrassistant

# 声纹注册
[SET]START_SPEAKER_ENROLL user_{SUITEID} 你好{SUITENAME} 1 0
[EXP]START_SPEAKER_ENROLL_RET code:0

[SET]DATA {WORKPATH}/audio/voiceprint_enroll.wav
[EXP]startEnroll userId:user_{SUITEID};result:success <timeout=5>

[SET]END_SPEAKER_ENROLL
[EXP]END_SPEAKER_ENROLL_RET code:0

# 声纹验证
[SET]VERIFY_VOICEPRINT user_{SUITEID} 你好{SUITENAME} 0
[SET]DATA {WORKPATH}/audio/voiceprint_verify.wav
[EXP]verifyVoiceprint userId:user_{SUITEID};result:match <timeout=3>

[SET]FREE
<<<
```

### 🌐 场景4：按Case隔离测试
```dsl
>>> 1
# 打印Case级信息（CASEID仅TEST Case有效）
[SYS]PRINT === 开始Case执行: {CASEID} ===
[SYS]PULL AIBSServer cmn {"brand":"0"}
[SYS]SLEEP 2

[TSA]CREATE cmn com.autoai.vr.service_vrassistant
[TSA]START 1

# 根据Case目录组织音频文件
[TSA]DATA {CASEPATH}/audio/greeting.wav

# 结果断言
[EXP]cloudASRResult confidence:>80 <timeout=3>

[TSA]STOP
[TSA]FREE
[SYS]KILL AIBSServer
[SYS]PRINT === Case执行完成: {CASEID} ===
<<<
```

### 🔧 场景5：配置和状态查询
```dsl
>>> 1
# 系统配置和状态检查
[TSA]CREATE cmn com.autoai.vr.service_vrassistant {CONFIGPATH}

# 获取版本信息
[TSA]GET_VERSION
[EXP]GET_VERSION_RET version:>1.0

# 获取配置项
[TSA]GET_CONFIG_ITEM {CONFIGPATH} debug_mode
[EXP]GET_CONFIG_ITEM_RET value:true

# 输出系统状态到文件
[SYS]CMD echo "CaseID: {CASEID}" > {LOGPATH}/system_info.log
[SYS]CMD echo "Config: {CONFIGPATH}" >> {LOGPATH}/system_info.log
[SYS]CMD echo "Library: {LIBPATH}" >> {LOGPATH}/system_info.log

[TSA]FREE
<<<
```

### 📱 场景6：JSON事件中使用环境变量
```dsl
>>> 1
# 在JSON事件数据中使用环境变量
[TSA]CREATE cmn com.autoai.vr.service_vrassistant
[TSA]START 1

# 发送包含环境变量的事件
[TSA]EVENT {"source":"NANO","suite":"{SUITENAME}","case_id":"{CASEID}","workpath":"{WORKPATH}"}

# 复杂的事件数据
[TSA]EVENT {
  "type": "TestEnvironment",
  "data": {
    "suite_id": "{SUITEID}",
    "suite_name": "{SUITENAME}",
    "case_id": "{CASEID}",
    "config_path": "{CONFIGPATH}",
    "work_directory": "{WORKPATH}",
    "timestamp": "2024-01-01T10:00:00Z"
  }
}

[TSA]STOP
[TSA]FREE
<<<
```

## 🔧 技术实现原理

### 变量替换机制
1. **解析时机**: 在指令执行前进行运行时替换
2. **替换算法**: 使用正则表达式 `r'(?<!\$)\{([A-Z_]+|EVAL:[^}]+)\}'` 匹配变量和 EVAL
3. **变量来源**: 通过 `ENVIRONMENT_VARIABLES` 的 `attribute/getoption/dynamic` 三类方式取值
4. **错误容错**: 获取失败的变量保持原样，记录警告

### 核心代码片段
```python
def _replace_environment_variables(self, text: str) -> str:
    """替换文本中的环境变量"""
    pattern = r'(?<!\$)\{([A-Z_]+|EVAL:[^}]+)\}'

    def replace_var(match):
        var_name = match.group(1)
        if var_name in ENVIRONMENT_VARIABLES:
            try:
                access_type, access_param = ENVIRONMENT_VARIABLES[var_name]
                if access_type == "attribute":
                    value = getattr(self.config, access_param, None)
                elif access_type == "getoption":
                    value = self.config.getoption(access_param, default=None)
                elif access_type == "dynamic":
                    value = access_param() if callable(access_param) else None
                else:
                    return match.group(0)
                if value is None:
                    logging.warning(f"环境变量 {var_name} 值为空")
                    return match.group(0)  # 保持原样
                return str(value).replace('\\', '/')  # 统一路径分隔符
            except Exception as e:
                logging.error(f"获取环境变量 {var_name} 失败: {e}")
                return match.group(0)
        else:
            logging.warning(f"未知环境变量: {var_name}")
            return match.group(0)
    
    return re.sub(pattern, replace_var, text)
```

### 变量映射表（当前代码）
```python
ENVIRONMENT_VARIABLES = {
    # 路径相关
    'WORKPATH': ('attribute', 'suite_dir'),
    'ROOTPATH': ('getoption', '--mongo_root_dir'),
    'WORKSPACE': ('getoption', '--mongo_workspace'),
    'BASEPATH': ('attribute', 'base_dir'),
    'LIBPATH': ('attribute', 'lib_path'),
    'CASEPATH': ('attribute', 'case_dir'),
    'LOGPATH': ('attribute', 'log_path'),
    'SOCKETPATH': ('attribute', 'socket_path'),

    # 配置相关
    'CONFIGPATH': ('attribute', 'decoder_config'),
    'CARPLAYCONFIG': ('attribute', 'carplay_config'),
    'LCSCONFIG': ('attribute', 'lcs_config'),
    'CASELIST': ('getoption', '--mongo_case_list'),
    'PARAMETERIZEDATA': ('getoption', '--mongo_parameterized_data'),

    # 元数据相关
    'SUITEID': ('getoption', '--mongo_suite_id'),
    'SUITENAME': ('getoption', '--mongo_suite_name'),
    'CASEID': ('attribute', 'case_id'),
}
```

## 📝 最佳实践

### 1. ✅ 推荐用法
```dsl
# 使用环境变量提高可移植性
[TSA]CREATE cmn com.autoai.vr.service_vrassistant
[TSA]DATA {WORKPATH}/audio/test.wav
[SYS]CMD mkdir -p {WORKPATH}/output

# 在JSON中使用变量
[TSA]EVENT {"suite":"{SUITENAME}","case_id":"{CASEID}"}

# 日志和调试信息
[SYS]PRINT Suite: {SUITENAME}, Case: {CASEID}
```

### 2. ❌ 不推荐用法
```dsl
# 硬编码路径（可移植性差）
[TSA]DATA /workspace/solution_filter/FILTER/1/audio/test.wav

# 硬编码语种（不够灵活）
[TSA]CREATE cmn com.autoai.vr.service_vrassistant

# 硬编码配置路径
[TSA]GET_CONFIG_ITEM /tmp/decoder.conf debug_mode
```

### 3. 🔍 调试技巧
```dsl
# 输出所有环境变量值进行调试
[SYS]PRINT === 环境变量信息 ===
[SYS]PRINT WORKPATH: {WORKPATH}
[SYS]PRINT CONFIGPATH: {CONFIGPATH}
[SYS]PRINT CASEPATH: {CASEPATH}
[SYS]PRINT CASEID: {CASEID}
[SYS]PRINT === 调试信息结束 ===
```

### 4. 📁 文件组织
```dsl
# 使用环境变量组织测试文件结构
[SYS]CMD mkdir -p {WORKPATH}/results/{SUITEID}
[SYS]CMD mkdir -p {WORKPATH}/logs/{SUITENAME}
[SYS]CMD mkdir -p {WORKPATH}/config/{SUITEID}
```

## ⚠️ 注意事项

### 变量命名规则
- **必须全大写**: 变量名只能包含大写字母和下划线
- **用花括号包围**: 格式必须为`{VARIABLE_NAME}`
- **区分大小写**: `{workpath}`不等于`{WORKPATH}`

### 错误处理
- **未定义变量**: 保持原样，不进行替换，记录警告日志
- **空值变量**: 保持原样，记录警告日志
- **获取异常**: 保持原样，记录错误日志

### 性能考虑
- **延迟求值**: 变量值在使用时才获取，确保获取到最新值
- **缓存机制**: 同一用例内的变量值会被缓存，避免重复计算

## 🛠️ 扩展指南

### 添加新的环境变量
1. 在 `src/testsuite/NANO/config.py` 的 `ENVIRONMENT_VARIABLES` 中添加变量映射
2. 如果是 `attribute` 类型，确保 `pytestconfig` 在执行阶段已注入对应属性
3. 添加相应的文档说明和使用示例
4. 进行充分的测试验证

```python
# 示例：添加新的环境变量
'NEWVAR': ('attribute', 'new_attribute'),
```

## 🔄 向后兼容性

- **完全兼容**: 现有不使用环境变量的DSL用例无需修改
- **渐进升级**: 可以逐步将硬编码值替换为环境变量
- **错误容错**: 未定义的变量不影响测试执行，只是不进行替换

---

**环境变量系统让NANO测试套件更加灵活和可维护，是提高测试用例质量的重要工具！**

**Write By Baihuidong 2025/10/20**