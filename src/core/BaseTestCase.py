#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2025/4/21 18:59
# @Author  : huidong.bai
# @File    : BaseTestCase.py
# @Software: PyCharm
# @Mail    : MasterBai2018@outlook.com
import os
import pdb
import sys
import io
from abc import ABC
import pytest
import allure
import shutil
from loguru import logger
from src.utils.common import assert_key_value_config, uuid, color
worker_id = os.environ.get("PYTEST_XDIST_WORKER")
suite_dir = os.environ.get("MONGO_SUITE_DIR")


class ThresholdFlushBuffer:
    """
    带阈值自动 flush 的日志缓冲区。
    当缓冲区累计行数超过阈值时，自动将内容输出到 stderr 并清空缓冲区；
    Case 结束时可通过 flush_all() 主动 flush 剩余内容。
    """

    def __init__(self, threshold: int = 30):
        self._buffer = io.StringIO()
        self._threshold = threshold
        self._line_count = 0

    def write(self, message: str):
        """loguru 写入日志时调用此方法"""
        self._buffer.write(message)
        self._line_count += message.count('\n')
        if self._line_count >= self._threshold:
            self._do_flush()

    def _do_flush(self):
        """将缓冲区内容输出到 stderr 并清空"""
        self._buffer.seek(0)
        content = self._buffer.getvalue()
        if content:
            sys.stderr.write(content)
            sys.stderr.flush()
        self._buffer.truncate(0)
        self._buffer.seek(0)
        self._line_count = 0

    def flush(self):
        """loguru 框架调用的 flush 占位，由阈值机制控制实际输出时机"""
        pass

    def flush_all(self):
        """Case 结束时主动 flush 所有剩余内容"""
        self._do_flush()


def logger_init():
    log_buffer = ThresholdFlushBuffer(threshold=30)
    if worker_id:
        worker_dir = f"{suite_dir}/data/popen-{worker_id}"
        is_multi_process = True
    else:
        worker_dir = suite_dir
        is_multi_process = False
    
    log_path = f"{worker_dir}/mongo.log"
    
    try:
        logger.remove()
    except Exception as e:
        logger.error(f"移除logger handler失败: {e}")
    
    # 文件输出：记录所有DEBUG及以上级别的日志（所有日志都记录）
    logger.add(sink=log_path, format="{message}", level="TRACE", enqueue=True, colorize=True)

    # 终端输出：记录所有INFO及以上级别的日志（正常显示）
    logger.add(sink=log_buffer if is_multi_process else sys.stderr, format="{message}", level="SUCCESS", enqueue=True, colorize=True)
    return worker_dir, log_buffer, is_multi_process


