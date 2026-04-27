#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/6/16 17:18
# @Author  : huidong.bai
# @File    : conftest.py
# @Software: PyCharm
# @Mail    : MasterBai2018@outlook.com
import os
import pytest
import subprocess
import time
import sys
import signal
from filelock import FileLock
from loguru import logger
from src.utils.common import copy_configs, copy_libs, redirect_config, redirect_librarys, update_config_file
from src.utils.file_reader import FileReader
from src.utils.common import async_color_print


@pytest.fixture(scope="session", autouse=True)
def environment_preparation(tmp_path_factory, pytestconfig):
    """项目级别环境准备，使用文件锁确保lib库只拷贝一次，配置文件每个worker独立拷贝"""
    base_dir_abs = tmp_path_factory.getbasetemp()
    root_dir = pytestconfig.getoption("--mongo_root_dir")
    base_dir = os.path.relpath(base_dir_abs, root_dir)

    decoder_config = pytestconfig.getoption("--mongo_config")
    config_reader = FileReader(decoder_config)
    
    # 设置配置路径（每个worker都需要）
    pytestconfig.base_dir = base_dir
    pytestconfig.suite_dir = pytestconfig.getoption("--mongo_suite_dir")
    pytestconfig.nlu_input_path = config_reader.get_config("MONGO_NLU_INPUT_PATH")
    pytestconfig.nlu_callback_path = config_reader.get_config("MONGO_NLU_CALLBACK_PATH")
    pytestconfig.mango_mini_dialogue = config_reader.get_config("MANGO_MINI_DIALOGUE")
    pytestconfig.lib_path = os.path.join(pytestconfig.suite_dir, 'lib')
    pytestconfig.socket_path = os.path.join(base_dir, 'ports')
    pytestconfig.log_path = os.path.join(base_dir, 'log')
    pytestconfig.car_type = "{\"brand\":\"0\"}"
    
    # 创建当前worker的socket端口文件夹（每个worker独立）
    if not os.path.exists(pytestconfig.socket_path):
        os.makedirs(pytestconfig.socket_path)

    # 创建当前worker的log文件夹（每个worker独立）
    if not os.path.exists(pytestconfig.log_path):
        os.makedirs(pytestconfig.log_path)
    
    # 定义锁文件和标记文件的路径（使用共享的suite_dir作为锁文件位置）
    lock_file_path = os.path.join(pytestconfig.suite_dir, ".lib_setup.lock")
    done_file_path = os.path.join(pytestconfig.suite_dir, ".lib_setup.done")
    
    # 使用文件锁确保只有一个worker拷贝lib库（全局只需要一次）
    with FileLock(lock_file_path):
        if not os.path.exists(done_file_path):
            logger.info("🚀 开始拷贝lib库")
            origin_path = pytestconfig.getoption("--mongo_lib_path")
            dest_path = pytestconfig.lib_path
            if not redirect_librarys(origin_path, dest_path):
                logger.error(f"❌ 拷贝lib库失败: {origin_path} -> {dest_path}")
                pytest.exit(reason=f"Failed to copy lib files from {origin_path} to {dest_path}")
            logger.info(f"✅ lib库拷贝完成并设置权限: {origin_path} -> {dest_path}")
            
            # 创建标记文件，表示lib库拷贝完成
            with open(done_file_path, 'w') as f:
                f.write("done")
    
    # 拷贝配置文件到当前worker的base_dir（每个worker都需要独立拷贝）
    pytestconfig.daemon_config = config_reader.get_config("OTA_CONFIG_PATH")
    pytestconfig.daemon_config = redirect_config(pytestconfig.daemon_config, base_dir, "MANGO_SUITE_DIR", base_dir)

    lcs_origin_config = pytestconfig.getoption("--mongo_project")
    lcs_config = lcs_origin_config if lcs_origin_config else config_reader.get_config("LCS_DECODER_PATH")
    pytestconfig.lcs_config = redirect_config(lcs_config, base_dir, "MANGO_SUITE_DIR", base_dir)

    pytestconfig.carplay_config = config_reader.get_config("CARPLAY_SDK_CONF")
    pytestconfig.carplay_config = redirect_config(pytestconfig.carplay_config, base_dir, "MANGO_SUITE_DIR", base_dir)

    pytestconfig.decoder_config = redirect_config(decoder_config, base_dir, "MANGO_SUITE_DIR", base_dir)
    model_name = config_reader.get_config("MODEL_NAME")
    if model_name:
        pytestconfig.model_name = model_name
    else:
        pytestconfig.model_name = "0"

    if "24mm" in pytestconfig.getoption("--mongo_environment") or "nissan" in pytestconfig.getoption("--mongo_environment"):
        # 更新配置文件：如果配置项存在则更新，不存在则追加
        config_updates = {
            'LCS_DECODER_PATH': pytestconfig.lcs_config.strip(),
            'OTA_CONFIG_PATH': pytestconfig.daemon_config.strip(),
            'CARPLAY_SDK_CONF': pytestconfig.carplay_config.strip()
        }
        update_config_file(pytestconfig.decoder_config, config_updates)
