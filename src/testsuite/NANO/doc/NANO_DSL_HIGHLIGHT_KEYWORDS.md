# NANO DSL 高亮关键词清单

## 1. 目的

本文档用于统一记录 **NANO `.mgo` 时序 DSL** 在编辑器中需要高亮的关键词与语法元素。

目标有两个：

1. 给 Vim/Neovim 语法文件提供单一维护入口。
2. 明确哪些内容应该使用“静态词表高亮”，哪些内容应该使用“通用语法规则高亮”。

本文档以**当前代码真实实现**为准，主要依据：

- `src/testsuite/NANO/config.py`
- `src/testsuite/NANO/dsl_engine.py`
- `src/testsuite/NANO/assertion/AssertionParser.py`
- `conf/assert_key_value.yaml`
- `README.md`
- `src/testsuite/NANO/doc/`
- `src/testsuite/NANO/runner/NANORunner.py`

## 2. 高亮设计原则

### 2.1 适合静态词表高亮的内容

- 块关键字
- 客户端标签
- 客户端命令名
- `EXP` 断言类型
- `LOG` / `SUM` 子关键字
- 内置环境变量
- 文件断言类型
- TSR 指令
- 常见模式关键字

### 2.2 适合通用规则高亮的内容

- `${变量}` 参数化占位符
- `{环境变量}` 与 `{EVAL:...}`
- `<timeout=...>`
- `[0]` 这类通道前缀
- `key=value`
- `field:value`
- 数字、布尔值、字符串
- 比较运算符
- 注释

### 2.3 不建议维护成静态词表的内容

- `field:value` 中的字段名
- `LOG MATCH JSON` 里的 JSON 路径
- 任意普通参数值
- 文件路径、业务文案、音频名

这些内容数量太大、变化太快，使用通用规则高亮更稳。

## 3. 块结构关键字

### 3.1 块边界

- `>>>`
- `<<<`

### 3.2 Fixture / Case 块关键字

- `SETUP`
- `TEARDOWN`
- `SUITE_TEARDOWN`
- `PARAMETER`

### 3.3 特殊块头写法

- `>>> 1`
- `>>> 2`
- `>>> 3`
- 任意 `>>> <数字>` 都表示 Case 重复次数
- `>>> PARAMETER default`
- `>>> PARAMETER xxx.csv`
- 裸 `>>>` 也合法，表示普通测试块

### 3.4 对应实现

- `src/testsuite/NANO/dsl_engine.py`
- `case_pattern = r'^>>>\s*(SETUP|TEARDOWN|SUITE_TEARDOWN|PARAMETER\s+[^\n]+|\d+)?\s*\n(.*?)\n<<<'`

## 4. 注释

`.mgo` 用例中的注释按以下规则高亮：

- 行首 `#`
- 行尾 `# ...`

说明：

- `.mgo` 主解析流程按 `#` 处理注释。
- `//` 在部分辅助逻辑里会被跳过，但不是主 DSL 注释标准。
- Vim 可以顺带兼容 `//`，但核心应以 `#` 为主。

## 5. 客户端标签

以下客户端标签需要高亮：

- `TSA`
- `SET`
- `VOI`
- `OMS`
- `TTS`
- `HWK`
- `PST`
- `TIA`
- `CPL`
- `ENR`
- `PIS`
- `TSS`
- `SYS`
- `TSR`
- `NIS`
- `NSE`
- `EXP`

对应写法：

```dsl
[TSA]
[SYS]
[EXP]
```

## 6. 客户端命令关键字

以下命令以 `config.py -> CLIENT_COMMANDS` 为准。

### 6.1 TSA

