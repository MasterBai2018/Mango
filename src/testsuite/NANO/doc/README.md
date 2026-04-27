# NANO测试套件

![Python](https://img.shields.io/badge/Python-3.6%2B-blue.svg)
![License](https://img.shields.io/badge/License-Internal-red.svg)
![Version](https://img.shields.io/badge/Version-2.0.0-green.svg)

NANO是一个基于DSL（领域特定语言）驱动的创新测试框架，专为Mango项目中的C++ SDK综合测试而设计。通过外部DSL测试文件动态驱动测试执行，实现了测试逻辑与代码的完全分离，提供了高度灵活和可维护的测试解决方案。

## 🌟 核心特性

### 🎯 DSL驱动架构
- **声明式语法**: 使用简洁直观的DSL语法定义复杂测试流程
- **动态执行**: 无需重编译，修改DSL文件即可调整测试逻辑
- **高度可读**: 非技术人员也能理解和编写测试用例

### 🔀 多客户端支持
- **TSA客户端**: 语音助手服务测试
- **SET客户端**: 设置服务测试
- **VOI客户端**: 语音输入服务测试
- **OMS客户端**: OMS管理服务测试
- **TTS客户端**: 文本转语音服务测试
- **SYS客户端**: 系统级操作和控制
- **并发管理**: 支持多客户端同时运行和交互

### ⚡️ Class级别Fixture
- **`SETUP` / `TEARDOWN`**: 支持在用例文件级别定义前后置操作。
- **高效执行**: 避免在每个Case中重复初始化和清理，提升执行效率。
- **原子化管理**: 保证环境准备和清理的原子性。

### 🔍 智能断言系统
- **实时验证**: 强大的测试结果自动验证系统
- **多种断言**: 支持回调断言、API断言、状态断言、文件断言、日志断言等
- **智能匹配**: 实时匹配回调结果与期望值
- **超时等待**: 支持带超时的异步断言，使用信号量机制等待回调到达（`<timeout=X>`）
- **文件验证**: 支持文件存在性、大小、MD5值和JSON内容验证
- **日志断言**: 支持关键字搜索、键值对匹配、JSON提取、正则提取和时间差计算

### 🌍 环境变量系统
- **动态路径**: 支持工作路径、配置路径等动态变量
- **运行时信息**: 获取Suite信息、语种、服务路径等
- **跨平台兼容**: 自动处理路径分隔符差异

### 🔧 完整接口覆盖
- **100%覆盖**: 完整封装aibs_client_api.h中的所有C层接口
- **62个指令**: 支持所有语音SDK功能的DSL指令（含文件断言）
- **参数配置**: 支持引擎参数动态设置和查询
- **多语言支持**: 支持中英粤语种切换

### 📊 数据驱动测试（参数化）
- **外部CSV数据源**: 通过CSV文件提供测试数据，实现数据与用例分离
- **占位符语法**: 使用 `${variable}` 占位符语法，简洁直观
- **自动展开**: 一个模板用例自动生成多个测试实例
- **SETUP/TEARDOWN支持**: 前后置也支持参数化，使用CSV第一行数据
- **智能检测**: 自动检测占位符并验证CSV文件是否提供
- **Allure集成**: 参数化信息完整展示在测试报告中

## 🚀 快速开始

### 环境要求
- Python 3.6+
- pytest 6.0+
- allure-pytest
- ctypes库支持
- C++ SDK动态库文件

### 运行命令
```shell
# 执行NANO测试套件
python3 Run_Mongo.py -f NANO \
  -C TestCase/conf/Mongo/config/decoder/decoder.conf \
  -a TestCase/caselist/24MM/SDK/NANO/nano.mgo \
  -p TestCase/conf/Mongo/config/lcs/lcs_OTA_test.conf

# 执行参数化测试（使用CSV数据文件）
python3 Run_Mongo.py -f NANO \
  -C TestCase/conf/Mongo/config/decoder/decoder.conf \
  -a TestCase/caselist/24MM/SDK/NANO/nano_parameterized.mgo \
  -p TestCase/conf/Mongo/config/lcs/lcs_OTA_test.conf \
  -P TestCase/caselist/24MM/SDK/NANO/test_data.csv
```

### DSL文件格式
```yaml
# 可选的SETUP块
>>> SETUP
# Suite级别的初始化指令
<<<

# 测试用例块
>>> 循环次数
# 用例描述和注释
[客户端类型]指令名称 参数1 参数2 参数N
[EXP]断言类型 字段1:期望值1;字段2:期望值2
<<<

# 可选的TEARDOWN块
>>> TEARDOWN
# Suite级别的清理指令
<<<
```

## 📖 文档目录

### ⚡️ Fixture系统 (前后置)
前后置指令的使用说明请参阅：**[FIXTURE.md](FIXTURE.md)**

### 🎮 指令系统
详细的指令使用说明请参阅：**[COMMAND.md](COMMAND.md)**

包含内容：
- **基础指令**: CREATE、START、STOP、DATA、EVENT等7个通用指令
- **引擎控制**: PAUSE、RESUME、GET_VERSION、FREEWAKEUP、TEXT、STRATEGY等7个控制指令
- **系统设置**: CAR_TYPE、LOG_PATH、MIC_STATUS等6个设置指令
- **声纹功能**: SPEAKER_ENROLL、VERIFY_VOICEPRINT等10个声纹指令
- **系统操作**: PULL、KILL、CMD、SLEEP、PRINT、UPLOAD、ALLURE等8个系统级指令
  - **UPLOAD**: 支持JSON、LINE、REPLACE、DELETE四种文件更新方式
  - **ALLURE**: 支持将文件添加到Allure测试报告附件
- **TSR指令**: ASR_ACCURACY、DELAY、WAKEUP_ACCURACY、PSTT_ACCURACY等Suite级统计指令
- 每个指令的参数说明、使用示例、底层接口对应关系

### 🌍 环境变量系统
环境变量注入和使用说明请参阅：**[ENV.md](ENV.md)**

包含内容：
- **路径变量**: `{WORKPATH}`、`{ROOTPATH}`、`{LIBPATH}`等
- **配置变量**: `{CONFIGPATH}`、`{CASELIST}`等  
- **元数据变量**: `{SUITEID}`、`{SUITENAME}`、`{CASEID}`等
- **动态变量**: `{UUID}`、`{TIMESTAMP}`、`{NOW}` 以及 `{EVAL:...}`
- 使用示例和最佳实践

### 🔍 断言系统
断言类型和写法说明请参阅：**[EXPECT.md](EXPECT.md)**

包含内容：
- **回调断言**: ASRResult、NLPResult、VoiceDetectionResult等
- **API断言**: GET_VERSION_RET、SETVRCONFIG_RET等
- **断言语法**: 超时机制、通道指定、字段匹配
- **比较操作**: 等值、大于、小于、包含等
- 断言示例和错误处理

### 📄 日志断言系统
日志断言功能说明请参阅：**[LOG_ASSERTION.md](LOG_ASSERTION.md)**

包含内容：
- **SEARCH模式**: 关键字搜索、存在性验证、数量统计
- **MATCH模式**: 键值对提取（KV）、JSON路径提取、正则表达式提取（EXTRACT）
- **DIFF模式**: 时间差计算、性能验证、时序校验
- **窗口管理**: Case级别的日志读取指针，防止重复计算
- 完整的使用示例和最佳实践

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    NANO测试套件架构                      │
├─────────────────────────────────────────────────────────┤
│  🎯 DSL用例文件 (.mgo)                                   │
│  ├── >>> 循环次数                                      │
│  ├── [客户端]指令 参数                                  │
│  ├── [EXP]断言类型 期望值                               │
│  └── <<<                                                │
├─────────────────────────────────────────────────────────┤
│  🔍 DSL解析层 (dsl_engine.py)                           │
│  ├── DSLEngine: 语法解析和验证                           │
│  ├── DSLCommand: 指令对象                               │
│  └── 环境变量替换                                        │
├─────────────────────────────────────────────────────────┤
│  ⚙️ 执行控制层 (runner_engine.py)                       │
│  ├── NANORunner: 主执行引擎                             │
│  ├── SystemManager: 系统操作管理                        │
│  ├── AssertionEngine: 断言验证引擎                      │
├─────────────────────────────────────────────────────────┤
│  🧪 测试入口层 (test_nano.py)                           │
│  ├── TestNANO: Pytest测试类                            │
│  ├── AssertionDataManager: 断言数据管理                 │
│  └── 回调处理和结果收集                                  │
├─────────────────────────────────────────────────────────┤
│  🔌 客户端接口层 (client.py)                           │
│  ├── NANOClientManager: 客户端生命周期管理              │
│  ├── NANOClient: 单客户端操作封装                       │
│  └── C++ SDK ctypes接口封装                            │
└─────────────────────────────────────────────────────────┘
```

## 💡 DSL语法示例

### Class Fixture (前后置)
```yaml
# d.mgo
# SETUP块只在所有测试开始前执行一次
>>> SETUP
[SYS]PULL AIBSServer cmn {"brand":"0"}
[SYS]PULL LCSEngine cmn
[TSA]CREATE cmn com.autoai.vr.service_vrassistant
<<<

# 第一个测试用例
>>>
[TSA]START 1
[TSA]TEXT 打电话给张三
[TSA]STOP
<<<

# 第二个测试用例
>>>
[TSA]START 1
[TSA]TEXT 导航到公司
[TSA]STOP
<<<

# TEARDOWN块在所有测试结束后执行一次
>>> TEARDOWN
[TSA]FREE
[SYS]KILL AIBSServer
[SYS]KILL LCSEngine
<<<
```

### 基础测试用例
```yaml
>>> 1
# 语音识别基础测试
[TSA]CREATE cmn com.autoai.vr.service_vrassistant
[TSA]START 1
[TSA]DATA TestAudio/audio/weather_query.wav
[EXP]cloudASRResult [0]asr:今天天气怎么样;confidence:>80 <timeout=5>
[EXP]NLPResult [0]skill:WEATHER;intention:QUERY <timeout=5>
[TSA]STOP
[TSA]FREE
<<<
```

### 多客户端协作
```yaml
>>>1
# 多客户端并发测试
[SYS]PULL AIBSServer cmn {"brand":"0"}
[SYS]SLEEP 2
[TSA]CREATE cmn com.autoai.vr.service_vrassistant
[SET]CREATE cmn com.pachira.set
[TSA]START 1
[SET]SETVRCONFIG WAKEUP_ALIAS 你好小白 cmn
[EXP]WAKEUP_ALIAS_RET code:0
[TSA]DATA TestAudio/audio/wakeup.wav
[EXP]cloudASRResult asr:你好小白 <timeout=5>
[TSA]FREE
[SET]FREE
[SYS]KILL AIBSServer
<<<
```

### 声纹功能测试
```yaml
>>> 1
# 声纹注册和验证
[TSA]CREATE cmn com.autoai.vr.service_vrassistant
[SET]CREATE cmn com.setting.com
[SET]START_SPEAKER_ENROLL user001 测试文本 1 0
[EXP]START_SPEAKER_ENROLL_RET code:0
[SET]DATA TestAudio/audio/enroll_voice.wav
[EXP]startEnroll userId:user001
[SET]END_SPEAKER_ENROLL
[SET]VERIFY_VOICEPRINT user001 测试文本 0
[SET]DATA TestAudio/audio/verify_voice.wav
[SET]FREE
<<<
```

### 文件操作和报告管理
```yaml
>>> 1
# 动态修改配置文件并添加到报告
# 1. 更新JSON配置文件
[SYS]UPLOAD JSON {WORKPATH}/daemon_tag.json data.text.start 320
[SYS]UPLOAD JSON {WORKPATH}/config.json app.enabled true

# 2. 更新配置文件行
[SYS]UPLOAD LINE {WORKPATH}/decoder.conf ASK_SIL_DURATION 540
[SYS]UPLOAD LINE {WORKPATH}/decoder.conf LANGUAGE cmn

# 3. 验证配置文件修改是否生效（文件断言）
[EXP]FILEDIF JSON {WORKPATH}/daemon_tag.json data.text.start=320
[EXP]FILEDIF JSON {WORKPATH}/config.json app.enabled=true

# 4. 执行测试
[SYS]PULL AIBSServer cmn {"brand":"0"}
[SYS]SLEEP 2
[TSA]CREATE cmn com.autoai.vr.service_vrassistant
[TSA]START 1
[TSA]DATA {WORKPATH}/audio/test.wav
[EXP]cloudASRResult asr:测试结果 <timeout=3>

# 5. 将关键文件添加到Allure报告
[SYS]ALLURE TEXT {WORKPATH}/decoder.conf
[SYS]ALLURE CSV {WORKPATH}/asr_report.csv
[SYS]ALLURE JSON {WORKPATH}/config.json

# 6. 验证生成的文件（文件断言）
[EXP]FILEEXIT {WORKPATH}/asr_report.csv 1
[EXP]FILESIZE {WORKPATH}/asr_report.csv > 100

[TSA]STOP
[TSA]FREE
[SYS]KILL AIBSServer
<<<
```

### 文件断言示例
```yaml
>>> 1
# 文件断言完整示例
# 1. 验证文件存在
[EXP]FILEEXIT {WORKPATH}/lcs.zip 1

# 2. 验证文件大小
[EXP]FILESIZE {WORKPATH}/lcs.zip > 1000000

# 3. 验证文件MD5完整性
[EXP]FILEMD5 {WORKPATH}/lcs.zip = abc123def456789

# 4. 修改配置后验证
[SYS]UPLOAD JSON {WORKPATH}/config.json data.timeout 5000
[EXP]FILEDIF JSON {WORKPATH}/config.json data.timeout=5000

# 5. 验证嵌套JSON路径
[EXP]FILEDIF JSON {WORKPATH}/daemon_tag.json data.shsh[0].txt.status=0
<<<
```

### 🆕 数据驱动测试（参数化）

#### DSL文件（使用占位符）
```yaml
# nano_parameterized.mgo
>>> SETUP
[SYS]PULL AIBSServer ${LANGUAGE} {"brand":"0"}
[SYS]PULL LCSEngine ${LANGUAGE}
[SYS]PULL SpeechEngine ${LANGUAGE}
[TSA]CREATE ${LANGUAGE} com.autoai.vr.service_vrassistant
<<<

>>> TEARDOWN
[TSA]FREE
[SYS]KILL SpeechEngine
[SYS]KILL LCSEngine
[SYS]KILL AIBSServer
<<<

# 参数化测试模板 - 根据CSV自动生成多个测试实例
>>>
[TSA]START 1
[TSA]TEXT ${text}
[EXP]NLPResult skill:${skill};intention:${intention} <timeout=2>
[TSA]STOP
<<<

# 普通测试（不使用占位符）
>>>
[TSA]START 1
[TSA]TEXT 今天天气怎么样
[EXP]NLPResult skill:WEATHER <timeout=2>
[TSA]STOP
<<<
```

#### CSV数据文件
```csv
text,skill,intention,LANGUAGE
打电话给张三,Phone,CALL,cmn
拨打张三的电话,Phone,CALL,cmn
给10086打电话,Phone,CALL,cmn
导航到公司,Navigation,NAVI,cmn
去北京天安门,Navigation,NAVI,cmn
播放周杰伦的歌,Music,PLAY,cmn
```

#### 执行效果
- **SETUP/TEARDOWN**: 使用CSV第一行数据（`LANGUAGE=cmn`），只执行一次
- **第1个TEST块**: 生成6个测试实例（对应CSV的6行数据）
  - `nano_parameterized.mgo[0_P1]`: text=打电话给张三
  - `nano_parameterized.mgo[0_P2]`: text=拨打张三的电话
  - `nano_parameterized.mgo[0_P3]`: text=给10086打电话
  - `nano_parameterized.mgo[0_P4]`: text=导航到公司
  - `nano_parameterized.mgo[0_P5]`: text=去北京天安门
  - `nano_parameterized.mgo[0_P6]`: text=播放周杰伦的歌
- **第2个TEST块**: 保持原样，只生成1个测试实例

#### 关键特性
1. **占位符语法**: `${variable}` - 简洁直观
2. **智能检测**: 
   - 如果DSL中有 `${variable}` 但未提供 `-P` 参数，会报错提示
   - 如果CSV中缺少某个变量列，会报错提示具体缺失的变量名
3. **路径支持**: CSV文件路径支持相对路径（相对于.mgo文件）和绝对路径
4. **Allure报告**: 每个参数化实例在报告中独立展示，包含完整的参数信息表格

## 🛠️ 开发和调试

### 详细日志模式
```bash
# 启用详细日志输出，显示DEBUG级别信息
python3 Run_Mongo.py -f NANO -V
```

### 🐛 GDB断点调试模式

NANO测试框架支持完整的GDB调试功能，可以对测试过程中的**服务进程**和**客户端进程**进行断点调试。

#### 🚀 启动GDB调试模式
```bash
# 启用GDB调试模式
python3 Run_Mongo.py -f NANO -g -C config.conf -a test.mgo
```

#### 📋 调试流程说明

1. **启动测试**：使用 `-g` 参数启动测试
2. **服务进程调试**：当拉起服务时（LCSEngine、SpeechEngine、AIBSServer），框架会：
   - 启动服务进程
   - 显示进程PID和GDB attach命令
   - **暂停等待**用户在新终端中attach GDB
3. **客户端进程调试**：当加载客户端库时，框架会：
   - 加载动态库
   - 显示客户端进程信息
   - **暂停等待**用户设置断点

#### 🖥️ 实际操作步骤

**Step 1**: 启动NANO测试
```bash
python3 Run_Mongo.py -f NANO -g -C decoder.conf -a nano.mgo
```

**Step 2**: 当看到如下提示时：
```bash
============================== GDB调试模式 ================================
[AIBSServer] GDB模式已启用进程PID: 12345, 请在另一个终端执行: gdb -p 12345
设置断点后按回车继续加载动态库...
==========================================================================
```

**Step 3**: 在**新终端**中执行GDB attach：
```bash
# 终端2 - attach到AIBSServer进程
gdb -p 12345

# 在GDB中设置断点
(gdb) break aibs_create_engine
(gdb) break aibs_start_session
(gdb) continue
```

**Step 4**: 回到原终端按**回车**继续

**Step 5**: 重复上述步骤调试其他进程（LCSEngine、SpeechEngine、客户端）

#### 🎯 支持的调试目标

| 调试目标 | 触发时机 |
|----------|----------|
| **LCSEngine** | `[SYS]PULL LCSEngine` |
| **SpeechEngine** | `[SYS]PULL SpeechEngine` |
| **AIBSServer** | `[SYS]PULL AIBSServer` |
| **AIBSClient客户端进程** | Client客户端库加载so时 |

```bash
# 可以同时在多个终端中调试不同进程
终端1: python3 Run_Mongo.py -f NANO -g
终端2: gdb -p <LCSEngine_PID>
终端3: gdb -p <SpeechEngine_PID>  
终端4: gdb -p <AIBSServer_PID>
```

### 测试报告
```bash
# 生成Allure报告
allure serve workspace/reports/
```

## 📊 功能统计

- **客户端类型**: 15种业务客户端 + SYS/EXP（TSA/SET/VOI/OMS/TTS/HWK/PST/TIA/CPL/NIS/NSE/ENR/PIS/TSS/TSR）
- **Fixture支持**: Class级别的SETUP和TEARDOWN
- **系统操作指令**: 11个（PULL、KILL、SLEEP、CMD、PRINT、ENV、UPLOAD、ALLURE、FOTA_RANDOM_ZIP、BREF、CLEAR_ASSERT）
- **断言类型**: 20+种回调断言 + 30+种API断言 + 4种文件断言 + 3种日志断言模式
- **文件断言**: FILEEXIT（存在性）、FILESIZE（大小）、FILEMD5（MD5值）、FILEDIF（JSON内容）
- **日志断言**: SEARCH（关键字搜索）、MATCH（精准匹配，支持KV/JSON/EXTRACT）、DIFF（时间差计算）
- **环境变量**: 18个内置变量
- **接口覆盖率**: 100%（aibs_client_api.h）
- **文件操作**: 支持JSON、LINE、REPLACE三种文件更新方式
- **数据驱动**: 支持CSV参数化，占位符语法`${variable}`，自动展开测试实例

## 🤝 贡献指南

1. 遵循现有的代码风格和文档格式
2. 新增指令需要同时更新COMMAND.md文档
3. 新增断言类型需要更新EXPECT.md或LOG_ASSERTION.md文档
4. 所有变更需要包含相应的测试用例

## 📧 技术支持

如有问题或建议，请联系baihuidong

---

**NANO测试套件 - 让语音SDK测试更简单、更可靠、更高效！**

**Write By Baihuidong 2025/10/20**
**Updated 2025/12/30 - 新增日志断言功能：支持SEARCH、MATCH（KV/JSON/EXTRACT）、DIFF三种模式，提供强大的日志验证能力**
**Updated 2025/11/06 - 新增Class级别Fixture功能**
**Updated 2025/11/07 - 新增超时断言功能：支持 `<timeout=X>` 语法，使用信号量机制等待异步回调**
**Updated 2025/10/27 - 新增文件断言功能：FILEEXIT、FILESIZE、FILEMD5、FILEDIF**
**Updated 2025/11/07 - 新增数据驱动测试功能：支持CSV参数化，`${variable}`占位符语法，自动生成测试实例**