class BaseTestCase(ABC):
    """
    测试Suite基类
    """
    delay_time = None
    strategy_option = None
    SuiteName: str
    SuiteSummary: str
    CaseFormat: str
    case_header = {}
    worker_dir: str = None
    log_buffer: ThresholdFlushBuffer = None
    is_multi_process: bool = False
    assert_config: dict = assert_key_value_config

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        required_attrs = ['SuiteName', 'SuiteSummary']
        for attr in required_attrs:
            if not hasattr(cls, attr):
                raise TypeError(f"未定义的类变量: {attr}")

    @classmethod
    def setup_class(cls):
        # 初始化logger
        cls.worker_dir, cls.log_buffer, cls.is_multi_process = logger_init()

    @pytest.fixture(scope="session", autouse=False)
    def base_session_fixture(self):
        """
        Session级别的fixture，用于临时修改logger格式，只保留日志内容
        子类可以通过依赖此fixture来使用简化日志格式
        """
        # 临时修改logger格式，只保留日志内容（去掉时间戳、日志级别、代码信息）
        original_handler_ids = []
        try:
            for handler_id in list(logger._core.handlers.keys()):
                original_handler_ids.append(handler_id)
            logger.remove()
        except Exception:
            pass

        # 格式为"{message}"，只保留日志内容
        logger.add(
            sink=sys.stderr,
            format="{message}",
            level="SUCCESS",
            enqueue=True,
            colorize=True
        )
        logger.success(color("======================================= test session start =======================================", "cyan"))
        
        yield
        logger.success(color("======================================== test session end ========================================", "cyan"))

    @pytest.fixture(scope="class", autouse=True)
    def mongo_testsuite_fixture(self, request, name="MongoTestSuiteFixture"):
        self.__class__.case_header = request.config.shared_case_header
        yield

    @pytest.fixture(scope="function", autouse=True, name="MongoPreTestFixture")
    def mongo_pretest_fixture(self, request):
        case = request.getfixturevalue('testcase')
        suite_id = request.config.getoption("--mongo_suite_id")
        suite_abstract = request.config.getoption("--mongo_suite_abstract")
        scene_name = request.config.getoption("--mongo_scene_name")
        workspace = request.config.getoption("--mongo_workspace")

        case_info_parts = [
            os.path.basename(case.casefile) if case.casefile else None,
            f"-F {case.case_line_range}" if case.case_line_range else None,
            f"-PF {case.param_line_range}" if case.param_line_range else None
        ]
        show_case_detail = " ".join(filter(None, case_info_parts))
        logger.success(color(f"======================================= test case start {show_case_detail} =======================================", "green"))

        # tag / epic / feature / story 必须在 description 之前写入
        # 否则 story() 会覆盖 description 的内容
        allure.dynamic.tag(request.config.getoption('--mongo_suite_tag'))
        allure.dynamic.epic(f"[ Solution ] {workspace}")
        allure.dynamic.feature(f"[ Scene ] {scene_name}")
        allure.dynamic.story(f"[ Suite ] [{suite_id}] {suite_abstract}")

        # 如果是参数化case，添加参数到 Allure 报告
        if case.param_row:
            for key, value in case.param_row.items():
                allure.dynamic.parameter(key, value)

        yield
        if os.environ.get("DockerMode", "False") == "True":
            run_cmds = ["python3", "Run_Docker.py"]
        else:
            run_cmds = ["python3", "Run_Mongo.py"]
        run_cmds.extend(["-f", request.config.getoption('--mongo_suite_name')])
        run_cmds.extend(["-C", request.config.getoption('--mongo_config')])
        run_cmds.extend(["-a", request.config.getoption('--mongo_case_list')])
        run_cmds.extend(["-b", request.config.getoption('--mongo_environment')])

        lcs_config = request.config.getoption('--mongo_project')
        if lcs_config is not None:
            run_cmds.extend(["-p", lcs_config])
        
        parameterized_data = request.config.getoption('--mongo_parameterized_data')
        if parameterized_data is not None:
            run_cmds.extend(["-P", parameterized_data])
        
        steps_data = request.config.getoption('--mongo_steps_data')
        if steps_data is not None:
            run_cmds.extend(["-S", steps_data])

        delay_option = os.environ.get("DELAY_OPTION")
        if delay_option is not None:
            run_cmds.extend(["-delay", str(delay_option)])

        strategy_option = os.environ.get("STRATEGY_OPTION")
        if strategy_option is not None:
            run_cmds.extend(["-strategy", str(strategy_option)])
        
        # 添加Case行范围过滤参数（-F）
        case = request.getfixturevalue('testcase')
        if case.case_line_range:
            run_cmds.extend(["-F", case.case_line_range])
        
        # 如果Case需要参数化，添加参数化行范围过滤参数（-PF）
        if case.param_line_range:
            run_cmds.extend(["-PF", case.param_line_range])
        
        with allure.step("执行命令："): pass
        with allure.step(" ".join(run_cmds)): pass

        # ===== 测试失败时，自动附加日志和音频到Allure报告 =====
        self._attach_logs_on_failure(request)

        logger.success(color(f"======================================== test case end {show_case_detail} ========================================", "green"))

        if self.__class__.is_multi_process:
            # Case 结束时主动 flush 缓冲区中剩余的日志
            self.log_buffer.flush_all()

    def _attach_logs_on_failure(self, request):
        """
        测试失败时，自动将日志文件和音频文件附加到Allure报告中。
        依赖 conftest.py 中的 pytest_runtest_makereport hook 将测试结果
        存储到 request.node.rep_call 上。
        """
        try:
            # 通过 pytest_runtest_makereport hook 获取测试执行结果
            rep_call = getattr(request.node, "rep_call", None)
            if rep_call is None or rep_call.passed:
                return  # 测试通过或无法获取结果，跳过附件

            # 检查日志保存开关（环境变量 SAVE_LOG_OPTION，默认开启）
            save_log_option = os.environ.get("SAVE_LOG_OPTION", "False")
            if save_log_option.lower() not in ["true", "1", "yes"]:
                return

            self._attach_zip_log(request.config.log_path)

        except Exception as e:
            logger.warning(f"附加失败日志/音频到Allure时发生异常: {e}")

    def _attach_zip_log(self, log_dir):
        """
        压缩 C++ SDK 日志目录并附加到 Allure 报告（纯内存，不落盘）。
        Args:
            log_dir: 日志目录路径（通常为 {suite_dir}/log）
        """
        import zipfile  # 标准库，已内置

        try:
            if not log_dir or not os.path.exists(log_dir):
                return

            # ① 在内存中构建 zip
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for root, dirs, files in os.walk(log_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, log_dir)
                        zf.write(file_path, arcname)

            # ② 直接把内存中的字节附加到 Allure，不经过磁盘
            zip_buffer.seek(0)
            allure.attach(
                zip_buffer.read(),
                name="运行日志.zip",
                attachment_type=allure.attachment_type.ZIP,
            )
            logger.debug("压缩并附加SDK日志成功.")
        except Exception as e:
            logger.debug(f"压缩并附加SDK日志失败: {e}")
