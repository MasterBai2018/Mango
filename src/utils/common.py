#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2023/8/1 20:58
# @Author  : huidong.bai
# @File    : common.py
# @Software: PyCharm
# @Mail    : MasterBai2018@outlook.com
import os
import sys
import ast
import json
import time
import yaml
import re
import pytest
import socket
import psutil
import shutil
import pickle
import datetime
import tempfile
import configparser
import subprocess
from loguru import logger
from pathlib import Path
from functools import wraps
from contextlib import contextmanager
from src.utils.ConfigParser import ConfigParser
from src.utils.MangoDB import MangoDatabase

color_template = {
    "red": "\033[1;31m%s\033[0m",        # 红色 - 粗体亮红
    "green": "\033[1;32m%s\033[0m",      # 绿色 - 粗体亮绿
    "yellow": "\033[1;33m%s\033[0m",     # 黄色 - 粗体亮黄
    "blue": "\033[1;34m%s\033[0m",       # 蓝色 - 粗体亮蓝
    "magenta": "\033[1;35m%s\033[0m",    # 洋红色 - 粗体亮洋红
    "cyan": "\033[36m%s\033[0m",         # 青色 - 普通青色
    "white": "\033[1;37m%s\033[0m",      # 白色 - 粗体亮白
    "gray": "\033[1;30m%s\033[0m",       # 灰色 - 粗体暗灰
    "deep_blue": "\033[38;5;104m%s\033[0m",      # 蓝色 - 深蓝色
    "deep_green": "\033[38;5;78m%s\033[0m",      # 绿色 - 深绿色
    "deep_yellow": "\033[38;5;229m%s\033[0m",    # 黄色 - 深黄色
    "bg_green": "\033[48;5;28m%s\033[0m",        # 背景绿色
    "bg_purple": "\033[48;5;135m%s\033[0m",      # 背景紫色
    "bg_red": "\033[48;5;88m%s\033[0m",          # 背景红色
    "bg_blue": "\033[48;5;26m%s\033[0m",         # 背景蓝色
    "bg_black": "\033[48;5;16m%s\033[0m",        # 背景黑色
    "bg_yellow": "\033[48;5;192m%s\033[0m",      # 背景黄色
    "None": "%s",                                # 无颜色 - 默认终端颜色

    'TSA': '\033[1;34m%s\033[0m',          # TSA语音助手客户端 - 绿色（主要功能，使用鲜明的绿色）
    'TTS': '\033[36m%s\033[0m',            # TTS文本转语音客户端 - 蓝色（语音合成相关，使用沉稳的蓝色）
    'SET': '\033[36m%s\033[0m',            # 语音设置客户端 - 黄色（配置相关，使用醒目的黄色提醒）
    'VOI': '\033[36m%s\033[0m',            # 语音输入法客户端 - 洋红色（输入功能，使用特殊的洋红色）
    'OMS': '\033[36m%s\033[0m',            # OMS车载管理客户端 - 青色（管理功能，使用冷静的青色）
    'NANO': '\033[1;30m%s\033[0m',         # NANO测试客户端 - 白色（测试框架，使用中性的白色）
    'FOTA': '\033[36m%s\033[0m',           # FOTA升级客户端 - 灰色（系统功能，使用低调的灰色）

    'HWK': '\033[1;34m%s\033[0m',         # HWK语音助手客户端 - 绿色（主要功能，使用鲜明的绿色）
    'PST': '\033[36m%s\033[0m',           # PST文本转语音客户端 - 蓝色（语音合成相关，使用沉稳的蓝色）
    'TIA': '\033[36m%s\033[0m',           # TIA语音助手客户端 - 洋红色（输入功能，使用特殊的洋红色）

    'NIS': '\033[1;34m%s\033[0m',         # NISSAN语音助手客户端 - 绿色（主要功能，使用鲜明的绿色）
    'NSE': '\033[36m%s\033[0m',           # NISSAN语音设置客户端 - 蓝色（语音合成相关，使用沉稳的蓝色）

    'CPL': '\033[1;35m%s\033[0m',         # CarPlay客户端 - 洋红色（CarPlay功能，使用醒目的洋红色）

    'PIS': '\033[1;34m%s\033[0m',         # PISA助手客户端 - 绿色（主要功能，使用鲜明的绿色）

    'TSS': "\033[1;32m%s\033[0m",           # TSS语音助手客户端 - 绿色（主要功能，使用鲜明的绿色）
}

