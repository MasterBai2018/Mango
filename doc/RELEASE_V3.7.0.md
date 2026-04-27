# Mango 自动化测试框架 V3.7.0 版本发布通知

---

**发版日期**: 2026年3月11日  
**版本号**: v3.7.0  
**维护者**: huidong.bai (MasterBai2018@outlook.com)

---

## 📢 版本概述

Mango V3.7.0 是一个功能扩展和架构升级的重要版本。本次更新新增了**PISA大模型客户端**、**ECNR降噪引擎客户端**、**TSR Suite级统计报告体系**等核心特性，同时优化了断言逻辑、回调机制、并发输出等关键功能，并修复了多个已知问题，进一步提升了框架的测试覆盖能力和易用性。

---

## ✨ 核心新功能

### 🛠️ 1. Allure报告增强
- **新增Mango统计页** 用于统计Solution中的每个Define以及每个Suite的运行Case，通过数，失败数，总数，通过率
- **新增TSR指令的报告呈现** 现在，TSR指令，将直观的报告呈现在Jenkins的Allure报告中。
- 你可以通过Allure报告-->Mango 统计-->测试统计，看出整个Solution运行的结果。
- 你可以通过Allure报告-->Mango 统计-->Suite 报告，看出某些需要Suite级别的统计报告，例如时延测试。

### 🎯 2. 运行速度增强
- **动态并发扩容**，支持运行时动态调整并发数以提高Mango运行效率
- 现在，SDK/NLU回归，降低至30分钟；

### 🎯 3. 新增PISA大模型客户端（PIS）
- **新增PISALLMClient**，支持PISA大模型全双工WebSocket协议
- 支持CREATE、START、STOP、FREE、DATA、WAIT_UNTIL、UPDATE等指令
- 支持异步音频推流、流控阻塞、session.update等能力
- 协议参考：`PISA_REALTIME_API_PROTOCOL.md`

### 🔧 4. 新增ECNR降噪引擎客户端（ENR）
- **新增ECNRClient**，支持ECNR降噪引擎完整测试能力
- 支持CREATE、START、STOP、FREE、SET_WORKMODE、DATA等指令
- 支持PNR参数配置、版本查询、多通道音频处理
- **ECNR动态库重定向**，支持灵活配置ECNR库路径

### 📊 5. TSR Suite级统计报告体系
- **TSR客户端重构**，采用装饰器自动注册机制，易于扩展
- **新增6大统计指令**：
  - `ASR_ACCURACY` - ASR准确率计算（句准率、字准率等）
  - `ASR_LANGUAGE` - ASR语种识别正确率
  - `DELAY` - ASR实时/最终结果时延分析
  - `WAKEUP_ACCURACY` - 唤醒词FA/FR准确率计算
  - `VAD_ACCURACY` - VAD FA/FR检测率计算
  - `VAD_PRECISION` - VAD时间边界精度分析
- **Allure报告集成**，TSR统计结果支持Allure网页展示，每一个TSR指令，将生成独一无二的测试报告，提供Allure展示。
- **TSR指令优化**，CSV文件头支持`@`参数（如`@DELAY: 0`）

### 🛠️ 6. 测试工具增强
- **新增日志转NANOCase工具**（log2mgo_converter.py），支持将日志转换为mgo用例
- **新增RT/MEM内存曲线绘制工具**（plot_mem_rt.py），支持绘制内存和RT曲线
- **优化asr_language工具**，标准化断言语种代码
- **更新yaml2mgo工具**，支持kit分支的Case与新的NANO Case转换
- **GDB调试工具**增加`-b`指令，支持静默查看崩溃信息

### 🚀 7. 其他新功能
- **动态LCS订阅脚本**，支持LCS订阅脚本运行时更新
- **回调结果session级写入**，支持将所有回调结果写入callback.jsonl文件，用于后续整体断言操作
- **修改CaseID为CaseIndex**，Allure报告中呈现的Case名更清晰

---

## 🚀 功能优化

### 断言系统优化
- **添加同一时间段只保留一个断言类型**，避免断言冲突
- **添加操作符`&&`**，支持复合断言条件
- **当预期是列表空值时**，修复断言显示错误
- **过滤清屏理解结果的断言**，减少误报
- **修改音区隔离断言**，提升断言准确性

### 回调与数据处理优化
- **调整callback中的音频路径获取方式**
- **墓碑文件生成txt**，便于结果追踪
- **调整时间戳相关问题**，提升时间戳一致性
- **减少打印阻塞**，修改SpeechEngineWakeup信号的start和end的json路径

