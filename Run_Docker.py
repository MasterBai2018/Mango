#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2025/11/11
# @Author  : huidong.bai
# @File    : Run_Docker.py
# @Software: PyCharm

import os
import sys
import subprocess
import uuid
import time
import argparse
import shlex
import shutil


def parse_mount_arg(mount_spec):
    """
    解析 -m 挂载参数
    支持格式：
        /host/path                      -> /host/path:/host/path:ro
        /host/path:/container/path      -> /host/path:/container/path:ro
        /host/path:/container/path:rw   -> /host/path:/container/path:rw
    返回：(host_path, container_path, permission)
    """
    parts = mount_spec.split(':')
    
    if len(parts) == 1:
        # 格式: /host/path -> 容器路径与宿主机路径相同，默认ro
        host_path = parts[0]
        container_path = parts[0]
        permission = 'ro'
    elif len(parts) == 2:
        # 格式: /host/path:/container/path -> 默认ro
        host_path = parts[0]
        container_path = parts[1]
        permission = 'ro'
    elif len(parts) == 3:
        # 格式: /host/path:/container/path:ro|rw
        host_path = parts[0]
        container_path = parts[1]
        permission = parts[2]
        if permission not in ('ro', 'rw'):
            print(f"错误: 无效的权限 '{permission}'，只支持 'ro' 或 'rw'")
            sys.exit(1)
    else:
        print(f"错误: 无效的挂载格式 '{mount_spec}'")
        print("支持格式: /host/path 或 /host/path:/container/path 或 /host/path:/container/path:ro|rw")
        sys.exit(1)
    
    # 验证宿主机路径是否存在
    if not os.path.exists(host_path):
        print(f"错误: 挂载路径 '{host_path}' 不存在")
        sys.exit(1)
    
    return (host_path, container_path, permission)


def get_symlink_real_path(link_name):
    """
    获取项目根目录下软链接的真实绝对路径
    """
    # 获取项目根目录
    project_root = os.path.dirname(os.path.abspath(__file__))
    link_path = os.path.join(project_root, link_name)
    if not os.path.islink(link_path):
        # 如果不是软链接，直接返回绝对路径，以增加兼容性
        if os.path.exists(link_path):
             return os.path.abspath(link_path)
        print(f"警告: '{link_name}' 不是一个软链接或不存在于项目根目录。")
        return None
    
    # 读取软链接指向的真实路径
    real_path = os.readlink(link_path)
    
    # 如果是相对路径，则转换为绝对路径
    if not os.path.isabs(real_path):
        real_path = os.path.abspath(os.path.join(project_root, real_path))
        
    return real_path


