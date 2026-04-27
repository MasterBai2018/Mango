# TSR (Test Suite Report) 客户端文档

## 概述

TSR（Test Suite Report）客户端是一个独立的 Suite 级别统计和报告生成工具，用于在测试执行完成后（通常在 `SUITE_TEARDOWN` 阶段）进行结果统计、准确率计算和报告生成。

### 特点

- **独立运行**：不依赖 NANORunner，可在测试结束后独立执行
- **装饰器注册**：采用装饰器自动注册机制，易于扩展新指令
- **环境变量支持**：完整支持框架的环境变量系统（如 `{WORKPATH}`、`{SUITEID}` 等）
- **命令行工具**：每个指令都支持独立命令行运行，便于调试和单独使用

## 指令列表

| 指令 | 功能 | 状态 |
|------|------|------|
| `ASR_ACCURACY` | ASR 准确率计算 | ✅ 已实现 |
| `ASR_LANGUAGE` | ASR 语种识别正确率 | ✅ 已实现 |
| `DELAY` | ASR 实时/最终结果时延分析 | ✅ 已实现 |
| `WAKEUP_ACCURACY` | 唤醒词 FA/FR 准确率计算 | ✅ 已实现 |
| `VAD_ACCURACY` | VAD FA/FR 检测率计算 | ✅ 已实现 |
| `VAD_PRECISION` | VAD 时间边界精度分析 | ✅ 已实现 |
| `TIME_BOUNDARY_ACCURACY` | 时间边界误差统计 | ✅ 已实现 |
| `LLM` | 大模型离线批量智能评测 | ✅ 已实现 |
| `PSTT_ACCURACY` | PSTT 测试集综合统计 | ✅ 已实现 |

## 使用方式

### 1. 在 DSL 测试用例中使用

```yaml
>>> SUITE_TEARDOWN
# 在 Suite 结束时计算 ASR 准确率
[TSR]ASR_ACCURACY result={WORKPATH}/asr.csv ref=TestCase/ref/answer.csv output={WORKPATH}/asr_report.xlsx
<<<
```

### 2. 独立命令行运行

```bash
# 进入项目目录
cd /path/to/mango

# 执行 ASR 准确率计算
python3 src/testsuite/NANO/tools/tsr/asr_accuracy.py \
  -r <识别结果.csv> \
  -ref <参考答案.csv> \
  -o <报告输出.xlsx>
```

---

## ASR_ACCURACY 指令

### 功能说明

`ASR_ACCURACY` 用于计算 ASR（自动语音识别）的准确率，支持以下指标：

| 指标 | 说明 | 计算方式 |
|------|------|----------|
| **句准率** | 完全匹配的比例 | 正确数 / 总数 |
| **字准率** | 字符级准确率 | 1 - (替换+插入+删除) / 参考文本总字数 |
| **插入率** | 识别结果中多余字符的比例 | 插入数 / 参考文本总字数 |
| **删除率** | 识别结果中缺失字符的比例 | 删除数 / 参考文本总字数 |
| **替换率** | 识别结果中替换字符的比例 | 替换数 / 参考文本总字数 |
| **空结果率** | 识别结果为空的比例 | 空结果数 / 总数 |

### DSL 语法

```
[TSR]ASR_ACCURACY result=<识别结果文件> ref=<参考答案文件> [output=<报告输出路径>]
```

#### 参数说明

| 参数 | 必需 | 说明 |
|------|------|------|
| `result=` | ✅ | 识别结果 CSV 文件路径 |
| `ref=` | ✅ | 参考答案 CSV 文件路径 |
| `output=` | ❌ | Excel 报告输出路径（默认：`{WORKPATH}/asr_accuracy.xlsx`）|

### 输入文件格式

#### 识别结果文件（result）

支持 Tab 或逗号分隔的 CSV 文件，需包含以下字段：

| 字段 | 说明 |
|------|------|
| `voice` | 音频文件路径（作为关联 key）|
| `result` | 识别结果文本 |
| `type` | 回调类型（用于过滤最终结果）|
| `confidence` | 置信度（可选）|

**类型过滤规则**：只保留 `*ASRResult` 类型的最终结果，自动过滤 `*ASRResultTemp` 中间结果。

支持的类型：
- `ASRResult`
- `cloudASRResult`
- `localASRResult`
- `SpeechASRResult`
- `PSTTASRResult`
- `TiTanASRResult`

**示例**：
```csv
voice	result	type	channel	start	end	confidence
TestAudio/test1.wav	打开空调	TiTanASRResult	0	0.92	1.84	99
TestAudio/test2.wav	导航去公司	TiTanASRResult	0	1.04	2.48	97
```

#### 参考答案文件（ref）

支持 Tab 或逗号分隔的 CSV 文件，需包含音频路径和标准答案文本。

**支持的字段名**：

| 音频路径字段（任选一个） | 文本字段（任选一个） |
|-------------------------|---------------------|
| `AUDIOPATH` | `TEXT` |
| `audiopath` | `text` |
| `voice` | `ref` |
| `audio` | `reference` |
| `path` | `answer` |

**示例**：
```csv
AUDIOPATH	TEXT
TestAudio/test1.wav	打开空调
TestAudio/test2.wav	导航去公司
```

### 输出

#### 1. 终端 Summary

```
********************************************************************************
********************************* ASR_ACCURACY *********************************
********************************************************************************
  总数: 17  |  正确: 16  |  错误: 1  |  空结果: 0

  句准率:     94.12%    (完全匹配的比例)
  字准率:     98.33%    (字符级准确率)
  插入率:      0.00%    (插入错误比例)
  删除率:      0.00%    (删除错误比例)
  替换率:      1.67%    (替换错误比例)
  空结果率:    0.00%    (空结果比例)

  详细报告: /path/to/asr_accuracy_report.xlsx
********************************************************************************
```

#### 2. Excel 详细报告

生成的 Excel 文件包含 3 个 Sheet：

| Sheet | 内容 |
|-------|------|
| **汇总统计** | 总数、正确数、错误数、各项准确率指标及说明 |
| **详细结果** | 每条数据的对比结果、置信度、编辑距离、状态（正确/错误）|
| **错误详情** | 仅显示错误数据，便于快速定位问题 |