### 报告与输出优化
- **调整Allure报告展示的易读性**
- **调整并发时mango的终端输出逻辑**，采用带缓冲的刷新方式
- **修改delay统计工具的时延计算方式**及报告输出
- **调整VAD结果分析工具**
- **更新唤醒率统计工具**

### 项目支持优化
- **800D项目**：修改800D LCS地址，添加800D项目TTS文言
- **日产项目**：更新nano车参修改，修改日产客户端传的车参默认为0，添加日产断言Key
- **Docker**：更新Docker容器中的DNS解析问题

### 其他优化
- **超时逻辑修改**，优化断言超时处理
- **添加日志查询的复合搜索**，增强日志断言能力
- **Jenkins日产车参**，修复报错问题

---

## 🐛 问题修复

### 关键BUG修复
- ✅ **修复data送音频数据切片时由于浮点类型精度问题导致音频数据错乱的BUG**
- ✅ **修复保存唤醒结果错误的问题**
- ✅ **修复Jenkins的日产车参报错的问题**
- ✅ **修复在NANO中执行原生Command时shell不一致导致的报错**
- ✅ **解决Redmine BUG: 134536**

---

## 📚 文档更新

- ✅ **新增TSR.md**，完整TSR客户端使用文档（1000+行）
- ✅ **新增NLU测试用例编写指南**
- ✅ **新增PISA_REALTIME_API_PROTOCOL.md**，PISA实时API协议说明
- ✅ **更新COMMAND.md**，新增ENV、ECNR、PIS等指令说明
- ✅ **更新EXPECT.md**，完善断言配置
- ✅ **更新LOG_ASSERTION.md**

---

## 🔢 版本统计

### 功能统计
- **新增客户端类型**: 2个（PIS、ENR）
- **新增DSL指令**: SYS ENV、TSR 6大统计指令、PIS/ENR完整指令集
- **新增测试工具**: 2个（log2mgo、plot_mem_rt）
- **TSR体系**: 从5个指令重构为6大专业统计指令

### 代码质量
- **修复BUG**: 5+个
- **功能优化**: 20+项
- **文档更新**: 6份

---

## 📥 获取方式

### Git仓库
```bash
git clone git@git.pachira.cn:asr/mango.git
git checkout v3.7.0
```

### 依赖要求
- Python 3.6+
- pytest 6.0+
- loguru, psutil, allure-pytest
- websockets（PISA客户端）
- Linux (CentOS 7+)

---

## 📖 使用指南

### 快速开始
```bash
# 基础运行
python3 Run_Mongo.py -f NANO \
  -C TestCase/conf/decoder.conf \
  -a TestCase/caselist/nano.mgo \
  -b 24mm

# 使用TSR统计指令（在SUITE_TEARDOWN中）
[TSR]ASR_ACCURACY result={WORKPATH}/asr.csv ref=TestCase/ref/answer.csv output={WORKPATH}/asr_report.xlsx
[TSR]DELAY ref=label.txt result={WORKPATH}/callback.jsonl type=PSTTASRResult output={WORKPATH}/delay.xlsx
[TSR]WAKEUP_ACCURACY result={WORKPATH}/wakeup.csv ref=TestCase/ref/wakeup_ref.csv

# 使用SYS ENV设置环境变量
[SYS]ENV ro.vendor-iauto.unityversion=313
[SYS]PULL AIBSServer cmn
```

### 详细文档
- **框架文档**: `PROJECT.md`
- **NANO文档**: `src/testsuite/NANO/doc/README.md`
- **DSL指令手册**: `src/testsuite/NANO/doc/COMMAND.md`
- **TSR文档**: `src/testsuite/NANO/doc/TSR.md`
- **PISA协议**: `PISA_REALTIME_API_PROTOCOL.md`

---

## ⚠️ 升级注意事项

### 兼容性说明
- **向后兼容**: V3.7.0完全兼容V3.6.0及之前版本的测试用例
- **TSR变更**: 原TSR指令（DELAY_TEST、WAKEUP_FA等）已重构为新的统计指令体系，请参考TSR.md迁移
- **配置变更**: 无破坏性配置变更

### 建议升级步骤
1. 备份现有测试用例和配置文件
2. 更新代码到V3.7.0版本
3. 验证现有测试用例运行正常
4. 逐步使用新功能（PISA客户端、ECNR客户端、TSR统计等）

---

## 📞 技术支持

如有问题或建议，请联系：
- **开发者**: huidong.bai
- **邮箱**: MasterBai2018@outlook.com
- **项目地址**: git@git.pachira.cn:asr/mango.git

---

**Mango测试框架 - 让语音SDK测试更简单、更可靠、更高效！**

*基于企业级需求设计，专为语音识别领域量身定制的自动化测试解决方案*