def timer(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        end = time.perf_counter()
        logger.success(f"{func.__name__} 耗时：{end - start:.6f} 秒")
        return result
    return wrapper


def method(prototype):
    class MethodDescriptor(object):
        def __init__(self, func):
            self.func = func
            self.bound_funcs = {}

        def __get__(self, obj, types=None):
            assert obj is not None
            try:
                return self.bound_funcs[obj, types]
            except KeyError:
                rets = self.bound_funcs[obj, types] = prototype(self.func.__get__(obj, types))
                return rets
    return MethodDescriptor


def async_color_print(*args):
    color_msg = ""
    for msg, color in args:
        color_msg += color_template[str(color)] % msg
    print(color_msg)


def color(output, color=None):
    if color is None or color not in color_template:
        return output
    color_msg = color_template[color]
    return color_msg % output


def print_streaming_line(prefix: str, content: str, color_template_str=None, newline: bool = False) -> None:
    """
    在终端同一行覆盖显示流式内容。超出终端宽度时只显示末尾部分。
    使用 sys.__stdout__ 绕过 pytest 的 stdout 捕获，使 \\r 能在真实终端生效。

    :param prefix: 前缀（如 "[PIS] [>>>回调>>>] [0][ResponseTTSTemp] "）
    :param content: 流式内容
    :param color_template_str: 颜色模板，如 color_template["PIS"]，None 则无颜色
    :param newline: 是否在末尾换行（ResponseTTS 为 True，ResponseTTSTemp 为 False）
    """
    try:
        columns, _ = shutil.get_terminal_size()
    except Exception:
        columns = 80
    prefix_width = len(prefix.encode('gbk'))
    available = columns - 1 - prefix_width
    if len(content.encode('gbk')) <= available:
        display_msg = prefix + content
    else:
        # 超出则只显示 content 末尾部分（按全中文估算：每字约 2 列）
        tail_len = available // 2
        display_msg = prefix + content[-tail_len:]
    msg = (color_template_str or "%s") % display_msg
    out = getattr(sys, "__stdout__", sys.stdout) or sys.stdout
    out.write(f"\r{msg}\033[K" + ("\n" if newline else ""))
    out.flush()


def get_log_time():
    timestamp = datetime.datetime.now()
    formatted_time = timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")
    return formatted_time[:-3]


def get_timestamp():
    return int(time.time() * 1000)


def get_date(offset_days=0):
    """
    获取当前日期，支持偏移量（天）
    :param offset_days: 偏移天数，默认0
    """
    from datetime import datetime, timedelta
    target_date = datetime.now() + timedelta(days=int(offset_days))
    return target_date.strftime("%Y-%m-%d %H:%M:%S")


def find_free_ports(num_ports=2, start_port=8000):
    ports = []
    current_port = start_port

    while len(ports) < num_ports:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('0.0.0.0', current_port))
                ports.append(current_port)
        except socket.error:
            pass
        current_port += 1
    return ports


def kill_process_by_port(port) -> int:
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            connections = proc.connections()
            for conn in connections:
                if conn.status == psutil.CONN_LISTEN and conn.laddr.port == port:
                    try:
                        proc.terminate()
                        return 0
                    except psutil.NoSuchProcess:
                        return -1
        except psutil.AccessDenied:
            pass
    return -1


def profile_redirect(source, destination, root, config_items) -> int:
    if (not os.path.exists(source)) or os.path.getsize(source) == 0:
        return -1
    new_file = open(destination, 'w+', encoding='UTF-8')
    try:
        with open(source, 'r', encoding='UTF-8') as fp:
            lines = fp.readlines()
            for line in lines:
                info = line.strip()
                if line.isspace() or info[0] == "#" or info[:2] == "//":
                    continue
                for key, value in config_items.items():
                    if key in line:
                        if type(value) == int:
                            new_value = f'{key} = {value};\n'
                        elif type(value) == bool:
                            new_value = f'{key} = {str(value).lower()};\n'
                        else:
                            new_value = f'{key} = "{value}";\n'
                        new_file.write(new_value)
                        del config_items[key]
                        break
                else:
                    new_file.write(line)

            for key, value in config_items.items():
                if type(value) == int:
                    new_value = f'{key} = {value};\n'
                elif type(value) == bool:
                    new_value = f'{key} = {str(value).lower()};\n'
                else:
                    new_value = f'{key} = "{value}";\n'
                new_file.write(new_value)
        fp.close()

        new_file.close()
        return 0
    except Exception as e:
        new_file.close()
        print(f"rewrite file[{source}] error: {e}")
        return -1