- `CREATE`
- `START`
- `STOP`
- `FREE`
- `DATA`
- `EVENT`
- `CANCEL`
- `FREEWAKEUP`
- `PARALLELSR`
- `SETVRCONFIG`
- `TEXT`
- `STRATEGY`
- `PAUSE`
- `RESUME`
- `GET_VERSION`
- `CAR_TYPE`
- `LOG_PATH`
- `MIC_STATUS`
- `VR_STATUS`
- `LINK_TYPE`
- `VREVENT`
- `START_RECORD`
- `STOP_RECORD`
- `OPEN_VOICE_INPUT`
- `CLOSE_VOICE_INPUT`
- `START_SPEAKER_ENROLL`
- `END_SPEAKER_ENROLL`
- `RECOGNIZE_SPEAKER`
- `VOICEPRINT_LOGIN`
- `VERIFY_VOICEPRINT`
- `CANCEL_VERIFY_VOICEPRINT`
- `DELETE_SPEAKER`
- `GET_SPEAKER_INFO`
- `GET_SPEAKERS`
- `GET_ENROLL_TEXT`
- `SENSITIVE_WORD_CHECK`
- `REGISTER_VOICEPRINT_LIST`
- `CLEAR_VR_CONFIG`
- `GET_CONFIG_ITEM`
- `GET_FOTA_STATUS`
- `WRITE_LOG`
- `CONFIG_VOICELOG`
- `SET_VOICELOG_PATH`
- `SET_PARAM`
- `SET_TTS_STATE`
- `SET_LANGUAGE_MODE`
- `SET_WORKMODE`
- `UPDATE_PERSONALIZED`
- `SET_PAGE_INTENT`
- `GET_WAKEUP_WORD`
- `GET_VR_CONFIG`
- `INPUTEVENT`
- `CALLBACK`

### 6.2 SET

- `CREATE`
- `START`
- `STOP`
- `FREE`
- `DATA`
- `EVENT`
- `CANCEL`
- `FREEWAKEUP`
- `TEXT`
- `STRATEGY`
- `SETVRCONFIG`
- `PAUSE`
- `RESUME`
- `CAR_TYPE`
- `LOG_PATH`
- `MIC_STATUS`
- `VR_STATUS`
- `LINK_TYPE`
- `VREVENT`
- `CLEAR_VR_CONFIG`
- `GET_CONFIG_ITEM`
- `SET_TTS_STATE`
- `SET_LANGUAGE_MODE`
- `SET_WORKMODE`
- `GET_VR_CONFIG`
- `GET_WAKEUP_WORD`
- `SET_WAKEUP_WORD`
- `SET_WAKEUP_ENABLE`
- `GET_FOTA_STATUS`
- `REGISTER_VOICEPRINT_LIST`
- `VOICEPRINT_LOGIN`
- `START_SPEAKER_ENROLL`
- `END_SPEAKER_ENROLL`
- `RECOGNIZE_SPEAKER`
- `VERIFY_VOICEPRINT`
- `CANCEL_VERIFY_VOICEPRINT`
- `DELETE_SPEAKER`
- `GET_SPEAKER_INFO`
- `GET_SPEAKERS`
- `GET_ENROLL_TEXT`
- `SENSITIVE_WORD_CHECK`

### 6.3 VOI

- `CREATE`
- `START`
- `STOP`
- `FREE`
- `DATA`
- `EVENT`
- `CANCEL`
- `FREEWAKEUP`
- `TEXT`
- `STRATEGY`
- `SETVRCONFIG`
- `PAUSE`
- `RESUME`
- `OPEN_VOICE_INPUT`
- `CLOSE_VOICE_INPUT`
- `GET_ENROLL_TEXT`
- `RECOGNIZE_SPEAKER`
- `SENSITIVE_WORD_CHECK`
- `SET_LANGUAGE_MODE`
- `SET_WORKMODE`

### 6.4 OMS

- `CREATE`
- `START`
- `STOP`
- `FREE`
- `DATA`
- `EVENT`
- `CANCEL`
- `FREEWAKEUP`
- `TEXT`
- `STRATEGY`
- `SETVRCONFIG`
- `GET_FOTA_STATUS`

