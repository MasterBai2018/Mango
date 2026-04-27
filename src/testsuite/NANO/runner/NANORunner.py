#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2025/09/28
# @Author  : Claude Code
# @File    : NANORunner.py
# @Software: PyCharm
# @Mail    : baihuidong@pachiratech.com
import os
import re
import json
import time
import allure
from pytest import Config
from loguru import logger
from typing import Any, Dict, List, Optional
from src.testsuite.NANO.client.TSRClient import TSRClient
from src.utils.common import color, mango_config, replace_file, timer
from src.testsuite.NANO.dsl_engine import DSLCommand
from src.testsuite.NANO.client.NANOClientManager import NANOClientManager
from src.testsuite.NANO.client.AIBSClient import AIBSClient
from src.testsuite.NANO.client.SpeechEngineClient import SpeechEngineClient
from src.testsuite.NANO.client.CarPlayClient import CarPlayClient
from src.testsuite.NANO.client.PSTTClient import PSTTClientServer
from src.testsuite.NANO.client.AITiTan import TiTanService
from src.testsuite.NANO.client.EcnrClient import ECNRClient
from src.testsuite.NANO.client.PISALLMClient import PISALLMClient
from src.testsuite.NANO.client.TSSClient import TSSClient
from src.testsuite.NANO.dsl_engine import DSLCommand, Status
from src.testsuite.NANO.config import CLIENT_COMMANDS, ENVIRONMENT_VARIABLES
from src.testsuite.NANO.runner.SystemManager import SystemManager
from src.testsuite.NANO.tools.event_parser import NANOEventParser
from src.testsuite.NANO.tools.text2audioRouter import Text2AudioRouter
from src.testsuite.NANO.assertion.AssertionDataManager import AssertionDataManager
from src.testsuite.NANO.assertion.AssertionEngine import AssertionEngine
from src.testsuite.NANO.assertion.AssertionTextReporter import AssertionTextReporter