### 使用示例

#### 示例 1：基础用法

```yaml
>>> SUITE_TEARDOWN
[TSR]ASR_ACCURACY result={WORKPATH}/asr.csv ref=TestCase/ref/cmn_answer.csv
<<<
```

#### 示例 2：指定输出路径

```yaml
>>> SUITE_TEARDOWN
[TSR]ASR_ACCURACY result={WORKPATH}/asr.csv ref=TestCase/ref/cmn_answer.csv output={WORKPATH}/my_report.xlsx
<<<
```

#### 示例 3：使用环境变量

```yaml
>>> SUITE_TEARDOWN
# 使用 WORKSPACE 环境变量
[TSR]ASR_ACCURACY result={WORKSPACE}/asr.csv ref={ROOTPATH}/TestCase/ref/answer.csv output={WORKSPACE}/report_{SUITEID}.xlsx
<<<
```

### 命令行独立运行

```bash
# 查看帮助
python3 src/testsuite/NANO/tools/tsr/asr_accuracy.py -h

# 基础用法
python3 src/testsuite/NANO/tools/tsr/asr_accuracy.py \
  -r workspace/asr.csv \
  -ref TestCase/ref/answer.csv

# 指定输出路径
python3 src/testsuite/NANO/tools/tsr/asr_accuracy.py \
  -r workspace/asr.csv \
  -ref TestCase/ref/answer.csv \
  -o /tmp/my_report.xlsx
```

---

## ASR_LANGUAGE 指令

### 功能说明

`ASR_LANGUAGE` 用于计算 ASR 识别结果中**语种识别的正确率**。适用于多语种 ASR 场景下，验证语种检测的准确性。

| 指标 | 说明 | 计算方式 |
|------|------|----------|
| **语种正确率** | 语种识别正确的比例 | 正确数 / 总数 |
| **空结果率** | 无语种信息的比例 | 空结果数 / 总数 |

### DSL 语法

```
[TSR]ASR_LANGUAGE result=<识别结果文件> ref=<期望语种> [output=<报告输出路径>]
```

#### 参数说明

| 参数 | 必需 | 说明 |
|------|------|------|
| `result=` | ✅ | 识别结果 CSV 文件路径 |
| `ref=` | ✅ | 期望的语种代码（如 `cmn`、`en`、`yue`）|
| `output=` | ❌ | Excel 报告输出路径（默认：`{WORKPATH}/asr_language.xlsx`）|

### 语种匹配规则

| 原始值 | 标准化后 | 说明 |
|--------|----------|------|
| `zh-cmn` | `cmn` | 普通话 |
| `cmn` | `cmn` | 普通话 |
| `zh-yue` | `yue` | 粤语 |
| `yue` | `yue` | 粤语 |
| `en` | `en` | 英语 |

- 语种代码**不区分大小写**
- `zh-xxx` 格式会自动转换为 `xxx` 格式

### 输入文件格式

#### 识别结果文件（result）

支持 Tab 或逗号分隔的 CSV 文件，需包含以下字段：

| 字段 | 说明 |
|------|------|
| `voice` | 音频文件路径（作为关联 key）|
| `lang` | 识别的语种代码 |
| `type` | 回调类型（用于过滤最终结果）|
| `confidence` | 置信度（可选）|

**类型过滤规则**：与 `ASR_ACCURACY` 相同，只保留 `*ASRResult` 类型的最终结果。

**示例**：
```csv
voice	result	type	lang	confidence
TestAudio/test1.wav	打开空调	TiTanASRResult	zh-cmn	99
TestAudio/test2.wav	hello world	TiTanASRResult	en	97
```

### 输出

#### 1. 终端 Summary

```
************************************* ASR_LANGUAGE ***************************************
*  期望语种: cmn
*  总数: 17  |  正确: 16  |  错误: 1  |  空结果: 0
*  语种正确率:   94.12% (16/17)	(语种识别正确的比例)
*  空结果率:      0.00% (0/17)	(无语种信息的比例)
*  语种分布: cmn:16, en:1
*  详细报告: /path/to/asr_language.xlsx
******************************************************************************************
```

#### 2. Excel 详细报告

生成的 Excel 文件包含 3 个 Sheet：

| Sheet | 内容 |
|-------|------|
| **汇总统计** | 期望语种、总数、正确数、错误数、语种分布统计 |
| **详细结果** | 每条数据的检测语种、标准化语种、期望语种、状态、置信度 |
| **错误详情** | 仅显示语种识别错误的数据，便于快速定位问题 |

### 使用示例

#### 示例 1：基础用法

```yaml
>>> SUITE_TEARDOWN
[TSR]ASR_LANGUAGE result={WORKPATH}/asr.csv ref=cmn
<<<
```

#### 示例 2：指定输出路径

```yaml
>>> SUITE_TEARDOWN
[TSR]ASR_LANGUAGE result={WORKPATH}/asr.csv ref=cmn output={WORKPATH}/lang_report.xlsx
<<<
```

#### 示例 3：验证英语语种

```yaml
>>> SUITE_TEARDOWN
[TSR]ASR_LANGUAGE result={WORKPATH}/asr.csv ref=en
<<<
```

### 命令行独立运行

```bash
# 查看帮助
python3 src/testsuite/NANO/tools/tsr/asr_language.py -h

# 基础用法
python3 src/testsuite/NANO/tools/tsr/asr_language.py \
  -r workspace/asr.csv \
  -ref cmn

# 指定输出路径
python3 src/testsuite/NANO/tools/tsr/asr_language.py \
  -r workspace/asr.csv \
  -ref cmn \
  -o /tmp/lang_report.xlsx
```

---

## DELAY 指令

### 功能说明

`DELAY` 用于分析 ASR 识别结果的**上屏时延**，支持两种模式：

| 模式 | 触发条件 | 说明 |
|------|----------|------|
| **实时上屏时延** | `type` 以 `Temp` 结尾 | 分析每一条中间上屏结果的时延，同时统计上屏间隔、卡顿率、缺失率 |
| **最终结果时延** | `type` 不以 `Temp` 结尾 | 分析最终断句结果的整体上屏时延 |

#### 统计指标

