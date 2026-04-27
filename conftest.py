#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2025/4/21 18:58
# @Author  : huidong.bai
# @File    : conftest.py
# @Software: PyCharm
# @Mail    : MasterBai2018@outlook.com
import os
import sys
import time
import pytest
import allure
from loguru import logger
from _pytest.python import Metafunc
from pytest import Config
from _pytest.terminal import TerminalReporter
from src.utils.common import mango_config, uuid, assert_key_value_config
from src.testsuite.NANO.dsl_engine import DSLEngine, DSLCase
from src.testsuite.NANO.client.TSRClient import TSRClient
from src.testsuite.NANO.assertion.AssertionTextReporter import AssertionTextReporter


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """
    将测试结果存储到 item 节点上，供 fixture teardown 阶段读取。
    存储属性：item.rep_setup / item.rep_call / item.rep_teardown
    """
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)


def pytest_addoption(parser):
    parser.addoption(
        "--mongo_lib_path",  # C++ lib path
        action="store",
        type=str,
        default=None,
        help="The C++ lib path.",
    )
    parser.addoption(
        "--mongo_root_dir",  # running root directory
        action="store",
        type=str,
        default=None,
        help="The runing root directory.",
    )
    parser.addoption(
        "--mongo_filter_case_line",  # Case的行过滤
        action="store",
        type=str,
        default=None,
        help="The testcase list filter, eg: 10-20.",
    )
    parser.addoption(
        "--mongo_case_list",  # test case file
        action="store",
        type=str,
        help="The testcase list for each suite.",
    )
    parser.addoption(
        "--mongo_config",  # speech engine config file
        action="store",
        type=str,
        help="The speech engine config file.",
    )
    parser.addoption(
        "--mongo_project",  # lcs engine config file
        action="store",
        type=str,
        default=None,
        help="The lcs engine config file.",
    )
    parser.addoption(
        "--mongo_workspace",  # running workspace
        action="store",
        type=str,
        help="The running workspace.",
    )
    parser.addoption(
        "--mongo_suite_name",  # test suite name
        action="store",
        type=str,
        default=None,
        help="The test suite name.",
    )
    parser.addoption(
        "--mongo_scene_name",  # test scene name
        action="store",
        type=str,
        default=None,
        help="The test scene name.",
    )
    parser.addoption(
        "--mongo_suite_tag",  # testsuite tag
        action="store",
        type=str,
        default="",
        help="The test suite tag.",
    )
    parser.addoption(
        "--mongo_suite_abstract",  # testsuite abstract
        action="store",
        type=str,
        default=None,
        help="The test suite abstract.",
    )
    parser.addoption(
        "--mongo_suite_id",  # testsuite id
        action="store",
        type=str,
        default=None,
        help="The test suite id.",
    )
    parser.addoption(
        "--mongo_suite_dir",  # test suite dir
        action="store",
        type=str,
        default=None,
        help="The test suite dir path.",
    )
    parser.addoption(
        "--mongo_report",  # test suite report file path
        action="store",
        type=str,
        default=None,
        help="The test suite report file path.",
    )
    parser.addoption(
        "--mongo_environment",  # running project
        action="store",
        type=str,
        choices=mango_config.get_all_project_names(),  # 限制参数值只能是这两个选项
        default="24mm/ota2",  # 默认值24mm/ota2
        help=f"Mongo environment to use (must be {mango_config.get_all_project_names()})."
    )
    parser.addoption(
        "--mongo_parameterized_data",
        action="store",
        type=str,
        default=None,
        help="The CSV file path for parameterizing DSL test cases (field-level parameters).",
    )
    parser.addoption(
        "--mongo_parameterized_data_filter",
        action="store",
        type=str,
        default=None,
        help="Filter parameterized data CSV file by row range, e.g. 10-20 (row numbers start from 1, excluding header).",
    )
    parser.addoption(
        "--mongo_steps_data",
        action="store",
        type=str,
        default=None,
        help="The CSV file path for dynamic steps parameterization (step-level with CaseID).",
    )


def pytest_configure(config: Config):
    # 记录测试会话开始时间
    config.test_session_start = time.time()
    
    if not hasattr(config, "workerinput"):
        # 在master节点进程中解析case数据
        case_file = config.getoption("--mongo_case_list")
        case_filter_line = config.getoption("--mongo_filter_case_line")
        parameterized_data = config.getoption("--mongo_parameterized_data")
        parameterized_data_filter = config.getoption("--mongo_parameterized_data_filter")
        steps_data = config.getoption("--mongo_steps_data")
        project = config.getoption("--mongo_environment")

        # 解析Case文件
        try:
            dsl_engine = DSLEngine(
                parameterized_data_file=parameterized_data,
                parameterized_data_filter=parameterized_data_filter,
                steps_data_file=steps_data,
                project=project
            )
            all_case_list = dsl_engine.parse_case_file(case_file, case_filter_line)
            case_nums = len([case for case in all_case_list if case.is_test()])

            # 将 DSLCase 对象列表转换为可序列化的字典列表
            case_list_serializable = [case.to_dict() for case in all_case_list]

            # 解析之后放入缓存中
            config.cache.set("case_list", case_list_serializable)
            config.cache.set("case_header", None)
            config.cache.set("case_nums", case_nums)
            
            logger.info(f"✅ 成功解析并序列化 {len(all_case_list)} 个用例到缓存")
        except Exception as e:
            raise Exception(f"❌ Mongo running error: {e}, caselist: {case_file}")


