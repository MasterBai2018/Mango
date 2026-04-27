# SOLUTION 编写手册

本文档说明当前 Mango YAML 版 `solution` 的编写规则。

当前实现对应：

- `src/userInterface/parse_solution.py`
- `src/userInterface/run_test.py`

目标：

- 使用 YAML 编写 solution
- 支持 `global -> scenario -> suite` 的部分字段继承
- 兼容当前 `run_test.py` 主执行链路

## 1. 文件结构

`solution` 顶层固定包含两个字段：

```yaml
global:
  ...

scenarios:
  - name: 场景1
    ...
```

## 2. 顶层字段说明

### 2.1 `global`

`global` 用于放全局默认配置。

当前支持字段：

- `environment`：全局运行环境，决定当前 solution 运行在哪个工程下，例如 `24mm/ota2`。该字段必填，且只能写在 `global`。
- `global_max_workers`：solution 级调度总并发上限，限制同一时刻最多允许多少个 suite 被调度执行。
- `online_max_workers`：主标签为 `ONLINE` 的 suite 最大并发数。
- `cp_max_workers`：主标签为 `CP` 的 suite 最大并发数。
- `offline_max_workers`：主标签为 `OFFLINE` 的 suite 最大并发数，支持整数或 `auto`。当为 `auto` 时，离线并发会根据剩余全局并发动态计算。
- `enable`：场景启用列表，用于控制本次 solution 中哪些 scenario 会参与执行。常见写法是 `[ALL]`。
- `disable`：场景禁用列表，用于显式跳过某些 scenario；如果包含 `ALL`，则整份 solution 不执行。
- `project_config`：全局默认 LCS 配置路径，供 scenario 和 suite 继承使用；若下层未配置，则使用这里的值。
- `retry`：全局默认失败重试次数，对应 pytest 的 `--reruns`；可被 scenario 或 suite 覆盖。
- `xdist_workers`：全局默认 xdist 并发数，对应 pytest 的 `-n`；可被 scenario 或 suite 覆盖。

示例：

```yaml
global:
  environment: 24mm/ota2
  global_max_workers: 25
  online_max_workers: 5
  cp_max_workers: 1
  offline_max_workers: auto
  enable: [ALL]
  project_config: null
  retry: 0
  xdist_workers: 0
```

### 2.2 `scenarios`

`scenarios` 是场景列表，每一项表示一个场景。

每个场景下固定使用：

- `name`：场景名称，也是报告展示和目录命名使用的名称，建议语义清晰且保持唯一。
- `suites`：当前场景下要执行的 suite 列表，是场景的核心内容。

可选字段：

- `owner`：场景负责人列表，主要用于说明该场景的维护人或归属人。
- `project_config`：当前 scenario 级默认 LCS 配置路径，会覆盖 `global.project_config`，并可继续被 suite 级覆盖。
- `retry`：当前 scenario 级默认失败重试次数，会覆盖 `global.retry`，并可继续被 suite 级覆盖。
- `xdist_workers`：当前 scenario 级默认 xdist 并发数，会覆盖 `global.xdist_workers`，并可继续被 suite 级覆盖。

示例：

```yaml
scenarios:
  - name: AIBS_智能语音
    project_config: TestCase/conf/Mongo/config/24mm_ota_2/lcs_OTA2_test.conf
    owner: [zhanglukai]
    suites:
      - { config: xxx, case: yyy, tag: [OFFLINE], abstract: 示例 }
```

## 3. Suite 字段说明

每个 `suite` 当前支持以下字段：