**通用指标**（两种模式均有）：

| 指标 | 说明 | 计算方式 |
|------|------|----------|
| **最小时延** | 所有测量点中最小的时延 | `min(audiotime - label_end_time)` |
| **最大时延** | 所有测量点中最大的时延 | `max(audiotime - label_end_time)` |
| **平均时延** | 所有测量点的平均时延 | `mean(audiotime - label_end_time)` |

**实时模式专有指标**：

| 指标 | 说明 | 计算方式 |
|------|------|----------|
| **上屏间隔方差** | 相邻结果 audiotime 差的方差，反映上屏节奏稳定性 | `variance(gaps)` |
| **瞬时吐字率** | 间隔极短（≤ 10 ms）的比例，反映连续快速上屏情况 | 极短间隔数 / 总间隔数 |
| **识别卡顿率** | 间隔较长（≥ 300 ms）的比例，反映中途停顿情况 | 超长间隔数 / 总间隔数 |
| **上屏结果缺失率** | 期望按字数逐步增加的上屏步数中缺失的比例 | 缺失步数 / 期望总步数 |

### DSL 语法

```
[TSR]DELAY ref=<标注文件> result=<callback_jsonl> type=<回调类型> [output=<报告输出路径>]
```

#### 参数说明

| 参数 | 必需 | 说明 |
|------|------|------|
| `ref=` | ✅ | 卡拉OK式标注文件路径 |
| `result=` | ✅ | `callback.jsonl` 文件路径 |
| `type=` | ✅ | 回调类型；以 `Temp` 结尾 → 实时上屏模式，否则 → 最终结果模式 |
| `output=` | ❌ | Excel 报告输出路径（默认：`{WORKPATH}/delay.xlsx`）|

### 输入文件格式

#### 标注文件（ref）—— 卡拉OK式

每行一句独立发话，格式为：

```
<音频路径>   <时间0>字0<时间1>字1...<时间N>
```

**规则说明**：
- 每个字的结束时间 = 它后面的时间标记
- 最后一个 `<timeN>`（后面没有文字）是整句的结束时间点
- 时间单位：**秒（float）**
- 同一音频的多段发话各占一行

**示例**：
```
TestAudio/1.wav   <0.3>打<0.5>开<0.8>车<1.2>窗<1.5>
TestAudio/1.wav   <3.3>关<3.5>闭<3.8>空<4.2>调<4.5>
TestAudio/2.wav   <0.3>你<0.5>好<0.8>
```

解读第一行：「打」结束于 0.5s，「开」结束于 0.8s，「车」结束于 1.2s，「窗」结束于 1.5s（整句结束）。

#### callback.jsonl 文件（result）

由测试框架的 `TestNANO` 回调函数自动写入，每行一条 JSON，需包含以下字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `callback_type` | str | 回调类型，与 `type` 参数对应 |
| `data.audio` | str | 音频文件路径 |
| `data.audiotime` | float | 结果对应的音频时间点（**秒**）|
| `data.asr` | str | 识别文本 |
| `data.start` | int | 音频起始时间（**毫秒**，内部自动转换）|
| `data.end` | int | 音频结束时间（**毫秒**，内部自动转换）|

**示例**：
```jsonl
{"client_name": "pstt", "callback_type": "PSTTASRResultTemp", "timestamp": 1700000001.23, "data": {"audio": "TestAudio/1.wav", "audiotime": 0.52, "asr": "打", "start": 0, "end": 1500}}
{"client_name": "pstt", "callback_type": "PSTTASRResultTemp", "timestamp": 1700000001.85, "data": {"audio": "TestAudio/1.wav", "audiotime": 0.84, "asr": "打开", "start": 0, "end": 1500}}
{"client_name": "pstt", "callback_type": "PSTTASRResult", "timestamp": 1700000002.10, "data": {"audio": "TestAudio/1.wav", "audiotime": 1.52, "asr": "打开车窗", "start": 0, "end": 1500}}
```

### 输出

#### 1. 终端 Summary

**实时上屏模式**：
```
********************************************************************************
*********************************** DELAY **************************************
********************************************************************************
  分析类型    : 实时上屏时延
  回调类型    : PSTTASRResultTemp
  已匹配发话  : 20
  未匹配发话  : 0

  最小时延    : 12.5 ms
  最大时延    : 187.3 ms
  平均时延    : 58.2 ms

  上屏间隔方差  : 124.50 ms²
  瞬时吐字率    : 5.2%  （间隔 ≤ 10 ms）
  识别卡顿率    : 3.1%  （间隔 ≥ 300 ms）
  上屏结果缺失率: 2.4%

  详细报告: /path/to/delay.xlsx
********************************************************************************
```

**最终结果模式**：
```
********************************************************************************
*********************************** DELAY **************************************
********************************************************************************
  分析类型    : 最终结果时延
  回调类型    : PSTTASRResult
  已匹配发话  : 20
  未匹配发话  : 0

  最小时延    : 48.0 ms
  最大时延    : 312.7 ms
  平均时延    : 143.5 ms

  详细报告: /path/to/delay.xlsx
********************************************************************************
```

#### 2. Excel 详细报告

生成的 Excel 文件包含 4 个 Sheet：

| Sheet | 内容 | 模式 |
|-------|------|------|
| **汇总** | 分析模式、回调类型、匹配数、最小/最大/平均时延及实时专项指标 | 两种模式 |
| **时延明细** | 每条测量点的音频名、发话文本、识别文本、字数、标注结束时间、audiotime、时延值 | 两种模式 |
| **上屏间隔分布** | 相邻两条实时结果的 audiotime 差值、是否瞬时吐字/卡顿 | 仅实时模式 |
| **上屏缺失明细** | 每句发话的期望上屏次数、实际上屏次数、缺失次数、缺失率、缺失的字数位置 | 仅实时模式 |

### 使用示例

#### 示例 1：实时上屏时延分析

```yaml
>>> SUITE_TEARDOWN
[TSR]DELAY ref=TestCase/ref/label.txt result={WORKPATH}/callback.jsonl type=PSTTASRResultTemp
<<<
```

#### 示例 2：最终结果时延分析