def pytest_generate_tests(metafunc: Metafunc):
    # 从序列化文件中读取case数据
    solution_path = metafunc.config.getoption("--mongo_workspace")
    case_file = metafunc.config.getoption("--mongo_case_list")
    case_name = os.path.basename(case_file)
    scene_name = metafunc.config.getoption("--mongo_scene_name")
    suite_id = metafunc.config.getoption("--mongo_suite_id")

    # 从缓存中获取序列化的字典列表，并反序列化为 DSLCase 对象列表
    case_list_dict = metafunc.config.cache.get("case_list", None)
    case_header = metafunc.config.cache.get("case_header", None)
    case_nums = metafunc.config.cache.get("case_nums", None)

    # 反序列化：将字典列表转换为 DSLCase 对象列表
    if case_list_dict:
        all_case_list = [DSLCase.from_dict(case_dict) for case_dict in case_list_dict]
    else:
        logger.warning(f"⚠️ 无法从缓存中获取 case_list，可能 master 进程未正确初始化")
        all_case_list = []
    
    # 将完整的case列表（包含SETUP/TEARDOWN/SUITE_TEARDOWN）存储到config中供fixture使用
    metafunc.config.shared_case_list = all_case_list
    metafunc.config.shared_case_header = case_header
    metafunc.config.shared_case_nums = case_nums

    # 只参数化TEST类型的case，过滤掉SETUP、TEARDOWN和SUITE_TEARDOWN
    test_case_list = [case for case in all_case_list if case.is_test()] if all_case_list else []
    
    # 更新testcase的唯一ids（只为TEST类型的case生成）
    ids = [f"{scene_name}_{suite_id}_{case_name}_{case.index}" for i, case in enumerate(test_case_list)]

    # 给每个DSLCase对象添加unique_id属性，包含场景和Suite信息
    for i, case in enumerate(test_case_list):
        case.unique_id = f"{solution_path}_{scene_name}_{suite_id}_{case.index}"

    # 参数化测试用例（只参数化TEST类型的case）
    metafunc.parametrize("testcase", test_case_list, ids=ids)

def pytest_collection_modifyitems(items: list):
    for item in items:
        item.name = item.name.encode("utf-8").decode("unicode_escape")
        item._nodeid = item.nodeid.encode("utf-8").decode("unicode_escape")


