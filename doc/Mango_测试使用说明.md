# Mango 测试使用说明

---

## 1. Mango框架简介

Mango 是语音 SDK 自动化测试框架，测试执行主要使用 **NANO DSL**（`.mgo` 文件）。

测试人员日常只需要关注 5 件事：
- 准备环境与配置
- 运行  `Run_Docker.py`
- 编写/维护 `.mgo` 时序用例和`.csv`参数化文件 
- 使用 `EXP`/`LOG` 断言验证结果
- 查看Allure报告和日志定位问题

---

## 2. 测试环境部署与配置

### 2.1 必备环境
- Python 3.6+
- Git
- Linux（推荐）
- Docker（可选）

### 2.2 部署手顺
> 准备 4 个资源：`mango`、`TestCase`、`TestResource`、`TestAudio`。

- `mango`：测试框架主仓，入口脚本为 `Run_Mongo.py`，部署时使用 `develop` 分支。
- `TestCase`：测试用例仓，存放 `.mgo`、配置与 case 列表，部署时使用 `develop` 分支。
- `TestResource`：测试资源仓，存放运行依赖资源文件，部署时使用 `develop` 分支。
- `TestAudio`：本地音频目录（非 Git 仓），存放测试音频，通过软链接挂到 `mango/TestAudio`。

1. 选择一个工作目录，例如 `/data1/baihuidong/work`，并进入该目录。

2. 拉取 `mango` 主仓库并切到 `develop` 分支：

   ```
   # git clone mango 主仓到本地
   git clone git@git.pachira.cn:asr/mango.git

   # 切换到develop分支
   git checkout develop
   ```

3. 在mango的同级目录下，准备 `TestCase`：
   ```
   # git clone TestCase 自己fork的仓到本地, username就是自己的git账户
   git clone git@git.pachira.cn:username/TestCase.git
   
   # 添加asr/TestCase.git的远程主仓
   git remote add upstream git@git.pachira.cn:asr/TestCase.git
   
   # 创建本地develop分支并绑定远程仓
   git checkout -b develop upstream/develop
   ```
   
4. 在mango的同级目录下，准备 `TestResource`：
   ```
   # git clone TestResource 自己fork的仓到本地, username就是自己的git账户
   git clone git@git.pachira.cn:username/TestResource.git
   
   # 添加asr/TestResource.git的远程主仓
   git remote add upstream git@git.pachira.cn:asr/TestResource.git
   
   # 创建本地develop分支并绑定远程仓
   git checkout -b develop upstream/develop
   ```

5. 准备相应软连接路径与音频 `TestAudio`：
   - 获取音频目录后，在 `mango` 目录下创建软链接 `TestAudio -> 你的TestAudio绝对路径`
      ```
      cd mango
      ln -s TestAudio /data1/NFS_DATA/TestAudio
      ```
   - 在 `mango` 目录下创建软链接 `TestCase`
      ```
      cd mango
      ln -s TestCase ../TestCase
      ```
   - 在 `mango` 目录下创建软链接 `TestResource`
      ```
      cd mango
      ln -s TestResource ../TestResource
      ```

6. 进入 `mango` 目录执行一次冒烟命令，确认环境可用：
```bash
python3 Run_Mongo.py -h
```

### 2.3 关键目录与文件

- 入口脚本：`Run_Mongo.py`
- Docker 入口：`Run_Docker.py`
- 配置目录：`conf/`
- NANO 文档目录：`src/testsuite/NANO/doc/`

### 2.4 测试前要确认的路径

- `-C`：解码配置文件路径
- `-a`：`.mgo` 用例路径
- `-P`：参数化 CSV（可选）
- `-S`：动态步骤 CSV（可选）

### 2.5 推荐先安装编辑器高亮

为了便于测试同学编写、阅读和排查 NANO Case，Mango提供了NANO的 `.mgo` 的编辑器高亮插件。高亮和 Hover 能直接帮助你识别：

- `SETUP` / `TEARDOWN` / `PARAMETER` 等块结构
- `[TSA]`、`[SET]`、`[EXP]` 等客户端标签
- 命令、断言、环境变量、`<timeout=...>` 等 DSL 关键元素的使用说明以及示例代码

#### 2.5.1 Vim 安装手顺

项目已经提供系统级安装脚本：`plugins/vim/install_mgo_vim_systemwide.sh`

推荐步骤：

1. 执行如下脚本安装：

```bash
sh plugins/vim/install_mgo_vim_systemwide.sh
```

2. 安装完成后，重新打开 `.mgo` 文件，即可展示NANO DSL语法高亮。

#### 2.5.2 VSCode/Cursor 插件安装手顺

项目内置了 NANO DSL 的 VSCode/Cursor 插件源码目录：`plugins/vscode-mgo-extension`

插件能力包括：

- `.mgo` 语法高亮
- 命令/客户端/断言自动补全
- Hover 悬浮说明（语法、参数、示例）
- 基础静态诊断

推荐安装方式如下：

1. 已提供 `.vsix` 安装包：

```bash
plugins/vscode-mgo-extension/mango-nano-mgo-0.0.4.vsix
```

2、VSCode/Cursor界面安装：
- a. 点击VSCode顶部搜索框，选择: `显示并运行命令 >`
- b. 或者组合键: `Command + Shift + P`
- c. 选择: `扩展:从VSIX安装...`或者`Extensions: Install from VSIX...` 进行安装。
- d. 选择Mango路径下的插件文件: `plugins/vscode-mgo-extension/mango-nano-mgo-0.0.4.vsix` 安装即可。

2. 安装完成后，用 VSCode/Cursor 打开任意 `.mgo` 文件，确认是否已经具备语法高亮、补全和 Hover 提示。

---

## 3. 快速入门（Quick Start）

```bash
python3 Run_Docker.py -f NANO \
  -C TestCase/conf/decoder/decoder.conf \
  -a TestCase/caselist/24MM/SDK/NANO/nano.mgo \
  -b 24mm/ota2
```

### 3.1 常用增强参数
```bash
# 并发
python3 Run_Mongo.py ... -n 5

# 失败重试
python3 Run_Mongo.py ... -R 1

# 全局参数化
python3 Run_Mongo.py ... -P TestCase/data/test_data.csv

# 参数化行过滤
python3 Run_Mongo.py ... -P TestCase/data/test_data.csv -PF 10-30

# 动态步骤
python3 Run_Mongo.py ... -S TestCase/data/steps.csv
```

---

## 4. 参数定义

