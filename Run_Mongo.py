#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2025/11/15 15:46
# @Author  : huidong.bai
# @File    : Run_Mango.py.py
# @Software: PyCharm
# @Mail    : MasterBai2018@outlook.com
import os
import argparse
import signal
import sys
import psutil
from psutil import NoSuchProcess
from src.userInterface.run_test import run_all_test


def signal_handler(sig: int, frame) -> None:
    """处理中断信号，清理子进程"""
    try:
        proc = psutil.Process()
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        for child in proc.children(recursive=True):
            try:
                child.kill()
            except NoSuchProcess:
                pass
    except NoSuchProcess:
        pass
    sys.exit(0)


def init_input() -> argparse.Namespace:
    """初始化命令行参数解析"""
    parser = argparse.ArgumentParser(description='Mongo Automatic Testing Framework')

    # 参数配置列表（选项，类型，默认值，帮助信息）
    standard_args = [
        ('-t', '--mongo_tag', str, None, 'Filter test suites by tags, e.g. [ONLINE][OFFLINE]. Use +tag for required tags'),
        ('-w', '--mongo_workspace', str, 'workspace', 'Specify working directory'),
        ('-f', '--mongo_filter', str, None, 'Test name filter pattern (positive/negative patterns separated by :)'),
        ('-C', '--mongo_filter_config', str, None, 'Path to filter configuration'),
        ('-a', '--mongo_case', str, None, 'Override test case list from config'),
        ('-p', '--mongo_project', str, None, 'Specify scenario configuration'),
        ('-r', '--mongo_report', str, 'Mongo_Report', 'Test report name'),
        ('-k', '--mongo_voice_seek', str, None, 'Audio index seek configuration'),
        ('-F', '--mongo_filter_case_line', str, None, 'Filter test cases by line numbers'),
        ('-G', '--mongo_generate_case', str, None, 'Generate new test cases (skill:intention format)'),
        ('-E', '--mongo_enable', str, None, 'Enable features defined in solution'),
        ('-D', '--mongo_ftp_downloader', int, None, 'FTP download options: 0=All, 1=Audio, 2=Resources'),
        ('-J', '--mongo_library_downloader', str, None, 'Auto-download libraries (format: component1:build1,component2:build2 or "new" for latest)'),
        ('-L', '--mongo_log_save_option', str, 'yes', 'Save SDK logs: yes/no'),
        ('-d', '--mongo_docker_option', str, 'no', 'Docker container options'),
        ('-delay', '--mongo_delay_option', float, None, 'Process audio data delay time'),
        ('-strategy', '--mongo_strategy_option', int, None, 'TSAP Strategy options'),
        ('-b', '--mongo_environment', str, '24mm/ota2', 'Environment project verification selection: bev/24mm/pstt/seres/psl'),
        ('-n', '--mongo_multiprocess_number', str, None, 'The xdist multiprocess number, None: not use multiprocess, 5: 5 tasks, auto: auto use cpu idle number'),
        ('-R', '--mongo_retry_count', int, None, 'Number of retries for failed test cases (default: no retries)'),
        ('-P', '--mongo_parameterized_data', str, None, "Traditional parameterized data CSV file (field-level parameters)"),
        ('-PF', '--mongo_parameterized_data_filter', str, None, "Filter parameterized data CSV file by row range, e.g. 10-20 (row numbers start from 1, excluding header)"),
        ('-S', '--mongo_steps_data', str, None, "Dynamic steps parameterized data CSV file (step-level parameters with CaseID)")
    ]

    # 标志参数列表（选项，帮助信息）
    flag_args = [
        ('-s', '--mongo_rescue', 'Enable rescue mode for error recovery'),
        ('-l', '--mongo_list_suites', 'List available test suites'),
        ('-e', '--mongo_email', 'Enable email notifications'),
        ('-g', '--mongo_gdb', 'Enable GDB debugging'),
        ('-u', '--mongo_update_common_resource', 'Update common resources'),
        ('-V', '--mongo_detail_version', 'Enable detailed version info'),
        ('-M', '--mongo_message_wechat', 'Send WeChat notifications'),
        ('-docker', '--mongo_docker', 'Run docker mode'),
    ]

    # 添加标准参数
    for short, full, type_, default, help_ in standard_args:
        parser.add_argument(short, full, type=type_, default=default, help=help_)

    # 添加标志参数
    for short, full, help_ in flag_args:
        parser.add_argument(short, full, action='store_true', help=help_)

    parser.add_argument('-c', '--mongo_solution', nargs='*', type=str, help='Path to test solution file list')
    return parser.parse_args()


if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    args = init_input()
    args.mongo_environment = args.mongo_environment.lower()
    print("Starting test execution...")
    run_all_test(args, os.path.abspath(os.path.dirname(__file__)))
    print("Test execution completed.")
