# ⚡️ NANO测试套件 - Fixture系统

NANO测试套件引入了强大的 **Class级别Fixture（前后置）系统**，允许在测试用例文件的维度上定义`SETUP`（前置）、`TEARDOWN`（后置）和`SUITE_TEARDOWN`（Suite级别后置）操作。这极大地提高了测试用例的执行效率和可维护性，避免了在每个测试用例中重复执行相同的初始化和清理指令。

## 🎯 核心功能

NANO框架支持三种类型的Fixture块，每种都有不同的执行时机和用途：

### 1. SETUP 块（Session级别前置）
- **执行时机**: 在当前文件中**所有**测试用例执行之前，每个并发进程执行一次
- **执行位置**: 在 `test_nano.py` 的 `nano_class_fixture` 中执行
- **适用场景**: 启动服务、创建客户端、初始化配置等操作
- **并发行为**: 在多进程并发模式下，每个worker进程都会执行一次SETUP

### 2. TEARDOWN 块（Session级别后置）
- **执行时机**: 在当前文件中**所有**测试用例执行之后，每个并发进程执行一次
- **执行位置**: 在 `test_nano.py` 的 `nano_class_fixture` 中执行
- **适用场景**: 销毁客户端、杀死服务、清理环境等操作
- **并发行为**: 在多进程并发模式下，每个worker进程都会执行一次TEARDOWN

### 3. SUITE_TEARDOWN 块（Suite级别后置）
- **执行时机**: 在所有测试用例执行完成后，**只在主进程执行一次**
- **执行位置**: 在 `conftest.py` 的 `pytest_sessionfinish` 中执行
- **适用场景**: Suite级别的统计、报告生成、汇总分析等操作
- **并发行为**: 在多进程并发模式下，只在主进程执行，worker进程不执行
- **特殊说明**: 主要用于执行TSR（Test Suite Report）客户端指令，进行Suite级别的统计和报告生成

### 4. CASE_SETUP 块（CASE级别前置）
- **执行时机**: 在每个测试用例执行前执行一次（函数级别）
- **执行位置**: 在 `test_nano.py` 的 `nano_case_setup_fixture` 中执行（`yield` 前）
- **适用场景**: 单个Case执行前的环境准备、状态初始化、启动前置流程等
- **并发行为**: 在多进程并发模式下，各worker会在自己执行的每个Case前执行

### 5. CASE_TEARDOWN 块（CASE级别后置）
- **执行时机**: 在每个测试用例执行后执行一次（函数级别）
- **执行位置**: 在 `test_nano.py` 的 `nano_case_setup_fixture` 中执行（`yield` 后）
- **适用场景**: 单个Case执行后的状态清理、资源释放、回收收尾动作等
- **并发行为**: 在多进程并发模式下，各worker会在自己执行的每个Case后执行

## ✍️ DSL语法

Fixture系统使用一种特殊的DSL块语法，易于识别和编写。

```yaml
# ================= SETUP块 =================
# Session级别前置：在所有测试用例前执行一次（每个并发进程执行一次）
>>> SETUP
[SYS]PULL AIBSServer cmn {"brand":"0"}
[SYS]PULL LCSEngine cmn
[SYS]PULL SpeechEngine cmn
[TSA]CREATE cmn com.autoai.vr.service_vrassistant
<<<
# ============================================

# ============ 普通测试用例块 ============
>>>
# 这是第一个测试用例
[TSA]START 1
[TSA]TEXT 打电话给张三
[EXP]NLPResult skill:Phone;intention:CALL <timeout=2>
[TSA]STOP
<<<

>>>
# 这是第二个测试用例
[TSA]START 1
[TSA]TEXT 导航到公司
[EXP]NLPResult skill:Navigation;intention:NAVI <timeout=2>
[TSA]STOP
<<<
# ============================================

# =============== TEARDOWN块 ===============
# Session级别后置：在所有测试用例后执行一次（每个并发进程执行一次）
>>> TEARDOWN
[TSA]FREE
[SYS]KILL SpeechEngine
[SYS]KILL AIBSServer
[SYS]KILL LCSEngine
<<<
# ============================================

# =========== SUITE_TEARDOWN块 ============
# Suite级别后置：只在主进程执行一次，用于统计和报告生成
>>> SUITE_TEARDOWN
# 生成 Suite 级统计报告
[TSR]ASR_ACCURACY result={WORKPATH}/asr.csv ref=TestCase/ref/cmn_answer.csv output={WORKPATH}/asr_accuracy.xlsx
[TSR]DELAY ref=TestCase/ref/label.txt result={WORKPATH}/callback.jsonl type=PSTTASRResultTemp output={WORKPATH}/delay.xlsx
<<<
# ============================================
```

