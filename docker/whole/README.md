# 🥭 Mango Docker 部署指南

本文档介绍如何构建和使用Mango自动化测试框架的Docker镜像。

## 📋 目录结构

```
docker/
├── build_image.sh  # 基础镜像构建脚本（mango:vX.Y.Z）
├── build_whole.sh  # 整体镜像构建脚本（mango-app:vX.Y.Z）
└── whole/
    ├── Dockerfile
    ├── Run_Docker.py
    └── README.md
```

## 🏗️ 镜像架构

```
┌─────────────────────────────────────────────────────────────┐
│  mango-app:v3.6.0 (新镜像)                                  │
├─────────────────────────────────────────────────────────────┤
│  基础层: mango:v3.6.0                                       │
│  ├── Python 3.x 运行环境                                    │
│  ├── pytest, allure-pytest, loguru, psutil 等依赖           │
│  └── 系统工具 (tini, gdb等)                                 │
├─────────────────────────────────────────────────────────────┤
│  应用层: Mango测试框架代码                                   │
│  ├── Run_Mongo.py     # 入口脚本                            │
│  ├── conftest.py      # pytest配置                          │
│  ├── pytest.ini       # pytest参数配置                       │
│  ├── conf/            # 框架配置文件                         │
│  ├── src/             # 核心源代码                           │
│  ├── tools/           # 工具脚本                             │
│  └── plugins/         # 插件目录（Allure/Vim/VSCode等）      │
├─────────────────────────────────────────────────────────────┤
│  挂载点 (用户提供):                                          │
│  ├── /mango/lib           # C++库文件 (rw)                  │
│  ├── /mango/workspace     # 测试结果 (rw)                   │
│  ├── /mango/TestAudio     # 测试音频 (ro)                   │
│  ├── /mango/TestCase      # 测试用例 (ro)                   │
│  └── /mango/TestResource  # 模型资源 (rw)                   │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 快速开始

### 1. 构建镜像

```bash
# 在项目根目录执行
cd /path/to/mango
chmod +x docker/build_image.sh docker/build_whole.sh
./docker/build_image.sh v3.6.0
./docker/build_whole.sh v3.6.0
```

### 2. 准备挂载目录

创建以下目录结构（可以在任意位置）:

```bash
# 示例: 在/data1/mango_data目录下创建
mkdir -p /data1/mango_data/{lib,workspace,TestAudio,TestCase,TestResource}

# 目录说明:
# lib/          - 放置C++动态库 (如: libAIBSClientDynamic.so)
# workspace/    - 测试结果输出目录 (自动生成)
# TestAudio/    - 测试音频文件
# TestCase/     - DSL测试用例文件 (.mgo)
# TestResource/ - 模型资源文件
```

### 3. 配置运行脚本

将 `docker/Run_Docker.py` 复制到任意目录，并修改配置:

```python
# 修改 MOUNT_CONFIG 中的路径为你的实际路径
MOUNT_CONFIG = {
    "lib": "/data1/mango_data/lib",
    "workspace": "/data1/mango_data/workspace",
    "TestAudio": "/data1/mango_data/TestAudio",
    "TestCase": "/data1/mango_data/TestCase",
    "TestResource": "/data1/mango_data/TestResource",
}
```

### 4. 运行测试

```bash
# 查看帮助
python3 Run_Docker.py --help

# 运行NANO测试套件
python3 Run_Docker.py -f NANO \
    -C TestCase/conf/decoder.conf \
    -a TestCase/caselist/test.mgo \
    -b 24mm

# 多进程并发运行
python3 Run_Docker.py -f NANO \
    -C TestCase/conf/decoder.conf \
    -a TestCase/caselist/test.mgo \
    -b 24mm \
    -n 5

# 数据驱动测试
python3 Run_Docker.py -f NANO \
    -C TestCase/conf/decoder.conf \
    -a TestCase/caselist/test.mgo \
    -P TestCase/data/test_data.csv \
    -b 24mm
```

## 📁 目录挂载说明

| 目录 | 容器路径 | 权限 | 说明 |
|------|----------|------|------|
| `lib` | `/mango/lib` | 读写(rw) | C++动态库文件，研发会随时替换 |
| `workspace` | `/mango/workspace` | 读写(rw) | 测试结果、日志、Allure报告输出 |
| `TestAudio` | `/mango/TestAudio` | 只读(ro) | 测试音频文件 |
| `TestCase` | `/mango/TestCase` | 只读(ro) | DSL测试用例文件(.mgo)和配置 |
| `TestResource` | `/mango/TestResource` | 读写(rw) | 语音模型资源，研发会修改 |

## 🔧 高级配置

### 额外挂载目录

如果需要挂载额外的目录（如共享数据盘），修改 `Run_Docker.py` 中的 `EXTRA_MOUNTS`:

```python
EXTRA_MOUNTS = [
    "/data:/data:ro",
    "/data1:/data1:ro",
    "/shared/audio:/mango/extra_audio:ro",
]
```

### 自定义Docker镜像名称

修改 `Run_Docker.py` 中的 `DOCKER_IMAGE`:

```python
DOCKER_IMAGE = "my-registry/mango-app:v3.6.0"
```

### GDB调试模式

运行脚本已默认启用GDB调试支持 (`--cap-add=SYS_PTRACE`):

```bash
python3 Run_Docker.py -f NANO -g \
    -C TestCase/conf/decoder.conf \
    -a TestCase/caselist/test.mgo \
    -b 24mm
```

## 🐛 常见问题

### 1. 权限问题

如果遇到文件权限问题，确保挂载目录对当前用户可读写:

```bash
# 检查当前用户ID
id

# 确保目录权限正确
chmod -R 755 /data1/mango_data
chown -R $(id -u):$(id -g) /data1/mango_data/workspace
```

### 2. Docker命令未找到

确保Docker已安装并在PATH中:

```bash
# 检查Docker版本
docker --version

# 检查Docker服务状态
systemctl status docker
```

### 3. 基础镜像不存在

确保 `mango:v3.6.0` 基础镜像存在:

```bash
# 查看本地镜像
docker images | grep mango

# 如果不存在，需要先构建或拉取基础镜像
```

### 4. 容器内路径问题

测试用例和配置文件中的路径应该使用**容器内路径**:

```bash
# 正确 (使用容器内路径)
python3 Run_Docker.py -f NANO \
    -C TestCase/conf/decoder.conf \
    -a TestCase/caselist/test.mgo

# 错误 (使用宿主机路径)
python3 Run_Docker.py -f NANO \
    -C /data1/mango_data/TestCase/conf/decoder.conf \
    -a /data1/mango_data/TestCase/caselist/test.mgo
```

## 📊 测试结果

测试完成后，结果保存在 `workspace` 目录:

```
workspace/
├── solution_xxx/           # 测试解决方案目录
│   ├── SCENE/              # 场景目录
│   │   └── SUITE/          # Suite目录
│   │       ├── log/        # 日志文件
│   │       └── report/     # Allure报告数据
│   └── ...
└── Mongo.log               # 主日志文件
```

查看Allure报告:

```bash
# 安装allure命令行工具后
allure serve /data1/mango_data/workspace/solution_xxx/SCENE/SUITE/report/
```

## 📞 技术支持

- **开发者**: huidong.bai
- **邮箱**: MasterBai2018@outlook.com
- **项目版本**: v3.6.0

---

**Mango测试框架 - 让语音SDK测试更简单、更可靠、更高效！**
