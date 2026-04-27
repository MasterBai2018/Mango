#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2025/09/28
# @Author  : baihuidong
# @File    : SystemManager.py
# @Software: PyCharm
# @Mail    : baihuidong@pachiratech.com
import os
import time
import allure
import signal
import subprocess
from loguru import logger
from src.utils.common import wait_gdb_attach, color
from src.testsuite.NANO.tools.upload_manager import UploadManager


class SystemManager:
    """系统管理器，负责处理SYS指令"""

    def __init__(self, lib_path, config):
        self.config = config
        self.processes = {}  # 进程名 -> 进程对象
        self.log_files = {}  # 进程名 -> 日志文件对象
        # 从cmder获取服务路径
        self.service_commands = {
            'LCSEngine': os.path.join(lib_path, 'LCSEngine'),
            'SpeechEngine': os.path.join(lib_path, 'SpeechEnginebin'), 
            'AIBSServer': os.path.join(lib_path, 'AIBSService'),
            'NissanAIBSService': os.path.join(lib_path, 'AIBSService')
        }

    def pull_service(self, service_name: str, lang: str = "cmn", car_type: str = None) -> bool:
        """
        拉起服务
        Args:
            service_name: 服务名称 (LCSEngine, SpeechEngine, AIBSServer)
            lang: 语种类型，默认为cmn
            car_type: 车参信息，仅AIBSServer需要，格式如：{"brand":"0"}
        """
        try:
            # 构建服务启动命令
            cmd = self._build_service_command(service_name, lang, car_type)
            if not cmd:
                logger.error(f"启动服务失败: {service_name}, lang: {lang}, car_type: {car_type}, 命令构建失败")
                return False

            pid = self._start_service_process(service_name, cmd)

            # 检查是否为GDB调试模式
            if os.environ.get("GDB_OPTION") == "1":
                wait_gdb_attach(service_name, pid)
            
            return True

        except Exception as e:
            logger.error(f"拉起服务失败: {service_name}, 错误: {e}")
            return False

    def _build_service_command(self, service_name: str, lang: str, car_type: str = None) -> str:
        """构建服务启动命令"""
        if service_name == 'LCSEngine':
            # ./workspace/solution_filter/FILTER/1/lib/LCSEngine workspace/solution_filter/FILTER/1/BEV_PreCV_Pre.conf cmn
            if not os.path.exists(self.service_commands['LCSEngine']) or not self.config.lcs_config:
                return None
            cmd = [
                self.service_commands['LCSEngine'], 
                self.config.lcs_config, 
                lang
            ]
            
        elif service_name == 'SpeechEngine':
            # ./workspace/solution_filter/FILTER/1/lib/SpeechEnginebin --config workspace/solution_filter/FILTER/1/decoder.conf --lang cmn --log_path workspace/solution_filter/FILTER/1/log
            if not os.path.exists(self.service_commands['SpeechEngine']) or not self.config.lcs_config or not self.config.log_path:
                return None
            cmd = [
                self.service_commands['SpeechEngine'], 
                "--config", self.config.decoder_config, 
                "--lang", lang, 
                "--log_path", self.config.log_path
            ]
            
        elif service_name == 'AIBSServer':
            # ./workspace/solution_filter/FILTER/1/lib/AIBSService --config workspace/solution_filter/FILTER/1/decoder.conf --log_path workspace/solution_filter/FILTER/1/log --lang cmn --car_type "{\"brand\":\"0\"}"
            if not os.path.exists(self.service_commands['AIBSServer']) or not self.config.decoder_config or not car_type or not self.config.log_path:
                return None
            cmd = [
                self.service_commands['AIBSServer'],
                "--config", self.config.decoder_config,
                "--log_path", self.config.log_path, 
                "--lang", lang, 
                "--car_type", car_type
            ]

        elif service_name == 'NissanAIBSService':
            if not os.path.exists(self.service_commands['NissanAIBSService']) or not self.config.decoder_config or not self.config.log_path:
                return None
            cmd = [
                self.service_commands['NissanAIBSService'], 
                self.config.decoder_config, 
                self.config.log_path, 
                lang
            ]
        else:
            return None
            
        return cmd

    def _start_service_process(self, service_name: str, cmd: str) -> bool:
        """启动服务进程"""
        try:
            # 构建日志文件路径
            log_file_path = f"{self.config.log_path}/{service_name}.log"
            
            # 打开日志文件，以追加模式写入（如果文件不存在会自动创建）
            log_file = open(log_file_path, 'a', encoding='utf-8')
            
            # 将 stdout 和 stderr 都重定向到日志文件
            process = subprocess.Popen(
                cmd, 
                stdout=log_file, 
                stderr=subprocess.STDOUT  # 将 stderr 也重定向到 stdout（即日志文件）
            )
            self.processes[service_name] = process
            self.log_files[service_name] = log_file  # 保存文件对象引用，以便后续关闭
            logger.info(f"服务进程已启动: {service_name}, PID: {process.pid}, 日志文件: {log_file_path}")
            return process.pid
            
        except Exception as e:
            logger.error(f"启动服务进程失败: {service_name}, 错误: {e}")
            return False

    def kill_service(self, service_name: str) -> bool:
        """杀死服务"""
        try:
            if service_name in self.processes:
                process = self.processes[service_name]
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()

                # 关闭日志文件
                if service_name in self.log_files:
                    try:
                        self.log_files[service_name].close()
                    except Exception as e:
                        logger.warning(f"关闭日志文件失败: {service_name}, 错误: {e}")
                    del self.log_files[service_name]

                del self.processes[service_name]
                logger.info(f"成功杀死服务: {service_name}")
                return True
        except Exception as e:
            logger.error(f"杀死服务失败: {service_name}, 错误: {e}")
            return False

    def execute_command(self, command: str) -> bool:
        """执行系统命令 - 直接输出，不捕获"""
        try:
            logger.info(f"执行系统命令: {command}")
            # 直接执行命令，输出直接到终端，不捕获
            subprocess.call(command, shell=True)
            logger.info(f"命令执行成功: {command}")
            return True

        except Exception as e:
            logger.error(f"执行命令失败: {command}, 错误: {e}")
            return False

    def sleep(self, seconds: float):
        """睡眠"""
        logger.info(f"睡眠 {seconds} 秒")
        time.sleep(seconds)

    def print_message(self, message: str):
        """打印消息"""
        logger.success(color(f"[SYS]{message}", 'yellow'))

    def upload_file(self, upload_type: str, file_path: str, *args) -> bool:
        """
        更新文件内容
        
        Args:
            upload_type: 更新 (JSON, LINE, REPLACE, DELETE)
            file_path: 文件路径
            *args: 其他参数，根据类型不同而不同
                - JSON: field_path, new_value
                - LINE: key, new_value
                - REPLACE: old_value, new_value
                - DELETE: key
        
        Returns:
            bool: 是否成功
        """
        try:
            if upload_type == 'JSON':
                if len(args) < 2:
                    logger.error(f"UPLOAD JSON参数不足: 需要file_path, field_path, new_value")
                    return False
                field_path = args[0]
                new_value = args[1]
                return UploadManager.upload_json(file_path, field_path, new_value)
            
            elif upload_type == 'LINE':
                if len(args) < 2:
                    logger.error(f"UPLOAD LINE参数不足: 需要file_path, key, new_value")
                    return False
                key = args[0]
                new_value = args[1]
                return UploadManager.upload_line(file_path, key, new_value)
            
            elif upload_type == 'REPLACE':
                if len(args) < 2:
                    logger.error(f"UPLOAD REPLACE参数不足: 需要file_path, old_value, new_value")
                    return False
                old_value = args[0]
                new_value = args[1]
                return UploadManager.upload_replace(file_path, old_value, new_value)

            elif upload_type == 'DELETE':
                if len(args) < 1:
                    logger.error(f"UPLOAD DELETE参数不足: 需要file_path, key")
                    return False
                key = args[0]
                return UploadManager.upload_delete(file_path, key)
            
            else:
                logger.error(f"不支持的UPLOAD类型: {upload_type}")
                return False

        except Exception as e:
            logger.error(f"上传文件异常: {upload_type}, {file_path}, 错误: {e}")
            return False

    def attach_to_allure(self, attachment_type: str, file_path: str) -> bool:
        """
        将文件添加到Allure报告附件中
        
        Args:
            attachment_type: 附件类型 (TEXT, CSV, JSON等)
            file_path: 文件路径
        
        Returns:
            bool: 是否成功
        """
        try:
            if not os.path.exists(file_path):
                logger.error(f"文件不存在，无法添加到Allure: {file_path}")
                return False

            # 根据类型确定allure附件类型
            if attachment_type.upper() == 'TEXT':
                allure_attachment_type = allure.attachment_type.TEXT
            elif attachment_type.upper() == 'XLSX':
                allure_attachment_type = allure.attachment_type.XLSX
            elif attachment_type.upper() == 'CSV':
                allure_attachment_type = allure.attachment_type.CSV
            elif attachment_type.upper() == 'JSON':
                allure_attachment_type = allure.attachment_type.JSON
            else:
                # 默认为TEXT类型
                allure_attachment_type = allure.attachment_type.TEXT
                logger.warning(f"未知的附件类型: {attachment_type}, 使用TEXT类型")

            # 添加到Allure, 获取文件名作为附件名称
            file_name = os.path.basename(file_path)
            allure.attach.file(source=file_path, name=file_name, attachment_type=allure_attachment_type)

            logger.info(f"成功将文件添加到Allure报告: {file_path}, 类型: {attachment_type}")
            return True

        except Exception as e:
            logger.error(f"添加Allure附件异常: {file_path}, 错误: {e}")
            return False

    def cleanup(self):
        """清理所有进程"""
        for service_name in list(self.processes.keys()):
            self.kill_service(service_name)