- `config`：suite 对应的 decoder 配置文件路径。
- `case`：suite 对应的测试用例文件路径，通常是 `.mgo` 文件。
- `tag`：suite 标签列表，必须包含且只能包含一个主标签：`ONLINE`、`OFFLINE` 或 `CP`。
- `abstract`：suite 简介，用于报告展示和问题定位。
- `parameter`：suite 级参数化 CSV 文件路径，会在运行时映射为内部的 `parameterized_data`。
- `steps`：suite 级动态步骤参数文件路径，会在运行时映射为内部的 `steps_data`。
- `project_config`：suite 级 LCS 配置路径，会覆盖 scenario/global 继承值。
- `retry`：suite 级失败重试次数，会覆盖 scenario/global 继承值。
- `xdist_workers`：suite 级 xdist 并发数，会覆盖 scenario/global 继承值。
- `name`：suite 类型名称，当前可选；不写时默认使用 `NANO`。

其中：

- `config`：decoder 配置文件路径
- `case`：测试用例文件路径
- `tag`：suite 标签，必须包含一个主标签
- `abstract`：suite 简介
- `parameter`：参数化 CSV 文件路径
- `steps`：动态步骤参数文件路径
- `project_config`：LCS 配置路径，可覆盖上层
- `retry`：pytest reruns 次数，可覆盖上层
- `xdist_workers`：pytest `-n` 并发数，可覆盖上层
- `name`：可选，默认是 `NANO`

示例：

```yaml
suites:
  - { config: TestCase/conf/Mongo/config/24mm_ota_2/Lexus_D/decoder.conf, case: TestCase/nano/24MM/SDK/AIBS/freetalk_timeout.mgo, tag: [OFFLINE], abstract: FreetalkTimeout超时逻辑 }
  - { retry: 3, xdist_workers: 2, config: TestCase/conf/Mongo/config/24mm_ota_2/T1/decoder.conf, case: TestCase/nano/24MM/SDK/AIBS_BUG_CASE/wakeup_bug_yf.mgo, tag: [OFFLINE], abstract: BugCaseList_YF }
  - { parameter: TestCase/nano/24MM/SDK/DIGIT/digital_online.csv, config: TestCase/conf/Mongo/config/24mm_ota_2/Lexus_D/decoder.conf, case: TestCase/nano/24MM/SDK/DIGIT/digital.mgo, tag: [ONLINE], abstract: 中文数字转换在线 }
```

## 4. 继承规则

当前只有以下 3 个字段支持三级继承：

- `project_config`
- `retry`
- `xdist_workers`

优先级：

`suite > scenario > global > 默认值`

默认值如下：

- `project_config`: `null`
- `retry`: `0`
- `xdist_workers`: `0`

说明：

- `environment` 不支持继承，只能写在 `global`
- `config` / `case` / `tag` / `abstract` / `parameter` / `steps` 都是 suite 级字段，不参与继承

## 5. `environment` 规则

`environment` 只能写在 `global`，并且必填。

示例：

```yaml
global:
  environment: 24mm/ota2
```

要求：

- 必须存在
- 必须是 Mango 支持的工程名

例如：

- `24mm/ota2`
- `24mm/ota3`
- `24mm/mp`

## 6. `project_config` 规则

`project_config` 允许为空。

但如果最终 `environment` 属于依赖 LCS 的工程，则运行时最终生效的 `project_config` 不能为空，否则会报错。

当前依赖 LCS 的典型工程包括：

- `24mm/mp`
- `24mm/ota1`
- `24mm/ota2`
- `24mm/ota3`
- `bev`
- `nissan`
- `800d`

## 7. 标签规则

### 7.1 主标签要求

每个 suite 的 `tag` 必须且只能包含一个主标签：

- `ONLINE`
- `OFFLINE`
- `CP`

合法示例：

```yaml
tag: [OFFLINE]
tag: [ONLINE]
tag: [AIBS_ASR_NLU, OFFLINE]
```

非法示例：

```yaml
tag: []
tag: [ONLINE, OFFLINE]
tag: [WAKEUP]
```

### 7.2 标签不能重复

例如以下写法非法：

```yaml
tag: [ONLINE, ONLINE]
```

## 8. `enable` / `disable` 规则

`global.enable` 和 `global.disable` 用于按场景名控制执行。

示例：