### 6.5 TTS

- `CREATE`
- `START`
- `STOP`
- `FREE`
- `DATA`
- `EVENT`
- `CANCEL`
- `FREEWAKEUP`
- `TEXT`
- `STRATEGY`
- `SETVRCONFIG`
- `GET_FOTA_STATUS`

### 6.6 HWK

- `CREATE`
- `START`
- `STOP`
- `FREE`
- `DATA`
- `CANCEL`
- `SET_PARAM`
- `INIT_DECODE`
- `SET_DATA_TYPE`
- `UPDATE_PERSONALIZED`
- `SET_WORK_MODE`
- `SET_TTS_STATE`
- `SET_FREETALK_STATE`
- `ADD_WAKEUP_WORD`
- `GET_WAKEUP_TERM`
- `SET_WAKEUP_ENABLE`
- `SET_VOICE_WAKEUP_OPTION`
- `SET_SRE_REQUEST`
- `SET_SRE_ENABLE_OPTION`
- `OPEN_VOICE_INPUT`
- `CLOSE_VOICE_INPUT`
- `SET_LANGUAGE_INFO`
- `CONFIG_VOICELOG`
- `SET_VOICELOG_PATH`
- `SET_VR_SILENCE_TIMEOUT`
- `SET_LINK_TYPE`
- `SET_MIC_STATUS`
- `SET_CAR_TYPE`
- `START_RECORD`
- `STOP_RECORD`
- `SENSITIVE_WORD_CHECK`
- `HMI`

### 6.7 PST

- `CREATE`
- `FREE`
- `DATA`
- `HMI`
- `DATA_QUEUE`

### 6.8 TIA

- `CREATE`
- `DATA`
- `CASELIST`

### 6.9 CPL

- `CREATE`
- `FREE`

### 6.10 ENR

- `SET_DOWNLINK`
- `AMP_TYPE`
- `ECNR_TYPE`
- `CREATE`
- `START`
- `STOP`
- `FREE`
- `SET_WORKMODE`
- `DATA`
- `GET_VERSION`
- `SET_PNR_MIC_MUTE_OPTION`
- `SET_PNR_ENABLE_OPTION`
- `SET_PNR_AUDIO_QUALITY`
- `GET_PNR_VERSION`
- `GET_PNR_HFT_PARAM`
- `GET_PNR_MVR_PARAM`
- `GET_PNR_GEN_PARAM`
- `ANALYZE_AUDIO_DATA`

### 6.11 PIS

- `CREATE`
- `AIBSServer`
- `AIBS_SET_CARTYPE`
- `AIBS_SET_WORK_MODE`
- `AIBS_CREATE`
- `AIBS_START`
- `AIBS_STOP`
- `START`
- `STOP`
- `FREE`
- `DATA`
- `VEDIO`
- `WAIT`
- `UPDATE`

### 6.12 TSS

- `START_SERVICE`
- `START`
- `SET_CARTYPE`
- `STOP`
- `CREATE`
- `DATA`
- `SET_PARAM`
- `SET_LANGUAGE_MODE`
- `SET_WAKEUP_WORD`
- `SET_WAKEUP_ENABLE`
- `GET_WAKEUP_WORD`
- `FREE`

### 6.13 SYS

- `PULL`
- `KILL`
- `SLEEP`
- `CMD`
- `PRINT`
- `ENV`
- `UPLOAD`
- `ALLURE`
- `FOTA_RANDOM_ZIP`
- `BREF`
- `CLEAR_ASSERT`

### 6.14 TSR

- `ASR_ACCURACY`
- `ASR_LANGUAGE`
- `DELAY`
- `WAKEUP_ACCURACY`
- `VAD_ACCURACY`
- `VAD_PRECISION`
- `TIME_BOUNDARY_ACCURACY`
- `LLM`
- `PSTT_ACCURACY`

### 6.15 NIS

与 `TSA` 相同：