> 参数说明：参数意义 + 可传值 + 示例。

| <span style="display:inline-block;min-width:50px">参数</span> | 参数意义 | 可传值 | 示例 |
|---|---|---|---|
| `-v` | Docker 挂载目录（仅 `Run_Docker.py`） | 3种写法：`/host/path`（容器内同路径，默认 `ro`）；`/host:/container`（默认 `ro`）；`/host:/container:ro|rw`（显式权限） | `-v /data1/cases:/mango/TestCase:ro` |
| `-f` | 套件过滤 | 字符串（固定写 `NANO` ），仅单跑时，传入 | `-f NANO` |
| `-C` | SpeechEngine配置文件路径 | 配置文件路径（`.conf`） | `-C TestCase/conf/decoder/decoder.conf` |
| `-a` | 时序/用例路径 | `.mgo` 文件路径 | `-a TestCase/caselist/24MM/SDK/NANO/nano.mgo` |
| `-p` | LCSEngine配置路径 | 配置文件路径（通常 LCS 配置） | `-p TestCase/conf/Mongo/config/lcs/lcs_OTA_test.conf` |
| `-b` | 环境选择 | 当前可选：`24mm/mp`、`24mm/ota1`、`24mm/ota2`、`24mm/ota3`、`bev`、`pstt`、`seres`、`psl`、`nissan`、`thai`、`titan`、`800d`、`pisa`、`tss` | `-b 24mm/ota2` |
| `-w` | 工作目录根路径（日志/报告/中间产物输出位置） | 相对路径或绝对路径；不传默认 `workspace`。区别：不传时结果落在 `./workspace`，传入后所有输出落在你指定目录（含单跑与 solution 并发） | `-w /data/mango_workspace` |
| `-n` | 并发执行数 | 数字或 `auto` | `-n 5` |
| `-R` | 失败重试次数 | 非负整数 | `-R 1` |
| `-F` | 用例行号过滤 | 支持：`start-end`、`*-end`（从第1行到end）、`start-*`（从start到文件末尾） | `-F 6-20`、`-F *-10`、`-F 10-*` |
| `-t` | 按 Tag 过滤 suite（solution 模式） | 方括号格式；单个：`[ONLINE]`；多个：`[ONLINE][CP]`；必选标签可加 `+`：`[+ONLINE][CP]` | `-t [ONLINE][CP]` |
| `-L` | Allure报告是否保存 SDK 日志 | `yes` / `no` | `-L yes` |
| `-P` | 全局参数化数据 | CSV 文件路径 | `-P TestCase/data/test_data.csv` |
| `-PF` | 参数化 CSV 行过滤（不含表头，从1开始计数） | 支持：`start-end`、`*-end`、`start-*` | `-PF 10-30`、`-PF *-10`、`-PF 10-*` |
| `-S` | 动态步骤数据 | CSV 文件路径（需包含 `CaseID`、`StepCase`） | `-S TestCase/data/steps.csv` |
| `-D` | FTP 资源下载类型 | `0` 全部 / `1` 音频 / `2` 资源 | `-D 0` |
| `-J` | Jenkins 依赖库下载构建号 | 按“项目依赖的 Jenkins 个数”用 `-` 分隔：`new`/`latest`（最新成功构建）或数字构建号；多依赖示例：`new-new`、`123-456`、`new-456`。 | `-J new-new` |
| `-g` | 开启 GDB 调试 | 开关型（按项目脚本约定传值） | `-g` |
| `-E` | solution 的 DEFINE 过滤开关（按名字启用） | 逗号分隔的 DEFINE 名称列表；仅执行命中的 DEFINE 配置（等价覆盖/补充 solution 内 `ENABLE`） | `-E ONLINE_SMOKE,CP_REGRESSION` |
| `-c` | 传入 solution 文件并按 solution 方式执行（支持并发调度） | 1个或多个 solution 文件路径（空格分隔）；每个 solution 可包含多个 scene/suite，并按配置并发运行 | `-c TestCase/conf/solution/smoke.yaml TestCase/conf/solution/regression.yaml` |
| `-l` | 列出可用 suite（废弃） | 开关型（通常不带值） | `-l` |
| `-s` | 救援模式（废弃） | 开关型（按项目脚本约定传值） | `-s 1` |

---

## 5. 新增特性：MGO 时序文件与 CSV 参数化

### 5.1 MGO 时序块
- `SETUP`：所有用例前执行，一般用于配置文件临时修改，服务启动，创建引擎等操作，**每个Suite仅会执行一次**

  ```
  >>> SETUP
  [SYS]PULL         AIBSServer cmn {"brand":"0"}
  [SYS]PULL         LCSEngine cmn
  [SYS]PULL         SpeechEngine cmn
  [TSA]CREATE       cmn com.autoai.vr.service_vrassistant
  [SET]CREATE       cmn com.autoai.vrsetting
  <<<
  ```

- `TEST`：测试主体，**根据参数化文件，该测试主体将会执行多次**

  ```
  >>>
  [TSA]START        1
  [SET]SETVRCONFIG  DIALOGUE_LANGUAGE cmn
  [SET]SETVRCONFIG  WAKEUP_KEYWORD_OPTION 0
  [SET]SETVRCONFIG  WAKEUP_ENABLE 你好雷克萨斯 cmn
  [TSA]FREEWAKEUP   1
  [TSA]STRATEGY     1
  [TSA]DATA         TestResource/FTP_RES/voicedata/SDK/24MM/VR/geiniqugemzjzengdayinliang.wav frame=320 delay=1
  [EXP]NLPResult    text:给你取个名字叫增大音量;skill:VRWakeWord;intention:setWakeWordWithName <timeout=5>
  [TSA]STOP
  <<<
  ```

- `TEARDOWN`：所有用例后执行，一般用于服务的清理，报告统计，上传报告附件等等，**每个Suite仅会执行一次**

  ```
  >>> TEARDOWN
  [SYS]KILL   SpeechEngine
  [SYS]KILL   LCSEngine
  [SYS]KILL   AIBSServer
  [SYS]ALLURE TEXT {WORKPATH}/callback.jsonl
  <<<
  ```

- `SUITE_TEARDOWN`：suite 结束后执行（常用于统计），一般用于Suite级别的报告统计（TSR客户端），**每个Suite仅会执行一次**

  ```
  >>> SUITE_TEARDOWN
  [TSR]DELAY ref=${DELAY_REF} result={WORKPATH}/callback.jsonl type=ASRResultTemp
  [TSR]DELAY ref=${DELAY_REF} result={WORKPATH}/callback.jsonl type=ASRResult
  <<<
  ```