```yaml
>>> SUITE_TEARDOWN
[TSR]DELAY ref=TestCase/ref/label.txt result={WORKPATH}/callback.jsonl type=PSTTASRResult
<<<
```

#### 示例 3：指定输出路径

```yaml
>>> SUITE_TEARDOWN
[TSR]DELAY ref=TestCase/ref/label.txt result={WORKPATH}/callback.jsonl type=TiTanASRResultTemp output={WORKPATH}/delay_report.xlsx
<<<
```

#### 示例 4：使用环境变量

```yaml
>>> SUITE_TEARDOWN
[TSR]DELAY ref={ROOTPATH}/TestCase/ref/label.txt result={WORKPATH}/callback.jsonl type=PSTTASRResultTemp output={WORKPATH}/delay_{SUITEID}.xlsx
<<<
```

### 命令行独立运行

```bash
# 查看帮助
python3 src/testsuite/NANO/tools/tsr/delay.py -h

# 实时上屏时延分析
python3 src/testsuite/NANO/tools/tsr/delay.py \
  -ref TestCase/ref/label.txt \
  -r workspace/callback.jsonl \
  -t PSTTASRResultTemp

# 最终结果时延分析，指定输出路径
python3 src/testsuite/NANO/tools/tsr/delay.py \
  -ref TestCase/ref/label.txt \
  -r workspace/callback.jsonl \
  -t PSTTASRResult \
  -o /tmp/delay_report.xlsx
```

#### 命令行参数

| 参数 | 简写 | 必需 | 说明 |
|------|------|------|------|
| `--ref` | `-ref` | ✅ | 卡拉OK式标注文件路径 |
| `--result` | `-r` | ✅ | callback.jsonl 文件路径 |
| `--type` | `-t` | ✅ | 回调类型 |
| `--output` | `-o` | ❌ | 输出路径（默认：当前目录/delay.xlsx）|

---

## WAKEUP_ACCURACY 指令

### 功能说明

`WAKEUP_ACCURACY` 用于计算唤醒词检测的 **FA/FR 准确率**，对比参考唤醒标注文件与实际识别结果，输出以下指标：

| 指标 | 说明 | 计算方式 |
|------|------|----------|
| **唤醒率** | 成功唤醒的比例 | (Ref 总数 - FR 数) / Ref 总数 |
| **FA 误检率** | 多余误检的比例 | FA 数 / Result 总数 |
| **FR 漏检率** | 漏检的比例 | FR 数 / Ref 总数 |
| **关键词错误率** | 时间重叠但关键词不一致的比例 | 关键词错误数 / Ref 总数 |
| **唤醒音区检测** | `ref.channel` 与 `result.channel` 一致性校验（可选启用） | 逐条配对后比较 channel，输出 Pass/Faild |
| **断句数** | 1 个 ref 段被识别为多段（不计 FA/FR）| — |
| **连句数** | 多个 ref 段被识别为 1 段（不计 FA/FR）| — |

#### 新增说明（channel 音区检测）

- `result` 文件支持新增可选列 `channel`，用于表示唤醒结果来自哪个声道。
- `ref` 文件支持可选第 5 列 `channel`（位于最后一列）。
- 当 `ref` 提供 `channel` 列时，自动启用“唤醒音区检测”统计，输出以下字段：
  - 参考关键字、参考开始时间、参考结束时间、参考channel
  - 实际关键字、实际开始时间、实际结束时间、实际channel
  - 唤醒音区检测结果（Pass/Faild）
- 当 `ref` 只有 4 列（无 `channel`）时，不启用该统计，保持原有 FA/FR/关键词错误逻辑不变。

#### 判定规则

| 情况 | 条件 | 计入 |
|------|------|------|
| 正确匹配 | 时间重叠 且 关键词一致 | 匹配数 |
| 关键词错误 | 时间重叠 但 关键词不一致 | 关键词错误（不计 FA/FR）|
| FA（误检） | result 有，ref 无时间重叠 | FA |
| FR（漏检） | ref 有，result 无时间重叠 | FR |
| 断句 | 1 个 ref → ≥2 个 result，全部完全匹配 | 断句（不计 FA/FR）|
| 连句 | ≥2 个 ref → 1 个 result，全部完全匹配 | 连句（不计 FA/FR）|

### DSL 语法

```
[TSR]WAKEUP_ACCURACY result=<识别结果文件> ref=<参考唤醒文件> [output=<报告输出路径>]
```

#### 参数说明

| 参数 | 必需 | 说明 |
|------|------|------|
| `result=` | ✅ | 识别结果 CSV 文件路径（有表头）|
| `ref=` | ✅ | 参考唤醒文件路径（无表头）|
| `output=` | ❌ | Excel 报告输出路径（默认：`{WORKPATH}/wakeup_accuracy.xlsx`）|

### 输入文件格式

#### 识别结果文件（result）—— 有表头 CSV

| 字段 | 说明 |
|------|------|
| `audio` | 音频文件路径 |
| `result` | 识别到的关键词 |
| `start` | 唤醒开始时间（秒）|
| `end` | 唤醒结束时间（秒）|
| `channel` | 唤醒输出声道（可选）|

**示例**：
```csv
audio,result,start,end,channel
TestAudio/noise.wav,你好小云,1.23,2.10,0
TestAudio/noise.wav,你好小云,8.40,9.15,1
```

#### 参考唤醒文件（ref）—— 无表头 CSV

列顺序为：`音频路径, 关键词, 开始时间(s), 结束时间(s)[,channel]`

**示例**：
```csv
TestAudio/noise.wav,你好小云,1.20,2.05,0
TestAudio/noise.wav,你好小云,8.35,9.10,1
TestAudio/speech.wav,你好小云,0.50,1.30,0
```

### 输出

#### 1. 终端 Summary

```
***************************** WAKEUP_ACCURACY *****************************
*  Ref 总数:   100  |  Result 总数: 98
*  匹配数:     95  |  断句: 1  |  连句: 0
*
*  总唤醒率:       96.00%  (96/100)
*  FA 误检率:       1.02%  (1/98)
*  FR 漏检率:       4.00%  (4/100)
*  关键词错误率:    1.00%  (1/100)
*  唤醒音区检测:    Pass 92 / Faild 4 / Total 96
*
*  详细报告: /path/to/wakeup_accuracy.xlsx
***************************************************************************
```