- `CREATE`
- `START`
- `STOP`
- `FREE`
- `DATA`
- `EVENT`
- `CANCEL`
- `FREEWAKEUP`
- `SETVRCONFIG`
- `TEXT`
- `STRATEGY`
- `PAUSE`
- `RESUME`
- `GET_VERSION`
- `CAR_TYPE`
- `LOG_PATH`
- `MIC_STATUS`
- `VR_STATUS`
- `LINK_TYPE`
- `VREVENT`
- `START_RECORD`
- `STOP_RECORD`
- `OPEN_VOICE_INPUT`
- `CLOSE_VOICE_INPUT`
- `START_SPEAKER_ENROLL`
- `END_SPEAKER_ENROLL`
- `RECOGNIZE_SPEAKER`
- `VOICEPRINT_LOGIN`
- `VERIFY_VOICEPRINT`
- `CANCEL_VERIFY_VOICEPRINT`
- `DELETE_SPEAKER`
- `GET_SPEAKER_INFO`
- `GET_SPEAKERS`
- `GET_ENROLL_TEXT`
- `SENSITIVE_WORD_CHECK`
- `REGISTER_VOICEPRINT_LIST`
- `CLEAR_VR_CONFIG`
- `GET_CONFIG_ITEM`
- `GET_FOTA_STATUS`
- `WRITE_LOG`
- `CONFIG_VOICELOG`
- `SET_VOICELOG_PATH`
- `SET_PARAM`
- `SET_TTS_STATE`
- `SET_LANGUAGE_MODE`
- `SET_WORKMODE`
- `UPDATE_PERSONALIZED`
- `SET_PAGE_INTENT`
- `GET_WAKEUP_WORD`
- `GET_VR_CONFIG`
- `INPUTEVENT`
- `CALLBACK`

### 6.16 NSE

- `CREATE`
- `START`
- `STOP`
- `FREE`
- `DATA`
- `EVENT`
- `CANCEL`
- `FREEWAKEUP`
- `TEXT`
- `STRATEGY`
- `SETVRCONFIG`
- `PAUSE`
- `RESUME`
- `CAR_TYPE`
- `LOG_PATH`
- `MIC_STATUS`
- `VR_STATUS`
- `LINK_TYPE`
- `VREVENT`
- `CLEAR_VR_CONFIG`
- `GET_CONFIG_ITEM`
- `SET_TTS_STATE`
- `SET_LANGUAGE_MODE`
- `SET_WORKMODE`
- `GET_VR_CONFIG`
- `GET_WAKEUP_WORD`
- `SET_WAKEUP_WORD`
- `SET_WAKEUP_ENABLE`
- `REGISTER_VOICEPRINT_LIST`
- `VOICEPRINT_LOGIN`
- `START_SPEAKER_ENROLL`
- `END_SPEAKER_ENROLL`
- `RECOGNIZE_SPEAKER`
- `VERIFY_VOICEPRINT`
- `CANCEL_VERIFY_VOICEPRINT`
- `DELETE_SPEAKER`
- `GET_SPEAKER_INFO`
- `GET_SPEAKERS`
- `GET_ENROLL_TEXT`
- `SENSITIVE_WORD_CHECK`

## 7. EXP 断言关键词

`[EXP]` 后的第一个词需要高亮。

其真实集合由以下四部分组成：

1. `AssertCodeTypeList`
2. `conf/assert_key_value.yaml` 顶层键
3. `FILE_ASSERT_COMMANDS`
4. `LOG`、`SUM`

### 7.1 API 返回值断言类型