### 5.2 三层 CSV 参数化
参数化适用场景：
- 同一条测试逻辑需要覆盖多组输入（文本、音频、期望 skill/intention）
- 同一套用例需要在不同语言/环境变量下重复执行
- 同一 MGO 需要按不同步骤序列动态生成执行链路

参数化基础写法（MGO）：
- 在 MGO 中使用占位符：`${变量名}`
- 变量名必须和 CSV 表头一致（区分大小写）

```dsl
>>>
[TSA]DATA ${AUDIOPATH} frame=320 delay=${DELAY}
[EXP]ASRResult asr:${TEXT} <timeout=3>
<<<
```

CSV 文件怎么写：
- 第一行是表头（变量名），后续每行是一组测试数据
- 支持逗号或 Tab 分隔
- 支持注释行/空行过滤
- 全局参数可使用头部 `@` 参数（例如 `@DELAY: 0`）

```csv
@DELAY: 0

AUDIOPATH   TEXT
TestAudio/1.wav  今天天气怎么样
TestAudio/2.wav  帮我打开车窗
```

三种参数化方式：

1. 全局 CSV（`-P`）
- 适合：整份 MGO 中多个 case 共享同一份参数表
- 命令示例：
```bash
python3 Run_Mongo.py -f NANO -C xxx.conf -a demo.mgo -b 24mm/ota2 -P TestCase/data/test_data.csv
```

2. Case 级 CSV（`>>> PARAMETER xxx.csv`）
- 适合：某个 case 使用独立参数表，避免和全局 CSV 混用
- MGO 示例：
```dsl
>>> PARAMETER TestCase/data/case1_data.csv
...
[TSA]TEXT ${text}
[EXP]NLPResult skill:${skill}
...
<<<

>>> PARAMETER TestCase/data/case1_data2.csv
...
[TSA]TEXT ${text}
...
<<<
```
3. Solution中配置参数化文件
```dsl
# SUITE: NANO,配置文件,mgo时序文件,csv参数化文件,[TAG]
DEFINE
    NAME  :  ASR_Multi_Lang
    CONFIG : TestCase/conf/Mongo/config/24mm_ota_2/lcs_OTA2_test.conf
    SUITE : NANO,TestCase/conf/Mongo/config/24mm_ota_2/Lexus_D/decoder.conf,TestCase/nano/24MM/SDK/ASR_Multi_Lang/asr.mgo,TestCase/nano/24MM/SDK/ASR_Multi_Lang/multi_lang_cmn_online.csv,[ONLINE]
    ARG_ABSTRACT : 在线中文识别
    REPEAT : 1
    STDOUT : ./all-report-log/24mm-lexus-asr-rate
    PARALLEL : true
    PURPOSE : "zeroshot唤醒全链路测试"    @Describe the purpose of the current scene
    OWNER : sujun
END
```

### 5.3 CSV 规则
- 支持逗号/Tab 自动识别
- 支持无效行过滤（空行、注释）
- 支持头部 `@` 参数（例如 `@DELAY: 0`）
- 支持 `-PF` 行范围过滤

---

## 6. 高频指令与特性

> 本章是测试人员最常用内容，重点看 `TSA/SYS/EXP/TSR`。

### 6.1 TSA 客户端（功能链路主执行）

推荐时序（最常用）：
1. `SETUP` 中创建：`[TSA]CREATE`
2. `TEST` 中执行：`[TSA]START -> (FREEWAKEUP/STRATEGY) -> DATA/TEXT/EVENT -> EXP断言 -> [TSA]STOP`
3. `TEARDOWN` 中释放：`[TSA]FREE`

常用接口写法（含参数）：

| 接口 | 语法 | 可传参数 | 示例 |
|---|---|---|---|
| `CREATE` | `[TSA]CREATE language appid [config_file]` | `language`：`cmn/eng/...`；`appid`：应用包名；`config_file`：可选配置路径 | `[TSA]CREATE cmn com.autoai.vr.service_vrassistant` |
| `START` | `[TSA]START channel_num` | `channel_num`：通道数（常用 `1`） | `[TSA]START 1` |
| `FREEWAKEUP` | `[TSA]FREEWAKEUP status` | `status`：`0` 关闭免唤醒；`1` 开启免唤醒 | `[TSA]FREEWAKEUP 1` |
| `STRATEGY` | `[TSA]STRATEGY status` | `status`：`0/1/2`（按项目策略定义） | `[TSA]STRATEGY 1` |
| `DATA` | `[TSA]DATA audio_path [named_parameters...]` | `audio_path`：音频路径；可选命名参数：`frame=320/640/1280`、`delay=秒`、`range=[start,end]`、`abstime=0/1` | `[TSA]DATA TestAudio/demo.wav frame=320 delay=1` |
| `TEXT` | `[TSA]TEXT text` | `text`：文本请求 | `[TSA]TEXT 打开空调` |
| `EVENT` | `[TSA]EVENT json_event_data` | JSON字符串或事件文件路径（项目内常用事件文件路径） | `[TSA]EVENT TestCase/caselist/.../set_VRWakeUp_success.json` |
| `STOP` | `[TSA]STOP` | 无 | `[TSA]STOP` |
| `FREE` | `[TSA]FREE` | 无 | `[TSA]FREE` |

示例1（语音链路）：
```dsl
>>>
[TSA]START        1
[TSA]FREEWAKEUP   1
[TSA]STRATEGY     1
[TSA]DATA         TestAudio/Wakeup/voice_alis/xiaobaitu.wav frame=320 delay=1
[EXP]NLPResult    skill:VRWakeWord;intention:addInfoWakeWord <timeout=5>
[TSA]EVENT        TestCase/caselist/Mongo/caselist/smoke/wakeup/event/set_VRWakeUp_success.json
[TSA]STOP
<<<
```

示例2（文本链路）：
```dsl
>>>
[TSA]START 1
[TSA]FREEWAKEUP 1
[TSA]STRATEGY 1
[TSA]TEXT 导航到公司
[EXP]NLPResult skill:NAVI;intention:naviPlanRouteToDest <timeout=3>
[TSA]STOP
<<<
```

### 6.2 SYS 客户端

推荐时序（最常用）：
1. `SETUP`：`ENV -> PULL -> SLEEP`（先设环境变量，再拉服务）
2. `TEST`：必要时用 `CMD` 做运行时文件/日志/资源处理，`BREF` 写当前 case 简介
3. `TEARDOWN`：`KILL` 清理服务