#### 2. Excel 详细报告

生成的 Excel 文件包含 6~7 个 Sheet（是否包含“唤醒音区检测”取决于 ref 是否提供 channel）：

| Sheet | 内容 |
|-------|------|
| **概要** | 参考/结果文件路径、汇总统计、每条音频唤醒率（按唤醒率高低色标）|
| **FA详情** | 误检的结果段（result 有，ref 无匹配）|
| **FR详情** | 漏检的参考段（ref 有，result 无匹配）|
| **关键词错误** | 时间重叠但关键词不一致的配对 |
| **Signal** | result 文件全览，每条附状态（匹配/FA/关键词错误/断句/连句）|
| **Ref** | ref 文件全览，每条附状态（匹配/FR/关键词错误/断句/连句）|
| **唤醒音区检测** | 当 ref 提供 channel 时生成，展示 ref/result channel 一致性与 Pass/Faild 结果 |

#### 概要 Sheet 唤醒率色标

| 颜色 | 含义 |
|------|------|
| 🟢 绿色 | 唤醒率 ≥ 95% |
| ⚪ 无色 | 80% ≤ 唤醒率 < 95% |
| 🔴 红色 | 唤醒率 < 80% |

### 使用示例

#### 示例 1：基础用法

```yaml
>>> SUITE_TEARDOWN
[TSR]WAKEUP_ACCURACY result={WORKPATH}/wakeup.csv ref=TestCase/ref/wakeup_ref.csv
<<<
```

#### 示例 2：指定输出路径

```yaml
>>> SUITE_TEARDOWN
[TSR]WAKEUP_ACCURACY result={WORKPATH}/wakeup.csv ref=TestCase/ref/wakeup_ref.csv output={WORKPATH}/wakeup_report.xlsx
<<<
```

#### 示例 3：使用环境变量

```yaml
>>> SUITE_TEARDOWN
[TSR]WAKEUP_ACCURACY result={WORKPATH}/wakeup.csv ref={ROOTPATH}/TestCase/ref/wakeup_ref.csv output={WORKPATH}/wakeup_{SUITEID}.xlsx
<<<
```

### 命令行独立运行

```bash
# 查看帮助
python3 src/testsuite/NANO/tools/tsr/wakeup_accuracy.py -h

# 基础用法
python3 src/testsuite/NANO/tools/tsr/wakeup_accuracy.py \
  -r workspace/wakeup.csv \
  -ref TestCase/ref/wakeup_ref.csv

# 指定输出路径
python3 src/testsuite/NANO/tools/tsr/wakeup_accuracy.py \
  -r workspace/wakeup.csv \
  -ref TestCase/ref/wakeup_ref.csv \
  -o /tmp/wakeup_report.xlsx
```

#### 命令行参数

| 参数 | 简写 | 必需 | 说明 |
|------|------|------|------|
| `--result` | `-r` | ✅ | 识别结果 CSV 文件路径（有表头）|
| `--reference` | `-ref` | ✅ | 参考唤醒文件路径（无表头）|
| `--output` | `-o` | ❌ | 输出路径（默认：当前目录/mango_report/）|

---

## VAD_ACCURACY 指令

### 功能说明

`VAD_ACCURACY` 用于计算 VAD（语音活动检测）的 **FA/FR 准确率**。与 `WAKEUP_ACCURACY` 的核心差异是：**VAD 无关键词概念，时间重叠即为正确匹配**。

| 指标 | 说明 | 计算方式 |
|------|------|----------|
| **检测率** | 成功检测的比例 | (Ref 总数 - FR 数) / Ref 总数 |
| **FA 误检率** | 多余误检的比例 | FA 数 / Result 总数 |
| **FR 漏检率** | 漏检的比例 | FR 数 / Ref 总数 |
| **断句数** | 1 个 ref 段被检测为多段（不计 FA/FR）| — |
| **连句数** | 多个 ref 段被检测为 1 段（不计 FA/FR）| — |

### DSL 语法

```
[TSR]VAD_ACCURACY result=<result_txt> ref=<ref_txt> [output=<report_xlsx>]
```

#### 参数说明

| 参数 | 必需 | 说明 |
|------|------|------|
| `result=` | ✅ | VAD 识别结果文件路径 |
| `ref=` | ✅ | 参考 VAD 文件路径 |
| `output=` | ❌ | Excel 报告输出路径（默认：`{WORKPATH}/vad_accuracy.xlsx`）|

### 输入文件格式

ref 和 result 使用**相同格式**（空格分隔，无表头）：

```
音频路径  00h_S  开始时间(s)  结束时间(s)
```

**示例**：
```
TestAudio/noise.wav  00h_S  0.320000  1.450000
TestAudio/noise.wav  00h_S  5.120000  6.380000
```

### 输出

#### 1. 终端 Summary

```
***************************** VAD_ACCURACY *****************************
*  Ref 总数:   200  |  Result 总数: 195
*  匹配数:     188  |  断句: 2  |  连句: 1
*
*  总检测率:    96.00%  (192/200)
*  FA 误检率:    2.56%  (5/195)
*  FR 漏检率:    4.00%  (8/200)
*
*  详细报告: /path/to/vad_accuracy.xlsx
************************************************************************
```

#### 2. Excel 报告（5 个 Sheet）

| Sheet | 内容 |
|-------|------|
| **概要** | 参考/结果文件路径、汇总统计、每条音频检测率（按检测率高低色标）|
| **FA详情** | 误检的结果段 |
| **FR详情** | 漏检的参考段 |
| **Signal** | result 文件全览，每条附状态（匹配/FA/断句/连句）|
| **Ref** | ref 文件全览，每条附状态（匹配/FR/断句/连句）|

### 使用示例

```yaml
>>> SUITE_TEARDOWN
[TSR]VAD_ACCURACY result={WORKPATH}/vad.txt ref=TestCase/ref/vad_ref.txt
<<<
```

### 命令行独立运行

```bash
python3 src/testsuite/NANO/tools/tsr/vad_accuracy.py \
  -r workspace/vad.txt \
  -ref TestCase/ref/vad_ref.txt \
  -o /tmp/vad_accuracy.xlsx
```