```yaml
global:
  enable: [ALL]
```

或：

```yaml
global:
  enable: [AIBS_智能语音, Digit_数字转换]
  disable: [AIBS_BUG_CASE]
```

规则：

- `enable` 不配置时，默认等价于 `[ALL]`
- `disable` 可不写
- `disable` 中如果包含 `ALL`，则整个 solution 不再执行

另外，命令行显式传入的 `--mongo_enable` 会覆盖 YAML 中的 `global.enable`

## 9. CLI 参数优先级

当前代码中，以下字段支持被命令行覆盖：

- `project_config`
- `retry`
- `xdist_workers`

优先级如下：

- `project_config`: `CLI(-p) > suite > scenario > global > null`
- `retry`: `CLI(-R) > suite > scenario > global > 0`
- `xdist_workers`: `CLI(-n) > suite > scenario > global > 0`

说明：

- 如果 CLI 没有显式传值，则使用 YAML 继承结果
- `environment` 不走 CLI 覆盖，按当前 YAML `global.environment` 为准

## 10. 参数化字段命名

YAML 版 solution 使用以下命名：

- `parameter`
- `steps`

因此在 YAML 中请统一写新名字，不要再写旧名字。

推荐：

```yaml
- { parameter: TestCase/data/demo.csv, steps: TestCase/data/demo_steps.csv, config: xxx, case: yyy, tag: [OFFLINE], abstract: 示例 }
```

## 11. 日志输出规则

当前 `stdout` 不再从 YAML 配置。

日志路径由代码统一生成，格式如下：

```text
<workspace>/<solution_name>/<scene_name>/terminal_output/log_suiteID_<suite_id>.txt
```

示例：

```text
workspace/solution_24mm_sdk_ota2/个性化/terminal_output/log_suiteID_1.txt
```

运行时采用 `tee`，因此：

- 终端会实时打印 pytest 输出
- 日志文件也会同时保存一份完整输出

## 12. 最小完整示例

```yaml
global:
  environment: 24mm/ota2
  global_max_workers: 25
  online_max_workers: 5
  cp_max_workers: 1
  offline_max_workers: auto
  enable: [ALL]
  project_config: null
  retry: 0
  xdist_workers: 0

scenarios:
  - name: AIBS_智能语音
    project_config: TestCase/conf/Mongo/config/24mm_ota_2/lcs_OTA2_test.conf
    owner: [zhanglukai]
    suites:
      - { config: TestCase/conf/Mongo/config/24mm_ota_2/Lexus_D/decoder.conf, case: TestCase/nano/24MM/SDK/AIBS/freetalk_timeout.mgo, tag: [OFFLINE], abstract: FreetalkTimeout超时逻辑 }

  - name: Digit_数字转换
    project_config: TestCase/conf/Mongo/config/24mm_ota_2/lcs_OTA2_test.conf
    retry: 1
    suites:
      - { parameter: TestCase/nano/24MM/SDK/DIGIT/digital_offline.csv, config: TestCase/conf/Mongo/config/24mm_ota_2/Lexus_D/decoder.conf, case: TestCase/nano/24MM/SDK/DIGIT/digital.mgo, tag: [OFFLINE], abstract: 中文数字转换离线 }
      - { xdist_workers: 2, parameter: TestCase/nano/24MM/SDK/DIGIT/digital_online.csv, config: TestCase/conf/Mongo/config/24mm_ota_2/Lexus_D/decoder.conf, case: TestCase/nano/24MM/SDK/DIGIT/digital.mgo, tag: [ONLINE], abstract: 中文数字转换在线 }
```

## 13. 当前实现边界

当前 YAML 解析器只保证兼容：

- `run_test.py` 主执行链路

不保证完整兼容：

- 旧 TXT solution
- `parse_config.py` 的全部历史能力
- 旧的恢复/救援等边缘链路

如果后续扩展了 `run_test.py` 或 `parse_solution.py`，请同步更新本文档。