常用接口写法（含参数）：

| 接口 | 语法 | 可传参数 | 示例 |
|---|---|---|---|
| `PULL` | `[SYS]PULL service_name language [car_type]` | `service_name`：`LCSEngine`/`SpeechEngine`/`AIBSServer`；`language`：如 `cmn`；`car_type`：仅 AIBSServer 常用，JSON | `[SYS]PULL AIBSServer cmn {"brand":"0"}` |
| `KILL` | `[SYS]KILL service_name` | 服务名 | `[SYS]KILL AIBSServer` |
| `SLEEP` | `[SYS]SLEEP seconds` | 秒（支持小数） | `[SYS]SLEEP 0.5` |
| `ENV` | `[SYS]ENV key=value` | `key` 环境变量名；`value` 可含 `=`，可用单/双引号包裹 | `[SYS]ENV MY_CONFIG_PATH=/data/test/config` |
| `CMD` | `[SYS]CMD command` | 任意 Linux shell 命令（支持管道、重定向、组合命令） | `[SYS]CMD mkdir -p {WORKPATH}/output` |
| `UPLOAD` | `[SYS]UPLOAD upload_type file_path [params...]` | `upload_type` 支持：`JSON`、`LINE`、`REPLACE`、`DELETE` | `[SYS]UPLOAD LINE {WORKPATH}/decoder.conf ASK_SIL_DURATION 540` |
| `BREF` | `[SYS]BREF message` | case 简介文本（可多词） | `[SYS]BREF 天气查询-冒烟` |
| `CLEAR_ASSERT` | `[SYS]CLEAR_ASSERT [type]` | 可选 `type`：`ALL`（默认）、`CALLBACK`、`API`，或具体类型（如 `ASRResult`、`GET_VERSION_RET`） | `[SYS]CLEAR_ASSERT CALLBACK` |

`UPLOAD` 重点说明（运行时改文件）：
- `JSON`：按字段路径修改 JSON 值  
  语法：`[SYS]UPLOAD JSON file_path field_path new_value`
- `LINE`：按 key 修改配置行（常用于 `.conf`）  
  语法：`[SYS]UPLOAD LINE file_path key new_value`
- `REPLACE`：全文字符串替换  
  语法：`[SYS]UPLOAD REPLACE file_path old_value new_value`
- `DELETE`：删除某个Key
  语法：`[SYS]UPLOAD DELETE file_path key`

`UPLOAD` 示例：
```dsl
# 1) JSON字段更新
[SYS]UPLOAD JSON {WORKPATH}/daemon_tag.json data.text.start 320

# 2) 按key更新配置项
[SYS]UPLOAD LINE {CONFIGPATH} ASK_SIL_DURATION 540

# 3) 全文替换
[SYS]UPLOAD REPLACE {CONFIGPATH} /old/path /new/path

# 4) 按key删除配置项
[SYS]UPLOAD DELETE {CONFIGPATH} Key1
```

`CLEAR_ASSERT` 重点说明（多轮场景强烈建议使用）：
- 作用：清空当前 case 的断言上下文，避免“上一轮回调/接口结果”干扰下一轮断言匹配。
- 典型场景：一个 case 内有多轮 `TEXT/DATA + EXP`，或先跑预热动作再做正式断言。
- 推荐时机：每一轮关键断言前执行一次，确保断言只命中“本轮新增数据”。

`CLEAR_ASSERT` 示例：
```dsl
>>>
[TSA]START 1
[TSA]TEXT 今天天气怎么样
[EXP]NLPResult skill:WEATHER;intention:QUERY <timeout=3>

# 清空上一轮断言上下文，避免下一轮串数据
[SYS]CLEAR_ASSERT ALL

[TSA]TEXT 导航到公司
[EXP]NLPResult skill:NAVI;intention:naviPlanRouteToDest <timeout=3>
[TSA]STOP
<<<
```

`CMD` 重点说明（推荐重点掌握）：

- 核心能力：把 Linux shell 直接嵌入测试时序，适合做测试前准备、运行中动态处理、测试后数据整理。
- 与 `ENV` 配合：先 `[SYS]ENV key=value`，再通过 `[SYS]CMD` 使用该环境变量，可实现“同一用例逻辑 + 不同环境配置”。
- 常见场景：
  - 运行前准备目录/软链接/配置备份
  - 运行中采样日志、提取关键字段、快速统计
  - 运行后归档结果、生成中间数据供断言或报告使用

`CMD` 示例（配合环境变量和 shell）：

```dsl
>>> SETUP
...
[SYS]CMD cp {CONFIGPATH} {WORKPATH}/decoder.conf.bak
[SYS]PULL AIBSServer cmn {"brand":"0"}
[SYS]PULL LCSEngine cmn
[SYS]SLEEP 2
<<<

>>>
[SYS]BREF ASR时延冒烟-在线
[SYS]CMD echo "[INFO] start ${CASE_NAME}" >> {LOGPATH}/runtime.log
[SYS]CMD cat {WORKPATH}/callback.jsonl | wc -l > ${WORKPATH}/callback_lines.txt
<<<

>>> TEARDOWN
[SYS]CMD tar -czf ${LOGPATH}/logs.tgz {LOGPATH}
[SYS]KILL LCSEngine
[SYS]KILL AIBSServer
<<<
```

注意事项：
- `ENV` 必须写在对应 `PULL` 之前，否则服务进程拿不到变量。
- `CMD` 执行失败会直接影响 case 结果，复杂命令建议先在终端验证。
- 涉及路径含空格时建议加引号。
- `CLEAR_ASSERT` 不会清理日志文件本身，只清理断言引擎内存中的匹配上下文。

### 6.3 EXP 客户端（断言核心）

通用语法（回调/结果类）：
```dsl
[EXP]断言类型 字段1:期望值;字段2:期望值 <timeout=秒>
```

推荐时序：
1. 先触发行为（`[TSA]DATA` / `[TSA]TEXT` / `[TSA]EVENT`）
2. 再写对应 `EXP` 断言
3. 最后 `STOP`，避免回调被提前中断

#### A. 回调断言（最常用）