---

## VAD_PRECISION 指令

### 功能说明

`VAD_PRECISION` 用于分析 VAD 检测结果的**时间边界精度**，统计 start/end 时间误差的分布。与 `VAD_ACCURACY` 的关系：
- `VAD_ACCURACY` 回答「检出了多少、漏了多少」
- `VAD_PRECISION` 回答「检出的边界误差有多大」

| 指标 | 说明 |
|------|------|
| **Start 误差** | `result_start - ref_start`（有正负方向）|
| **End 误差** | `result_end - ref_end`（有正负方向）|
| **百分位容忍值** | 60 / 70 / 80 / 90 百分位的绝对误差阈值 |

### DSL 语法

```
[TSR]VAD_PRECISION result=<result_txt> ref=<ref_txt> [output=<report_xlsx>]
```

#### 参数说明

| 参数 | 必需 | 说明 |
|------|------|------|
| `result=` | ✅ | VAD 识别结果文件路径 |
| `ref=` | ✅ | 参考 VAD 文件路径 |
| `output=` | ❌ | Excel 报告输出路径（默认：`{WORKPATH}/vad_precision.xlsx`）|

### 匹配规则

使用**贪心算法**，对每个 ref 段，找重叠比例最大的 result 段：
- 重叠比例 = 重叠时长 / min(ref 时长, result 时长)
- 最低阈值：**30%**（固定，不可配置）
- 每个 result 段只能被匹配一次

### 输入文件格式

与 `VAD_ACCURACY` 相同，ref 和 result 均为：

```
音频路径  00h_S  开始时间(s)  结束时间(s)
```

### 输出

#### 1. 终端 Summary

```
***************************** VAD_PRECISION *****************************
*  Ref 总数: 200  |  匹配: 195  |  未匹配: 5  |  匹配率: 97.50%
*
*  平均 Start 误差: 0.023400s  (23.4 ms)
*  平均 End   误差: 0.018700s  (18.7 ms)
*
*  60% 容忍值:  Start=0.015000s  End=0.012000s
*  70% 容忍值:  Start=0.025000s  End=0.020000s
*  80% 容忍值:  Start=0.045000s  End=0.035000s
*  90% 容忍值:  Start=0.080000s  End=0.065000s
*
*  详细报告: /path/to/vad_precision.xlsx
*************************************************************************
```

#### 2. Excel 报告（2 个 Sheet）

| Sheet | 内容 |
|-------|------|
| **汇总** | 基本统计、平均误差、各百分位容忍值 |
| **误差明细** | 每对匹配的 ref/result 时间 + Start 误差 + End 误差（绝对误差 > 0.1s 标红）|

### 使用示例

```yaml
>>> SUITE_TEARDOWN
# 先跑 FA/FR，再跑精度分析
[TSR]VAD_ACCURACY result={WORKPATH}/vad.txt ref=TestCase/ref/vad_ref.txt
[TSR]VAD_PRECISION result={WORKPATH}/vad.txt ref=TestCase/ref/vad_ref.txt
<<<
```

### 命令行独立运行

```bash
python3 src/testsuite/NANO/tools/tsr/vad_precision.py \
  -r workspace/vad.txt \
  -ref TestCase/ref/vad_ref.txt \
  -o /tmp/vad_precision.xlsx
```

---

## TIME_BOUNDARY_ACCURACY —— 时间边界误差统计

### 功能概述

`TIME_BOUNDARY_ACCURACY` 用于统计 **语音段起止时间的误差**，支持：

- 起点误差：`hyp_start - ref_start`（平均值 / 绝对平均值 / 最大绝对值）
- 终点误差：`hyp_end - ref_end`（平均值 / 绝对平均值 / 最大绝对值）
- 绝对时间误差：`|ΔStart|(ms)`、`|ΔEnd|(ms)`（支持阈值高亮）
- 端云边界对比：本地识别结果 vs 云端识别结果的起止时间差异

生成内容：

- **终端 Summary**：整体起点 / 终点误差的统计信息
- **Excel 报告**：支持单类型 / 端云对比（`type=both`），包含：
  - `汇总信息`：样本数量、起点/终点误差的均值、极值、百分位
  - `本地边界结果`：localASRResult 明细
  - `云端边界结果`：cloudASRResult 明细
  - `端云边界误差`：本地 vs 云端起止时间差值
- **HTML 报告**：与 Excel 内容对应的可视化页面

### 输入文件格式

支持两类结果文件：

#### 1. 纯文本时间边界文件（推荐用于离线验证）

ref/result 使用相同格式，每行一条记录，空格分隔、无表头：

```text
音频路径  标签  开始时间(s)  结束时间(s)
```

- 例如（只保留 `00h_S` 段）：

```text
TestAudio/SDK/time_boundary/0_output.wav  00h_S  1.026  2.686
TestAudio/SDK/time_boundary/0_output.wav  00h_S  4.674  6.110
```

在统计时：

- ref 文件会过滤，只保留标签为 `00h_S` 的段
- result 文件会按“最近邻时间距离”进行一一配对：
  - 距离定义：`distance_ms = sqrt(ΔStart_ms^2 + ΔEnd_ms^2)`

#### 2. JSONL 回调日志（callback.jsonl）

当 `result` 为 `.jsonl` 文件时，会按行解析 JSON，对字段有如下要求：

- `startMts` / `endMts`：起止时间，单位毫秒
- `audio` 或等价字段：音频路径（需能与 ref 中的路径匹配）
- `type` 或 `callback_type`：结果类型，用于筛选：
  - 单类型：`ASRResult` / `localASRResult` / `cloudASRResult`
  - 端云对比：`type=both` 时，同时统计 `localASRResult` 和 `cloudASRResult`

### TSR 指令用法

基本格式：

```text
[TSR]TIME_BOUNDARY_ACCURACY result=<result_file> ref=<ref_file> [output=<report_path>] [threshold=<秒>] [type=<结果类型>]
```

参数说明：

- **result**：检测结果文件路径（必需）
  - 可为 txt 边界文件或 `callback.jsonl`