## 📜 规则与约束

为了确保Fixture系统的稳定和可预测性，NANO框架强制执行以下规则：

1.  **SETUP和TEARDOWN成对出现**: `SETUP` 和 `TEARDOWN` 必须**成对出现**。一个用例文件中不能只有`SETUP`而没有`TEARDOWN`，反之亦然。要么两者都有，要么都没有。

2.  **SUITE_TEARDOWN可选**: `SUITE_TEARDOWN` 是**可选的**，可以根据需要选择是否添加。如果不需要Suite级别的统计和报告生成，可以不添加此块。

3.  **唯一性**: 每个用例文件**最多只能包含一个** `>>> SETUP` 块、一个 `>>> TEARDOWN` 块和一个 `>>> SUITE_TEARDOWN` 块。如果检测到多个，DSL文件解析将失败并报错。

4.  **指令兼容性**: 
   - `SETUP` 和 `TEARDOWN` 块内可以包含任何NANO支持的DSL指令，包括 `[SYS]`, `[TSA]`, `[EXP]` 等
   - `SUITE_TEARDOWN` 块主要用于执行 `[TSR]` 客户端指令，用于Suite级别的统计和报告生成

5.  **执行顺序**: Fixture块的执行顺序为：`SETUP` → `TEST cases` → `TEARDOWN` → `SUITE_TEARDOWN`

6.  **并发执行**: 
   - `SETUP` 和 `TEARDOWN` 在每个并发进程（worker）中都会执行一次
   - `SUITE_TEARDOWN` 只在主进程（master）中执行一次，用于汇总所有worker的测试结果

## 💡 最佳实践

### SETUP 和 TEARDOWN 使用建议

- **服务管理**: 将服务的 `PULL` 和 `KILL` 操作放在`SETUP`和`TEARDOWN`中，确保每个并发进程都有独立的服务实例。
- **客户端管理**: 将客户端的 `CREATE` 和 `FREE` 操作放在`SETUP`和`TEARDOWN`中，避免在每个测试用例中重复创建和销毁。
- **环境准备**: 如果多个测试用例需要依赖相同的文件或配置，可以在`SETUP`中使用 `[SYS]UPLOAD` 或 `[SYS]CMD` 指令来准备。
- **断言使用**: 可以在`SETUP`中使用断言（`[EXP]`）来验证环境是否准备成功，如果断言失败，整个测试将被中断。

### SUITE_TEARDOWN 使用建议

- **统计报告**: 使用 `[TSR]` 客户端指令进行Suite级别的统计和报告生成，例如：
  - `[TSR]ASR_ACCURACY` - ASR 准确率统计
  - `[TSR]ASR_LANGUAGE` - 语种识别统计
  - `[TSR]DELAY` - 实时/最终结果时延统计
  - `[TSR]WAKEUP_ACCURACY` - 唤醒词 FA/FR 统计
  - `[TSR]VAD_ACCURACY` / `[TSR]VAD_PRECISION` - VAD 统计
  - `[TSR]TIME_BOUNDARY_ACCURACY` - 时间边界误差统计
  - `[TSR]LLM` / `[TSR]PSTT_ACCURACY` - 大模型评测 / PSTT 测试集统计

- **环境变量**: `SUITE_TEARDOWN` 中可以使用环境变量，例如 `{WORKPATH}` 来指定报告输出路径。

- **数据汇总**: `SUITE_TEARDOWN` 执行时，框架会自动收集所有worker进程的测试结果，包括通过数、失败数、失败用例详情等，这些数据会自动传递给TSR客户端。

### 示例：完整的Fixture使用