| 断言类型 | 作用 | 常用字段 | 示例 |
|---|---|---|---|
| `ASRResult` | 断言最终 ASR 识别结果 | `asr`、`confidence`、`lang` | `[EXP]ASRResult asr:今天天气怎么样 <timeout=3>` |
| `cloudASRResult` | 断言云端 ASR 回调 | `asr`、`confidence` | `[EXP]cloudASRResult asr:导航到公司 <timeout=3>` |
| `NLPResult` | 断言语义解析结果 | `skill`、`intention`、`tts`、`text` | `[EXP]NLPResult skill:NAVI;intention:naviPlanRouteToDest <timeout=3>` |

回调断言支持的操作符：
- 精确匹配：`value`
- 任意值：`*`
- 通配符：`*pattern*`
- 或：`v1|v2`
- 非：`!value`
- 空值/非空：`None` / `!None`
- 比较：`>N`、`>=N`、`<N`、`<=N`
- 区间（开区间）：`(N~M)`，即 `N < x < M`
- 包含/不包含：`~value` / `!~value`
- IN/NOT IN：`@in(val)` / `@notin(val)`
- 忽略大小写：`@i(expr)`
- 列表匹配（顺序无关）：`[v1,v2,v3]`
- 转义特殊字符：`\|`、`\~`、`\!`、`\@`、`\(`、`\)`、`\[`、`\]`

操作符示例（回调字段）：
```dsl
[EXP]NLPResult skill:WEATHER|NAVI <timeout=3>
[EXP]ASRResult asr:~天气 <timeout=3>
[EXP]ASRResult asr:!~报错 <timeout=3>
[EXP]ASRResult confidence:>=80 <timeout=3>
[EXP]ASRResult confidence:(60~100) <timeout=3>
[EXP]NLPResult intention:@in(query) <timeout=3>
[EXP]NLPResult tts:@notin(错误) <timeout=3>
[EXP]NLPResult skill:@i(weather) <timeout=3>
```

回调断言示例（完整链路）：
```dsl
>>>
[TSA]START 1
[TSA]FREEWAKEUP 1
[TSA]TEXT 导航到公司
[EXP]ASRResult asr:导航到公司 <timeout=3>
[EXP]NLPResult skill:NAVI;intention:naviPlanRouteToDest <timeout=3>
[TSA]STOP
<<<
```

更多断言类型，详情见mango仓根目录下：`conf/assert_key_value.yaml`文件。

#### B. `SUM` 计数断言

用途：
- 统计某类回调在当前 case 中匹配到的次数，并进行数量比较。

语法：
```dsl
[EXP]SUM [通道]回调类型 COUNT 操作符 数值 <timeout=秒>
```

参数说明：
- `通道`：可省略；支持单通道 `[0]`、多通道 `[0,1,2,3]`
- `回调类型`：常用 `ASRResult`、`localASRResult`、`NLPResult`、`SpeechWakeup`
- `COUNT`：固定关键字（大小写不敏感）
- `操作符`：`==`、`!=`、`>`、`<`、`>=`、`<=`

示例：
```dsl
# 省略通道：统计全通道
[EXP]SUM ASRResult COUNT == 1 <timeout=3>

# 指定单通道
[EXP]SUM [0]ASRResult COUNT >= 1 <timeout=3>

# 指定多通道
[EXP]SUM [0,1,2,3]localASRResult COUNT <= 4 <timeout=3>
```

#### C. API 返回断言

| 断言类型 | 作用 | 常用字段 | 示例 |
|---|---|---|---|
| `GET_VERSION_RET` | 断言接口返回码/返回字段 | `code`（最常用） | `[EXP]GET_VERSION_RET code:0 <timeout=2>` |

API 断言示例：
```dsl
>>>
[TSA]GET_VERSION
[EXP]GET_VERSION_RET code:0 <timeout=2>
<<<
```

#### D. 文件断言

| 断言类型 | 语法 | 参数说明 | 示例 |
|---|---|---|---|
| `FILEEXIT` | `[EXP]FILEEXIT file_path [expected_exists]` | `expected_exists`：`1`存在、`0`不存在（不传默认断言存在） | `[EXP]FILEEXIT {WORKPATH}/callback.jsonl 1` |
| `FILESIZE` | `[EXP]FILESIZE file_path operator expected_size` | `operator`：`>` `<` `=` `>=` `<=`；`expected_size` 为字节数 | `[EXP]FILESIZE {WORKPATH}/callback.jsonl > 1000` |
| `FILEMD5` | `[EXP]FILEMD5 file_path = expected_md5` | 断言文件 MD5 值 | `[EXP]FILEMD5 {WORKPATH}/download.zip = 5d41402abc4b2a76b9719d911017c592` |
| `FILEDIF` | `[EXP]FILEDIF JSON file_path json_path_expr` | JSON 字段比对（字段路径=期望值） | `[EXP]FILEDIF JSON {WORKPATH}/config.json data.timeout=5000` |

文件断言示例：
```dsl
>>>
[EXP]FILEEXIT {WORKPATH}/callback.jsonl 1
[EXP]FILESIZE {WORKPATH}/callback.jsonl > 1000
[EXP]FILEMD5 {WORKPATH}/result.bin = 1921u2u192u1921212
[EXP]FILEDIF JSON {WORKPATH}/daemon_tag.json data.shsh[0].txt.status=0
<<<
```

#### E. 日志断言（`LOG`）

语法：
```dsl
[EXP]LOG 文件名 模式 参数...
```

1) `SEARCH`（关键字搜索）
```dsl
# 存在
[EXP]LOG sdk.log SEARCH "System Start" EXISTS
# 不存在
[EXP]LOG sdk.log SEARCH "[ERROR]" ABSENT
# 数量比较
[EXP]LOG sdk.log SEARCH "Retry" COUNT == 3
```

2) `MATCH KV`（键值对提取）
```dsl
[EXP]LOG sdk.log MATCH "add Client" KV "socket_fd" != -1
[EXP]LOG sdk.log MATCH "add Client" KV "type" == 1
```

3) `MATCH JSON`（JSON 路径提取）
```dsl
[EXP]LOG sdk.log MATCH "API_RESPONSE" JSON "$.code" == 200
[EXP]LOG sdk.log MATCH "API_RESPONSE" JSON "$.data.meta.total" == 50
```

4) `MATCH EXTRACT`（正则提取）
```dsl
[EXP]LOG sdk.log MATCH "processing completed" EXTRACT /in (\d+)ms/ < 100
[EXP]LOG sdk.log MATCH "Task-" EXTRACT /Task-([A-Z0-9]+)/ == "A123"
```