- **ref**：参考时间文件路径（必需），txt 格式，`00h_S` 段
- **output**：Excel 报告输出路径（可选），不指定时使用默认路径
- **threshold**：命中阈值（单位：秒，默认 `0.3`）
  - HTML/Excel 中 `|ΔStart|(ms)` / `|ΔEnd|(ms)` 超过该阈值会标红
- **type**：结果类型（可选）：
  - `ASRResult` / `localASRResult` / `cloudASRResult`
  - `both`：同时对比本地 & 云端结果（单一报告，含 4 张表）

### 示例（TSR DSL）

```text
[TSR]TIME_BOUNDARY_ACCURACY result=workspace/solution_filter/FILTER/1/callback.jsonl \
  ref=TestAudio/SDK/time_boundary/0_output_timelist.txt \
  output=workspace/solution_filter/FILTER/1/mango_report/time_boundary_accuracy.xlsx \
  threshold=0.3 \
  type=both
```

### 命令行独立运行

```bash
python3 -m src.testsuite.NANO.tools.tsr.time_boundary_accuracy \
  -r workspace/solution_filter/FILTER/1/callback.jsonl \
  -ref TestAudio/SDK/time_boundary/0_output_timelist.txt \
  -o workspace/solution_filter/FILTER/1/mango_report/time_boundary_accuracy.xlsx \
  -t 0.3 \
  --rtype both
```

---

## LLM 指令

### 功能说明

`LLM` 是一个**万金油大模型智能评测器**。它可以读取任意格式的测试结果 CSV，套用外部 Prompt 模板，并发请求大模型（DeepSeek / OpenAI 兼容接口），强制大模型返回 JSON，然后将大模型的 JSON 结果**动态拼接**回原始数据，最后生成统一风格的 Excel + HTML 报告。

| 指标 | 说明 | 计算方式 |
|------|------|----------|
| **通过率** | score ≥ 60 的比例 | 通过数 / 总数 |
| **平均分** | 所有条目的平均 score | mean(score) |

#### 大模型返回规范

框架强制大模型必须在 JSON 中包含以下两个字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `score` | int（0-100） | 评测得分，< 60 为不及格 |
| `result` | str（`"pass"` / `"fail"`） | 由 score 推导，框架校验一致性 |

大模型可自由添加其他字段（如 `reason`、`suggestion`、`error_type` 等），这些字段会自动展开为报告新列。

### DSL 语法

```
[TSR]LLM result=<csv文件> prompt=<Prompt模板文件> [output=<报告路径>] [batch=<每批条数>]
```

#### 参数说明

| 参数 | 必需 | 默认值 | 说明 |
|------|------|--------|------|
| `result=` | ✅ | — | 待评测的原始 CSV 文件路径 |
| `prompt=` | ✅ | — | 外部 Prompt 模板文件路径，内部用 `{列名}` 占位符 |
| `output=` | ❌ | `{WORKPATH}/mango_report/llm_eval.xlsx` | Excel 报告输出路径 |
| `batch=` | ❌ | `10` | 每次请求大模型的数据条数 |

#### 环境变量

| 变量名 | 必需 | 默认值 | 说明 |
|--------|------|--------|------|
| `DEEPSEEK_API_KEY` | ✅ | — | API 密钥 |
| `DEEPSEEK_API_URL` | ❌ | `https://api.deepseek.com/v1/chat/completions` | API 地址（兼容 OpenAI 格式） |
| `DEEPSEEK_MODEL` | ❌ | `deepseek-chat` | 模型名称 |

### Prompt 模板格式

Prompt 文件描述**单条数据的评测维度**，用 `{列名}` 引用 CSV 表头中的任意字段，框架自动将多条数据组装成批量请求：

```
请评测以下语音识别结果是否满足用户意图：

用户说：{asr_text}
参考答案：{ref_text}
NLU 执行意图：{intent}
NLU 执行结果：{nlu_result}

请给出评分（0-100）和判断理由。
```

> **注意**：若 CSV 中缺少某个占位符对应的列，框架会安全地保留原始 `{列名}` 文本，不会报错。

### 输出

#### 1. 终端 Summary

```
************************************* LLM ****************************************
*  模型:      deepseek-chat
*  总数:      100
*  通过数:    87  (score ≥ 60)
*  不及格数:  13  (score < 60)
*  通过率:    87.00%  (87/100)
*  平均分:    78.35
*  详细报告:  /path/to/llm_eval.xlsx
**********************************************************************************
```

#### 2. Excel 详细报告（3 个 Sheet）

| Sheet | 内容 |
|-------|------|
| **汇总统计** | 模型名称、总数、通过数、不及格数、通过率、平均分 |
| **评测详情** | 原始 CSV 全部列 + 大模型返回的所有字段（动态列），状态列自动着色 |
| **不及格详情** | 仅显示 `result=fail` 的行，便于快速定位问题 |

#### 3. HTML 报告

与其他 TSR 指令一致，自动生成并注册到 Allure `mango-plugin` 的 "Suite 报告" 侧栏。

### 使用示例

#### 示例 1：基础用法

```yaml
>>> SUITE_TEARDOWN
[TSR]LLM result={WORKPATH}/nlu_result.csv prompt=TestCase/eval_prompts.txt
<<<
```

#### 示例 2：指定输出路径和批量大小

```yaml
>>> SUITE_TEARDOWN
[TSR]LLM result={WORKPATH}/nlu_result.csv prompt=TestCase/eval_prompts.txt output={WORKPATH}/llm_report.xlsx batch=20
<<<
```

#### 示例 3：使用环境变量

```yaml
>>> SUITE_TEARDOWN
[TSR]LLM result={WORKPATH}/nlu_result.csv prompt={ROOTPATH}/TestCase/prompts/nlu_eval.txt output={WORKPATH}/llm_{SUITEID}.xlsx batch=5
<<<
```

### 命令行独立运行

```bash
# 查看帮助
python3 src/testsuite/NANO/tools/tsr/llm.py -h

# 基础用法（需先设置环境变量）
export DEEPSEEK_API_KEY=sk-xxxx
python3 src/testsuite/NANO/tools/tsr/llm.py \
  -r workspace/nlu_result.csv \
  -p TestCase/eval_prompts.txt

# 指定输出路径和批量大小
python3 src/testsuite/NANO/tools/tsr/llm.py \
  -r workspace/nlu_result.csv \
  -p TestCase/eval_prompts.txt \
  -o /tmp/llm_report.xlsx \
  -b 5
```