```yaml
# ================= SETUP块 =================
>>> SETUP
# 启动服务
[SYS]PULL AIBSServer cmn {"brand":"0"}
[SYS]PULL LCSEngine cmn
# 创建客户端
[TSA]CREATE cmn com.autoai.vr.service_vrassistant
# 验证环境准备成功
[EXP]CREATE_RET 0 <timeout=5>
<<<

# ============ 测试用例 ============
>>>
[TSA]START 1
[TSA]TEXT 今天天气怎么样
[EXP]NLPResult skill:WEATHER;intention:QUERY <timeout=2>
[TSA]STOP
<<<

# =============== TEARDOWN块 ===============
>>> TEARDOWN
# 清理客户端
[TSA]FREE
# 清理服务
[SYS]KILL AIBSServer
[SYS]KILL LCSEngine
<<<

# =============== CASE_SETUP块 ===============
>>> CASE_SETUP
[TSA]START        1
[TSA]FREEWAKEUP   1
[TSA]STRATEGY     2
<<<

# =============== CASE_TEARDOWN块 ===============

>>> CASE_TEARDOWN
[TSA]STOP
<<<

# =========== SUITE_TEARDOWN块 ============
>>> SUITE_TEARDOWN
# 生成 Suite 级别的统计报告
[TSR]ASR_ACCURACY result={WORKPATH}/asr.csv ref=TestCase/ref/cmn_answer.csv output={WORKPATH}/asr_accuracy.xlsx
[TSR]DELAY ref=TestCase/ref/label.txt result={WORKPATH}/callback.jsonl type=PSTTASRResultTemp output={WORKPATH}/delay.xlsx
<<<
```

## 🔍 TSR客户端指令说明

TSR（Test Suite Report）客户端专门用于 Suite 级别的统计和报告生成，当前代码实际支持以下指令：

| 指令 | 说明 | 参数 | 示例 |
|------|------|------|------|
| `ASR_ACCURACY` | ASR 准确率统计 | `result=<csv> ref=<csv> [output=<xlsx>]` | `[TSR]ASR_ACCURACY result={WORKPATH}/asr.csv ref=TestCase/ref/cmn_answer.csv` |
| `ASR_LANGUAGE` | 语种识别统计 | `result=<csv> ref=<lang> [output=<xlsx>]` | `[TSR]ASR_LANGUAGE result={WORKPATH}/asr.csv ref=cmn` |
| `DELAY` | 实时/最终结果时延统计 | `ref=<txt> result=<jsonl> type=<callback> [output=<xlsx>]` | `[TSR]DELAY ref=TestCase/ref/label.txt result={WORKPATH}/callback.jsonl type=PSTTASRResultTemp` |
| `WAKEUP_ACCURACY` | 唤醒词 FA/FR 统计 | `result=<csv> ref=<csv> [output=<xlsx>]` | `[TSR]WAKEUP_ACCURACY result={WORKPATH}/wakeup.csv ref=TestCase/ref/wakeup_ref.csv` |
| `VAD_ACCURACY` | VAD FA/FR 统计 | `result=<txt> ref=<txt> [output=<xlsx>]` | `[TSR]VAD_ACCURACY result={WORKPATH}/vad.txt ref=TestCase/ref/vad_ref.txt` |
| `VAD_PRECISION` | VAD 边界精度统计 | `result=<txt> ref=<txt> [output=<xlsx>]` | `[TSR]VAD_PRECISION result={WORKPATH}/vad.txt ref=TestCase/ref/vad_ref.txt` |
| `TIME_BOUNDARY_ACCURACY` | 时间边界误差统计 | `result=<txt/jsonl> ref=<txt> [output=<xlsx>] [threshold=<s>] [type=<rtype>]` | `[TSR]TIME_BOUNDARY_ACCURACY result={WORKPATH}/callback.jsonl ref=TestAudio/SDK/time_boundary/0_output_timelist.txt type=both` |
| `LLM` | 大模型批量评测 | `result=<csv> prompt=<txt> [output=<xlsx>] [batch=<n>]` | `[TSR]LLM result={WORKPATH}/nlu_result.csv prompt=TestCase/eval_prompts.txt` |
| `PSTT_ACCURACY` | PSTT 测试集综合统计 | `result=<file|dir> [ref=<file|dir>] type=<expr> [output=<xlsx>]` | `[TSR]PSTT_ACCURACY result={WORKPATH}/result_file ref=TestCase/ref/pstt type=auto` |

**注意**: TSR指令主要在`SUITE_TEARDOWN`中使用，因为此时所有测试用例已完成，可以获取完整的统计信息。

通过遵循这些实践，你可以编写出更简洁、更高效、更可靠的NANO测试用例，并能够自动生成Suite级别的统计报告。