def replace_file(file, old, new) -> int:
    if not os.path.exists(file):
        print(f"Replace file error, file: [{file}], pls check it.")
        return -1
    if (not old) or (not new):
        print(f"Replace file error, file: [{file}], old: [{old}], new: [{new}], pls check it.")
        return -1
    cmd = f"sed -i 's|{old}|{new}|g' {file}"
    os.system(cmd)
    return file


def copy_configs(source_path, dest_dir, old, new):
    if old is None or new is None or source_path is None or dest_dir is None:
        pytest.exit(reason=f"Copy config file [{source_path}] error, old value is {old}, new value is {new}.")
    config_name = os.path.basename(source_path)
    dest_path = os.path.join(dest_dir, config_name)
    sed_cmd = f"sed 's|{old}|{new}|g' {source_path} > {dest_path}"
    os.system(sed_cmd)
    return dest_path


def copy_libs(item, key, destination, project):
    project_config = configparser.ConfigParser()
    project_config.read('conf/project.ini', encoding='utf-8')
    mango_config = configparser.ConfigParser()
    mango_config.read('conf/mongo.ini', encoding='utf-8')
    lib_name = mango_config.get(item, key).split('/')[-1]
    local_lib_path = os.path.join(project_config.get(f'{project}', 'path'), lib_name)
    if not os.path.exists(local_lib_path):
        pytest.exit(reason=f"Copy lib path error: {local_lib_path}")

    shutil.copy(local_lib_path, destination)
    return os.path.join(destination, lib_name)


def redirect_librarys(source_path, dest_dir):
    """
    拷贝source_path路径下的所有内容到dest_dir目录下
    
    Args:
        source_path: 源文件或目录路径
        dest_dir: 目标目录路径
        
    Returns:
        bool: 成功返回 True，失败返回 False
    """
    try:
        # 验证源路径
        if not source_path or not os.path.exists(source_path):
            return False
        
        # 创建目标目录
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir, mode=0o755, exist_ok=True)
        
        # 拷贝文件或目录
        if os.path.isfile(source_path):
            # 如果是文件，直接拷贝到目标目录
            shutil.copy2(source_path, dest_dir)
        elif os.path.isdir(source_path):
            # 如果是目录，遍历目录下的所有内容，逐个拷贝到目标目录
            for item in os.listdir(source_path):
                item_path = os.path.join(source_path, item)
                dest_item_path = os.path.join(dest_dir, item)
                
                if os.path.isfile(item_path):
                    # 拷贝文件
                    shutil.copy2(item_path, dest_item_path)
                elif os.path.isdir(item_path):
                    # 拷贝目录（如果目标已存在则先删除）
                    if os.path.exists(dest_item_path):
                        shutil.rmtree(dest_item_path)
                    shutil.copytree(item_path, dest_item_path)
        
        # 设置可执行权限
        os.system(f"chmod -R +x {dest_dir}")
        
        return True
    except Exception as e:
        return False


def is_available_file(file: str):
    if not file:
        return False
    else:
        if os.path.exists(file) and os.path.getsize(file) > 0 and os.path.isfile(file):
            return True
        else:
            return False


def read_config(path):
    with open(path, "rb") as fp:
        serialized_object = fp.read()
        fp.close()
    return pickle.loads(serialized_object)


def uuid(tag=None):
    import uuid
    uuids = str(uuid.uuid4()).upper().replace("-", '')
    if tag:
        return uuids + str(tag)
    else:
        return uuids


def load_yaml_config(yaml_config):
    try:
        with open(yaml_config, 'r') as file:
            _config = yaml.safe_load(file)
        file.close()
        return _config
    except yaml.YAMLError as e:
        print(f"Error loading yaml file: {e}")
        raise e


def get_open_file_count_psutil():
    try:
        # 获取当前进程对象
        process = psutil.Process()
        # 获取当前进程已打开的文件句柄数量
        return process.num_fds()
    except psutil.Error as e:
        print(f"Error: {e}")
        return None