#### 命令行参数

| 参数 | 简写 | 必需 | 说明 |
|------|------|------|------|
| `--result` | `-r` | ✅ | 待评测 CSV 文件路径 |
| `--prompt` | `-p` | ✅ | Prompt 模板文件路径 |
| `--output` | `-o` | ❌ | 输出路径（默认：当前目录/mango_report/llm_eval.xlsx）|
| `--batch`  | `-b` | ❌ | 每批条数（默认：10）|

---

## 扩展新指令

TSR 客户端采用装饰器自动注册机制，扩展新指令非常简单：

### 1. 创建指令文件

在 `src/testsuite/NANO/tools/tsr/` 目录下创建新的 Python 文件：

```python
# src/testsuite/NANO/tools/tsr/my_command.py

import os
import sys

# 支持独立运行和模块导入
try:
    from . import register_tsr_command
    from .base import BaseTSRHandler
except ImportError:
    _current_dir = os.path.dirname(os.path.abspath(__file__))
    _project_root = os.path.abspath(os.path.join(_current_dir, '..', '..', '..', '..', '..'))
    if _project_root not in sys.path:
        sys.path.insert(0, _project_root)
    from src.testsuite.NANO.tools.tsr import register_tsr_command
    from src.testsuite.NANO.tools.tsr.base import BaseTSRHandler


@register_tsr_command("MY_COMMAND")
class MyCommandHandler(BaseTSRHandler):
    """自定义指令处理器"""
    
    COMMAND_NAME = "MY_COMMAND"
    
    def execute(self, params: list, output_report: str = None) -> str:
        """
        执行指令
        
        Args:
            params: 参数列表
            output_report: 报告输出路径
        
        Returns:
            str: Summary 报告字符串
        """
        # 实现指令逻辑
        ...
        
        # 返回格式化的 Summary
        return self.format_summary_box("MY_COMMAND", "执行结果内容", width=80)


# 命令行入口（可选）
def main():
    import argparse
    parser = argparse.ArgumentParser(description='自定义指令')
    # 添加参数...
    args = parser.parse_args()
    
    handler = MyCommandHandler()
    summary = handler.execute([...])
    print(summary)


if __name__ == "__main__":
    main()
```

### 2. 更新 config.py（可选）

如果需要在 DSL 解析时进行指令验证，需要在 `config.py` 中注册：

```python
# src/testsuite/NANO/config.py

CLIENT_COMMANDS = {
    # ...
    'TSR': ['ASR_ACCURACY', 'MY_COMMAND'],  # 添加新指令
    # ...
}
```

### 3. 自动发现

模块加载时会自动发现并注册 `tools/tsr/` 目录下所有使用 `@register_tsr_command` 装饰器的指令。

---

## 技术细节

### 编辑距离算法

ASR_ACCURACY 使用 **Levenshtein Distance（编辑距离）** 算法计算字符级别的差异：

- **替换（Substitution）**：将一个字符替换为另一个字符
- **插入（Insertion）**：在识别结果中多出的字符
- **删除（Deletion）**：在识别结果中缺失的字符

**字符错误率（CER）计算公式**：
```
CER = (S + I + D) / N
```
其中：
- S = 替换次数
- I = 插入次数
- D = 删除次数
- N = 参考文本字符总数

**字准率 = 1 - CER**

### 文件目录结构

```
src/testsuite/NANO/tools/tsr/
├── __init__.py           # 装饰器注册机制、自动发现、指令分发
├── base.py               # 基类定义、编辑距离算法、共享工具
├── asr_accuracy.py       # ASR_ACCURACY   指令实现
├── asr_language.py       # ASR_LANGUAGE   指令实现
├── delay.py              # DELAY          指令实现
├── wakeup_accuracy.py    # WAKEUP_ACCURACY 指令实现
├── vad_accuracy.py       # VAD_ACCURACY   指令实现
├── vad_precision.py      # VAD_PRECISION  指令实现
└── time_boundary_accuracy.py # TIME_BOUNDARY_ACCURACY 时间边界误差统计
```

---

## 常见问题

### Q1: 为什么识别结果文件中的数据没有被统计？

检查以下几点：
1. `type` 字段是否为最终结果类型（`*ASRResult`），中间结果（`*ASRResultTemp`）会被自动过滤
2. `voice` 字段路径是否与参考答案文件中的路径完全匹配

### Q2: 如何处理 CSV 文件的编码问题？

工具默认使用 UTF-8 编码读取文件。如果文件使用其他编码，请先转换为 UTF-8。

### Q3: Excel 报告无法生成？

确保已安装 `openpyxl` 库：
```bash
pip3 install openpyxl
```

如果未安装，工具会自动降级生成 CSV 格式的报告。

### Q4: 环境变量没有被替换？

确保在 DSL 测试用例中使用，环境变量替换需要 `config` 对象支持。独立命令行运行时不支持 `{WORKPATH}` 等环境变量。

### Q5: DELAY 指令提示"JSONL 中没有对应类型的记录"？

检查以下几点：
1. `type` 参数的值是否与 `callback.jsonl` 中 `callback_type` 字段的值完全一致（大小写敏感）
2. `callback.jsonl` 是否在测试执行后正确生成（需要 `TestNANO` 中的回调写入逻辑正常运行）
3. 实时模式需传入以 `Temp` 结尾的类型（如 `PSTTASRResultTemp`），最终模式传入不以 `Temp` 结尾的类型（如 `PSTTASRResult`）

### Q6: DELAY 指令的"未匹配发话"数量偏高？

DELAY 会将标注文件中的每句发话与 `callback.jsonl` 按音频文件名和起始时间进行匹配，匹配容忍窗口为：
- 实时上屏模式：± 3 秒
- 最终结果模式：± 2 秒

如果同一音频有多段发话且时间间隔较近，可能导致匹配歧义。建议检查标注文件中相邻发话的起始时间差是否足够大，或确认 `callback.jsonl` 中 `data.start` 字段（毫秒）的值是否正确。