class NANORunner:
    """NANO执行引擎"""

    def __init__(self, config: Config, assert_data: AssertionDataManager, yaml_config: Dict):
        self.config = config
        self.client_manager = NANOClientManager(config.lib_path, config)
        self.system_manager = SystemManager(config.lib_path, self.config)
        self.tsr_client = TSRClient(config)

        # 新的断言引擎（用于EXP指令）
        self.assertion_engine = AssertionEngine(assert_data, yaml_config)
        
        # 初始化事件解析器（用于INPUTEVENT和CALLBACK指令）
        self.event_parser = None
        self._init_event_parser()
        self.text2audio_router = Text2AudioRouter(config)
        
        # 初始化环境变量缓存（用于调试输出）
        self._env_cache = {}
        logger.debug(f"NANO Runner初始化完成，支持 {len(ENVIRONMENT_VARIABLES)} 个环境变量")

        # 初始化断言文本报告器
        worker_id = os.environ.get('PYTEST_XDIST_WORKER', 'main')
        suite_dir = config.getoption('--mongo_suite_dir')
        if suite_dir:
            report_path = os.path.join(suite_dir, f'result_{worker_id}.txt')
            suite_info = {
                'solution': os.path.basename(config.getoption('--mongo_workspace') or ''),
                'define': config.getoption('--mongo_scene_name') or '',
                'suite_name': config.getoption('--mongo_suite_name') or 'NANO',
                'suite_abstract': config.getoption('--mongo_suite_abstract') or '',
                'mgo': config.getoption('--mongo_case_list') or '',
                'caselist': config.getoption('--mongo_parameterized_data') or '',
            }
            self.reporter = AssertionTextReporter(report_path, suite_info)
            self.assertion_engine.reporter = self.reporter
        else:
            self.reporter = None
    
    def _init_event_parser(self):
        """初始化事件解析器，从mango.ini读取配置"""
        try:
            # 从mango.ini读取事件路径配置
            input_path = mango_config.get_config_value('NANOEvents', 'input')
            callback_path = mango_config.get_config_value('NANOEvents', 'callback')
            # 转换为绝对路径
            root_dir = self.config.getoption('--mongo_root_dir')
            input_path = os.path.join(root_dir, input_path) if not os.path.isabs(input_path) else input_path
            callback_path = os.path.join(root_dir, callback_path) if not os.path.isabs(callback_path) else callback_path
            
            # 创建事件解析器
            self.event_parser = NANOEventParser(input_path, callback_path)
            logger.info(f"事件解析器初始化完成: Input={input_path}, Callback={callback_path}")
        
        except Exception as e:
            logger.warning(f"事件解析器初始化失败: {e}，INPUTEVENT和CALLBACK指令将不可用")
            self.event_parser = None
    
    def cleanup(self):
        """
        清理资源
        
        注意：需要先调用每个 client.free(command) 释放资源，
        然后从 ClientManager 中移除实例
        """
        try:
            # 遍历所有已创建的客户端并释放资源
            for client_type in self.client_manager.get_all_client_types():
                try:
                    client = self.client_manager.get_client(client_type)
                    
                    if client_type not in ["PST", "TIA"]:
                        # 创建临时 DSLCommand 用于资源释放
                        temp_command = DSLCommand(client_type, 'FREE', [], 0)
                        
                        # 调用 client.free() 释放底层引擎资源
                        client.free(temp_command)
                    
                    # 从管理器移除实例
                    self.client_manager.remove_client(client_type)
                    
                except Exception as e:
                    logger.error(f"释放客户端 {client_type} 失败: {e}")
            
            # 清理系统管理器
            self.system_manager.cleanup()
            
            logger.info("NANO执行引擎清理完成")
        except Exception as e:
            logger.error(f"清理资源异常: {e}")

    def _get_eval_globals(self):
        """
        构建EVAL表达式的通用全局执行上下文
        包含：标准库、框架配置、通用工具函数
        """
        import datetime
        import time
        import random
        import uuid
        import json
        import math
        import os
        import re
        from src.utils import common

        # 1. 基础标准库支持
        context = {
            'datetime': datetime,
            'timedelta': datetime.timedelta,
            'time': time,
            'random': random,
            'uuid': uuid,
            'json': json,
            'math': math,
            'os': os,
            're': re,
            'config': self.config, # 注入pytest配置对象
        }

        # 2. 自动注入 src.utils.common 中的所有工具函数
        # 这样未来在common中添加新函数，EVAL里自动就能用，无需改这里
        for name in dir(common):
            if not name.startswith('_'):
                val = getattr(common, name)
                if callable(val):
                    context[name] = val
        
        return context

    def _replace_environment_variables(self, text: str) -> str:
        """
        运行时替换文本中的环境变量
        
        注意：本方法只处理环境变量 {VARIABLE_NAME}，不处理参数化变量 ${variable}
        - 环境变量：{VARIABLE_NAME} - 全大写字母和下划线，运行时替换
        - 动态表达式：{EVAL:expression} - Python表达式，运行时计算
        - 参数化变量：${variable} - 在解析阶段已被替换
        
        支持的格式：
        - {WORKPATH} -> 替换为实际路径
        - {EVAL:now(1)} -> 替换为明天日期
        - {UUID} -> 动态生成UUID
        
        Args:
            text: 包含环境变量的文本
            
        Returns:
            str: 替换后的文本
        """
        if not text or '{' not in text:
            return text
            
        # 匹配环境变量模式 {VARIABLE_NAME} 或 {EVAL:expression}
        # 使用负向前瞻(?<!\$)确保不匹配 ${variable} 格式
        pattern = r'(?<!\$)\{([A-Z_]+|EVAL:[^}]+)\}'
        
        def replace_var(match):
            var_name = match.group(1)

            # 1. 处理通用 {EVAL:expression} 格式
            if var_name.startswith('EVAL:'):
                expression = var_name[5:]  # 去掉 "EVAL:" 前缀
                try:
                    # 获取全功能的上下文环境
                    eval_globals = self._get_eval_globals()
                    
                    # 执行表达式
                    result = eval(expression, eval_globals)
                    logger.debug(f"Eval表达式执行: {{EVAL:{expression}}} -> {result}")
                    return str(result) if result is not None else ''
                except Exception as e:
                    logger.error(f"Eval表达式执行失败: {{EVAL:{expression}}}, 错误: {e}")
                    return f"{{EVAL:{expression}}}"  # 保持原样，方便排查

            if var_name in ENVIRONMENT_VARIABLES:
                try:
                    # 从配置获取值（支持attribute、getoption、dynamic三种方式）
                    access_type, access_param = ENVIRONMENT_VARIABLES[var_name]
                    
                    if access_type == 'attribute':
                        # 直接获取pytestconfig的属性
                        var_value = getattr(self.config, access_param, None)
                    elif access_type == 'getoption':
                        # 通过getoption获取命令行参数
                        var_value = self.config.getoption(access_param, default=None)
                    elif access_type == 'dynamic':
                        # 调用动态生成函数
                        if callable(access_param):
                            var_value = access_param()
                            # 动态变量每次都生成新值，记录日志
                            logger.debug(f"环境变量动态生成: {{{var_name}}} -> {var_value}")
                        else:
                            logger.error(f"动态环境变量 {var_name} 的生成器不是可调用对象")
                            return f"{{{var_name}}}"
                    elif access_type == 'environ':
                        # 从 os.environ 读取（由父进程通过 suite_env 注入）
                        import os as _os
                        var_value = _os.environ.get(access_param)
                    else:
                        logger.error(f"未知的访问类型: {access_type}")
                        return f"{{{var_name}}}"
                    
                    if var_value is not None:
                        # 转换为字符串并统一路径分隔符
                        result = str(var_value).replace('\\', '/')
                        # 非动态变量缓存用于调试（避免重复输出日志）
                        if access_type != 'dynamic':
                            if var_name not in self._env_cache or self._env_cache[var_name] != result:
                                self._env_cache[var_name] = result
                                logger.debug(f"环境变量替换: {{{var_name}}} -> {result}")
                        return result
                    else:
                        logger.warning(f"环境变量 {var_name} 的值为空（{access_type}: {access_param}）")
                        return f"{{{var_name}}}"  # 保持原样
                except Exception as e:
                    logger.error(f"获取环境变量 {var_name} 失败: {e}")
                    return f"{{{var_name}}}"  # 保持原样
            else:
                # 不应该到这里，因为解析阶段已经验证过
                logger.warning(f"未定义的环境变量: {var_name}")
                return f"{{{var_name}}}"  # 保持原样
        
        result = re.sub(pattern, replace_var, text)
        return result
    
    def _replace_command_env_variables(self, command: DSLCommand):
        """
        替换DSLCommand中所有参数的环境变量
        
        Args:
            command: DSL指令对象（会原地修改params）
        """
        # 替换所有参数中的环境变量
        for i, param in enumerate(command.params):
            replaced_param = self._replace_environment_variables(param)
            if replaced_param != param:
                command.params[i] = replaced_param

    def execute_case(self, case_name: str, commands: List[DSLCommand], dsl_case=None) -> dict:
        """执行单个DSL用例"""
        try:
            # 添加报告信息
            if self.reporter and dsl_case:
                self.reporter.begin_case(dsl_case)

            if not commands or len(commands) == 0:
                logger.error(f"DSL用例中没有找到指令: {case_name}, commands: {commands}")
                return False

            # 逐个执行指令
            for command in commands:
                self._execute_command(command)
                # 记录指令执行信息到Allure
                self._record_command_to_allure(command)
                if command.status != Status.PASSED:
                    logger.error(f"指令执行失败: {command.message}")
            
            # Case执行结束，提交日志断言的指针 确保下一个Case从当前Case结束的地方开始读取日志
            self.assertion_engine.commit_log_pointers()

            if self.reporter and dsl_case:
                self.reporter.flush_case()

        except Exception as e:
            logger.error(f"执行单个DSL用例异常: {e}")
            self.assertion_engine.commit_log_pointers()
            return False

    def _execute_command(self, command: DSLCommand) -> dict:
        """执行单个指令"""
        try:
            # 在执行前替换环境变量
            self._replace_command_env_variables(command)

            if not (command.client_type == 'SYS' and command.command == 'PRINT'):
                logger.success(color(f"[{command.client_type}]{command.command} {' '.join(command.params)}", 'yellow'))

            if command.command == 'TEXT_DATA':
                self._execute_text_data_command(command)
                return
            if command.client_type == 'SYS':
                self._execute_sys_command(command)
            elif command.client_type == 'EXP':
                self._execute_exp_command(command)
            elif command.client_type in ['TSA', 'SET', 'VOI', 'TTS', 'OMS']:
                self._execute_aibs_client_command(command)
                self.assertion_engine.assert_data.add_api_call_data(command)
            elif command.client_type in ['NIS', 'NSE']:
                self._execute_nissan_client_command(command)
                self.assertion_engine.assert_data.add_api_call_data(command)
            elif command.client_type == 'HWK':
                self._execute_speech_engine_client_command(command)
                self.assertion_engine.assert_data.add_api_call_data(command)
            elif command.client_type == 'PST':
                self._execute_pst_command(command)
                self.assertion_engine.assert_data.add_api_call_data(command)
            elif command.client_type == 'TIA':
                self._execute_titan_command(command)
            elif command.client_type == 'CPL':
                self._execute_carplay_client_command(command)
                self.assertion_engine.assert_data.add_api_call_data(command)
            elif command.client_type == 'ENR':
                self._execute_ecnr_command(command)
            elif command.client_type == 'TSR':
                self.tsr_client.execute_command(command)
            elif command.client_type == 'PIS':
                self._execute_pis_command(command)
            elif command.client_type == 'TSS':
                self._execute_tss_command(command)
            else:
                command.status = Status.ERROR
                command.message = f'[Running Error] 不支持的客户端类型: {command.client_type}'

        except Exception as e:
            logger.error(f"指令执行异常: {e}")
            return {
                'success': False,
                'error': str(e),
                'command': f"[{command.client_type}]{command}"
            }

    def _parse_text_data_command_params(self, command: DSLCommand) -> Dict[str, Any]:
        """解析 TEXT_DATA 参数。"""
        parsed: Dict[str, Any] = {
            "text": "",
            "lang": None,
            "engine": "auto",
            "frame": None,
            "delay": None,
            "range": None,
            "abstime": None,
            "extra_params": [],
        }

        for token in command.params:
            if '=' not in token:
                continue
            key, value = token.split('=', 1)
            key = key.strip().lower()
            value = value.strip()

            if key == 'text':
                parsed['text'] = value
            elif key == 'lang':
                parsed['lang'] = value
            elif key == 'engine':
                parsed['engine'] = value
            elif key == 'frame':
                parsed['frame'] = value
            elif key == 'delay':
                parsed['delay'] = value
            elif key == 'range':
                parsed['range'] = value
            else:
                parsed['extra_params'].append(token)

        if not parsed["text"]:
            raise ValueError("TEXT_DATA 缺少必填参数 text")
        return parsed

    @staticmethod
    def _copy_command_result(src_command: DSLCommand, dst_command: DSLCommand):
        """将内部指令结果同步回原始指令。"""
        src_command.status = dst_command.status
        src_command.return_code = dst_command.return_code
        src_command.message = dst_command.message

    def _execute_text_data_command(self, command: DSLCommand):
        """执行 TEXT_DATA：文本转音频后内部转 DATA。"""
        try:
            parsed = self._parse_text_data_command_params(command)
            audio_path, engine_used = self.text2audio_router.synthesize(
                text=parsed["text"],
                lang=parsed["lang"],
                engine=parsed["engine"],
            )
            logger.success(color(f'[TTS] [>>>合成>>>][{engine_used}] {audio_path} :\t{parsed["text"]}', 'green'))

            # 构造内部 DATA 命令，复用既有音频链路
            data_params = [audio_path]
            if parsed["frame"] is not None:
                data_params.append(f"frame={parsed['frame']}")
            if parsed["delay"] is not None:
                data_params.append(f"delay={parsed['delay']}")
            if parsed["range"] is not None:
                data_params.append(f"range={parsed['range']}")
            if parsed["abstime"] is not None:
                data_params.append(f"abstime={parsed['abstime']}")
            data_params.extend(parsed["extra_params"])

            data_command = DSLCommand(command.client_type, 'DATA', data_params, command.timeout)

            if command.client_type in ['TSA', 'SET', 'VOI', 'TTS', 'OMS']:
                self._execute_aibs_client_command(data_command)
            elif command.client_type in ['NIS', 'NSE']:
                self._execute_nissan_client_command(data_command)
            elif command.client_type == 'HWK':
                self._execute_speech_engine_client_command(data_command)
            elif command.client_type == 'PST':
                self._execute_pst_command(data_command)
            elif command.client_type == 'TIA':
                self._execute_titan_command(data_command)
            elif command.client_type == 'PIS':
                self._execute_pis_command(data_command)
            elif command.client_type == 'TSS':
                self._execute_tss_command(data_command)
            else:
                raise ValueError(f"客户端 {command.client_type} 不支持 TEXT_DATA")

            self._copy_command_result(command, data_command)
            # 追加可观测信息，便于排查当前使用的引擎和落盘音频
            detail = f"text_data(engine={engine_used}, audio={audio_path})"
            if command.message:
                command.message = f"{detail}; {command.message}"
            else:
                command.message = detail

            # 保持历史行为：音频类客户端调用后写入断言数据
            if command.client_type in ['TSA', 'SET', 'VOI', 'TTS', 'OMS', 'NIS', 'NSE', 'HWK', 'PST']:
                self.assertion_engine.assert_data.add_api_call_data(command)

        except Exception as e:
            command.status = Status.ERROR
            command.message = f"[Running Error] TEXT_DATA 执行失败: {e}"

    def _execute_sys_command(self, command: DSLCommand):
        """执行SYS指令"""
        try:
            command.status = Status.PASSED
            # 拉起服务进程命令
            if command.command == 'PULL':
                service_name = command.params[0]
                lang = command.params[1] if len(command.params) > 1 else "cmn"

                # 这里CarType只能是字符串: {"brand":"0","device_name":"070D"} 或者 {"brand":"0"}
                car_type = command.params[2] if len(command.params) > 2 else None
                self.config.car_type = car_type if car_type else self.config.car_type
                success = self.system_manager.pull_service(service_name, lang, car_type)
                if not success:
                    command.status = Status.FAILED

            # 杀死服务进程命令
            elif command.command == 'KILL':
                service_name = command.params[0]
                success = self.system_manager.kill_service(service_name)
                if not success:
                    command.status = Status.FAILED

            # 睡眠命令
            elif command.command == 'SLEEP':
                seconds = float(command.params[0])
                self.system_manager.sleep(seconds)
                command.status = Status.PASSED

            # 执行系统命令
            elif command.command == 'CMD':
                cmd = ' '.join(command.params)
                success = self.system_manager.execute_command(cmd)
                if not success:
                    command.status = Status.FAILED

            # 打印消息
            elif command.command == 'PRINT':
                message = ' '.join(command.params)
                self.system_manager.print_message(message)
                command.status = Status.PASSED

            # 设置系统环境变量
            elif command.command == 'ENV':
                param_str = ' '.join(command.params)
                if '=' in param_str:
                    key, value = param_str.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    # 去除 value 外层的单引号或双引号
                    if len(value) >= 2:
                        if (value[0] == '"' and value[-1] == '"') or (value[0] == "'" and value[-1] == "'"):
                            value = value[1:-1]
                    if key:
                        os.environ[key] = value
                        command.status = Status.PASSED
                    else:
                        command.status = Status.ERROR
                        command.message = '[Running Error] ENV指令key不能为空'
                else:
                    command.status = Status.ERROR
                    command.message = f'[Running Error] ENV指令格式错误，需要 key=value: {param_str}'

            # 上传/更新文件内容
            elif command.command == 'UPLOAD':
                if len(command.params) < 3:
                    command.status = Status.ERROR
                    command.message = f'[Running Error] UPLOAD指令参数不足: {command.params}'
                else:
                    upload_type = command.params[0]
                    file_path = command.params[1]
                    # 剩余参数传递给upload_file方法
                    args = command.params[2:]
                    success = self.system_manager.upload_file(upload_type, file_path, *args)
                    if not success:
                        command.status = Status.FAILED
                        command.message = f'[Running Error] UPLOAD指令执行失败: {command.params}'
                    else:
                        command.status = Status.PASSED

            # 添加Allure附件
            elif command.command == 'ALLURE':
                if len(command.params) < 2:
                    command.status = Status.ERROR
                    command.message = f'[Running Error] ALLURE指令参数不足: {command.params}'
                else:
                    attachment_type = command.params[0]
                    file_path = command.params[1]
                    success = self.system_manager.attach_to_allure(attachment_type, file_path)
                    if not success:
                        command.status = Status.FAILED
                        command.message = f'[Running Error] ALLURE指令执行失败: {command.params}'
                    else:
                        command.status = Status.PASSED

            # 随机打包文件 (FOTA专用)
            elif command.command == 'FOTA_RANDOM_ZIP':
                # 参数: source_dir target_zip count [zip_root] [mode]
                if len(command.params) < 3:
                    command.status = Status.ERROR
                    command.message = f'[Running Error] FOTA_RANDOM_ZIP指令参数不足: {command.params}, 至少需要 source_dir target_zip count'
                else:
                    from src.utils.common import pack_random_files
                    
                    source_dir = command.params[0]
                    target_zip = command.params[1]
                    count = int(command.params[2])
                    zip_root = command.params[3] if len(command.params) > 3 else None
                    mode = command.params[4] if len(command.params) > 4 else "normal"
                    
                    success = pack_random_files(source_dir, target_zip, count, zip_root, mode)
                    if not success:
                        command.status = Status.FAILED
                        command.message = f'[Running Error] FOTA_RANDOM_ZIP打包失败: {command.params}'
                    else:
                        command.status = Status.PASSED

            # 设置Case简介到Allure报告
            elif command.command == 'BREF':
                if len(command.params) < 1:
                    command.status = Status.ERROR
                    command.message = f'[Running Error] BREF指令参数不足: {command.params}, 至少需要1个参数（Case简介）'
                else:
                    # 获取Case简介（支持多个参数拼接，用空格连接）
                    case_brief = ' '.join(command.params)
                    try:
                        allure.dynamic.description(case_brief)
                        command.status = Status.PASSED
                    except Exception as e:
                        command.status = Status.FAILED
                        command.message = f'[Running Error] BREF指令执行失败: {str(e)}'

            # 清空断言上下文
            elif command.command == 'CLEAR_ASSERT':
                try:
                    # 获取清空类型参数，默认为ALL
                    clear_type = command.params[0].upper() if command.params else 'ALL'
                    
                    if clear_type == 'ALL':
                        # 清空所有断言数据
                        self.assertion_engine.assert_data.clear_case_data()
                        logger.info("已清空所有断言上下文数据")
                    elif clear_type == 'CALLBACK':
                        # 只清空回调数据
                        self.assertion_engine.assert_data.clear_callback_data()
                        logger.info("已清空所有回调断言数据")
                    elif clear_type == 'API':
                        # 只清空API数据
                        self.assertion_engine.assert_data.clear_api_data()
                        logger.info("已清空所有API断言数据")
                    else:
                        # 按特定类型清空（可能是回调类型如ASRResult，也可能是API类型如GET_VERSION_RET）
                        # 尝试清空回调和API两种类型
                        self.assertion_engine.assert_data.clear_callback_data(clear_type)
                        self.assertion_engine.assert_data.clear_api_data(clear_type)
                        logger.info(f"已清空指定类型断言数据: {clear_type}")
                    
                    command.status = Status.PASSED
                except Exception as e:
                    command.status = Status.FAILED
                    command.message = f'[Running Error] CLEAR_ASSERT指令执行失败: {str(e)}'

            # 不支持的指令
            else:
                command.status = Status.ERROR
                command.message = f'[Running Error] 不支持的SYS指令: {command.command}'

            if command.status == Status.FAILED:
                command.message = f'[Running Error] [{command.client_type}] {command.command} failed.'

        except Exception as e:
            command.status = Status.ERROR
            command.message = f'[Running Error] Running {command.command} failed: {str(e)}'

    def _execute_exp_command(self, command: DSLCommand):
        """执行EXP断言指令"""
        try:
            if command.command not in CLIENT_COMMANDS['EXP']:
                command.status = Status.ERROR
                command.message = f'[Running Error] 不支持的EXP指令: {command.command}'
                return
            
            if len(command.params) < 1:
                command.status = Status.ERROR
                command.message = f'[Running Error] EXP断言参数错误: command:{command.command} params:{command.params}'
                return
            
            # 完整的断言语句，如 "[EXP]cloudASRResult [0]asr:把空调启动;lang:cmn"
            self.assertion_engine.do_assertion(command)
            command.status = Status.PASSED
        except Exception as e:
            command.status = Status.ERROR
            command.message = f'[Running Error] Running EXP {command.command} failed: {str(e)}'
    
    def _input_event(self, command: DSLCommand) -> dict:
        """
        处理INPUTEVENT指令
        格式: [TSA]INPUTEVENT event_name [path1:value1;path2:value2]
        
        Args:
            command: DSL命令对象
            
        Example:
            [TSA]INPUTEVENT AppStatus
            [TSA]INPUTEVENT AppStatus app.status:-2
            [TSA]INPUTEVENT AppStatus data.AppStoreGBookStatus:-2;source:TSA2
        """
        try:
            # 检查事件解析器是否初始化
            if not self.event_parser:
                command.status = Status.ERROR
                command.message = f'[Running Error] 事件解析器未初始化，无法使用INPUTEVENT指令'
                logger.error(command.message)
                return
            
            # 参数检查
            if len(command.params) < 1:
                command.status = Status.ERROR
                command.message = f'[Running Error] INPUTEVENT指令参数不足，至少需要事件名称, command: {command}'
                logger.error(command.message)
                return

            event_name = command.params[0]
            modifications = command.params[1] if len(command.params) > 1 else None
            
            # 获取事件JSON（带修改）
            try:
                event_json = self.event_parser.get_input_event(event_name, modifications)
                logger.info(f"获取InputEvent成功: {event_name}, 修改参数: {modifications}")
            except ValueError as e:
                command.status = Status.ERROR
                command.message = f'[Running Error] 获取InputEvent失败: {e}'
                logger.error(command.message)
                return
            
            # 通过EVENT接口发送给引擎
            client: AIBSClient = self.client_manager.get_client(command.client_type)
            ret = client.internal_event(event_json)
            
            command.return_code = ret
            command.status = Status.PASSED
            logger.info(f"INPUTEVENT指令执行成功: {event_name}, 返回码: {ret}")

        except Exception as e:
            logger.error(f"INPUTEVENT指令执行异常: {e}, command: {command}")
            command.status = Status.ERROR
            command.message = f'[Running Error] INPUTEVENT指令执行异常: {e}, command: {command}'

    def _callback_event(self, command: DSLCommand) -> dict:
        """
        处理CALLBACK指令
        格式: [TSA]CALLBACK event_name [path1:value1;path2:value2]
              [TSA]CALLBACK default [path1:value1;path2:value2]
        
        Args:
            command: DSL命令对象
            
        Example:
            [TSA]CALLBACK NaviCallBackDir
            [TSA]CALLBACK NaviCallBackDir data.text:111;status.abc:233
            [TSA]CALLBACK default data.text:111
        """
        try:
            # 检查事件解析器是否初始化
            if not self.event_parser:
                command.status = Status.ERROR
                command.message = f'[Running Error] 事件解析器未初始化，无法使用CALLBACK指令'
                logger.error(command.message)
                return
            
            # 参数检查
            if len(command.params) < 1:
                command.status = Status.ERROR
                command.message = f'[Running Error] CALLBACK指令参数不足，至少需要事件名称或default, command: {command}'
                logger.error(command.message)
                return

            callback_name = command.params[0]
            modifications = command.params[1] if len(command.params) > 1 else None

            client: AIBSClient = self.client_manager.get_client(command.client_type)
            if callback_name == "default":
                ctrl_cls = type(client)
                callback_name = ctrl_cls.dirCallbackType
                if not callback_name or callback_name in ["", None, "NULL", "None", "none", "Null"]:
                    command.status = Status.ERROR
                    command.message = (
                        f'[Running Error] CALLBACK default 需要 NLPResult 已写入 {ctrl_cls.__name__}.dirCallbackType，当前为空'
                    )
                    logger.error(command.message)
                    return
                logger.info(f"CALLBACK使用default，事件名来自 {ctrl_cls.__name__}.dirCallbackType: {callback_name}")

            # 获取事件JSON（带修改）
            try:
                event_json = self.event_parser.get_callback_event(callback_name, modifications)
                logger.debug(f"获取CallbackEvent成功: {callback_name}, 修改参数: {modifications}")
                logger.debug(f"  事件内容: {json.dumps(event_json, ensure_ascii=False)}")
            except ValueError as e:
                command.status = Status.ERROR
                command.message = f'[Running Error] 获取CallbackEvent失败: {e}'
                logger.error(command.message)
                return
            
            ret = client.internal_event(event_json)
            
            command.return_code = ret
            command.status = Status.PASSED
            logger.debug(f"CALLBACK指令执行成功: {callback_name}, 返回码: {ret}")

        except Exception as e:
            logger.error(f"CALLBACK指令执行异常: {e}, command: {command}")
            command.status = Status.ERROR
            command.message = f'[Running Error] CALLBACK指令执行异常: {e}, command: {command}'

    def _execute_aibs_client_command(self, command: DSLCommand) -> dict:
        """
        执行TSA/SET/VOI/OMS/TTS客户端指令
        
        职责：
        1. 特殊处理 CREATE 指令（提供默认配置）
        2. 特殊处理 FREE 指令（释放后移除实例）
        3. 其他指令直接路由到 Client 的对应方法
        
        注意：所有参数解析和业务逻辑都在 Client 层完成
        """
        try:
            # 🎯 特殊处理：CREATE 指令
            if command.command == 'CREATE':
                # 提供默认配置（如果参数只有 lang 和 appid）
                if len(command.params) == 2:
                    command.params.append(self.config.decoder_config)
                
                # 创建或获取客户端实例
                client: AIBSClient = self.client_manager.create_client(command.client_type)
                
                # 调用 client.create() 方法
                client.create(command)
                return
            
            # 🎯 特殊处理：FREE 指令
            if command.command == 'FREE':
                client: AIBSClient = self.client_manager.get_client(command.client_type)
                
                # 调用 client.free() 方法
                client.free(command)

                # 从管理器中移除
                self.client_manager.remove_client(command.client_type)
                return
            
            # 🎯 获取客户端实例（其他指令都需要已创建的客户端）
            try:
                client: AIBSClient = self.client_manager.get_client(command.client_type)
            except ValueError as e:
                command.status = Status.ERROR
                command.message = f'客户端 {command.client_type} 未创建，请先执行 CREATE 指令'
                logger.error(command.message)
                return
            
            # ========== 特殊指令 - NLU测试专用 ==========
            if command.command == 'INPUTEVENT':
                self._input_event(command)
            elif command.command == 'CALLBACK':
                self._callback_event(command)
            
            # 🎯 路由到客户端的对应方法（显式映射，清晰明确）
            # ========== 基础指令 ==========
            elif command.command == 'START':
                client.start(command)
            elif command.command == 'STOP':
                client.stop(command)
            elif command.command == 'EVENT':
                client.event(command)
            elif command.command == 'DATA':
                client.data(command)
            elif command.command == 'CANCEL':
                client.cancel(command)
            
            # ========== 扩展指令 - 引擎控制 ==========
            elif command.command == 'FREEWAKEUP':
                client.free_wakeup(command)
            elif command.command == 'PARALLELSR':
                client.parallelSR(command)
            elif command.command == 'TEXT':
                client.send_text(command)
            elif command.command == 'STRATEGY':
                client.set_strategy(command)
            elif command.command == 'SETVRCONFIG':
                ret = client.set_vr_config(command)
                if command.params[0] == "WAKEUP_ALIAS":
                    result = {"setVRWakeupAliasCode": ret}
                    self.assertion_engine.assert_data.add_callback_data(
                        command.client_type,
                        Status.PASSED,
                        result,
                        0,
                        'VRConfig'
                    )
            elif command.command == 'PAUSE':
                client.pause(command)
            elif command.command == 'RESUME':
                client.resume(command)
            elif command.command == 'GET_VERSION':
                client.get_version(command)
            
            # ========== 扩展指令 - 系统设置 ==========
            elif command.command == 'CAR_TYPE':
                client.set_car_type(command)
            elif command.command == 'LOG_PATH':
                client.set_log_path(command)
            elif command.command == 'MIC_STATUS':
                client.set_mic_status(command)
            elif command.command == 'VR_STATUS':
                client.set_vr_status(command)
            elif command.command == 'LINK_TYPE':
                client.set_link_type(command)
            elif command.command == 'VREVENT':
                client.set_vr_event(command)
            
            # ========== 扩展指令 - 录音功能 ==========
            elif command.command == 'START_RECORD':
                client.start_record(command)
            elif command.command == 'STOP_RECORD':
                client.stop_record(command)
            
            # ========== 扩展指令 - 语音输入 ==========
            elif command.command == 'OPEN_VOICE_INPUT':
                client.open_voice_input(command)
            elif command.command == 'CLOSE_VOICE_INPUT':
                client.close_voice_input(command)
            
            # ========== 扩展指令 - 配置管理 ==========
            elif command.command == 'CLEAR_VR_CONFIG':
                client.clear_vr_config(command)
            elif command.command == 'GET_FOTA_STATUS':
                client.get_fota_status(command)
            elif command.command == 'SET_PARAM':
                client.set_param(command)
            elif command.command == 'UPDATE_PERSONALIZED':
                client.update_personalized_info(command)
            elif command.command == 'SET_TTS_STATE':
                client.set_tts_state(command)
            elif command.command == 'SET_PAGE_INTENT':
                client.set_page_intent(command)
            elif command.command == 'SET_LANGUAGE_MODE':
                client.set_language_mode(command)
            elif command.command == 'SET_WAKEUP_WORD':
                client.set_wakeup_word(command)
            elif command.command == 'SET_WAKEUP_ENABLE':
                client.set_wakeup_word_enable(command)
            elif command.command == 'GET_WAKEUP_WORD':
                client.get_wakeup_word(command)
            elif command.command == 'SET_WORKMODE':
                client.set_workmode(command)
            elif command.command == 'GET_VR_CONFIG':
                result = client.get_vr_config(command)
                self.assertion_engine.assert_data.add_callback_data(
                    command.client_type, 
                    Status.PASSED, 
                    result, 
                    0, 
                    'VRConfig'
                )
            
            # ========== 扩展指令 - 声纹功能 ==========
            elif command.command == 'START_SPEAKER_ENROLL':
                client.start_speaker_enroll(command)
            elif command.command == 'END_SPEAKER_ENROLL':
                client.end_speaker_enroll(command)
            elif command.command == 'RECOGNIZE_SPEAKER':
                client.recognize_speaker(command)
            elif command.command == 'VOICEPRINT_LOGIN':
                client.voiceprint_login(command)
            elif command.command == 'VERIFY_VOICEPRINT':
                client.verify_voiceprint(command)
            elif command.command == 'CANCEL_VERIFY_VOICEPRINT':
                client.cancel_verify_voiceprint(command)
            elif command.command == 'DELETE_SPEAKER':
                client.delete_speaker(command)
            elif command.command == 'GET_SPEAKER_INFO':
                client.get_speaker_info(command)
            elif command.command == 'GET_SPEAKERS':
                client.get_registered_speakers(command)
            elif command.command == 'GET_ENROLL_TEXT':
                client.get_enroll_text(command)
            elif command.command == 'SENSITIVE_WORD_CHECK':
                client.sensitive_word_check(command)
            elif command.command == 'REGISTER_VOICEPRINT_LIST':
                client.register_voiceprint_list(command)
            
            # ========== 扩展指令 - 其他功能 ==========
            elif command.command == 'GET_CONFIG_ITEM':
                client.get_config_item(command)
            elif command.command == 'WRITE_LOG':
                client.write_log(command)
            elif command.command == 'CONFIG_VOICELOG':
                client.config_voicelog(command)
            elif command.command == 'SET_VOICELOG_PATH':
                client.set_voicelog_path(command)
            elif command.command == 'HMI':
                client.hmi(command)
            
            else:
                command.status = Status.ERROR
                command.message = f'[Running Error] 不支持的客户端指令: {command.command}'
                logger.error(command.message)

        except Exception as e:
            command.status = Status.ERROR
            command.message = f'[Running Error] 执行客户端指令异常: {e}, command: {command}'
            logger.error(f"指令执行异常: {e}, command: {command}")
    

    def _execute_nissan_client_command(self, command: DSLCommand) -> dict:
        """
        执行NISSAN日产测试客户端指令
        
        职责：
        1. 特殊处理 CREATE 指令（提供默认配置）
        2. 特殊处理 FREE 指令（释放后移除实例）
        3. 其他指令直接路由到 Client 的对应方法
        
        注意：所有参数解析和业务逻辑都在 Client 层完成
        """
        try:
            # 🎯 特殊处理：CREATE 指令
            if command.command == 'CREATE':
                # 提供默认配置（如果参数只有 lang 和 appid）
                if len(command.params) == 2:
                    command.params.append(self.config.decoder_config)
                
                # 创建或获取客户端实例
                client: AIBSClient = self.client_manager.create_client(command.client_type)
                
                # 调用 client.create() 方法
                client.create(command)
                return
            
            # 🎯 特殊处理：FREE 指令
            if command.command == 'FREE':
                client: AIBSClient = self.client_manager.get_client(command.client_type)
                
                # 调用 client.free() 方法
                client.free(command)

                # 从管理器中移除
                self.client_manager.remove_client(command.client_type)
                return
            
            # 🎯 获取客户端实例（其他指令都需要已创建的客户端）
            try:
                client: AIBSClient = self.client_manager.get_client(command.client_type)
            except ValueError as e:
                command.status = Status.ERROR
                command.message = f'客户端 {command.client_type} 未创建，请先执行 CREATE 指令'
                logger.error(command.message)
                return
            
            # ========== 特殊指令 - NLU测试专用 ==========
            if command.command == 'INPUTEVENT':
                self._input_event(command)
            elif command.command == 'CALLBACK':
                self._callback_event(command)
            
            # 🎯 路由到客户端的对应方法（显式映射，清晰明确）
            # ========== 基础指令 ==========
            elif command.command == 'START':
                client.start(command)
            elif command.command == 'STOP':
                client.stop(command)
            elif command.command == 'EVENT':
                client.event(command)
            elif command.command == 'DATA':
                client.data(command)
            elif command.command == 'CANCEL':
                client.cancel(command)
            
            # ========== 扩展指令 - 引擎控制 ==========
            elif command.command == 'FREEWAKEUP':
                client.free_wakeup(command)
            elif command.command == 'TEXT':
                client.send_text(command)
            elif command.command == 'STRATEGY':
                client.set_strategy(command)
            elif command.command == 'SETVRCONFIG':
                client.set_vr_config(command)
            elif command.command == 'PAUSE':
                client.pause(command)
            elif command.command == 'RESUME':
                client.resume(command)
            elif command.command == 'GET_VERSION':
                client.get_version(command)
            
            # ========== 扩展指令 - 系统设置 ==========
            elif command.command == 'CAR_TYPE':
                client.set_car_type(command)
            elif command.command == 'LOG_PATH':
                client.set_log_path(command)
            elif command.command == 'MIC_STATUS':
                client.set_mic_status(command)
            elif command.command == 'VR_STATUS':
                client.set_vr_status(command)
            elif command.command == 'LINK_TYPE':
                client.set_link_type(command)
            elif command.command == 'VREVENT':
                client.set_vr_event(command)
            
            # ========== 扩展指令 - 录音功能 ==========
            elif command.command == 'START_RECORD':
                client.start_record(command)
            elif command.command == 'STOP_RECORD':
                client.stop_record(command)
            
            # ========== 扩展指令 - 语音输入 ==========
            elif command.command == 'OPEN_VOICE_INPUT':
                client.open_voice_input(command)
            elif command.command == 'CLOSE_VOICE_INPUT':
                client.close_voice_input(command)
            
            # ========== 扩展指令 - 配置管理 ==========
            elif command.command == 'CLEAR_VR_CONFIG':
                client.clear_vr_config(command)
            elif command.command == 'GET_FOTA_STATUS':
                client.get_fota_status(command)
            elif command.command == 'SET_PARAM':
                client.set_param(command)
            elif command.command == 'UPDATE_PERSONALIZED':
                client.update_personalized_info(command)
            elif command.command == 'SET_TTS_STATE':
                client.set_tts_state(command)
            elif command.command == 'SET_PAGE_INTENT':
                client.set_page_intent(command)
            elif command.command == 'SET_LANGUAGE_MODE':
                client.set_language_mode(command)
            elif command.command == 'SET_WAKEUP_WORD':
                client.set_wakeup_word(command)
            elif command.command == 'SET_WAKEUP_ENABLE':
                client.set_wakeup_word_enable(command)
            elif command.command == 'GET_WAKEUP_WORD':
                client.get_wakeup_word(command)
            elif command.command == 'SET_WORKMODE':
                client.set_workmode(command)
            elif command.command == 'GET_VR_CONFIG':
                result = client.get_vr_config(command)
                logger.success(f">>>>>>>>>{json.dumps(result, ensure_ascii=False)}")
                self.assertion_engine.assert_data.add_callback_data(
                    command.client_type, 
                    Status.PASSED, 
                    result, 
                    0, 
                    'VRConfig'
                )
            
            # ========== 扩展指令 - 声纹功能 ==========
            elif command.command == 'START_SPEAKER_ENROLL':
                client.start_speaker_enroll(command)
            elif command.command == 'END_SPEAKER_ENROLL':
                client.end_speaker_enroll(command)
            elif command.command == 'RECOGNIZE_SPEAKER':
                client.recognize_speaker(command)
            elif command.command == 'VOICEPRINT_LOGIN':
                client.voiceprint_login(command)
            elif command.command == 'VERIFY_VOICEPRINT':
                client.verify_voiceprint(command)
            elif command.command == 'CANCEL_VERIFY_VOICEPRINT':
                client.cancel_verify_voiceprint(command)
            elif command.command == 'DELETE_SPEAKER':
                client.delete_speaker(command)
            elif command.command == 'GET_SPEAKER_INFO':
                client.get_speaker_info(command)
            elif command.command == 'GET_SPEAKERS':
                client.get_registered_speakers(command)
            elif command.command == 'GET_ENROLL_TEXT':
                client.get_enroll_text(command)
            elif command.command == 'SENSITIVE_WORD_CHECK':
                client.sensitive_word_check(command)
            elif command.command == 'REGISTER_VOICEPRINT_LIST':
                client.register_voiceprint_list(command)
            
            # ========== 扩展指令 - 其他功能 ==========
            elif command.command == 'GET_CONFIG_ITEM':
                client.get_config_item(command)
            elif command.command == 'WRITE_LOG':
                client.write_log(command)
            elif command.command == 'CONFIG_VOICELOG':
                client.config_voicelog(command)
            elif command.command == 'SET_VOICELOG_PATH':
                client.set_voicelog_path(command)
            elif command.command == 'HMI':
                client.hmi(command)
            
            else:
                command.status = Status.ERROR
                command.message = f'[Running Error] 不支持的客户端指令: {command.command}'
                logger.error(command.message)

        except Exception as e:
            command.status = Status.ERROR
            command.message = f'[Running Error] 执行客户端指令异常: {e}, command: {command}'
            logger.error(f"指令执行异常: {e}, command: {command}")


    def _execute_speech_engine_client_command(self, command: DSLCommand) -> dict:
        """
        执行HWK(SpeechEngine)客户端指令
        
        职责：
        1. 特殊处理 CREATE 指令（提供默认配置）
        2. 特殊处理 FREE 指令（释放后移除实例）
        3. 其他指令直接路由到 Client 的对应方法
        
        注意：所有参数解析和业务逻辑都在 Client 层完成
        """
        try:
            # 🎯 特殊处理：CREATE 指令
            if command.command == 'CREATE':
                # 创建或获取客户端实例
                client: SpeechEngineClient = self.client_manager.create_client(command.client_type)
                
                # 调用 client.create() 方法，SpeechEngineClient不需要参数，提供默认配置
                client.create(command, self.config.decoder_config, self.config.log_path)
                return
            
            # 🎯 特殊处理：FREE 指令
            if command.command == 'FREE':
                client: SpeechEngineClient = self.client_manager.get_client(command.client_type)
                
                # 调用 client.free() 方法
                client.free(command)

                # 从管理器中移除
                self.client_manager.remove_client(command.client_type)
                return
            
            # 🎯 获取客户端实例（其他指令都需要已创建的客户端）
            try:
                client: SpeechEngineClient = self.client_manager.get_client(command.client_type)
            except ValueError as e:
                command.status = Status.ERROR
                command.message = f'客户端 {command.client_type} 未创建，请先执行 CREATE 指令'
                logger.error(command.message)
                return
            
            # 🎯 路由到客户端的对应方法
            # ========== 基础指令 ==========
            if command.command == 'START':
                client.start(command)
            elif command.command == 'STOP':
                client.stop(command)
            elif command.command == 'DATA':
                client.data(command)
            elif command.command == 'CANCEL':
                client.cancel(command)
            
            # ========== 扩展指令 - 参数设置 ==========
            elif command.command == 'SET_PARAM':
                client.set_param(command)
            elif command.command == 'SET_DATA_TYPE':
                client.set_data_type(command)
            elif command.command == 'HMI':
                client.hmi(command)
            
            # ========== 扩展指令 - 引擎控制 ==========
            elif command.command == 'UPDATE_PERSONALIZED':
                client.update_personalized_info(command)
            elif command.command == 'SET_WORK_MODE':
                client.set_work_mode(command)
            elif command.command == 'SET_TTS_STATE':
                client.set_tts_state(command)
            elif command.command == 'SET_FREETALK_STATE':
                client.set_freetalk_state(command)
            
            # ========== 扩展指令 - 唤醒词管理 ==========
            elif command.command == 'ADD_WAKEUP_WORD':
                client.add_wakeup_word(command)
            elif command.command == 'GET_WAKEUP_TERM':
                client.get_wakeup_term(command)
            elif command.command == 'SET_WAKEUP_ENABLE':
                client.set_wakeup_word_enable(command)
            elif command.command == 'SET_VOICE_WAKEUP_OPTION':
                client.set_voice_wakeup_option(command)
            
            # ========== 扩展指令 - 声纹功能 ==========
            elif command.command == 'SET_SRE_REQUEST':
                client.set_sre_request(command)
            elif command.command == 'SET_SRE_ENABLE_OPTION':
                client.set_sre_enable_option(command)
            
            # ========== 扩展指令 - 语音输入 ==========
            elif command.command == 'OPEN_VOICE_INPUT':
                client.open_voice_input(command)
            elif command.command == 'CLOSE_VOICE_INPUT':
                client.close_voice_input(command)
            
            # ========== 扩展指令 - 语言设置 ==========
            elif command.command == 'SET_LANGUAGE_INFO':
                client.set_language_info(command)
            
            # ========== 扩展指令 - 语音日志 ==========
            elif command.command == 'CONFIG_VOICELOG':
                client.config_voicelog(command)
            elif command.command == 'SET_VOICELOG_PATH':
                client.set_voicelog_path(command)
            
            # ========== 扩展指令 - VR设置 ==========
            elif command.command == 'SET_VR_SILENCE_TIMEOUT':
                client.set_vr_silence_timeout(command)
            
            # ========== 扩展指令 - 系统设置 ==========
            elif command.command == 'SET_LINK_TYPE':
                client.set_link_type(command)
            elif command.command == 'SET_MIC_STATUS':
                client.set_mic_status(command)
            elif command.command == 'SET_CAR_TYPE':
                client.set_car_type(command)
            
            # ========== 扩展指令 - 录音功能 ==========
            elif command.command == 'START_RECORD':
                client.start_record(command)
            elif command.command == 'STOP_RECORD':
                client.stop_record(command)
            
            # ========== 扩展指令 - 敏感词检测 ==========
            elif command.command == 'SENSITIVE_WORD_CHECK':
                client.sensitive_word_check(command)
            
            else:
                command.status = Status.ERROR
                command.message = f'[Running Error] 不支持的HWK客户端指令: {command.command}'
                logger.error(command.message)

        except Exception as e:
            command.status = Status.ERROR
            command.message = f'[Running Error] 执行HWK客户端指令异常: {e}, command: {command}'
            logger.error(f"HWK指令执行异常: {e}, command: {command}")
    
    def _execute_pst_command(self, command: DSLCommand) -> dict:
        """
        执行PST客户端指令
        
        职责：路由PST客户端的指令
        
        注意：PST客户端的逻辑由 PSTTClient 处理
        """
        try:
            # 🎯 特殊处理：CREATE 指令
            if command.command == 'CREATE':
                # 创建或获取客户端实例
                client: PSTTClientServer = self.client_manager.create_client(command.client_type)
                
                # 调用 client.create() 方法
                client.create(command, self.config.decoder_config)
                return
            
            # 🎯 特殊处理：FREE 指令
            if command.command == 'FREE':
                client: PSTTClientServer = self.client_manager.get_client(command.client_type)
                client.free(command)
                self.client_manager.remove_client(command.client_type)
                return
            
            # 🎯 获取客户端实例
            try:
                client: PSTTClientServer = self.client_manager.get_client(command.client_type)
            except ValueError as e:
                command.status = Status.ERROR
                command.message = f'客户端 {command.client_type} 未创建，请先执行 CREATE 指令'
                logger.error(command.message)
                return
            
            # 🎯 路由到客户端的对应方法
            if command.command == 'DATA':
                client.process_single_audio(command)
            elif command.command == 'HMI':
                client.hmi(command)
            elif command.command == 'DATA_QUEUE':
                client.process_audio_list(command)
            else:
                command.status = Status.ERROR
                command.message = f'[Running Error] 不支持的PST客户端指令: {command.command}'
                logger.error(command.message)

        except Exception as e:
            command.status = Status.ERROR
            command.message = f'[Running Error] 执行PST客户端指令异常: {e}, command: {command}'
            logger.error(f"PST指令执行异常: {e}, command: {command}")
    
    def _record_command_to_allure(self, command: DSLCommand):
        """
        记录指令执行信息到Allure报告
        Args:
            command: DSL指令对象
        """
        try:
            if command.client_type == "EXP":
                return

            # 根据执行状态选择图标和颜色
            status_map = {
                Status.PASSED: ("▶️", "成功"),
                Status.FAILED: ("⚠️", "失败"),
                Status.ERROR: ("⚠️", "错误"),
                Status.NOT_RUN: ("⚠️", "未执行")
            }
            
            status_icon, status_text = status_map.get(command.status, ("❓", "未知"))
            
            # 构建指令信息
            command_str = f"[{command.client_type}]   {command.command}"
            params_str = " ".join(command.params) if command.params else ""
            
            # 格式化超时时间显示
            if command.timeout == -1:
                timeout_str = " <timeout=-1(无限等待)>"
            elif command.timeout > 0:
                timeout_str = f" <timeout={command.timeout}>"
            else:
                timeout_str = ""
            
            # 构建步骤标题
            step_title = f"{status_icon} {command_str} {params_str}{timeout_str} - {status_text}"
            
            with allure.step(step_title):
                # 格式化超时设置说明
                if command.timeout == -1:
                    timeout_desc = "无限等待"
                elif command.timeout > 0:
                    timeout_desc = f"{command.timeout}秒"
                else:
                    timeout_desc = "无（立即执行）"
                
                # 构建详细的指令信息
                command_detail = {
                    "客户端类型": command.client_type,
                    "指令名称": command.command,
                    "参数列表": command.params if command.params else [],
                    "执行状态": status_text,
                    "返回码": command.return_code if command.return_code is not None else "N/A",
                    "执行信息": command.message if command.message else "执行完成",
                    "超时设置": timeout_desc
                }
                
                # 如果执行失败或出错，添加错误信息
                if command.status == Status.FAILED or command.status == Status.ERROR:
                    command_detail["错误详情"] = command.message
                
                # 将指令详情作为JSON附件添加到Allure
                allure.attach(
                    json.dumps(command_detail, ensure_ascii=False, indent=2),
                    name=f"指令详情_{command.client_type}_{command.command}",
                    attachment_type=allure.attachment_type.JSON
                )
                
                # 如果是失败或错误状态，额外添加文本信息
                if command.status != Status.PASSED:
                    error_summary = f"指令执行{status_text}: {command_str}"
                    if command.message:
                        error_summary += f"\n错误信息: {command.message}"
                    if command.return_code is not None:
                        error_summary += f"\n返回码: {command.return_code}"
                    
                    allure.attach(
                        error_summary,
                        name="执行结果",
                        attachment_type=allure.attachment_type.TEXT
                    )
                    
        except Exception as e:
            logger.error(f"记录指令到Allure失败: {e}")

    def _execute_titan_command(self, command: DSLCommand) -> dict:
        """
        执行TiTan ASR指令
        
        职责：
        1. 特殊处理 CREATE 指令（创建客户端并加载配置）
        2. 特殊处理 FREE 指令（释放后移除实例）
        3. 其他指令直接路由到 Client 的对应方法
        
        注意：所有参数解析和业务逻辑都在 Client 层完成
        """
        try:
            # 🎯 特殊处理：CREATE 指令
            if command.command == 'CREATE':
                # 创建或获取客户端实例
                client: TiTanService = self.client_manager.create_client(command.client_type)
                
                # 调用 client.create() 方法加载配置
                client.create(command, self.config.decoder_config)
                return
            
            # 🎯 特殊处理：FREE 指令
            if command.command == 'FREE':
                client: TiTanService = self.client_manager.get_client(command.client_type)
                
                # TiTanService 不需要特殊的 free 操作，从管理器中直接移除即可
                self.client_manager.remove_client(command.client_type)
                command.status = Status.PASSED
                command.return_code = 0
                return
            
            # 🎯 获取客户端实例（其他指令都需要已创建的客户端）
            try:
                client: TiTanService = self.client_manager.get_client(command.client_type)
            except ValueError as e:
                command.status = Status.ERROR
                command.message = f'客户端 {command.client_type} 未创建，请先执行 CREATE 指令'
                logger.error(command.message)
                return
            
            # 🎯 路由到客户端的对应方法
            if command.command == 'DATA':
                # 单条音频送数据 参数格式: [音频路径]
                if len(command.params) < 1:
                    command.status = Status.ERROR
                    command.message = f'[{command.client_type}] DATA指令需要音频路径'
                    logger.error(command.message)
                    return
                
                audio_path = command.params[0]
                
                # 解析参数（支持命名参数）
                delay = 0.0
                
                # 解析命名参数
                for param in command.params[1:]:
                    if '=' in param:
                        key, value = param.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        if key == 'delay':
                            delay = float(value)

                result = client.process_single_audio(audio_path, delay)
                
                command.status = Status.PASSED if result else Status.FAILED
                command.message = f"识别结果: {result}" if result else "识别结果为空"
                command.return_code = 0 if result else -1
                
            elif command.command == 'CASELIST':
                # 批量音频送数据 参数格式: [音频列表文件路径]
                if len(command.params) < 1:
                    command.status = Status.ERROR
                    command.message = f'[{command.client_type}] CASELIST指令需要音频列表文件路径'
                    logger.error(command.message)
                    return
                
                caselist_path = command.params[0]

                # 解析命名参数
                delay = 0.0
                thread = 1
                for param in command.params[1:]:
                    if '=' in param:
                        key, value = param.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        if key == 'delay':
                            delay = float(value)
                        if key == 'thread':
                            thread = int(value)

                client.process_audio_list(caselist_path=caselist_path, delay=delay, max_workers=thread)
                
                command.status = Status.PASSED
                command.message = f"批量处理完成: {caselist_path}"
                command.return_code = 0
                
            else:
                command.status = Status.ERROR
                command.message = f'[Running Error] 不支持的TIA客户端指令: {command.command}'
                logger.error(command.message)
                
        except Exception as e:
            command.status = Status.ERROR
            command.message = f'[Running Error] 执行TIA客户端指令异常: {e}, command: {command}'
            logger.error(f"TIA指令执行异常: {e}, command: {command}")

    def _execute_carplay_client_command(self, command: DSLCommand) -> dict:
        """
        执行CarPlay客户端指令
        
        职责：
        1. 特殊处理 CREATE 指令（创建客户端并初始化引擎）
        2. 特殊处理 FREE 指令（释放后移除实例）
        3. 其他指令直接路由到 Client 的对应方法
        
        支持的指令：
        - CREATE: 创建CarPlay引擎
        - STATUS: 设置CarPlay状态
        - FREE: 释放CarPlay引擎
        - AUDIO_OUTPUT: 设置音频输出路径
        - CLOSE_AUDIO_OUTPUT: 关闭音频输出
        """
        try:
            # 🎯 特殊处理：CREATE 指令
            if command.command == 'CREATE':
                # 提供默认配置（如果参数只有 mode 和 lang）
                if len(command.params) == 2:
                    command.params.append(self.config.carplay_config)

                # 创建客户端实例
                client: CarPlayClient = self.client_manager.create_client(command.client_type)
                
                # 调用 client.create() 方法
                client.create(command)
                return
            
            # 🎯 特殊处理：FREE 指令
            if command.command == 'FREE':
                client: CarPlayClient = self.client_manager.get_client(command.client_type)
                
                # 调用 client.free() 方法
                client.free(command)
                
                # 从管理器中移除
                self.client_manager.remove_client(command.client_type)
                return
            
            # 🎯 获取客户端实例（其他指令都需要已创建的客户端）
            try:
                client: CarPlayClient = self.client_manager.get_client(command.client_type)
            except ValueError as e:
                command.status = Status.ERROR
                command.message = f'客户端 {command.client_type} 未创建，请先执行 CREATE 指令'
                logger.error(command.message)
                return

            else:
                command.status = Status.ERROR
                command.message = f'[Running Error] 不支持的CPL客户端指令: {command.command}'
                logger.error(command.message)
                
        except Exception as e:
            command.status = Status.ERROR
            command.message = f'[Running Error] 执行CPL客户端指令异常: {e}, command: {command}'
            logger.error(f"CPL指令执行异常: {e}, command: {command}")

    def _execute_ecnr_command(self, command: DSLCommand) -> dict:
        """
        执行ECNR客户端指令

        职责：路由ECNR客户端的指令

        注意：ECNR客户端的逻辑由 ECNRClient 处理
        """
        try:
            # 🎯 SET_DOWNLINK / AMP_TYPE / ECNR_TYPE（可在 CREATE 之前执行，需先创建 ENR 客户端实例）
            if command.command == 'SET_DOWNLINK':
                try:
                    client: ECNRClient = self.client_manager.get_client(command.client_type)
                except ValueError:
                    client: ECNRClient = self.client_manager.create_client(command.client_type)
                client.set_downlink(command)
                return
            if command.command == 'AMP_TYPE':
                try:
                    client: ECNRClient = self.client_manager.get_client(command.client_type)
                except ValueError:
                    client: ECNRClient = self.client_manager.create_client(command.client_type)
                client.amp_type(command)
                return
            if command.command == 'ECNR_TYPE':
                try:
                    client: ECNRClient = self.client_manager.get_client(command.client_type)
                except ValueError:
                    client: ECNRClient = self.client_manager.create_client(command.client_type)
                client.ecnr_type(command)
                return

            # 🎯 特殊处理：CREATE 指令
            if command.command == 'CREATE':
                # 创建或获取客户端实例
                try:
                    client: ECNRClient = self.client_manager.get_client(command.client_type)
                except ValueError:
                    # 客户端不存在，创建新客户端
                    client: ECNRClient = self.client_manager.create_client(command.client_type)

                # 调用客户端的create方法创建引擎
                client.create(command)
                return
            # 🎯 获取客户端实例
            try:
                client: ECNRClient = self.client_manager.get_client(command.client_type)
            except ValueError as e:
                command.status = Status.ERROR
                command.message = f'客户端 {command.client_type} 未创建，请先执行 CREATE 指令'
                logger.error(command.message)
                return


            # 🎯 特殊处理：FREE 指令
            if command.command == 'FREE':
                client: ECNRClient = self.client_manager.get_client(command.client_type)
                # 调用客户端的free方法释放引擎资源
                client.free(command)
                # 从管理器中移除客户端
                self.client_manager.remove_client(command.client_type)
                return


            # 🎯 路由到客户端的对应方法
            if command.command == 'START':
                client.start(command)
            elif command.command == 'STOP':
                client.stop(command)
            elif command.command == 'SET_PNR_MIC_MUTE_OPTION':
                client.set_pnr_mic_mute_option(command)
            elif command.command == 'SET_PNR_ENABLE_OPTION':
                client.set_pnr_enable_option(command)
            elif command.command == 'SET_PNR_AUDIO_QUALITY':
                client.set_pnr_audio_quality(command)
            elif command.command == 'SET_WORKMODE':
                client.set_work_mode(command)
                self.assertion_engine.assert_data.add_callback_data(
                    command.client_type,
                    Status.PASSED,
                    {"vec": command.vec_name} if command.vec_name else "N/A",
                    0,
                    'ECNR'
                )
            elif command.command == 'GET_PNR_VERSION':
                client.get_pnr_version(command)
                if command.status == Status.PASSED:
                    self.assertion_engine.assert_data.add_callback_data(
                        command.client_type,
                        Status.PASSED,
                        {"version": command.return_code},
                        0,
                        'ECNR'
                    )
            elif command.command == 'GET_PNR_HFT_PARAM':
                client.get_pnr_HFT_param(command)
            elif command.command == 'GET_PNR_MVR_PARAM':
                client.get_pnr_MVR_param(command)
            elif command.command == 'GET_PNR_GEN_PARAM':
                client.get_pnr_Gen_param(command)
            elif command.command == 'DATA':
                client.data(command)
                self.assertion_engine.assert_data.add_callback_data(
                    command.client_type,
                    Status.PASSED,
                    {"md5": command.md5} if command.md5 else "N/A",
                    0,
                    'ECNR'
                )
            elif command.command == 'ANALYZE_AUDIO_DATA':
                result = client.analyze_audio_data(command)
                if command.status == Status.PASSED:
                    self.assertion_engine.assert_data.add_callback_data(
                        command.client_type,
                        Status.PASSED,
                        {"rms": result},
                        0,
                        'ECNR'
                    )
            else:
                command.status = Status.ERROR
                command.message = f'[Running Error] 不支持的ECNR客户端指令: {command.command}'
                logger.error(command.message)

        except Exception as e:
            command.status = Status.ERROR
            command.message = f'[Running Error] 执行ECNR客户端指令异常: {e}, command: {command}'
            logger.error(f"ECNR指令执行异常: {e}, command: {command}")

    def _execute_pis_command(self, command: DSLCommand):
        """
        执行 PIS（PISA 大模型全双工 WebSocket）客户端指令。

        支持指令：
            CREATE — 初始化连接参数（url=, client_id=, video_url=）
            START  — 建立 WebSocket 连接，等待 session.created
            STOP   — 关闭 WebSocket 连接
            FREE   — 清理所有资源并移除客户端实例
            DATA   — 同步阻塞推流（主线程执行，支持 frame/delay/range 参数）
            VEDIO  — 上传关键帧图片到 Video LLM 服务，获取视觉理解结果
            WAIT   — 主线程阻塞等待下行事件或文本（event_type | text=xxx）
            UPDATE — 发送 session.update 更新会话配置
        """
        try:
            # ── 特殊处理：CREATE 指令（可在实例不存在时自动创建）──
            if command.command == 'CREATE':
                client: PISALLMClient = self.client_manager.create_client(command.client_type)
                client.create(command)
                return

            # ── 特殊处理：FREE 指令（释放资源后移除实例）──
            if command.command == 'FREE':
                try:
                    client: PISALLMClient = self.client_manager.get_client(command.client_type)
                except ValueError:
                    logger.warning(f"[PIS] FREE：客户端实例不存在，跳过")
                    command.status = Status.PASSED
                    command.return_code = 0
                    return
                client.free(command)
                self.client_manager.remove_client(command.client_type)
                return

            # ── 获取已创建的客户端实例（其余指令均需要）──
            try:
                client: PISALLMClient = self.client_manager.get_client(command.client_type)
            except ValueError:
                command.status = Status.ERROR
                command.message = f'[PIS] 客户端未创建，请先执行 [PIS]CREATE 指令'
                logger.error(command.message)
                return

            # ── 指令路由 ──
            if command.command == 'AIBSServer':
                client.aibs_server(command, self.config.decoder_config)

            elif command.command == 'AIBS_SET_CARTYPE':
                client.aibs_set_car_type(command)

            elif command.command == 'AIBS_SET_WORK_MODE':
                client.aibs_set_work_mode(command)

            elif command.command == 'AIBS_CREATE':
                client.aibs_create(command, self.config.decoder_config)

            elif command.command == 'AIBS_START':
                client.aibs_start(command)

            elif command.command == 'AIBS_STOP':
                client.aibs_stop(command)

            elif command.command == 'START':
                client.start(command)

            elif command.command == 'STOP':
                client.stop(command)

            elif command.command == 'DATA':
                client.data(command)

            elif command.command == 'WAIT':
                client.wait(command)

            elif command.command == 'UPDATE':
                client.update(command)

            elif command.command == 'VEDIO':
                client.vedio(command)

            else:
                command.status = Status.ERROR
                command.message = f'[PIS] 不支持的指令：{command.command}'
                logger.error(command.message)

        except Exception as e:
            command.status = Status.ERROR
            command.message = f'[Running Error] 执行PIS客户端指令异常: {e}, command: {command}'
            logger.error(f"PIS指令执行异常: {e}, command: {command}")

    def _execute_tss_command(self, command: DSLCommand):
        """
        执行TSS客户端指令

        职责：路由TSS客户端的指令

        注意：TSS客户端的逻辑由 TSSClient 处理
        """
        try:
            # ── 特殊处理：CREATE 指令（可在实例不存在时自动创建）──
            if command.command == 'START_SERVICE':
                client: TSSClient = self.client_manager.create_client(command.client_type)
                client.start_aibs_service(command, self.config.decoder_config)
                return

            # ── 特殊处理：FREE 指令（释放资源后移除实例）──
            if command.command == 'FREE':
                try:
                    client: TSSClient = self.client_manager.get_client(command.client_type)
                except ValueError:
                    logger.warning(f"[TSS] FREE：客户端实例不存在，跳过")
                    command.status = Status.PASSED
                    command.return_code = 0
                    return
                client.free(command)
                self.client_manager.remove_client(command.client_type)
                return

            # ── 获取已创建的客户端实例（其余指令均需要）──
            try:
                client: TSSClient = self.client_manager.get_client(command.client_type)
            except ValueError:
                command.status = Status.ERROR
                command.message = f'[TSS] 客户端未创建，请先执行 [TSS]CREATE 指令'
                logger.error(command.message)
                return

            if command.command == 'CREATE':
                client.create_client(command, self.config.decoder_config)

            elif command.command == 'SET_CARTYPE':
                client.set_car_type(command)

            elif command.command == 'SET_WORK_MODE':
                client.set_work_mode(command)

            elif command.command == 'START':
                client.start_engine(command)
            
            elif command.command == 'DATA':
                client.data(command)
            
            elif command.command == 'SET_PARAM':
                result = client.set_aibs_engine_param(command)
                if result == 0:
                    command.status = Status.PASSED
                    command.return_code = 0
                else:
                    command.status = Status.ERROR
                    command.message = f'[TSS] SET_AIBS_ENGINE_PARAM 失败：set_aibs_engine_param 返回 {result}'
                    logger.error(command.message)
            
            elif command.command == 'SET_LANGUAGE_MODE':
                client.set_language_mode(command)
            
            elif command.command == 'SET_WAKEUP_WORD':
                client.set_wakeup_word(command)

            elif command.command == 'SET_WAKEUP_ENABLE':
                client.set_wakeup_word_online(command)
            
            elif command.command == 'GET_WAKEUP_WORD':
                client.get_wakeup_word(command)
                if command.status == Status.PASSED:
                    self.assertion_engine.assert_data.add_callback_data(
                        command.client_type,
                        status=0,
                        result_data={"result": command.return_code},
                        channel='0',
                        callback_type='TSS',
                    )

            elif command.command == 'STOP':
                client.stop(command)

            elif command.command == 'FREE':
                client.free(command)

        except Exception as e:
            command.status = Status.ERROR
            command.message = f'[Running Error] 执行TSS客户端指令异常: {e}, command: {command}'
            logger.error(f"TSS指令执行异常: {e}, command: {command}")