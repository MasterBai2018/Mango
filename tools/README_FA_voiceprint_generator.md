# 声纹FA（False Acceptance）测试用例生成工具使用说明

## 功能概述

`generate_fa_voiceprint_cases.py` 是一个用于自动生成声纹FA（错误接受）测试用例的工具。该工具能够：

1. 根据指定的注册用户列表，生成对应的注册文件
2. 自动扫描音频文件，识别测试类型（唤醒/验证/登录）
3. 生成FA测试用例CSV文件，使用未注册用户进行验证
4. 期望验证结果为None（表示正确拒绝了未注册用户）
5. 支持多种唤醒词、音区和测试类型

## FA测试说明

- **FR（False Rejection）**：正向测试，注册用户验证应该通过
- **FA（False Acceptance）**：反向测试，未注册用户验证应该被拒绝
  - 如果验证结果是 **None**：表示Pass（正确拒绝了未注册用户）
  - 如果验证结果不是 **None**：表示NG（误检测，应该拒绝但通过了）

## 使用方法

### 基本语法

```bash
python3 tools/generate_fa_voiceprint_cases.py --users <注册用户列表>
```

### 参数说明

#### 必需参数
- `--users`: 注册用户列表，逗号分隔
  - 可用用户：`denggao`, `haijin`, `lianlian`, `mali`, `pengkun`, `qingfeng`, `tangjian`, `xinyu`, `yuehan`, `zhangchao`, `zhongjing`

#### 可选参数
- `--audio-path`: 音频文件根目录路径（默认：`TestAudio/vp_multi_channel`）
- `--output-dir`: 输出目录（默认：`TestCase/caselist/24MM/SDK/VoicePrint/vp_multi_performance/case_nano`）
- `--project-root`: 项目根目录路径（默认：脚本所在目录的父目录）

### 使用示例

#### 示例1：生成1个用户注册的FA测试用例

```bash
python3 tools/generate_fa_voiceprint_cases.py --users denggao
```

#### 示例2：生成2个用户注册的FA测试用例

```bash
python3 tools/generate_fa_voiceprint_cases.py --users denggao,haijin
```

#### 示例3：生成5个用户注册的FA测试用例

```bash
python3 tools/generate_fa_voiceprint_cases.py --users denggao,haijin,lianlian,mali,pengkun
```

#### 示例4：指定自定义路径

```bash
python3 tools/generate_fa_voiceprint_cases.py \
  --users denggao,haijin \
  --audio-path TestAudio/vp_multi_channel \
  --output-dir TestCase/caselist/24MM/SDK/VoicePrint/vp_multi_performance/case_nano
```

## 输出文件说明

### 生成的文件类型

1. **注册文件** (`enroll/<唤醒词目录>/<用户名>_<性别>.txt`)
   - 每个注册用户一个文件
   - 包含5条注册音频的路径（按固定顺序）
   - 格式：`音频路径\ttext:文本;channel:通道;user_id:用户ID;index:索引`

2. **FA测试用例文件** (`<测试类型>/<唤醒词目录>/fa/register<数量>_<用户列表>.csv`)
   - CSV格式的测试用例
   - 包含未注册用户的验证用例
   - 格式参照现有的FR测试用例格式

### 文件组织

- **注册文件路径**：
  - `TestCase/caselist/24MM/SDK/VoicePrint/vp_multi_performance/enroll/<唤醒词目录>/<用户名>_<性别>.txt`
  - 唤醒词目录：`xiaoyue`（你好小悦）、`fengtian`（你好丰田）、`lexus`（你好雷克萨斯）

- **测试用例路径**：
  - `TestCase/caselist/24MM/SDK/VoicePrint/vp_multi_performance/case_nano/<测试类型>/<唤醒词目录>/fa/register<数量>_<用户列表>.csv`
  - 测试类型：`sre_wakeup`（唤醒）、`sre_verify`（验证）、`sre_login`（登录）
  - 唤醒词目录：`nihaoxiaoyue`、`nihaofengtian`、`nihaolexus`

## 测试用例格式

### sre_wakeup（唤醒测试）

```csv
@delay: 0.8
@frame_size: 1280
@register_list: TestCase/caselist/24MM/SDK/VoicePrint/vp_multi_performance/enroll/xiaoyue/denggao_male.txt
@cartype: 2
audioPath	user_id
TestAudio/vp_multi_channel/haijin/zhu/10_你好小悦.wav	[0]user_id:haijin
```

### sre_verify（验证测试）

```csv
@delay: 0.8
@frame_size: 1280
@register_list: TestCase/caselist/24MM/SDK/VoicePrint/vp_multi_performance/enroll/xiaoyue/denggao_male.txt
@verifyChannel: 0
@cartype: 2
audioPath	verifyUser	verifyChannel	verifyText
TestAudio/vp_multi_channel/haijin/zhu/77_你好小悦我要登录声纹账号.wav	None	0	你好小悦，我要登录声纹账号
```

**注意**：`verifyUser` 字段为 `None`，表示期望验证失败（未注册用户应该被拒绝）

### sre_login（登录测试）

```csv
@delay: 0.8
@frame_size: 1280
@register_list: TestCase/caselist/24MM/SDK/VoicePrint/vp_multi_performance/enroll/xiaoyue/denggao_male.txt
@cartype: 2
audioPath	user_id
TestAudio/vp_multi_channel/haijin/zhu/65_你好小悦登录我的个人中心.wav	haijin
```

## 工作原理

### 用户选择逻辑

1. 从所有可用用户中排除注册用户
2. 剩余用户作为未注册用户，用于FA测试

### 音频文件选择逻辑

1. **注册音频**：每个用户按固定顺序选择5种类型的音频
   - 登录我的个人中心
   - 登录我的声纹记忆
   - 我要登录声纹账号
   - 我要登录个人中心
   - 声纹登录个人中心

2. **测试音频**：从未注册用户的音频中筛选
   - 匹配指定的唤醒词
   - 匹配测试类型（唤醒/验证/登录）
   - 覆盖所有音区（zhu/fu/left/right）

### 测试类型识别

- **sre_wakeup**：纯唤醒词音频（如"你好小悦.wav"）
- **sre_verify**：包含唤醒词+登录相关文本的音频
- **sre_login**：包含登录相关文本的音频（可能没有唤醒词前缀）

## 注意事项

1. **音频文件路径**：确保 `TestAudio/vp_multi_channel` 目录下存在所有用户的音频文件
2. **用户性别**：脚本会根据用户名自动判断性别（male/female）
3. **多用户注册**：如果指定多个注册用户，注册文件列表会用逗号分隔
4. **文件覆盖**：如果注册文件已存在，会被覆盖
5. **空用例**：如果某个测试类型没有匹配的音频文件，会跳过生成该文件

## 常见问题

### Q: 如何知道哪些用户可用？

A: 可用用户列表：`denggao`, `haijin`, `lianlian`, `mali`, `pengkun`, `qingfeng`, `tangjian`, `xinyu`, `yuehan`, `zhangchao`, `zhongjing`

### Q: 生成的测试用例中verifyUser为什么是None？

A: 这是FA测试的特点。FA测试使用未注册用户进行验证，期望结果是None（验证失败），表示系统正确拒绝了未注册用户。如果验证结果不是None，说明系统误接受了未注册用户，这是NG的情况。

### Q: 如何生成多个注册用户组合的测试用例？

A: 使用逗号分隔多个用户名，例如：`--users denggao,haijin,lianlian`

### Q: 注册文件中的5条音频是如何选择的？

A: 按照固定顺序选择5种类型的音频，优先从zhu音区选择，如果zhu音区没有，则从其他音区选择。
