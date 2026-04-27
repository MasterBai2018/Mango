# HawkVAD - 语音活动检测工具

HawkVAD 是一个高性能的语音活动检测（Voice Activity Detection, VAD）命令行工具，用于识别音频文件中的语音段和静音段。

## 功能特性

- ✅ **多种运行模式**：支持单个文件、文件列表、目录批量处理
- ✅ **并发处理**：支持多进程并发处理文件列表，显著提升处理速度
- ✅ **配置文件**：支持通过配置文件管理参数，简化命令行操作
- ✅ **灵活输出**：支持自定义输出目录，自动创建不存在的目录
- ✅ **详细统计**：输出语音/静音时长、处理时间、实时率等统计信息
- ✅ **多种格式**：支持 WAV 和 PCM 格式，支持 8kHz 和 16kHz 采样率
- ✅ **参数丰富**：支持多种 VAD 策略和参数配置

## 编译

```bash
cd src/vad/bin
make
```

## 快速开始

### 基本用法

```bash
# 处理单个音频文件
./hawkvad --caselist audio.wav --run_mode 0

# 处理文件列表
./hawkvad --caselist filelist.txt --run_mode 1

# 递归处理目录
./hawkvad --caselist /path/to/audio_dir --run_mode 2
```

### 使用配置文件

```bash
# 使用配置文件（推荐）
./hawkvad --config vad.conf
```

## 运行模式

| run_mode | 说明 | 示例 |
|----------|------|------|
| 0 | 单个音频文件 | `--caselist audio.wav --run_mode 0` |
| 1 | 文件列表 | `--caselist list.txt --run_mode 1` |
| 2 | 目录（递归） | `--caselist /audio/dir --run_mode 2` |

## 主要参数

### 必需参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `--caselist` | 输入路径（文件/列表/目录） | `--caselist test.wav` |
| `--run_mode` | 运行模式（0/1/2） | `--run_mode 1` |

### 常用参数

| 参数 | 说明 | 默认值 | 示例 |
|------|------|--------|------|
| `--config` | 配置文件路径 | - | `--config vad.conf` |
| `--jobs` | 并发进程数 | 1 | `--jobs 10` |
| `--output` | 输出目录 | 当前目录 | `--output ./results` |
| `--sample-rate` | 采样率（8000/16000） | 16000 | `--sample-rate 16000` |
| `--strategy` | VAD策略（0:low/1:medium/2:high） | 0 | `--strategy 1` |
| `--level` | VAD级别（0/1/2） | 0 | `--level 0` |
| `--snslist` | SNS输出文件名 | sns.list | `--snslist result.list` |

### VAD 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--silence` | 静音转换长度（ms） | 400 |
| `--speech` | 语音转换长度（ms） | 70 |
| `--energy` | 能量阈值 | 100 |
| `--left` | 前置静音长度（ms） | 0 |
| `--right` | 后置静音长度（ms） | 0 |
| `--peak-threshold` | 峰值概率阈值（0-1） | 0.1 |
| `--min-speech-len` | 最小语音长度 | 0 |
| `--low-power` | 低功耗模式 | 0 |

### 其他参数

| 参数 | 说明 |
|------|------|
| `--resource` | VAD模型资源路径 |
| `--mode` | VAD任务类型（0:ASR/1:WAKEUP） |
| `--append` | 追加模式（不覆盖输出文件） |
| `--type` | 文件类型（0:pcm&wave/1:wave/2:pcm） |
| `--help` | 显示帮助信息 |
| `--version` | 显示版本信息 |

## 配置文件

配置文件使用 `key=value` 格式，支持注释。

### 配置文件示例 (vad.conf)

```conf
# VAD 基本配置
caselist=/data/audio/test.list
run_mode=1
jobs=10

# VAD 参数
sample-rate=16000
strategy=1
level=0
silence=400
speech=70
energy=100

# 输出配置
output=./results
snslist=vad_result.list

# 高级参数
peak-threshold=0.1
low-power=0
min-speech-len=0
```

### 使用配置文件

```bash
./hawkvad --config vad.conf
```

**注意**：使用 `--config` 时，命令行的其他参数会被忽略，所有配置从配置文件读取。

## 并发处理

处理大量文件时，可以使用 `--jobs` 参数启用并发处理：

```bash
# 使用 10 个进程并发处理
./hawkvad --caselist large_list.txt --run_mode 1 --jobs 10 --output ./output
```

**并发特性**：
- 仅在文件列表模式（`--run_mode 1`）下生效
- 实际进程数 = min(指定并发数, 文件总数)
- 自动负载均衡，每个进程处理的文件数差异不超过 1
- 子进程结果自动合并为最终输出文件

## 输出文件

### 输出文件说明

所有输出文件都会保存在 `--output` 指定的目录中（如果指定）。

| 文件名 | 说明 | 格式 |
|--------|------|------|
| `sns.list` | VAD 结果（语音/静音段） | `音频路径 00h_S/00h_N 开始时间 结束时间` |
| `delay.log` | 延迟信息 | `音频路径 send_data:X receive_speech_start:Y delay:Z` |
| `vad.info` | 每个文件的语音时长 | `音频路径 开始时间 结束时间 时长` |
| `vad_debug.log` | 调试日志 | - |

