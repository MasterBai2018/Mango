#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2025/02/02
# @Author  : huidong.bai
# @File    : __init__.py
# @Software: PyCharm
# @Mail    : MasterBai2018@outlook.com
"""
TSR (Test Suite Report) 指令模块

使用装饰器自动注册机制，支持动态扩展新指令。

使用示例:
    from src.testsuite.NANO.tools.tsr import dispatch_command
    
    result = dispatch_command("ASR_ACCURACY", params, config)
"""
import os
import importlib
import pkgutil
from typing import Dict, Callable, Any, Optional
from loguru import logger

# 指令注册表: {指令名: 处理类}
_command_registry: Dict[str, type] = {}


def register_tsr_command(name: str):
    """
    TSR 指令注册装饰器
    
    使用方法:
        @register_tsr_command("ASR_ACCURACY")
        class ASRAccuracyHandler(BaseTSRHandler):
            def execute(self, params, config, output_report) -> str:
                ...
    
    Args:
        name: 指令名称（大写，如 "ASR_ACCURACY"）
    """
    def decorator(cls):
        if name in _command_registry:
            logger.warning(f"TSR 指令 '{name}' 已存在，将被覆盖")
        _command_registry[name] = cls
        return cls
    return decorator


def get_registered_commands() -> Dict[str, type]:
    """获取所有已注册的指令"""
    return _command_registry.copy()


def dispatch_command(command_name: str, params: list, config=None, output_report: str = None) -> str:
    """
    分发执行 TSR 指令
    
    Args:
        command_name: 指令名称
        params: 参数列表
        config: pytest config 对象（用于环境变量替换）
        output_report: 报告输出路径（可选）
    
    Returns:
        str: 执行结果的 Summary 字符串
    
    Raises:
        ValueError: 指令未注册
    """
    if command_name not in _command_registry:
        available = ", ".join(_command_registry.keys()) if _command_registry else "无"
        raise ValueError(f"TSR 指令 '{command_name}' 未注册。可用指令: {available}")
    
    handler_class = _command_registry[command_name]
    handler = handler_class(config)
    return handler.execute(params, output_report)


def _auto_discover_commands():
    """
    自动发现并导入当前包下的所有指令模块
    
    遍历 tsr 目录下的所有 .py 文件（排除 __init__.py、base.py），
    自动导入它们，触发装饰器注册。
    """
    package_dir = os.path.dirname(__file__)
    
    # 排除的模块名
    exclude_modules = {'__init__', 'base'}
    
    for _, module_name, is_pkg in pkgutil.iter_modules([package_dir]):
        if module_name in exclude_modules or is_pkg:
            continue
        
        try:
            # 动态导入模块
            importlib.import_module(f".{module_name}", __package__)
            logger.debug(f"TSR 模块已加载: {module_name}")
        except Exception as e:
            logger.error(f"TSR 模块加载失败: {module_name}, 错误: {e}")


# 模块加载时自动发现指令
_auto_discover_commands()