5) `DIFF`（时延断言）
```dsl
[EXP]LOG sdk.log DIFF "[REQ]" "[RESP]" < 500ms
[EXP]LOG sdk.log DIFF "StepA" "StepB" >= 0ms
```

#### F. 一段可直接套用的 EXP 组合模板

```dsl
>>>
[TSA]START 1
[TSA]TEXT 今天天气怎么样
[EXP]ASRResult asr:今天天气怎么样 <timeout=3>
[EXP]SUM ASRResult COUNT >= 1 <timeout=3>
[EXP]NLPResult skill:WEATHER;intention:QUERY <timeout=3>
[EXP]LOG sdk.log SEARCH "[ERROR]" ABSENT
[EXP]LOG sdk.log DIFF "[REQ]" "[RESP]" < 800ms
[EXP]FILEEXIT {WORKPATH}/callback.jsonl 1
[TSA]STOP
<<<
```

注意事项：
- `EXP` 字段名区分大小写，建议优先参考真实回调字段名。
- `timeout` 过小会导致误判失败，首轮调试建议适当放宽。
- `LOG` 断言是按 case 日志窗口读取，避免跨 case 相互污染。

### 6.4 TSR 客户端（suite 统计）

`TSR` 是 suite 级统计客户端，建议统一写在 `SUITE_TEARDOWN`。  
通用语法：
```dsl
[TSR]指令 result=<结果文件> ref=<参考输入> [其他参数] [output=<报告路径>]
```

#### 6.4.1 指令总览（每个都可独立跑）

| 指令 | result 输入 | ref 输入 | ref 格式要点 | 典型输出 |
|---|---|---|---|---|
| `ASR_ACCURACY` | `asr.csv` | 参考答案 CSV | `AUDIOPATH/TEXT` 或同义列名（如 `voice/ref`） | `asr_accuracy.xlsx` |
| `ASR_LANGUAGE` | `asr.csv` | 语种代码 | 直接写语种，如 `cmn` / `en` / `yue` | `asr_language.xlsx` |
| `DELAY` | `callback.jsonl` | 卡拉OK标注文本 | `<time>字` 连续标注，单位秒 | `delay.xlsx` |
| `WAKEUP_ACCURACY` | 唤醒结果 CSV（有表头） | 唤醒参考 CSV（无表头） | `音频,关键词,start,end` | `wakeup_accuracy.xlsx` |
| `VAD_ACCURACY` | VAD 结果 txt | VAD 参考 txt | `音频 00h_S start end`（空格分隔） | `vad_accuracy.xlsx` |
| `VAD_PRECISION` | VAD 结果 txt | VAD 参考 txt | 同 `VAD_ACCURACY` | `vad_precision.xlsx` |
| `TIME_BOUNDARY_ACCURACY` | 边界 txt 或 `callback.jsonl` | 边界参考 txt | `音频 00h_S start end`；可配 `threshold/type` | `time_boundary_accuracy.xlsx` |
| `LLM` | 任意评测 CSV | Prompt 模板文件 | `ref` 在该指令中由 `prompt=` 替代 | `llm_eval.xlsx` |

#### 6.4.2 各指令详细输入要求

1) `ASR_ACCURACY`
- DSL：
```dsl
[TSR]ASR_ACCURACY result={WORKPATH}/asr.csv ref=TestCase/ref/cmn_answer.csv output={WORKPATH}/asr_accuracy.xlsx
```
- `result`：CSV（逗号或Tab），至少包含 `voice`、`result`、`type`（`confidence` 可选）
- 类型过滤：仅统计最终 `*ASRResult`，自动过滤 `*ASRResultTemp`
- `ref`：答案 CSV，需包含“音频路径 + 标准文本”

2) `ASR_LANGUAGE`
- DSL：
```dsl
[TSR]ASR_LANGUAGE result={WORKPATH}/asr.csv ref=cmn output={WORKPATH}/asr_language.xlsx
```
- `result`：CSV，需有 `voice`、`lang`、`type`
- `ref`：期望语种代码（不是文件），如 `cmn`、`en`、`yue`
- 规则：语种大小写不敏感，`zh-cmn` 自动归一为 `cmn`

3) `DELAY`
- DSL（实时）：
```dsl
[TSR]DELAY ref=TestCase/ref/label.txt result={WORKPATH}/callback.jsonl type=PSTTASRResultTemp output={WORKPATH}/delay.xlsx
```
- DSL（最终）：
```dsl
[TSR]DELAY ref=TestCase/ref/label.txt result={WORKPATH}/callback.jsonl type=PSTTASRResult output={WORKPATH}/delay.xlsx
```
- `result`：`callback.jsonl`，需含 `callback_type`、`data.audio`、`data.audiotime`、`data.asr`
- `ref`：卡拉OK标注文本，每行形如：`音频路径 <0.3>打<0.5>开<0.8>`
- `type`：以 `Temp` 结尾表示实时上屏；否则为最终结果时延

4) `WAKEUP_ACCURACY`
- DSL：
```dsl
[TSR]WAKEUP_ACCURACY result={WORKPATH}/wakeup.csv ref=TestCase/ref/wakeup_ref.csv output={WORKPATH}/wakeup_accuracy.xlsx
```
- `result`：有表头 CSV，字段：`audio,result,start,end`
- `ref`：无表头 CSV，列顺序固定：`音频路径,关键词,开始(s),结束(s)`

5) `VAD_ACCURACY`
- DSL：
```dsl
[TSR]VAD_ACCURACY result={WORKPATH}/vad.txt ref=TestCase/ref/vad_ref.txt output={WORKPATH}/vad_accuracy.xlsx
```
- `result/ref`：同格式 txt，空格分隔，无表头：`音频路径 00h_S 开始(s) 结束(s)`

6) `VAD_PRECISION`
- DSL：
```dsl
[TSR]VAD_PRECISION result={WORKPATH}/vad.txt ref=TestCase/ref/vad_ref.txt output={WORKPATH}/vad_precision.xlsx
```
- 输入格式与 `VAD_ACCURACY` 完全一致
- 作用：统计 start/end 时间边界误差分布（不是 FA/FR）

7) `TIME_BOUNDARY_ACCURACY`
- DSL：
```dsl
[TSR]TIME_BOUNDARY_ACCURACY result={WORKPATH}/callback.jsonl ref=TestAudio/SDK/time_boundary/0_output_timelist.txt output={WORKPATH}/time_boundary_accuracy.xlsx threshold=0.3 type=both
```
- `result`：可用边界 txt 或 `callback.jsonl`
- `ref`：边界参考 txt（`音频 00h_S start end`）
- 常用参数：
  - `threshold`：阈值（秒），超阈值在报告中标红
  - `type`：`ASRResult` / `localASRResult` / `cloudASRResult` / `both`