def trans_digit(param: str):
    try:
        num = float(param)
        return int(num) if num.is_integer() else num
    except ValueError:
        return None


def pop(items: list, index: int):
    try:
        result = items.pop(index)
    except IndexError:
        result = ""
    return result


def is_english(s):
    start_is_eng = False
    end_is_eng = False
    if len(s) > 0:
        start_char = s[0]
        end_char = s[-1]
        if 65 <= ord(start_char) <= 90 or 97 <= ord(start_char) <= 122:
            start_is_eng = True
        if 65 <= ord(end_char) <= 90 or 97 <= ord(end_char) <= 122:
            end_is_eng = True
        return start_is_eng, end_is_eng
    else:
        return start_is_eng, end_is_eng


def is_digit(s):
    start_is_digit = False
    end_is_digit = False
    if len(s) > 0:
        start_char = s[0]
        end_char = s[-1]
        if 48 <= ord(start_char) <= 57:  # 0-9 的 ASCII 码范围
            start_is_digit = True
        if 48 <= ord(end_char) <= 57:
            end_is_digit = True
        return start_is_digit, end_is_digit
    else:
        return start_is_digit, end_is_digit


def join_with_spaces_if_english(text):
    words = text.split("|")
    result = []

    for i in range(len(words) - 1):
        # 检查是否包含英文
        _, end_is_eng = is_english(words[i])
        start_is_eng, _ = is_english(words[i+1])
        # 检查是否包含数字
        _, end_is_digit = is_digit(words[i])
        start_is_digit, _ = is_digit(words[i+1])

        # 英文和英文之间，英文和数字之间，数字和英文之间都需要加空格
        if (start_is_eng and end_is_eng) or (start_is_eng and end_is_digit) or (start_is_digit and end_is_eng):
            result.append(words[i] + " ")
        else:
            result.append(words[i])

    result.append(words[-1])
    return ''.join(result)


def check_line_filter(tag):
    s_tag = 1
    e_tag = 40000
    if not tag:
        return s_tag, e_tag
    try:
        start, end = [i.strip() for i in tag.split("-")]
        if len(start) == 0 or len(end) == 0:
            raise ValueError("Case Filter参数传入错误: {tag}, 请输入正确的-F参数")
        if start == "*":
            s_tag = 1
            e_tag = int(end)
            if e_tag <= 0:
                raise ValueError("Case Filter参数传入错误: {tag}, end tag不能小于0, 请输入正确的-F参数")
        elif end == "*":
            s_tag = int(start)
            e_tag = 40000
            if s_tag <= 0:
                raise ValueError("Case Filter参数传入错误: {tag}, start tag不能小于0, 请输入正确的-F参数")
        elif start == "*" and end == "*":
            raise ValueError("Case Filter参数传入错误: {tag}, 请输入正确的-F参数")

        else:
            s_tag = int(start)
            e_tag = int(end)
            if s_tag <= 0 or e_tag <= 0 or e_tag < s_tag:
                raise ValueError(f"Case Filter参数传入错误: {tag}, 请输入正确的-F参数")

        return int(s_tag), int(e_tag)
    except Exception as e:
        raise e

def wait_gdb_attach(process_name, pid):
    msg = []
    time.sleep(2)

    docker_prefix = ""
    # 检查是否在Docker环境下运行
    if os.environ.get("DockerMode", "False") == "True":
        container_name = os.environ.get("DOCKER_CONTAINER_NAME", "")
        docker_prefix = f"docker exec -it -w /mango {container_name} "

    msg.append("============================== GDB调试模式 ================================")
    msg.append(f"[{process_name}] GDB模式已启用进程PID: {pid}, 请在另一个终端执行:")
    msg.append(f"{docker_prefix}gdb -p {pid}")
    msg.append("==========================================================================")
    async_color_print(("\n".join(msg), "red"))
    input("按回车继续...")