def pytest_sessionfinish(session, exitstatus):
    """
    当所有测试完成后执行，用于统计各个 Suite 的数据
    注意：pytest-xdist 模式下，此函数会在每个 worker 进程和主进程中都执行
    """
    # 判断是否在主进程中（只在主进程执行 SUITE_TEARDOWN）
    is_master = not hasattr(session.config, 'workerinput')
    
    if not is_master:
        # Worker 进程中不执行统计和 SUITE_TEARDOWN
        return
    
    # 合并各 Worker 的断言报告
    try:
        suite_dir = session.config.getoption("--mongo_suite_dir", default=None)
        if suite_dir and os.path.isdir(suite_dir):
            final_path = os.path.join(suite_dir, 'result.txt')
            suite_info = {
                'solution': os.path.basename(session.config.getoption('--mongo_workspace', default='') or ''),
                'define': session.config.getoption('--mongo_scene_name', default='') or '',
                'suite_name': session.config.getoption('--mongo_suite_name', default='NANO') or 'NANO',
                'suite_abstract': session.config.getoption('--mongo_suite_abstract', default='') or '',
                'mgo': session.config.getoption('--mongo_case_list', default='') or '',
                'caselist': session.config.getoption('--mongo_parameterized_data', default='') or '',
                'start_time': getattr(session.config, 'test_session_start', None),
            }
            AssertionTextReporter.merge_worker_reports(suite_dir, final_path, suite_info)
    except Exception as e:
        logger.error(f"合并断言报告失败: {e}")

    # 1. 获取 terminalreporter 插件，它存储了所有测试结果
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    
    # 获取所有的结果分类
    # stats 字典包含: 'passed', 'failed', 'skipped', 'error' 等列表
    all_results = {
        "passed": reporter.stats.get("passed", []),
        "failed": reporter.stats.get("failed", []),
        "skipped": reporter.stats.get("skipped", []),
        "error": reporter.stats.get("error", [])
    }

    # 2. 按 Suite (文件路径) 进行数据归类
    suite_stats = {}
    
    # 获取 suite 的名称，使用与 BaseTestCase.py 中相同的格式: [ Suite ] [{suite_id}] {suite_abstract}
    # 从配置中获取 suite_id 和 suite_abstract（在整个session中是固定的，提取到循环外）
    suite_id = session.config.getoption("--mongo_suite_id", default="")
    suite_abstract = session.config.getoption("--mongo_suite_abstract", default="")
    suite_name = f"[ Suite ] [{suite_id}] {suite_abstract}"

    for status, items in all_results.items():
        for item in items:
            if suite_name not in suite_stats:
                suite_stats[suite_name] = {"total": 0, "passed": 0, "failed": 0, "skipped": 0, "error": 0}
            
            suite_stats[suite_name]["total"] += 1
            if status in suite_stats[suite_name]:
                suite_stats[suite_name][status] += 1

    # 6. 执行 SUITE_TEARDOWN
    try:
        # 在 pytest-xdist 并发模式下，shared_case_list 可能不在 session.config 中
        if hasattr(session.config, 'shared_case_list') and session.config.shared_case_list:
            all_case_list = session.config.shared_case_list
        else:
            # 从缓存中读取
            case_list_dict = session.config.cache.get("case_list", None)
            if case_list_dict:
                all_case_list = [DSLCase.from_dict(case_dict) for case_dict in case_list_dict]
            else:
                all_case_list = []
                logger.warning("⚠️ 无法从缓存中获取 case_list，SUITE_TEARDOWN 可能无法执行")
        
        suite_teardown_case = next((case for case in all_case_list if case.is_suite_teardown()), None) if all_case_list else None
        
        if suite_teardown_case:
            # 确保 session.config 有必要的属性（用于环境变量替换）
            # 这些属性是 TSR 客户端执行环境变量替换时需要的
            if not hasattr(session.config, 'suite_dir'):
                suite_dir = session.config.getoption("--mongo_suite_dir", default=None)
                if suite_dir:
                    session.config.suite_dir = suite_dir
                else:
                    # 如果没有 suite_dir，尝试从 workspace 和 suite_id 构建
                    workspace = session.config.getoption("--mongo_workspace", default="")
                    suite_id = session.config.getoption("--mongo_suite_id", default="")
                    scene_name = session.config.getoption("--mongo_scene_name", default="")
                    if workspace and suite_id and scene_name:
                        session.config.suite_dir = os.path.join(workspace, scene_name, str(suite_id))
                    else:
                        session.config.suite_dir = workspace  # 降级使用 workspace
            
            # 设置其他可能需要的属性
            if not hasattr(session.config, 'decoder_config'):
                session.config.decoder_config = session.config.getoption("--mongo_config", default=None)
            if not hasattr(session.config, 'lcs_config'):
                session.config.lcs_config = session.config.getoption("--mongo_project", default=None)
            if not hasattr(session.config, 'log_path'):
                if hasattr(session.config, 'suite_dir') and session.config.suite_dir:
                    session.config.log_path = os.path.join(session.config.suite_dir, "log")
                else:
                    session.config.log_path = None
            
            # 创建 TSR 客户端（传入 config 用于环境变量替换）
            tsr_client = TSRClient(config=session.config)
            # 收集 Suite 统计信息并传递给 TSR 客户端
            suite_stat = suite_stats.get(suite_name, {})
            failed_cases_list = []
            passed_cases_list = []
            
            # 收集失败用例详情
            for item in all_results.get("failed", []) + all_results.get("error", []):
                if hasattr(item, 'when') and item.when == 'call':
                    failed_cases_list.append({
                        "name": item.nodeid,
                        "duration": getattr(item, 'duration', 0),
                        "error": str(item.longrepr) if hasattr(item, 'longrepr') else ""
                    })
            
            # 收集通过用例详情
            for item in all_results.get("passed", []):
                if hasattr(item, 'when') and item.when == 'call':
                    passed_cases_list.append({
                        "name": item.nodeid,
                        "duration": getattr(item, 'duration', 0)
                    })
            
            # 设置统计信息
            tsr_client.set_suite_stats({
                "total": suite_stat.get("total", 0),
                "passed": suite_stat.get("passed", 0),
                "failed": suite_stat.get("failed", 0),
                "skipped": suite_stat.get("skipped", 0),
                "error": suite_stat.get("error", 0),
                "failed_cases": failed_cases_list,
                "passed_cases": passed_cases_list
            })
            
            # 执行 SUITE_TEARDOWN 中的所有 TSR 指令
            for cmd in suite_teardown_case.commands:
                if cmd.client_type == 'TSR':
                    tsr_client.execute_command(cmd)

    except Exception as e:
        logger.error(f"执行 SUITE_TEARDOWN 时发生错误: {e}")
        import traceback
        traceback.print_exc()
