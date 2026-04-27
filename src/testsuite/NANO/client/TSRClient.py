#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2025/01/16
# @Author  : huidong.bai
# @File    : TSRClient.py
# @Software: PyCharm
# @Mail    : MasterBai2018@outlook.com
"""
TSR (Test Suite Report) 客户端

用于执行 Suite 级别的统计和报告生成，不依赖 NANORunner。
采用装饰器自动注册机制，支持动态扩展新指令。

支持的指令:
    - ASR_ACCURACY: ASR 准确率计算

使用示例:
    [TSR]ASR_ACCURACY result=asr.csv ref=ref.csv output=report.xlsx
"""
import os
import re
from typing import Dict, List, Any, Optional
from loguru import logger

from src.testsuite.NANO.dsl_engine import DSLCommand, Status
from src.testsuite.NANO.config import ENVIRONMENT_VARIABLES
from src.testsuite.NANO.tools.tsr import dispatch_command, get_registered_commands


class TSRClient:
    """
    Test Suite Report 客户端
    
    独立的 Suite 级别统计和报告生成器，使用装饰器自动注册机制。
    """
    
    def __init__(self, config=None):
        """
        初始化 TSR 客户端
        
        Args:
            config: pytest config 对象（用于环境变量替换）
        """
        self.config = config
        self._env_cache = {}  # 环境变量缓存
        self.suite_stats = {}  # Suite 统计信息（由 conftest.py 设置）
        
        # 打印已注册的指令
        registered = get_registered_commands()

    def _replace_environment_variables(self, text: str) -> str:
        """
        运行时替换文本中的环境变量
        
        注意：本方法只处理环境变量 {VARIABLE_NAME}，不处理参数化变量 ${variable}
        - 环境变量：{VARIABLE_NAME} - 全大写字母和下划线，运行时替换
        - 动态表达式：{EVAL:expression} - Python表达式，运行时计算
        - 参数化变量：${variable} - 在解析阶段已被替换
        
        Args:
            text: 包含环境变量的文本
            
        Returns:
            str: 替换后的文本
        """
        if not text or '{' not in text:
            return text
        
        if not self.config:
            logger.warning("TSRClient 未传入 config，无法替换环境变量")
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
                    import datetime
                    import time
                    import uuid
                    import os as os_module
                    eval_globals = {
                        'datetime': datetime,
                        'time': time,
                        'uuid': uuid,
                        'os': os_module,
                        'config': self.config,
                    }
                    result = eval(expression, eval_globals)
                    logger.debug(f"Eval表达式执行: {{EVAL:{expression}}} -> {result}")
                    return str(result) if result is not None else ''
                except Exception as e:
                    logger.error(f"Eval表达式执行失败: {{EVAL:{expression}}}, 错误: {e}")
                    return f"{{EVAL:{expression}}}"

            if var_name in ENVIRONMENT_VARIABLES:
                try:
                    access_type, access_param = ENVIRONMENT_VARIABLES[var_name]
                    
                    if access_type == 'attribute':
                        var_value = getattr(self.config, access_param, None)
                    elif access_type == 'getoption':
                        var_value = self.config.getoption(access_param, default=None)
                    elif access_type == 'dynamic':
                        if callable(access_param):
                            var_value = access_param()
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
                        result = str(var_value).replace('\\', '/')
                        if access_type != 'dynamic':
                            if var_name not in self._env_cache or self._env_cache[var_name] != result:
                                self._env_cache[var_name] = result
                        return result
                    else:
                        logger.warning(f"环境变量 {var_name} 的值为空")
                        return f"{{{var_name}}}"
                except Exception as e:
                    logger.error(f"获取环境变量 {var_name} 失败: {e}")
                    return f"{{{var_name}}}"
            else:
                logger.warning(f"未定义的环境变量: {var_name}")
                return f"{{{var_name}}}"
        
        result = re.sub(pattern, replace_var, text)
        return result
    
    def _replace_command_env_variables(self, command: DSLCommand):
        """
        替换DSLCommand中所有参数的环境变量
        
        Args:
            command: DSL指令对象（会原地修改params）
        """
        for i, param in enumerate(command.params):
            replaced_param = self._replace_environment_variables(param)
            if replaced_param != param:
                command.params[i] = replaced_param
    
    def execute_command(self, command: DSLCommand) -> bool:
        """
        执行 TSR 指令
        通过装饰器注册机制自动分发到对应的处理器。
        Args:
            command: DSLCommand 对象
            
        Returns:
            bool: 执行是否成功
        """
        try:
            # 在执行前替换环境变量
            self._replace_command_env_variables(command)
            
            cmd_name = command.command
            
            # 使用装饰器注册机制分发指令
            registered = get_registered_commands()
            
            if cmd_name not in registered:
                available = ", ".join(registered.keys()) if registered else "无"
                logger.error(f"不支持的 TSR 指令: {cmd_name}。可用指令: {available}")
                command.status = Status.ERROR
                command.message = f'[TSR Error] 不支持的指令: {cmd_name}。可用指令: {available}'
                return False
            
            # 分发执行指令
            summary = dispatch_command(
                command_name=cmd_name,
                params=command.params,
                config=self.config,
                output_report=None  # 让指令从 params 中解析 output 参数
            )
            
            print(summary)
            
            command.status = Status.PASSED
            command.message = f'[TSR] {cmd_name} 执行成功'
            return True
                
        except FileNotFoundError as e:
            logger.error(f"TSR 指令执行失败 - 文件不存在: {e}")
            command.status = Status.ERROR
            command.message = f'[TSR Error] 文件不存在: {str(e)}'
            return False
        except ValueError as e:
            logger.error(f"TSR 指令执行失败 - 参数错误: {e}")
            command.status = Status.ERROR
            command.message = f'[TSR Error] 参数错误: {str(e)}'
            return False
        except Exception as e:
            logger.error(f"TSR 指令执行失败: {e}")
            command.status = Status.ERROR
            command.message = f'[TSR Error] 执行失败: {str(e)}'
            return False
    
    def set_suite_stats(self, stats: dict):
        """
        设置 Suite 统计信息（从 pytest session 中获取）
        
        此方法由 conftest.py 在 SUITE_TEARDOWN 阶段调用，
        用于传递测试统计信息，供未来需要统计数据的指令使用。
        
        Args:
            stats: 统计信息字典，包含:
                - total: 总数
                - passed: 通过数
                - failed: 失败数
                - skipped: 跳过数
                - error: 错误数
                - failed_cases: 失败用例列表
                - passed_cases: 通过用例列表
        """
        self.suite_stats = stats