def find_test_suites(directory='src/testsuite'):
    results = {}
    base_dir = Path(directory)

    for file_path in base_dir.rglob('*.py'):
        # 获取相对于当前工作目录的路径，并转换为POSIX格式（使用斜杠）
        try:
            relative_path = file_path.relative_to(Path.cwd()).as_posix()
        except ValueError:
            # 如果文件不在当前工作目录下，使用绝对路径转换
            relative_path = file_path.as_posix()

        with open(file_path, 'r', encoding='utf-8-sig') as file:
            for node in ast.walk(ast.parse(file.read(), filename=str(file_path))):
                if isinstance(node, ast.ClassDef):
                    suite_name = None
                    suite_summary = None

                    # 遍历类的每个成员（如赋值语句）
                    for item in node.body:
                        if isinstance(item, ast.Assign):
                            for target in item.targets:
                                if isinstance(target, ast.Name):
                                    # 检查变量名并提取值
                                    if target.id == 'SuiteName':
                                        value = item.value
                                        if isinstance(value, ast.Str):
                                            suite_name = value.s  # Python <3.8
                                        elif isinstance(value, ast.Constant):
                                            suite_name = value.value  # Python >=3.8
                                    elif target.id == 'SuiteSummary':
                                        value = item.value
                                        if isinstance(value, ast.Str):
                                            suite_summary = value.s
                                        elif isinstance(value, ast.Constant):
                                            suite_summary = value.value

                    # 如果找到两个变量，则添加到结果
                    if suite_name is not None and suite_summary is not None:
                        results[suite_name] = {"SuiteSummary": suite_summary, "SuitePath": relative_path}
    
    return results


def redirect_config(origin, dest, old_tag, new_tag):
    if not os.path.exists(origin):
        return dest
    file_name = os.path.basename(origin)
    dest_path = os.path.join(dest, file_name)
    with open(origin, 'r') as f_src, open(dest_path, 'w') as f_dest:
        content = f_src.read().replace(str(old_tag), str(new_tag))
        f_dest.write(content)
    return dest_path