8) `LLM`
- DSL：
```dsl
[TSR]LLM result={WORKPATH}/nlu_result.csv prompt=TestCase/eval_prompts.txt output={WORKPATH}/llm_eval.xlsx batch=10
```
- `result`：待评测 CSV（列名可自定义）
- `prompt`：模板文本文件，使用 `{列名}` 占位
- 额外依赖环境变量：`DEEPSEEK_API_KEY`（必需）

#### 6.4.3 推荐写法
```dsl
>>> SUITE_TEARDOWN
[TSR]ASR_ACCURACY result={WORKPATH}/asr.csv ref=TestCase/ref/cmn_answer.csv output={WORKPATH}/asr_accuracy.xlsx
[TSR]ASR_LANGUAGE result={WORKPATH}/asr.csv ref=cmn output={WORKPATH}/asr_language.xlsx
[TSR]DELAY ref=TestCase/ref/label.txt result={WORKPATH}/callback.jsonl type=PSTTASRResultTemp output={WORKPATH}/delay_temp.xlsx
[TSR]DELAY ref=TestCase/ref/label.txt result={WORKPATH}/callback.jsonl type=PSTTASRResult output={WORKPATH}/delay_final.xlsx
<<<
```

### 6.5 完整 Case 模板

```dsl
>>> SETUP
[SYS]PULL AIBSServer cmn {"brand":"0"}
[SYS]SLEEP 2
[TSA]CREATE cmn com.autoai.vr.service_vrassistant
<<<

# 天气查询-冒烟
>>>
[TSA]START 1
[TSA]FREEWAKEUP 1
[TSA]STRATEGY 1
[TSA]TEXT 今天天气怎么样
[EXP]NLPResult skill:WEATHER;intention:QUERY <timeout=2>
[EXP]LOG sdk.log SEARCH "[ERROR]" ABSENT
[TSA]STOP
<<<

>>> TEARDOWN
[TSA]FREE
[SYS]KILL AIBSServer
<<<

>>> SUITE_TEARDOWN
[TSR]ASR_LANGUAGE result={WORKPATH}/asr.csv ref=cmn output={WORKPATH}/asr_language.xlsx
<<<
```

---

## 7. 环境变量篇

### 7.1 语法与作用
- 环境变量语法：`{VARIABLE_NAME}`
- 动态表达式语法：`{EVAL:python_expression}`
- 作用：消除硬编码路径/名称，让同一份用例在不同机器、不同 workspace 下可复用。

示例：
```dsl
[TSA]DATA {WORKPATH}/audio/test.wav
[SYS]CMD cp {CONFIGPATH} {WORKPATH}/backup.conf
[SYS]PRINT Suite={SUITENAME}, ID={SUITEID}, TS={TIMESTAMP}
```

### 7.2 变量清单（与代码一致）

> 变量来源：`src/testsuite/NANO/config.py` 中 `ENVIRONMENT_VARIABLES`。

| 分类 | 变量 | 含义 |
|---|---|---|
| 路径 | `{WORKPATH}` | Suite 工作目录 |
| 路径 | `{ROOTPATH}` | 项目根目录 |
| 路径 | `{WORKSPACE}` | 工作空间路径 |
| 路径 | `{BASEPATH}` | 并发模式下当前 worker 的基路径 |
| 路径 | `{LIBPATH}` | 库文件路径 |
| 路径 | `{CASEPATH}` | 用例目录路径 |
| 路径 | `{LOGPATH}` | 日志目录路径 |
| 路径 | `{SOCKETPATH}` | Socket 端口文件路径 |
| 配置 | `{CONFIGPATH}` | 解码配置路径 |
| 配置 | `{CARPLAYCONFIG}` | CarPlay 配置路径 |
| 配置 | `{LCSCONFIG}` | LCS 配置路径 |
| 配置 | `{CASELIST}` | 用例列表路径 |
| 配置 | `{PARAMETERIZEDATA}` | 参数化数据文件路径 |
| 元数据 | `{SUITEID}` | Suite ID |
| 元数据 | `{SUITENAME}` | Suite 名称 |
| 元数据 | `{CASEID}` | CaseID 名称 |
| 动态 | `{UUID}` | 随机 UUID |
| 动态 | `{TIMESTAMP}` | 当前时间戳 |
| 动态 | `{NOW}` | 当前日期时间 |

### 7.3 实战用法

1) 路径组装（最常用）：
```dsl
[SYS]CMD mkdir -p {WORKPATH}/output
[SYS]CMD cp {CONFIGPATH} {WORKPATH}/decoder.conf.bak
[TSA]DATA {WORKPATH}/audio/query.wav
```

3) 运行时表达式（`EVAL`）：
```dsl
[SYS]PRINT 当前时间: {EVAL:datetime.datetime.now().strftime('%H:%M:%S')}
[SYS]PRINT 明日日期: {EVAL:get_date(1)}
```

### 7.4 注意事项
- 只替换 `{VAR}`，不会替换 `${var}`（`${}` 是参数化变量体系）。
- 变量名必须全大写；未定义变量会保留原样。
- `EVAL` 执行失败时会保留原表达式并记录日志，建议先小范围验证。

---

## 8. 测试用例编写篇

### 8.1 SDK 用例
关注接口链路：`CREATE -> START -> DATA/TEXT -> EXP -> STOP -> FREE`

编写步骤（建议）：
1. 先在 `SETUP` 拉起服务并 `CREATE` 客户端。
2. 在 `TEST` 块里只保留一条主链路动作（`DATA` 或 `TEXT`），避免一个 case 混太多目标。
3. 主断言优先写 `ASRResult/NLPResult`，再补 `LOG` 防回归断言。
4. 在 `TEARDOWN` 统一 `STOP/FREE/KILL`，保证 case 间相互隔离。

常见可调参数：
- `[TSA]DATA ... frame=320/640`：分帧大小
- `[TSA]DATA ... delay=1`：送音节奏（秒）
- `[TSA]FREEWAKEUP 0/1`：是否免唤醒
- `[TSA]STRATEGY 0/1/2`：识别策略

