# Mango 自动化测试框架 V3.7.2 版本发布通知

---

**发版日期**: 2026年4月20日  
**版本号**: v3.7.2  
**维护者**: huidong.bai (MasterBai2018@outlook.com)

---

## 📢 版本概述

Mango V3.7.2 是基于 V3.7.1 之后 `develop` 分支增量提交整理的稳定发布版本。本次版本重点聚焦在 **PISA/TSS/ECNR 客户端能力增强**、**PSTT/ASR 统计工具兼容性优化**、**solution 并发调度优化** 以及 **编辑器插件与文档可维护性提升**，用于进一步提升回归测试效率与结果一致性。

---

## ✨ 核心更新

### 1) 客户端与协议能力增强
- 增强 PISA 客户端回调信息能力，补充时间字段与 `event_id` 关键信息
- 新增/优化 PISA `final_done` 相关协议流程，提升会话结束阶段稳定性
- TSS 客户端支持非交织多声道音频与多声道送音场景
- ECNR 客户端修复尾帧补零处理，提升音频边界场景稳定性

### 2) 统计与断言能力优化
- 新增 `PSTT_ACCURACY` 指令并持续优化，支持多维度批跑统计分析
- 修复 `ASR_ACCURACY` 工具在 `ref` 行注释场景下的兼容性问题
- 优化唤醒率统计与报告字段处理，减少异常样本对整体统计结果的干扰
- 新增引擎版本断言能力，支持 NANO/ECNR/CarPlay 等场景版本校验

### 3) 运行与并发优化
- 优化 `solution` 并发调度策略，支持 ONLINE 槽位提前释放和 OFFLINE 动态抢占
- 支持 `solution` 文件按 Case 级别单独配置并发，提升复杂回归场景执行效率
- 增强运行过程的日志与故障定位信息输出（含容器 tcpdump 路径与 core 信息整理）

### 4) 文档与开发体验提升
- 补充并更新工具类与接口说明文档，降低使用和维护成本
- 新增并完善 VSCode/Vim 语法高亮插件与说明文档

---

## 🐛 重点问题修复

- ✅ 修复 TSS 客户端在 `block` 场景下 STOP 阻塞耗时异常的问题
- ✅ 修复 ECNR 客户端尾帧处理兼容性问题
- ✅ 修复 `ASR_ACCURACY` 在注释行输入下的解析稳定性问题
- ✅ 修复多项目场景下 `solution` 并发配置与调度细节问题

---

## 📚 文档更新

- `README.md`
- `doc/Mango_测试使用说明.md`
- `src/testsuite/NANO/doc/COMMAND.md`
- `src/testsuite/NANO/doc/TSR.md`
- `doc/RELEASE_V3.7.2.md`

---

## 📥 获取方式

```bash
git clone git@git.pachira.cn:asr/mango.git
git checkout v3.7.2
```

---

## ⚠️ 升级建议

1. 涉及 PISA/TSS/ECNR 的项目建议先执行一次端到端冒烟回归，确认协议与超时参数配置
2. 使用 `PSTT_ACCURACY` 与 `ASR_ACCURACY` 的项目建议校验 `ref` 文件格式和注释规范
3. 使用 `solution` 并发能力的项目建议重新核对 ONLINE/OFFLINE/Case 级并发配置

---

## 📞 技术支持

如有问题或建议，请联系：
- **开发者**: huidong.bai
- **邮箱**: MasterBai2018@outlook.com
- **项目地址**: git@git.pachira.cn:asr/mango.git

---

**Mango测试框架 - 让语音SDK测试更简单、更可靠、更高效！**