- `CREATE_RET`
- `START_RET`
- `STOP_RET`
- `FREE_RET`
- `DATA_RET`
- `EVENT_RET`
- `CANCEL_RET`
- `FREEWAKEUP_RET`
- `SETVRCONFIG_RET`
- `PAUSE_RET`
- `RESUME_RET`
- `GET_VERSION_RET`
- `CAR_TYPE_RET`
- `LOG_PATH_RET`
- `MIC_STATUS_RET`
- `VR_STATUS_RET`
- `LINK_TYPE_RET`
- `VREVENT_RET`
- `START_RECORD_RET`
- `STOP_RECORD_RET`
- `OPEN_VOICE_INPUT_RET`
- `CLOSE_VOICE_INPUT_RET`
- `CLEAR_VR_CONFIG_RET`
- `GET_FOTA_STATUS_RET`
- `SET_PARAM_RET`
- `UPDATE_PERSONALIZED_RET`
- `SET_TTS_STATE_RET`
- `SET_PAGE_INTENT_RET`
- `SET_LANGUAGE_MODE_RET`
- `SET_WAKEUP_WORD_RET`
- `SET_WAKEUP_ENABLE_RET`
- `GET_WAKEUP_WORD_RET`
- `SET_WORKMODE_RET`
- `GET_VR_CONFIG_RET`
- `START_SPEAKER_ENROLL_RET`
- `END_SPEAKER_ENROLL_RET`
- `RECOGNIZE_SPEAKER_RET`
- `VOICEPRINT_LOGIN_RET`
- `VERIFY_VOICEPRINT_RET`
- `CANCEL_VERIFY_VOICEPRINT_RET`
- `DELETE_SPEAKER_RET`
- `GET_SPEAKER_INFO_RET`
- `GET_SPEAKERS_RET`
- `GET_ENROLL_TEXT_RET`
- `SENSITIVE_WORD_CHECK_RET`
- `GET_CONFIG_ITEM_RET`
- `WRITE_LOG_RET`
- `CONFIG_VOICELOG_RET`
- `SET_VOICELOG_PATH_RET`
- `VR_OPTION_RET`
- `SHOW_STYLE_RET`
- `WAKEUP_ALIAS_RET`
- `DIALOGUE_STYLE_RET`
- `DIALOGUE_LANGUAGE_RET`
- `SOUND_AREA_OPTION_RET`
- `WAKEUP_KEYWORD_OPTION_RET`
- `VOICE_WAKEUP_OPTION_RET`
- `WAKEUP_ENABLE_RET`
- `SET_TTS_VOICE_TYPE_RET`
- `MULTI_DIALOGUE_RET`
- `EXPERIENCE_IMPROVENMENT_RET`
- `PERSONAL_SENSITIVE_AUTHORIZATION_RET`
- `VOICE_SENSITIVE_AUTHORIZATION_RET`
- `ACTIVE_INTERACTION_RET`
- `SRE_SENSITIVE_EMPOWER_OPTION_RET`
- `SRE_FUNC_ENABLE_OPTION_RET`
- `SERVER_CACHE_LANGUAGE_RET`
- `GPT_ENABLE_OPTION_RET`
- `SRE_MEMORY_RET`
- `VEHICLE_MEMORY_RET`
- `AIBS_PARAM_SESSION_LINK_TYPE_RET`
- `AIBS_PARAM_SEAT_SIGNAL_RET`
- `AIBS_PARAM_FULL_VEHICLE_SPEECH_RET`
- `AIBS_PARAM_REAL_TIME_RESULT_RET`
- `AIBS_PARAM_PUNC_RESULT_RET`
- `AIBS_PARAM_DIGIT_CONVERT_RESULT_RET`
- `AIBS_PARAM_SILENCE_DURATION_RET`
- `AIBS_PARAM_SILENCE_TIMEOUT_RET`
- `AIBS_PARAM_SPEECH_TIMEOUT_RET`
- `AIBS_PARAM_SCENAROI_NAME_RET`
- `AIBS_PARAM_WAKEUP_SCENE_RET`
- `AIBS_PARAM_WAKEUP_DELAY_ONESHOT_DURATION_RET`
- `AIBS_PARAM_SOUND_EVENT_OPTION_RET`
- `AIBS_PARAM_DISABLE_BUTTON_WAKEUP_RET`
- `AIBS_PARAM_EMOTION_OPTION_RET`
- `AIBS_PARAM_SR_PTT_OPTION_RET`
- `AIBS_PARAM_SR_VOICE_WAKEUP_RET`
- `AIBS_PARAM_SR_WAKEUP_SCENE_ENABLE_RET`
- `AIBS_PARAM_SR_AUDIO_SPECTRAL_RET`
- `AIBS_PARAM_SR_RECORD_DEVICE_STATE_RET`
- `CARPLAY_CREATE_RET`
- `CARPLAY_FREE_RET`

