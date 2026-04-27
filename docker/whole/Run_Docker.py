#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================
# Mango 自动化测试框架 - Docker运行脚本
# ============================================================
# 功能: 一键启动Mango测试框架Docker容器
# 用法: python3 Run_Docker.py [mango参数...]
# 示例: python3 Run_Docker.py -f NANO -C config.conf -a test.mgo -b 24mm
# ============================================================
# @Time    : 2025/01/21
# @Author  : huidong.bai
# @File    : Run_Docker.py
# ============================================================

import os
import sys
import subprocess
import uuid

# ============================================================
# 🔧 用户配置区域 - 请根据实际环境修改以下路径
# ============================================================

# Docker镜像名称
DOCKER_IMAGE = "mango-app:v3.6.0"

# 挂载路径配置 (请修改为你的实际路径)
# 格式: "宿主机路径" -> 容器内路径
MOUNT_CONFIG = {
    # C++库文件目录 (读写，会随时替换库文件)
    "lib": "/data1/baihuidong/mango_data/lib",
    
    # 测试结果输出目录 (读写，保存测试报告和日志)
    "workspace": "/data1/baihuidong/mango_data/workspace",
    
    # 测试音频文件目录 (只读，研发提供的音频文件)
    "TestAudio": "/data1/baihuidong/mango_data/TestAudio",
    
    # 测试用例目录 (只读，DSL测试用例文件)
    "TestCase": "/data1/baihuidong/mango_data/TestCase",
    
    # 模型资源目录 (读写，研发会修改这些资源)
    "TestResource": "/data1/baihuidong/mango_data/TestResource",
}

# 额外的只读挂载路径 (可选，用于挂载共享数据盘等)
# 格式: ["宿主机路径:容器路径:权限", ...]
EXTRA_MOUNTS = [
    # "/data:/data:ro",
    # "/data1:/data1:ro",
    # "/data2:/data2:ro",
]

# ============================================================
# 🚀 以下代码无需修改
# ============================================================

def validate_paths():
    """
    验证配置的挂载路径是否存在
    """
    missing_paths = []
    for name, path in MOUNT_CONFIG.items():
        if not os.path.exists(path):
            missing_paths.append(f"  - {name}: {path}")
    
    if missing_paths:
        print("❌ 错误: 以下挂载路径不存在，请检查配置或创建目录:")
        print("\n".join(missing_paths))
        print("\n💡 提示: 请修改脚本顶部的 MOUNT_CONFIG 配置，或创建这些目录")
        return False
    return True


def get_mount_permission(name):
    """
    根据目录名称返回挂载权限
    """
    # 只读目录
    readonly_dirs = {"TestAudio", "TestCase"}
    return "ro" if name in readonly_dirs else "rw"


def build_docker_command():
    """
    构建Docker运行命令
    """
    # 生成唯一容器名称
    container_name = f"mango_{str(uuid.uuid4())[:8].upper()}"
    
    # 基础Docker命令
    docker_cmd = [
        'docker', 'run', '--rm',
        '--init',  # 使用tini作为PID 1，确保信号正确转发
        '--name', container_name,
        
        # 用户映射 (使用当前用户权限)
        '--user', f'{os.getuid()}:{os.getgid()}',
        
        # 系统限制
        '--ulimit', 'nofile=65535:65535',
        '--ulimit', 'nproc=2048:4096',
        
        # GDB调试支持
        '--cap-add=SYS_PTRACE',
        
        # 环境变量
        '-e', 'TZ=Asia/Shanghai',
        '-e', f'DOCKER_CONTAINER_NAME={container_name}',
        
        # 用户信息映射 (解决权限问题)
        '-v', '/etc/passwd:/etc/passwd:ro',
        '-v', '/etc/group:/etc/group:ro',
    ]
    
    # 添加TTY支持
    if sys.stdout.isatty():
        docker_cmd.extend(['-it'])
    
    # 添加核心挂载目录
    for name, host_path in MOUNT_CONFIG.items():
        container_path = f"/mango/{name}"
        permission = get_mount_permission(name)
        docker_cmd.extend(['-v', f'{host_path}:{container_path}:{permission}'])
    
    # 添加额外挂载
    for mount in EXTRA_MOUNTS:
        if mount.strip():
            docker_cmd.extend(['-v', mount])
    
    # 添加镜像名称
    docker_cmd.append(DOCKER_IMAGE)
    
    # 添加传递给mango的参数
    docker_cmd.extend(sys.argv[1:])
    
    # 添加docker标记
    docker_cmd.append('-docker')
    
    return docker_cmd, container_name


def print_banner():
    """
    打印启动信息
    """
    print("=" * 60)
    print("🥭 Mango 自动化测试框架 - Docker版")
    print("=" * 60)
    print(f"📦 镜像: {DOCKER_IMAGE}")
    print("📂 挂载配置:")
    for name, path in MOUNT_CONFIG.items():
        perm = get_mount_permission(name)
        print(f"   {name:15} -> {path} [{perm}]")
    print("=" * 60)


def print_help():
    """
    打印帮助信息
    """
    print("""
🥭 Mango Docker 运行脚本

用法:
    python3 Run_Docker.py [mango参数...]

示例:
    # 查看帮助
    python3 Run_Docker.py --help
    
    # 运行NANO测试套件
    python3 Run_Docker.py -f NANO -C TestCase/conf/decoder.conf -a TestCase/caselist/test.mgo -b 24mm
    
    # 多进程运行
    python3 Run_Docker.py -f NANO -C config.conf -a test.mgo -b 24mm -n 5
    
    # 数据驱动测试
    python3 Run_Docker.py -f NANO -C config.conf -a test.mgo -P data.csv -b 24mm

配置说明:
    请修改脚本顶部的 MOUNT_CONFIG 字典，设置你的实际路径:
    - lib:          C++库文件目录
    - workspace:    测试结果输出目录  
    - TestAudio:    测试音频文件目录
    - TestCase:     测试用例目录
    - TestResource: 模型资源目录
""")


def main():
    """
    主函数
    """
    # 如果没有参数，显示帮助
    if len(sys.argv) == 1:
        print_help()
        sys.exit(0)
    
    # 打印启动信息
    print_banner()
    
    # 验证路径
    if not validate_paths():
        sys.exit(1)
    
    # 构建命令
    docker_cmd, container_name = build_docker_command()
    
    # 打印命令
    print("🚀 执行命令:")
    print(' '.join(docker_cmd))
    print("=" * 60)
    
    # 执行命令
    try:
        return_code = subprocess.call(docker_cmd)
        sys.exit(return_code)
    except FileNotFoundError:
        print("❌ 错误: 'docker' 命令未找到")
        print("💡 请确保Docker已安装并添加到系统PATH")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断执行")
        sys.exit(130)
    except Exception as e:
        print(f"❌ 执行错误: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