### 输出格式示例

**sns.list**:
```
audio1.wav 00h_N 0.00 2.57
audio1.wav 00h_S 2.57 3.10
audio1.wav 00h_N 3.10 5.33
audio2.wav 00h_S 0.00 1.20
```

**delay.log**:
```
audio1.wav send_data:2.58s receive_speech_start:2.57s delay:0.01s
```

**vad.info**:
```
audio1.wav 2.57 3.10 0.53
audio2.wav 0.00 1.20 1.20
```

## 使用示例

### 示例 1：处理单个文件

```bash
./hawkvad \
  --caselist test.wav \
  --run_mode 0 \
  --sample-rate 16000 \
  --strategy 1 \
  --output ./output
```

### 示例 2：批量处理文件列表

创建文件列表 `files.txt`：
```
/data/audio1.wav
/data/audio2.wav
/data/audio3.wav
```

运行：
```bash
./hawkvad \
  --caselist files.txt \
  --run_mode 1 \
  --output ./results
```

### 示例 3：并发处理大量文件

```bash
./hawkvad \
  --caselist large_list.txt \
  --run_mode 1 \
  --jobs 20 \
  --sample-rate 16000 \
  --strategy 1 \
  --output ./batch_results
```

### 示例 4：使用配置文件

创建配置文件 `production.conf`：
```conf
caselist=/data/production_audio.list
run_mode=1
jobs=16
sample-rate=16000
strategy=1
level=0
output=/data/results
snslist=production_vad.list
```

运行：
```bash
./hawkvad --config production.conf
```

### 示例 5：递归处理目录

```bash
./hawkvad \
  --caselist /data/audio_collection \
  --run_mode 2 \
  --output ./dir_results
```

## 统计信息

处理完成后，工具会输出统计信息：

```
silence:12.50000,speech:8.30000 
total_wav_time:20.80000,total_run_time:0.45000 rt:0.021635
```

- **silence**: 总静音时长（秒）
- **speech**: 总语音时长（秒）
- **total_wav_time**: 总音频时长（秒）
- **total_run_time**: 总处理时间（秒）
- **rt**: 实时率（处理时间/音频时长，越小越快）

## 性能优化建议

1. **使用并发处理**：处理大量文件时，设置合理的 `--jobs` 参数
   ```bash
   --jobs 10  # CPU 核心数的 1-2 倍
   ```

2. **合理设置输出目录**：避免频繁创建目录
   ```bash
   --output /fast_disk/results
   ```

3. **使用配置文件**：避免重复输入参数
   ```bash
   --config optimized.conf
   ```

4. **调整VAD参数**：根据实际场景调优
   - 高噪声环境：增加 `--energy` 阈值
   - 快速语音：减小 `--speech` 值
   - 长停顿：增加 `--silence` 值

## 故障排查

### 常见问题

**Q: 提示 "错误: 必须指定 --caselist 参数"**  
A: 确保命令行包含 `--caselist` 和 `--run_mode` 参数。

**Q: 提示 "sample rate is invalid"**  
A: 采样率只支持 8000 或 16000，检查 `--sample-rate` 参数。

**Q: 输出目录创建失败**  
A: 检查目录路径权限，确保有写入权限。

**Q: 并发处理没有加速**  
A: 确保使用文件列表模式（`--run_mode 1`），`--jobs` 只在该模式下生效。

**Q: 配置文件解析错误**  
A: 检查配置文件格式，确保使用 `key=value` 格式，等号两边可有空格。

## 文件格式要求

### 文件列表格式

文件列表（`--run_mode 1`）每行一个文件路径：

```
# 这是注释
/data/audio1.wav
/data/audio2.wav
/data/audio3.wav
```

- 支持 `#` 开头的注释行
- 支持空行
- 自动去除行尾的换行符（兼容 Windows 和 Linux）
- 文件路径可以是相对路径或绝对路径

### 音频格式

- **支持格式**：WAV, PCM
- **采样率**：8000 Hz 或 16000 Hz
- **声道**：单声道或立体声
- **位深**：16-bit

## 版本信息

查看版本：
```bash
./hawkvad --version
```

查看帮助：
```bash
./hawkvad --help
```

## 项目结构

```
HawkServer/
├── src/vad/bin/
│   ├── hawkvad.cpp          # 主程序源码
│   ├── hawkvad_cut.cpp      # 切分工具源码
│   └── Makefile             # 编译文件
├── model/                    # VAD 模型文件
└── README.md                 # 本文件
```

## 技术特点

- **多进程架构**：使用 fork() 实现真正的并发处理
- **内存优化**：文件列表一次性加载到内存，避免重复 I/O
- **结果合并**：子进程独立输出，主进程自动合并并清理临时文件
- **资源管理**：使用 RAII 和早期返回模式，确保无内存泄漏
- **跨平台兼容**：兼容 Linux 和 Windows 格式的文本文件

## 许可证

请参考项目许可证文件。

## 联系方式

如有问题或建议，请联系开发团队。

---

**Happy VAD Processing! 🎤✨**