### 7.2 回调 / JSON 断言类型

以下名称来自 `conf/assert_key_value.yaml` 顶层键：

- `NLPResult`
- `ASRInputResult`
- `ASRInputResultTemp`
- `HICARWakeup`
- `ASRResultTemp`
- `ASRResult`
- `cloudASRResult`
- `localASRResult`
- `startEnroll`
- `verifyVoiceprint`
- `SpeechWakeup`
- `VoiceInput-SilenceTimeout`
- `LCSInit`
- `SpeechASRResultTemp`
- `SpeechASRResult`
- `SpeechEngineWakeup`
- `TSSAIBSWakeup`
- `TiTanASRResultTemp`
- `TiTanASRResult`
- `PSTTASRResultTemp`
- `PSTTASRResult`
- `VRConfig`
- `CarPlayWakeup`
- `CarPlayVadStart`
- `CarPlayVadEnd`
- `CarPlayStatus`
- `PISASRResult`
- `ResponseTTS`
- `PISAVedioText`
- `PISToolCall`
- `TSS`
- `ECNR`

### 7.3 文件断言类型

- `FILEEXIT`
- `FILESIZE`
- `FILEMD5`
- `FILEDIF`

### 7.4 特殊断言类型

- `LOG`
- `SUM`

## 8. LOG / SUM 子关键字

### 8.1 LOG 模式关键字

- `SEARCH`
- `MATCH`
- `DIFF`

### 8.2 LOG 子操作关键字

- `EXISTS`
- `ABSENT`
- `COUNT`
- `KV`
- `JSON`
- `EXTRACT`

### 8.3 SUM 相关高亮要点

`SUM` 适合高亮：

- `SUM`
- `COUNT`
- 比较运算符
- 可选通道前缀，如 `[0]cloudASRResult`

## 9. 环境变量与占位符

### 9.1 内置环境变量

以下变量需要在 `{...}` 形式中高亮：

- `WORKPATH`
- `ROOTPATH`
- `WORKSPACE`
- `BASEPATH`
- `LIBPATH`
- `CASEPATH`
- `LOGPATH`
- `SOCKETPATH`
- `CONFIGPATH`
- `CARPLAYCONFIG`
- `LCSCONFIG`
- `CASELIST`
- `PARAMETERIZEDATA`
- `SUITEID`
- `SUITENAME`
- `CASEID`
- `UUID`
- `TIMESTAMP`
- `NOW`

### 9.2 动态表达式

- `{EVAL:...}`

### 9.3 参数化占位符

- `${variable}`
- `${NANO_STEPS}`

## 10. timeout 与通道语法

### 10.1 timeout

以下模式需要高亮：

- `<timeout=0>`
- `<timeout=1>`
- `<timeout=2.5>`
- `<timeout=-1>`

### 10.2 通道前缀

以下模式需要高亮：

- `[0]`
- `[1]`
- `[2]`
- `[3]`

说明：

- 这是断言语法中的 channel 前缀，不是客户端标签。
- 常见于：

```dsl
[EXP]cloudASRResult [0]asr:你好 <timeout=3>
```

## 11. 常见模式字面量

这些词不是 DSL 主关键字，但适合辅助高亮：

### 11.1 常见语言字面量

- `cmn`
- `eng`
- `yue`