示例：
```dsl
>>> SETUP
[SYS]PULL AIBSServer cmn {"brand":"0"}
[SYS]PULL LCSEngine cmn
[TSA]CREATE cmn com.autoai.vr.service_vrassistant
<<<

>>>
[TSA]START 1
[TSA]DATA {WORKPATH}/audio/test.wav frame=320 delay=1
[EXP]ASRResult asr:打开空调 <timeout=3>
[EXP]LOG sdk.log SEARCH "[ERROR]" ABSENT
[TSA]STOP
<<<

>>> TEARDOWN
[TSA]FREE
[SYS]KILL LCSEngine
[SYS]KILL AIBSServer
<<<
```

### 8.2 NLU 用例
关注 skill/intention 是否匹配。

编写要点：
- 文本用例优先使用 `[TSA]TEXT`，语音语义用例可用 `[TSA]DATA` + `NLPResult`。
- `NLPResult` 至少断言 `skill` 和 `intention`；关键场景再补 `tts` 或 `directivesType`。
- 推荐同时加一条 `SUM` 或 `LOG` 断言，避免“语义对了但过程异常”漏检。

示例：
```dsl
>>>
[TSA]START 1
[TSA]FREEWAKEUP 1
[TSA]STRATEGY 1
[TSA]TEXT 导航到公司
[EXP]NLPResult skill:NAVI;intention:naviPlanRouteToDest <timeout=2>
[EXP]SUM NLPResult COUNT >= 1 <timeout=2>
[TSA]STOP
<<<
```

推荐目录组织：
- 用例：`TestCase/caselist/.../*.mgo`
- 参数化：`TestCase/data/*.csv`
- 引用事件：`TestCase/caselist/.../event/*.json`

---

## 9. 结果查看与日志定位

### 9.1 主要产物
- `asr.csv`：识别结果汇总
- `wakeup.csv`：唤醒结果汇总
- `callback.jsonl`：全量回调记录
- Allure 报告目录：suite 的 `report/` 目录
- `workspace/.../log/`：运行日志（含客户端日志、执行日志）
- `workspace/.../allure_result/`：Allure 原始结果
- `workspace/.../mango_report/`：TSR 统计报告（xlsx/html）

### 9.2 日志在哪看
优先顺序：
1. 终端实时输出
2. suite 目录下 `log/` 文件
3. `callback.jsonl` 回放关键回调
4. Allure 中的失败步骤与附件

快速定位建议：
- 看失败 case 名称后，先定位同名 suite 目录。
- 在 `callback.jsonl` 中按音频名/时间段查对应回调。
- `EXP` 失败先确认“没回调”还是“字段不匹配”，两者排查路径不同。

### 9.3 常见排障路径
1. 先看主断言失败点（功能是否没返回）
2. 再看 `LOG` 断言（是否有异常日志）
3. 最后看 `callback.jsonl` 的回调时序

建议排障闭环：
1. 复现失败（固定 `-F` 行范围、必要时加 `-R 1`）
2. 缩小范围（只跑单个 case / 单条参数化行）
3. 对比成功样本（同场景同参数）找差异
4. 输出最小复现命令，便于研发联调

---

## 10. 文档索引（功能查阅导航）

当你需要定位某个功能时，优先按下表查文档：

| 需求场景 | 建议先看文档 | 说明 |
|---|---|---|
| 新人快速上手、部署、参数、用例编写 | `doc/Mango_测试使用说明.md` | 统一入口文档，覆盖日常测试执行主链路 |
| 查看 v3.6.0 新增/修复内容 | `doc/RELEASE_V3.6.0.md` | 包含 CarPlay、LOG断言、Case级参数化、BREF 等版本变化 |
| 查看 v3.7.0 新增/修复内容 | `doc/RELEASE_V3.7.0.md` | 包含 TSR 体系、PIS/ENR 客户端、并发与报告增强 |
| 查某个 DSL 指令语法/参数 | `src/testsuite/NANO/doc/COMMAND.md` | 指令全集，按客户端分类，含语法与示例 |
| 查断言系统（EXP）细节 | `src/testsuite/NANO/doc/EXPECT.md` | 回调/API/文件/SUM 等断言说明 |
| 查日志断言（LOG）高级玩法 | `src/testsuite/NANO/doc/LOG_ASSERTION.md` | SEARCH/MATCH/DIFF 及窗口机制 |
| 查环境变量与 EVAL | `src/testsuite/NANO/doc/ENV.md` | `{WORKPATH}` 等变量和 `{EVAL:...}` 用法 |
| 查 TSR 指令输入格式与报告字段 | `src/testsuite/NANO/doc/TSR.md` | ASR/DELAY/WAKEUP/VAD/LLM 全部统计指令 |

推荐查阅顺序：
1. 先在 `doc/Mango_测试使用说明.md` 找“功能入口”和标准用法。
2. 再到专项文档（`COMMAND.md` / `EXPECT.md` / `TSR.md` / `ENV.md`）看参数细节。
3. 最后用 `doc/RELEASE_V3.6.0.md`、`doc/RELEASE_V3.7.0.md` 确认版本差异与兼容性。

---

## 11. 常见问题

### 11.1 参数化不生效
- case 中没有 `${}`
- 没传 `-P` 且没写 `>>> PARAMETER xxx.csv`
- `-PF` 把数据过滤空了
- CSV 表头与 `${变量名}` 不一致（大小写不一致）
- `-S` 文件缺少 `CaseID` / `StepCase` 列

### 11.2 用例跑不起来
- `-C` 或 `-a` 路径错误
- 项目参数 `-b` 不匹配
- 服务未拉起（检查 `SYS PULL`）
- `TestCase/TestResource/TestAudio` 软链接失效
- `-p`（LCS 配置）未传或文件不存在（LCS 依赖环境必填）

### 11.3 Docker 模式路径错误
- 命令里应使用容器内路径（如 `TestCase/...`）
- `-v` 宿主机路径必须真实存在
- 挂载只读导致写失败（需要时改为 `:rw`）
- 容器内外路径混用（宿主机绝对路径不能直接给容器内命令）

### 11.4 EXP 断言总是超时
- `timeout` 太短，先放宽到 `3~5s` 验证链路
- 断言类型不匹配（例如应使用 `NLPResult` 却写成 `ASRResult`）
- `START/STOP` 时序不对，回调尚未产生就结束会话

### 11.5 TSR 报告为空或数据异常
- `result/ref` 文件格式不符合指令要求（表头、分隔符、列顺序）
- `DELAY` 的 `type` 与 `callback_type` 不一致（大小写敏感）
- 路径里环境变量未正确替换（确认 `{WORKPATH}` 是否有效）