def main():
    """
    主函数，用于构建并执行Docker命令
    """
    # 1. 获取Docker镜像
    docker_image = "mango:v3.6.0"

    # 2. 获取当前项目目录的绝对路径
    project_root = os.path.dirname(os.path.abspath(__file__))

    # 使用argparse解析 -v 参数，其余参数传递给Run_Mongo.py
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('-v', dest='volume', help='动态挂载路径，格式: /host/path[:/container/path][:<ro|rw>]')
    parser.add_argument(
        '-T', '--tcpdump',
        nargs='?',
        const='',
        default=None,
        metavar='STR',
        help='容器内 tcpdump；不传则关闭。-T 表示网卡 any；-T （例: -T "eth0 port 5060"）',
    )
    args, remaining_args = parser.parse_known_args()

    tcpdump_on = args.tcpdump is not None
    if tcpdump_on:
        td_parts = shlex.split(args.tcpdump or '')
        tcpdump_iface = td_parts[0] if td_parts else 'any'
        tcpdump_bpf = ' '.join(td_parts[1:]).strip()

    run_tcpdump = tcpdump_on and os.geteuid() == 0
    if tcpdump_on and not run_tcpdump:
        print(
            "警告: 当前非 root（有效 UID 非 0），无法安全启用容器内 tcpdump，已跳过抓包；"
        )

    # 解析挂载参数
    extra_volume = parse_mount_arg(args.volume) if args.volume else None

    # 3. 动态获取软链接的真实挂载路径
    test_resource_path = get_symlink_real_path('TestResource')
    test_case_path = get_symlink_real_path('TestCase')
    test_audio_path = get_symlink_real_path('TestAudio')

    # 4. 设置一个唯一的容器id
    container_name = "mango_" + str(uuid.uuid4())[:8].upper().replace("-", "")
    
    # 基础Docker命令
    docker_command = [
        'docker', 'run', '--rm',
        # 使用tini作为PID 1，确保信号正确转发和子进程清理
        '--init',
        # 设置容器name
        '--name', container_name,
        # 设置用户
        '--user', f'{os.getuid()}:{os.getgid()}',
        # 设置用户组
        '--group-add', f'{os.stat(test_audio_path).st_gid}',

        # 设置 ulimits
        '--ulimit', 'nofile=65535:65535',
        '--ulimit', 'nproc=2048:4096',

        # 使用host模式共享网络栈
        '--network', 'host',
        
        # 添加SYS_PTRACE capability，允许GDB使用ptrace进行调试
        '--cap-add=SYS_PTRACE',

        # 设置时区
        '-e', 'TZ=Asia/Shanghai',
        
        # 传递容器名称到容器内部，供GDB调试使用
        '-e', f'DOCKER_CONTAINER_NAME={container_name}',

        # 挂载路径
        '-v', f'{project_root}:/mango:rw',
        '-v', '/etc/passwd:/etc/passwd:ro',
        '-v', '/etc/group:/etc/group:ro',
        '-v', '/data:/data:ro',
        '-v', '/data1:/data1:ro',
        '-v', '/data2:/data2:ro',
        '-v', '/data3:/data3:ro',
        '-v', '/tmp:/tmp:rw',
    ]

    # 存在TTY环境，则增加-it参数
    if sys.stdout.isatty():
        docker_command.extend(['-it'])

    # 动态添加软链接挂载
    if test_resource_path and os.path.exists(test_resource_path):
        docker_command.extend(['-v', f'{test_resource_path}:/mango/TestResource:rw'])
    if test_case_path and os.path.exists(test_case_path):
        docker_command.extend(['-v', f'{test_case_path}:/mango/TestCase:ro'])
    if test_audio_path and os.path.exists(test_audio_path):
        docker_command.extend(['-v', f'{test_audio_path}:/mango/TestAudio:rw'])
    
    # 添加用户自定义的动态挂载（-v 参数指定）
    if extra_volume:
        host_path, container_path, permission = extra_volume
        docker_command.extend(['-v', f'{host_path}:{container_path}:{permission}'])

    # 添加镜像名称
    docker_command.append(docker_image)

    tcpdump_basename = f'tcpdump_{time.strftime("%Y%m%d_%H%M%S")}.pcap'
    # 5. 拼接内部执行的指令（将 Run_Docker.py 替换为 Run_Mongo.py）
    if run_tcpdump:
        os.makedirs('/tmp/mango_tcpdump_pcap', exist_ok=True)
        capture_output = os.path.join('/tmp/mango_tcpdump_pcap', tcpdump_basename)
        print(f'tcpdump capture_output: {capture_output}')
        app_command = ['stdbuf', '-oL', '-eL', 'python3', 'Run_Mongo.py'] + remaining_args + ['-docker']
        app_command_str = ' '.join(shlex.quote(item) for item in app_command)
        filt = f' {tcpdump_bpf}' if tcpdump_bpf else ''
        shell_script = (
            f'tcpdump -U -i {shlex.quote(tcpdump_iface)} -w {shlex.quote(capture_output)}{filt} '
            f'& t=$!; trap \'kill $t 2>/dev/null; wait $t 2>/dev/null || true\' EXIT INT TERM; {app_command_str}'
        )
        internal_command = ['bash', '-lc', shell_script]
    else:
        internal_command = ['stdbuf', '-oL', '-eL', 'python3', 'Run_Mongo.py'] + remaining_args + ['-docker']

    # 组合成最终的完整命令
    final_command = docker_command + internal_command

    print("="*30)
    print("即将执行以下Docker命令:")
    print(' '.join(final_command))
    print("="*30)

    try:
        return_code = subprocess.call(final_command)
        sys.exit(return_code)
    except FileNotFoundError as e:
        print("错误：'docker' 命令未找到。请确保Docker已安装并且在您的系统PATH中。")
        sys.exit(1)
    except Exception as e:
        print(f"执行Docker命令时发生错误: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