def get_environment(key: str, timeout: int = 5):
    """
    获取环境变量，带超时重试功能
    
    Args:
        key: 环境变量键名
        timeout: 超时时间（秒），默认10秒
        
    Returns:
        环境变量的值，如果不存在或超时则返回 None
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        value = os.getenv(key)
        if value is not None:
            return value
        time.sleep(0.1)
    return None


def update_lcs_event_parser(lcs_path_list) -> int:
    for lcs_path in lcs_path_list:
        if lcs_path is None or len(lcs_path) == 0 or not os.path.exists(lcs_path) or "lcs" not in lcs_path.lower():
            continue

        lcs_event_parser = ""
        with open(lcs_path, "r", encoding="utf-8") as file:
            lines = file.readlines()
            for line in lines:
                if line.startswith("LCS_RES_PATH"):
                    lcs_event_parser = line.replace('LCS_RES_PATH = "', "").split('"')[0]
                    break
        # 动态遍历 ClientRes 下所有语言子目录（如 cmn、eng、jpn 等）
        client_res_path = os.path.join(lcs_event_parser, "ClientRes")
        event_parser_files = []
        if os.path.isdir(client_res_path):
            for lang_dir in os.listdir(client_res_path):
                event_parser_file = os.path.join(client_res_path, lang_dir, "EventParser", "event_parser.json")
                event_parser_files.append(event_parser_file)

        for file in event_parser_files:
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    json_data = json.load(f)
                print("文件读取成功！")
                # 修改json指定字段
                for data in json_data["subscriber_protocol"]:
                    if data["name"] == "SpeechWakeup":
                        if "inputAdapter" in data["subscribers"]:
                            break
                        else:
                            data["subscribers"].append("inputAdapter")
                    if data["name"] == "VoiceDetectionResult0":
                        if "inputAdapter" in data["subscribers"]:
                            break
                        else:
                            data["subscribers"].append("inputAdapter")
                    if data["name"] == "VoiceDetectionResult1":
                        if "inputAdapter" in data["subscribers"]:
                            break
                        else:
                            data["subscribers"].append("inputAdapter")
                    if data["name"] == "VoiceDetectionResult2":
                        if "inputAdapter" in data["subscribers"]:
                            break
                        else:
                            data["subscribers"].append("inputAdapter")
                    if data["name"] == "VoiceDetectionResult3":
                        if "inputAdapter" in data["subscribers"]:
                            break
                        else:
                            data["subscribers"].append("inputAdapter")
                    if data["name"] == "VoiceDetectionResult4":
                        if "inputAdapter" in data["subscribers"]:
                            break
                        else:
                            data["subscribers"].append("inputAdapter")
                    if data["name"] == "VoiceDetectionResult5":
                        if "inputAdapter" in data["subscribers"]:
                            break
                        else:
                            data["subscribers"].append("inputAdapter")
                    if data["name"] == "VoiceDetectionResult6":
                        if "inputAdapter" in data["subscribers"]:
                            break
                        else:
                            data["subscribers"].append("inputAdapter")
                with open(file, 'w', encoding='utf-8') as f:
                    json.dump(json_data, f, indent=2)

            except FileNotFoundError:
                print("文件不存在！")
            except json.JSONDecodeError:
                print("JSON格式错误！")
            except Exception as e:
                print(f"发生错误：{e}")
    return 1


def pack_random_files(source_dir: str, target_zip: str, count: int = 10, zip_root: str = None, mode: str = "normal") -> bool:
    """
    随机打包文件
    
    Args:
        source_dir: 源目录
        target_zip: 目标zip文件路径
        count: 随机选取的文件数量
        zip_root: zip包内的根目录名 (None或'.'表示无根目录)
        mode: 模式 'normal' 或 'lcs' (LCS模式会生成checksum.list)
    
    Returns:
        bool: 是否成功
    """
    try:
        import random
        import zipfile
        
        if not os.path.exists(source_dir):
            print(f"Source directory does not exist: {source_dir}")
            return False
            
        # LCS专用逻辑：只从TSAPResource选取
        scan_dir = source_dir
        if mode == 'lcs':
            scan_dir = os.path.join(source_dir, 'TSAPResource')
            if not os.path.exists(scan_dir):
                print(f"TSAPResource directory does not exist: {scan_dir}")
                return False
        
        # 收集所有文件
        all_files = []
        for root, dirs, files in os.walk(scan_dir):
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, scan_dir)
                all_files.append((file_path, rel_path))
        
        if not all_files:
            print(f"No files found in directory: {scan_dir}")
            return False
            
        # 随机选择
        selected_count = min(len(all_files), count)
        selected_files = random.sample(all_files, selected_count)
        print(f"Selected {selected_count} files from {scan_dir}")
        
        # 创建Zip
        # 确保目标目录存在
        os.makedirs(os.path.dirname(target_zip), exist_ok=True)
        
        with zipfile.ZipFile(target_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
            has_cmn = False
            has_eng = False
            
            for abs_path, rel_path in selected_files:
                # 计算zip内路径
                if mode == 'lcs':
                    # LCS模式：强制以TSAPResource开头
                    zip_internal_path = os.path.join('TSAPResource', rel_path).replace('\\', '/')
                    
                    # 检查语种用于生成checksum
                    if '/cmn/' in zip_internal_path or 'cmn/' in rel_path: has_cmn = True
                    if '/eng/' in zip_internal_path or 'eng/' in rel_path: has_eng = True
                else:
                    # 普通模式
                    if zip_root and zip_root != '.':
                        zip_internal_path = os.path.join(zip_root, rel_path).replace('\\', '/')
                    else:
                        zip_internal_path = rel_path.replace('\\', '/')
                
                zipf.write(abs_path, zip_internal_path)
            
            # LCS模式特殊处理：生成checksum.list
            if mode == 'lcs':
                if has_cmn:
                    zipf.writestr('TSAPResource/ClientRes/cmn/checksum.list', '')
                if has_eng:
                    zipf.writestr('TSAPResource/ClientRes/eng/checksum.list', '')
                    
        return True
        
    except Exception as e:
        print(f"Pack random files failed: {e}")
        return False

def update_config_file(config_file_path, config_updates):
    """
    更新配置文件中的配置项：如果配置项存在则更新其值，如果不存在则追加到文件末尾
    
    Args:
        config_file_path: 配置文件路径
        config_updates: 字典，包含要更新的配置项，格式为 {配置项名: 配置值} 例如: {'LCS_DECODER_PATH': '/path/to/lcs', 'OTA_CONFIG_PATH': '/path/to/ota'}
    Returns:
        int: 0表示成功，-1表示失败
    """
    try:
        # 读取配置文件内容
        with open(config_file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()
        
        # 标记哪些配置项已经找到
        found_configs = {key: False for key in config_updates.keys()}
        
        # 遍历每一行，查找并更新配置项
        for i, line in enumerate(lines):
            line = line.strip()
            if len(line) == 0 or line.startswith("#") or line.startswith("//") or line.startswith("@"):
                continue
            for config_key, config_value in config_updates.items():
                key_config = line.split("=")[0].strip()
                if key_config == config_key:
                    # 更新配置值
                    lines[i] = f'{config_key} = "{config_value}";\n'
                    found_configs[config_key] = True
                    break
        
        # 追加未找到的配置项
        new_lines = []
        for config_key, config_value in config_updates.items():
            if not found_configs[config_key]:
                new_lines.append(f'{config_key} = "{config_value}";\n')
        
        # 如果有新配置项，追加到文件末尾
        if new_lines:
            # 确保文件末尾有换行符
            if lines and not lines[-1].endswith('\n'):
                lines[-1] = lines[-1] + '\n'
            lines.extend(new_lines)

        # 写回配置文件
        with open(config_file_path, 'w', encoding='utf-8') as file:
            file.writelines(lines)
        
        return 0
    except Exception as e:
        print(f"更新配置文件 [{config_file_path}] 时发生错误: {e}")
        return -1

assert_key_value_config = load_yaml_config('conf/assert_key_value.yaml')
mango_config = ConfigParser('conf/mango.ini')

# 懒加载缓存，全局复用 MangoDatabase 和 mango.ini 配置
_tts_db: MangoDatabase | None = None
_tts_cfg: configparser.ConfigParser | None = None


class embeddedType:
    embeddedType_1 = "任务执行_成功_打开类"  
    embeddedType_2 = "任务执行_成功_关闭类"  
    embeddedType_3 = "任务执行_成功_调节类"  
    embeddedType_4 = "任务执行_成功_其他"  
    embeddedType_5 = "任务执行_失败_明确类"  
    embeddedType_6 = "任务执行_失败_不明确类"  
    embeddedType_7 = "文本回复"  
    embeddedType_8 = "多轮对话"  
    embeddedType_0 = "其他"  


def tts_info_to_except(data_str: str, project: str) -> str:
    """
    将 data_str 中的 ttsInfo:ttsID,lang,type 展开为各列期望值，并移除原始 ttsInfo 字段。
    例如：
        原始: "...;ttsInfo:duolun005,cmn,offline;..."
        展开: 追加各列 ";col:value" 并删除 ";ttsInfo:..."
    """
    global _tts_db, _tts_cfg

    ttsInfo_match = re.search(r'ttsInfo:([^;]+)', data_str)

    if not ttsInfo_match:
        print(f"未找到ttsInfo字段:{data_str}")
        return data_str

    ttsinfo = ttsInfo_match.group(1).split(",")
    if len(ttsinfo) == 0:
        print(f"ttsInfo格式错误: {data_str}")
        return data_str
    ttsID = ttsinfo[0].strip()
    tts_lang = "cmn"
    tts_type = "offline"
    if len(ttsinfo) > 1 and ttsinfo[1].strip():
        tts_lang = ttsinfo[1].strip()
    if len(ttsinfo) > 2 and ttsinfo[2].strip():
        tts_type = ttsinfo[2].strip()


    # 懒加载并复用 MangoDatabase 实例
    if _tts_db is None:
        _tts_db = MangoDatabase()
    database = _tts_db

    # 懒加载并复用 mango.ini 配置
    if _tts_cfg is None:
        cfg = configparser.ConfigParser()
        cfg.read('conf/mango.ini', encoding='utf-8')
        _tts_cfg = cfg
    mango_cfg = _tts_cfg

    section = project
    if tts_lang == 'cmn':
        columns = mango_cfg.get(section, 'support_title_cmn').split(",")
    elif tts_lang == 'eng':
        columns = mango_cfg.get(section, 'support_title_eng').split(",")
    else:
        columns = mango_cfg.get(section, 'support_title_cmn').split(",")

    # 根据 tts_type 过滤 ON / OFF 列，避免边遍历边删除
    if tts_type == "offline":
        columns = [c for c in columns if "ON" not in c]
    elif tts_type == "online":
        columns = [c for c in columns if "OFF" not in c]

    row = database.query_data(
        table=mango_cfg.get(section, 'db_table'),
        columns=', '.join(columns),
        condition="id",
        condition_value=ttsID,
    )

    if not row:
        print(f"未在 TTS 数据库中找到 ttsID={ttsID}, data_str={data_str}")
        return data_str

    # 追加各列期望值
    for col, value in zip(columns, row):
        if "embeddedType" in col:
            index_type = "embeddedType_" + str(value)
            value = getattr(embeddedType, index_type, embeddedType.embeddedType_0)
        data_str += f";{col}:{value}" if value != "nan" else f";{col}:None"

    # 删除原始 ttsInfo 字段
    data_str = data_str.replace(f";ttsInfo:{ttsInfo_match.group(1)}", "")
    return data_str

@contextmanager
def capture_library_output(save_to_file=None):
    """
    上下文管理器：临时捕获.so库的stdout和stderr输出
    
    Args:
        save_to_file: 如果为True，将输出保存到日志文件；如果为False，只捕获不保存
    
    Usage:
        with client._capture_library_output(save_to_file=True):
            client.some_library_function()
    """
    # 备份 stdout 和 stderr
    old_stdout_fd = os.dup(sys.stdout.fileno())
    old_stderr_fd = os.dup(sys.stderr.fileno())
    
    # 创建临时文件来捕获输出
    tmp_stdout = tempfile.TemporaryFile(mode='w+b')
    tmp_stderr = tempfile.TemporaryFile(mode='w+b')
    
    try:
        # 重定向 stdout 和 stderr
        os.dup2(tmp_stdout.fileno(), sys.stdout.fileno())
        os.dup2(tmp_stderr.fileno(), sys.stderr.fileno())
        
        yield
        
        # 刷新输出
        sys.stdout.flush()
        sys.stderr.flush()
        
    finally:
        # 恢复原始文件描述符
        os.dup2(old_stdout_fd, sys.stdout.fileno())
        os.dup2(old_stderr_fd, sys.stderr.fileno())
        os.close(old_stdout_fd)
        os.close(old_stderr_fd)
        
        # 读取捕获的输出
        tmp_stdout.seek(0)
        tmp_stderr.seek(0)
        stdout_content = tmp_stdout.read().decode('utf-8', errors='ignore')
        stderr_content = tmp_stderr.read().decode('utf-8', errors='ignore')
        
        # 如果设置了保存到文件，写入日志文件
        if save_to_file is not None:
            with open(save_to_file, 'a', encoding='utf-8') as file:
                file.write(stdout_content + '\n')
                file.write(stderr_content + '\n')
        
        # 关闭临时文件
        tmp_stdout.close()
        tmp_stderr.close()


def parse_params(params: str) -> dict:
    params_dict = {}
    if len(params) > 0 and params[0]:
        param_str = params[0]
        param_pairs = param_str.split(';')
        for pair in param_pairs:
            pair = pair.strip()
            if not pair:
                continue
            if ':' not in pair:
                logger.warning(f"参数格式错误，跳过: {pair}")
                continue
            key, value = pair.split(':', 1)
            key = key.strip()
            value = value.strip()
            params_dict[key] = value
    return params_dict

def check_core_file(workspace, start_time, end_time):
    # 结束的时候检查mango下是否有.core文件，如果有执行GDB.sh脚本，生成报告保存到data下
    try:
        output_dir = os.path.join(workspace, "tombstone")
        core_dir = "/mango"
        gdb_script = os.path.join(os.getcwd(), "GDB.sh")
        os.makedirs(output_dir, exist_ok=True)
        if not os.path.isdir(core_dir):
            print(f"{core_dir} 目录不存在，跳过core检查")
        else:
            for fname in os.listdir(core_dir):
                if fname.startswith("core"):
                    stat = os.stat(fname)
                    if stat.st_mtime < start_time or stat.st_mtime > end_time:
                        continue
                    core_path = os.path.join(core_dir, fname)
                    print(f"发现core文件: {core_path}")
                    cmd = ["gdb", "-q", "-batch", "-ex", "info auxv", "-c", core_path]
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    execfn = None
                    for line in result.stdout.splitlines():
                        if "AT_EXECFN" in line:
                            parts = line.split()
                            execfn = parts[-1] if parts else None
                            break
                    execfn = execfn.strip('"')
                    subprocess.run(
                        ["bash", gdb_script, "-b", "-n", "-o", output_dir, execfn, core_path],
                        capture_output=True,
                        text=True
                    )
                    output_file = os.path.join(output_dir, f"gdb_{fname}.txt")
                    if os.path.exists(output_file):
                        print(f"✅ GDB 报告已保存到: {output_file}")
                    else:
                        print(f"❌ GDB 报告不存在: {output_file}")
    except Exception as e:
        print(f"检查core文件失败: {e}")