### 11.2 常见文件模式字面量

- `JSON`
- `LINE`
- `REPLACE`
- `TEXT`
- `CSV`

### 11.3 常见布尔与空值

- `true`
- `false`
- `True`
- `False`
- `None`
- `null`
- `NULL`

## 12. VR 配置项关键字

以下关键字建议在 `.mgo` 中作为独立词表高亮，主要用于：

- `[TSA]SETVRCONFIG config_name ...`
- `[SET]SETVRCONFIG config_name ...`
- `[NIS]SETVRCONFIG config_name ...`
- `[NSE]SETVRCONFIG config_name ...`
- `[TSA]GET_VR_CONFIG config_name`
- `[SET]GET_VR_CONFIG config_name`

来源：

- `src/core/Status/AIBSSessionStatus.py`
- `src/include/aibs_client_api.h`
- `src/include/aibs_client_nissan_api.h`
- `src/testsuite/NANO/client/AIBSClient.py`
- `src/testsuite/NANO/client/NissanAIBSClient.py`

高亮目标值如下：

- `DEVICE_INFO`
- `VR_OPTION`
- `SHOW_STYLE`
- `WAKEUP_ALIAS`
- `DIALOGUE_STYLE`
- `DIALOGUE_LANGUAGE`
- `SOUND_AREA_OPTION`
- `WAKEUP_KEYWORD_OPTION`
- `VOICE_WAKEUP_OPTION`
- `WAKEUP_ENABLE`
- `GET_WAKEUP_WORD`
- `SET_TTS_VOICE_TYPE`
- `MULTI_DIALOGUE`
- `EXPERIENCE_IMPROVENMENT`
- `PERSONAL_SENSITIVE_AUTHORIZATION`
- `VOICE_SENSITIVE_AUTHORIZATION`
- `ACTIVE_INTERACTION`
- `SRE_SENSITIVE_EMPOWER_OPTION`
- `SRE_FUNC_ENABLE_OPTION`
- `SERVER_CACHE_LANGUAGE`
- `GPT_ENABLE_OPTION`
- `SRE_MEMORY`
- `VEHICLE_MEMORY`

## 13. 运算符与结构符号

这些建议用通用规则高亮：

- `:`
- `;`
- `=`
- `==`
- `!=`
- `>`
- `<`
- `>=`
- `<=`
- `~`
- `!~`
- `@in`
- `@notin`
- `@i`

## 14. 字段名高亮策略

以下内容不建议做静态词表，而是使用通用规则高亮：

- `field:value` 中的 `field`
- `key=value` 中的 `key`

例如：

```dsl
[EXP]NLPResult skill:WEATHER;intention:QUERY <timeout=2>
[TSR]ASR_ACCURACY result={WORKPATH}/asr.csv ref=TestCase/ref/cmn_answer.csv
```

建议：

- `skill`、`intention` 使用“字段键”规则高亮。
- `result`、`ref` 使用“参数键”规则高亮。

## 15. Vim 语法文件实现建议

### 15.1 静态词表层

适合用 `syntax keyword` 或显式 alternation：

- 客户端名
- Fixture 关键字
- 各客户端命令
- `EXP` 断言类型
- `LOG` / `SUM` 子关键字
- 环境变量

### 15.2 通用规则层

适合用 `syntax match` / `syntax region`：

- `>>>` / `<<<`
- `${...}`
- `{...}`
- `{EVAL:...}`
- `<timeout=...>`
- `[0]`
- `field:value`
- `key=value`
- 字符串
- 数字
- 注释

## 16. 维护规则

以后若 DSL 真实实现有变更，应按以下顺序同步：

1. 更新 `config.py`
2. 更新 `conf/assert_key_value.yaml`
3. 更新本文档
4. 更新 `plugins/vim/syntax/nano_mgo.vim`

这样可以保证“代码实现 -> 高亮清单 -> Vim 语法”三者一致。
