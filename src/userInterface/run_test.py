#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2025/11/15 15:48
# @Author  : huidong.bai
# @File    : run_test.py.py
# @Software: PyCharm
# @Mail    : MasterBai2018@outlook.com
import os
import sys
import time
import json
import shlex
import shutil
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
# 限制 OpenBLAS/MKL 等线性代数库的内部线程数，避免多进程场景下线程爆炸
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
from datetime import datetime
from src.utils.file_reader import FileReader
from src.utils.send_wechat import SendMessage
from src.utils.common import update_lcs_event_parser, find_test_suites, check_core_file
from src.utils.JenkinsDownloader import JenkinsDownloader
from src.utils.FTPDownloader import FTPDownloader, FileType
from src.userInterface.deploy_environment import get_work_mode
from src.userInterface.parse_config import Parse
from src.userInterface.parse_solution import Parse as YamlParse
from src.userInterface.process_result import merge_result, generate_report
from src.utils.ConfigParser import ConfigParser
from src.utils.loop_config_parser import parse_loop_config
mango_config = ConfigParser('conf/mango.ini')


def peek_mgo_headers(mgo_path: str) -> dict:
    """
    快速扫描 mgo 文件顶部连续的 @KEY: VALUE 行，遇到第一个非空、非注释、非@ 行立即停止。
    只读取少量行，不依赖 DSLEngine，开销极小。
    """
    headers = {}
    if not mgo_path or not os.path.exists(mgo_path):
        return headers
    try:
        with open(mgo_path, 'r', encoding='utf-8') as f:
            for line in f:
                s = line.strip()
                if not s or s.startswith('#'):
                    continue
                if s.startswith('@') and ':' in s:
                    key, val = s[1:].split(':', 1)
                    headers[key.strip().upper()] = val.strip()
                else:
                    break
    except Exception:
        pass
    return headers

# 依赖 LCS 项目配置的工程（与 conf/mango.ini 中 [project:...] 名称一致）
LCS_PROJECT_ENVIRONMENTS = frozenset(
    (
        "24mm/mp",
        "24mm/ota1",
        "24mm/ota2",
        "24mm/ota3",
        "bev",
        "nissan",
        "800d",
    )
)

_LAST_TESTER_ARGS = None


class AtomicSuite:
    suiteID = -1
    suiteName = None
    suiteTag = None
    suiteConf = None
    suiteCaseList = None
    suiteAbstract = None
    parameterizedData = None  # 参数化数据文件（-P参数）
    stepsData = None  # 动态步骤数据文件（-S参数）
    scenarioID = -1
    scenarioName = None
    scenarioConf = None
    solutionID = -1
    solutionName = None
    stdoutFile = None
    useValgrind = None
    repeatNum = 1
    nluRes = None
    project = None
    ctr = None
    workspace = None
    mainTag = None
    orderIndex = 0
    hasHistory = False
    predictedDuration = 0.0
    retryCount = 0
    xdistWorkers = 0      # 原始配置值（0/1 表示不开 xdist，>=2 表示开 xdist）
    requiredSlots = 1     # 本 suite 实际占用的调度槽位数（最小为 1）
    loopIndex = None      # 当前 loop 迭代索引（None 表示非 loop 模式）
    loopValue = None      # 当前 loop 迭代值
    loopTotal = None      # loop 总迭代次数

    def __init__(self, suiteID, suiteName, suiteTag, suiteConf, suiteCaseList, suiteAbstract, parameterizedData=None, stepsData=None):
        self.__reset()
        self.suiteID = suiteID
        self.suiteName = suiteName
        self.suiteTag = suiteTag
        self.suiteConf = suiteConf
        self.suiteCaseList = suiteCaseList
        self.suiteAbstract = suiteAbstract
        self.parameterizedData = parameterizedData
        self.stepsData = stepsData
        self.retryCount = 0
        self.xdistWorkers = 0
        self.requiredSlots = 1
        self.loopIndex = None
        self.loopValue = None
        self.loopTotal = None

    def __reset(self):
        self.suiteID = -1
        self.suiteName = None
        self.suiteTag = None
        self.suiteConf = None
        self.suiteCaseList = None
        self.suiteAbstract = None
        self.scenarionID = -1
        self.scenarioName = None
        self.scenarionConf = None
        self.solutionID = -1
        self.solutionName = None
        self.stdoutFile = None
        self.useValgrind = None
        self.repeatNum = 1
        self.ctr = None
        self.mainTag = None
        self.orderIndex = 0
        self.hasHistory = False
        self.predictedDuration = 0.0
        self.retryCount = 0
        self.xdistWorkers = 0
        self.requiredSlots = 1

    def setScenarioInfo(self, scenarioID, scenarioName, scenarioConf):
        self.scenarioID = scenarioID
        self.scenarioName = scenarioName
        self.scenarioConf = scenarioConf

    def setStdoutFile(self, stdoutFile):
        self.stdoutFile = stdoutFile

    def setUseValgrind(self, useValgrind):
        self.useValgrind = useValgrind

    def setRepeatNum(self, num):
        self.repeatNum = num

    def setConcurrentCtr(self, info):
        self.ctr = info

    def setSolutionInfo(self, solutionID, solutionName):
        self.solutionID = solutionID
        self.solutionName = solutionName

    def setWorkspace(self, workspace):
        self.workspace = workspace

    def setNluRes(self, nluRes):
        self.nluRes = nluRes

    def setproject(self, project):
        self.project = project

    def setMainTag(self, mainTag):
        self.mainTag = str(mainTag).upper() if mainTag else None

    def setOrderIndex(self, orderIndex):
        self.orderIndex = orderIndex

    def setRetryCount(self, retryCount):
        self.retryCount = retryCount

    def setXdistWorkers(self, xdistWorkers):
        """
        设置 xdist worker 数，同时推导出 requiredSlots：
        - xdistWorkers=0 或 1：不开 xdist，占 1 个槽位
        - xdistWorkers>=2：开 xdist，占 N 个槽位
        """
        self.xdistWorkers = xdistWorkers
        self.requiredSlots = max(1, int(xdistWorkers)) if int(xdistWorkers) >= 2 else 1

    def setLoopInfo(self, loopIndex: int, loopValue: str, loopTotal: int):
        self.loopIndex = loopIndex
        self.loopValue = loopValue
        self.loopTotal = loopTotal


def resuce_report(tester_args, time_info):
    """
    拯救已运行的报告数据，生成报告
    """
    
    mongo_solutions = tester_args.mongo_solution
    mongo_work_space = tester_args.mongo_workspace
    parses = []
    solutions = []

    # 支持跑多个solution
    for solution_config in mongo_solutions:
        solution_filename = os.path.splitext(os.path.basename(solution_config))[0]
        tester_args.mongo_workspace = os.path.join(mongo_work_space, solution_filename)

        report_data = []
        parse = Parse(solution_config, tester_args.mongo_tag, tester_args.mongo_enable, tester_args.mongo_workspace)
        parses.append(parse)
        tasks = parse.get_tasks()
        enable = parse.get_enable()
        disable = parse.get_disable()
        for scenario in tasks:
            if "ALL" in disable:
                break
            if scenario.name in disable:
                continue
            if scenario.name not in enable and "ALL" not in enable:
                continue
            sceneResult = {'sceneName': scenario.name, 'owner': scenario.owner, 'sceneInfo': {}}
            sceneResult['sceneInfo']['suiteSummary'] = {}
            sceneResult['sceneInfo']['suiteSummary']['suiteNum'] = 0
            sceneResult['sceneInfo']['suiteSummary']['passedNum'] = 0
            sceneResult['sceneInfo']['suiteSummary']['caseNum'] = 0
            sceneResult['sceneInfo']['suiteSummary']['totalTime'] = 0
            sceneResult['sceneInfo']['suiteSummary']['failedNum'] = 0
            sceneResult['sceneInfo']['suiteSummary']['S'] = 0
            sceneResult['sceneInfo']['suiteSummary']['A'] = 0
            sceneResult['sceneInfo']['suiteSummary']['B'] = 0
            sceneResult['sceneInfo']['suiteSummary']['C'] = 0
            sceneResult['sceneInfo']['suiteSummary']['D'] = 0
            sceneResult['sceneInfo']['suiteInfo'] = []

            report_dir = os.path.join(tester_args.mongo_workspace, scenario.name)
            if os.path.exists(report_dir) is False:
                continue
            file_list = os.listdir(report_dir)
            for f in file_list:
                if "_report_" not in f:
                    continue
                report = os.path.join(report_dir, f)
                merge_result(report, sceneResult['sceneInfo']['suiteInfo'], sceneResult['sceneInfo']['suiteSummary'])
            report_data.append(sceneResult)

        print("Begin to generate report....")
        time_info['end'] = time.time()
        data = generate_report(tester_args.mongo_workspace, tester_args.mongo_report, report_data, parse, time_info)
        print("Generate report complete....\n")

        solution = {'solution_name': os.path.basename(solution_config), 'solution_report': data}
        solutions.append(solution)
    tester_args.mongo_workspace = mongo_work_space
    return solutions

class WorkerPool:
    def __init__(self, max_workers):
        self.max_workers = max_workers
        self.available_workers = max_workers
        self.cond = threading.Condition()

    def acquire(self, n):
        with self.cond:
            while self.available_workers < n:
                self.cond.wait()
            self.available_workers -= n

    def release(self, n):
        with self.cond:
            self.available_workers += n
            self.cond.notify_all()

def get_case_count(testcase, parameterized_data):
    case_count = 0
    if testcase and os.path.exists(testcase):
        try:
            with open(testcase, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('>>>') and not any(x in line for x in ['SETUP', 'TEARDOWN']):
                        case_count += 1
        except Exception:
            pass
            
    if parameterized_data and os.path.exists(parameterized_data):
        try:
            with open(parameterized_data, 'r', encoding='utf-8') as f:
                csv_rows = sum(1 for _ in f) - 1
            if csv_rows > 0:
                case_count = case_count * csv_rows
        except Exception:
            pass
    return case_count


def _build_history_key(suite):
    return f"{suite.scenarioName}::{suite.suiteID}::{suite.suiteName}"


def _load_history(history_file):
    if not os.path.exists(history_file):
        return {}
    try:
        with open(history_file, "r", encoding="utf-8") as fp:
            data = json.load(fp)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def _save_history(history_file, history):
    try:
        parent = os.path.dirname(history_file)
        os.makedirs(parent, exist_ok=True)
        with open(history_file, "w", encoding="utf-8") as fp:
            json.dump(history, fp, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"WARNING: failed to save suite history file {history_file}, error: {e}")


def _get_slot_usage(running_counter):
    """返回当前各 tag 已占用的槽位数（slot 数，不是 suite 数）。"""
    return running_counter["ONLINE"], running_counter["OFFLINE"], running_counter["CP"]


def _can_start_suite(suite, running_counter, suite_counter, limits, pending_suites):
    """
    判断某个 suite 是否可以立即启动。

    running_counter：各 tag 当前已占用的槽位数（slot-based）。
    suite_counter  ：各 tag 当前正在运行的 suite 数（用于日志展示）。
    limits         ：scheduler_limits 字典。
    pending_suites ：当前待运行的 suite 列表。

    规则：
    1. GLOBAL 总槽位不能超；
    2. 对应 tag 的分类槽位不能超；
    3. 上述两个判断都是 已占用 + required_slots <= 上限。
    """
    slots = suite.requiredSlots
    online_slots, offline_slots, cp_slots = _get_slot_usage(running_counter)
    total_slots = online_slots + offline_slots + cp_slots

    # 全局槽位检查
    if total_slots + slots > limits["GLOBAL_MAX_WORKERS"]:
        return False

    tag = suite.mainTag
    if tag == "ONLINE":
        return online_slots + slots <= limits["ONLINE_MAX_WORKERS"]

    if tag == "CP":
        return cp_slots + slots <= limits["CP_MAX_WORKERS"]

    if tag == "OFFLINE":
        offline_cfg = limits["OFFLINE_MAX_WORKERS"]
        # OFFLINE 动态上限
        online_reserved = limits["ONLINE_MAX_WORKERS"] if any(s.mainTag == "ONLINE" for s in pending_suites) else 0
        cp_reserved = limits["CP_MAX_WORKERS"] if any(s.mainTag == "CP" for s in pending_suites) else 0
        offline_dynamic_max = limits["GLOBAL_MAX_WORKERS"] - online_reserved - cp_reserved - cp_slots
        if offline_cfg != "auto":
            offline_dynamic_max = min(int(offline_cfg), offline_dynamic_max)
        return offline_slots + slots <= offline_dynamic_max

    return False


def _select_next_suite(pending_suites, running_counter, suite_counter, limits):
    """
    从 pending_suites 中按 LPT（最长预测耗时优先）排序，
    遍历排序结果，返回第一个当前槽位满足条件的 suite。

    当排在前面的大任务被卡住时，允许后面槽位需求更小的任务插队，
    但整体仍遵循 LPT 顺序——不会无故跳过可以启动的长任务。
    """
    # LPT 排序：有历史耗时 > 无历史耗时，耗时长的优先，orderIndex 小的优先（用负号反转）
    sorted_suites = sorted(
        pending_suites,
        key=lambda s: (
            1 if s.hasHistory else 0,
            s.predictedDuration,
            -s.orderIndex,
        ),
        reverse=True,
    )
    for suite in sorted_suites:
        if _can_start_suite(suite, running_counter, suite_counter, limits, pending_suites):
            return suite
    return None


def _execute_suite_once(root_dir, tester_args, work_mode, suite_infos, suite):
    begin = time.time()
    result = run_per_suite(
        root_dir=root_dir,
        tester_args=tester_args,
        environment=suite.project if suite.project else tester_args.mongo_environment,
        work_mode=work_mode,
        suite_id=suite.suiteID,
        suite_name=suite.suiteName,
        enable_suites=suite_infos,
        scene_name=suite.scenarioName,
        workspace=suite.workspace,
        decoder_config=suite.suiteConf,
        testcase=suite.suiteCaseList,
        suite_tag=suite.suiteTag,
        suite_abstract=suite.suiteAbstract,
        project_config=suite.scenarioConf,
        stdout_file=suite.stdoutFile,
        multiprocess_number=suite.xdistWorkers,
        retry_count=suite.retryCount,
        parameterized_data=suite.parameterizedData,
        steps_data=suite.stepsData,
        use_valgrind=suite.useValgrind,
        loop_index=suite.loopIndex,
        loop_value=suite.loopValue,
        loop_total=suite.loopTotal,
    )
    return result, max(0.0, time.time() - begin)


def _run_solution_suites(root_dir, tester_args, work_mode, suite_infos, solution_name, run_suite_pool, scheduler_limits):
    if not run_suite_pool:
        return

    max_launch_gap_sec = int(mango_config.get_config_value("Concurrency", "max_launch_gap_sec"))
    min_launch_gap_sec = int(mango_config.get_config_value("Concurrency", "min_launch_gap_sec"))
    global_max_workers = int(scheduler_limits["GLOBAL_MAX_WORKERS"])

    # running_counter：各 tag 当前已占用的【槽位数】（slot-based，不是 suite 数）
    # suite_counter  ：各 tag 当前正在运行的【suite 数】（仅用于日志展示）
    running_counter = {"ONLINE": 0, "OFFLINE": 0, "CP": 0}
    suite_counter   = {"ONLINE": 0, "OFFLINE": 0, "CP": 0}

    pending_suites = list(run_suite_pool)

    history_file = os.path.join(tester_args.mongo_workspace, ".suite_duration_history", f"{solution_name}.json")
    suite_history = _load_history(history_file)

    for suite in pending_suites:
        history_key = _build_history_key(suite)
        duration = suite_history.get(history_key)
        if duration is not None:
            suite.hasHistory = True
            suite.predictedDuration = float(duration)
        else:
            suite.hasHistory = False
            suite.predictedDuration = 0.0

    # 线程池大小：最多同时调度 global_max_workers 个线程（每个线程跑一个 suite）。
    # 注意：这里 max_pool_workers 控制的是线程数（即最多同时运行的 suite 数），
    # 而槽位检查才是资源约束的核心。两者共同作用：
    #   - 线程池防止线程无限膨胀；
    #   - 槽位检查保证资源不超用。
    max_pool_workers = max(1, min(global_max_workers, len(pending_suites)))

    with ThreadPoolExecutor(max_workers=max_pool_workers) as executor:
        running_futures = {}  # future -> AtomicSuite

        while pending_suites or running_futures:
            launched = False

            # 尝试持续调度，直到无法再启动新 suite（槽位不足或 pending 为空）
            while len(running_futures) < max_pool_workers and pending_suites:
                target_suite = _select_next_suite(pending_suites, running_counter, suite_counter, scheduler_limits)
                if target_suite is None:
                    break

                pending_suites.remove(target_suite)
                tag = target_suite.mainTag
                slots = target_suite.requiredSlots

                # 同时更新槽位计数和 suite 计数
                running_counter[tag] += slots
                suite_counter[tag]   += 1

                future = executor.submit(_execute_suite_once, root_dir, tester_args, work_mode, suite_infos, target_suite)
                running_futures[future] = target_suite
                launched = True

                _dynamic_sleep = 0
                if pending_suites and max_launch_gap_sec > 0:
                    # 并发占比越高，sleep 越长，降低启动瞬间的 IO/资源冲击
                    total_slots_used = running_counter["ONLINE"] + running_counter["OFFLINE"] + running_counter["CP"]
                    _ratio = total_slots_used / max(1, global_max_workers)
                    _ratio = max(0.0, min(1.0, _ratio))
                    _dynamic_sleep = min_launch_gap_sec + (max_launch_gap_sec - min_launch_gap_sec) * _ratio
                    time.sleep(_dynamic_sleep)

                # 日志同时展示槽位占用数和 suite 数
                total_slots_used = running_counter["ONLINE"] + running_counter["OFFLINE"] + running_counter["CP"]
                total_suites_running = suite_counter["ONLINE"] + suite_counter["OFFLINE"] + suite_counter["CP"]
                print(
                    f"🚀 [调度] solution={solution_name} suite={target_suite.suiteName} "
                    f"tag={tag} slots={slots} "
                    f"slot_usage(ONLINE={running_counter['ONLINE']},OFFLINE={running_counter['OFFLINE']},CP={running_counter['CP']},TOTAL={total_slots_used}/{global_max_workers}) "
                    f"suite_count(ONLINE={suite_counter['ONLINE']},OFFLINE={suite_counter['OFFLINE']},CP={suite_counter['CP']},TOTAL={total_suites_running}) "
                    f"sleep={_dynamic_sleep:.1f}s"
                )

            if running_futures:
                done, _ = wait(set(running_futures.keys()), return_when=FIRST_COMPLETED)
                for future in done:
                    suite = running_futures.pop(future)
                    tag = suite.mainTag
                    slots = suite.requiredSlots

                    # 释放槽位和 suite 计数（一次性释放全部）
                    running_counter[tag] -= slots
                    suite_counter[tag]   -= 1

                    try:
                        result, duration = future.result()
                        suite_history[_build_history_key(suite)] = duration
                        total_slots_used = running_counter["ONLINE"] + running_counter["OFFLINE"] + running_counter["CP"]
                        total_suites_running = suite_counter["ONLINE"] + suite_counter["OFFLINE"] + suite_counter["CP"]
                        print(
                            f"✅ [完成] solution={solution_name} suite={suite.suiteName} "
                            f"tag={tag} slots_released={slots} duration={duration:.1f}s result={result} "
                            f"slot_usage(ONLINE={running_counter['ONLINE']},OFFLINE={running_counter['OFFLINE']},CP={running_counter['CP']},TOTAL={total_slots_used}/{global_max_workers}) "
                            f"suite_count(ONLINE={suite_counter['ONLINE']},OFFLINE={suite_counter['OFFLINE']},CP={suite_counter['CP']},TOTAL={total_suites_running})"
                        )
                    except Exception as e:
                        total_slots_used = running_counter["ONLINE"] + running_counter["OFFLINE"] + running_counter["CP"]
                        print(
                            f"❌ [异常] solution={solution_name} suite={suite.suiteName} "
                            f"tag={tag} slots_released={slots} error={e} "
                            f"slot_usage(TOTAL={total_slots_used}/{global_max_workers})"
                        )

            elif pending_suites and not launched:
                # 所有 pending suite 都因槽位不足无法启动，且当前没有任何 suite 在跑
                # 这是一个死锁状态，通常意味着某个 suite 的 required_slots 超过了可用上限
                # （正常情况下 parse_solution.py 的校验会提前拦截，此处作为最后防线）
                print(
                    f"❌ [调度死锁] solution={solution_name} "
                    f"存在 suite 的槽位需求无法被当前配置满足，调度终止。"
                    f"请检查 GLOBAL/ONLINE/CP/OFFLINE 的配置与各 suite 的 xdist_workers 设置。"
                )
                break

    _save_history(history_file, suite_history)

def run_all_test(tester_args, root_dir):
    global _LAST_TESTER_ARGS
    _LAST_TESTER_ARGS = tester_args

    time_info = {'start_time': datetime.now(), 'start': time.time(), 'end': None}
    suite_infos = find_test_suites()

    # 列出当前支持的Suite列表
    if tester_args.mongo_list_suites:
        for info in suite_infos:
            print(f"Support Test Suite: {info}: {suite_infos.get(info)}")
        sys.exit(0)

    if tester_args.mongo_rescue:
        resuce_report(tester_args, time_info)
        sys.exit(0)
    
    # 如果solution存在则判断是否存在
    if tester_args.mongo_solution:
        for solution in tester_args.mongo_solution:
            if solution and not os.path.exists(solution):
                print(f"❌ The solution file cannot be found, please check it: {solution}")
                sys.exit(1)
    
    # 检查输入的测试文件路径是否正确
    check_lists = [
        (tester_args.mongo_filter_config, "decoder config"),
        (tester_args.mongo_case, "testcase file"),
        (tester_args.mongo_project, "lcs config file")
    ]
    for path, description in check_lists:
        if path and not os.path.exists(path):
            print(f"❌ The {description} cannot be found, please check it: {path}")
            sys.exit(1)
    
    # 检查运行项目
    if tester_args.mongo_environment not in mango_config.get_all_project_names():
        print(f"❌ The project environment: {tester_args.mongo_environment} is not supported. see: {mango_config.get_all_project_names()}")
        sys.exit(1)
    
    # 如果传入参数不合法，则工作模式不可用，退出
    work_mode = get_work_mode(tester_args)
    if work_mode == "INVALID":
        print(f"Quit mongo test execution.")
        sys.exit(1)
    
    # 若工程依赖 LCS 配置，FILTER/GDB_FILTER 模式下必须提供有效的 lcs 配置文件
    if tester_args.mongo_environment in LCS_PROJECT_ENVIRONMENTS and work_mode in ["FILTER", "GDB_FILTER"]:
        if not tester_args.mongo_project or not os.path.exists(tester_args.mongo_project):
            print(f"❌ The lcs config file cannot be found, please check it: {tester_args.mongo_project}")
            sys.exit(1)
    
    # 如果需要下载Jenkins依赖则下载
    if tester_args.mongo_library_downloader:
        try:
            jenkins_download = JenkinsDownloader()
            jenkins_download.run_jenkins_download(tester_args.mongo_environment, tester_args.mongo_library_downloader)
        except Exception as e:
            print(f"❌ Download lib fail, error:{e}")
            sys.exit(1)

    # 单跑FILTER工作模式
    if work_mode == "FILTER" or work_mode == "GDB_FILTER":
        solutions = []
        report_data = []
        solution = {'solution_name': "FILTER", 'solution_report': report_data}
        solutions.append(solution)
        sceneResult = {'sceneName': 'FILTER', 'sceneInfo': {}}
        sceneResult['sceneInfo']['suiteInfo'] = []
        sceneResult['sceneInfo']['suiteSummary'] = {}
        sceneResult['sceneInfo']['suiteSummary']['suiteNum'] = 0
        sceneResult['sceneInfo']['suiteSummary']['passedNum'] = 0
        sceneResult['sceneInfo']['suiteSummary']['caseNum'] = 0
        sceneResult['sceneInfo']['suiteSummary']['totalTime'] = 0
        sceneResult['sceneInfo']['suiteSummary']['failedNum'] = 0
        sceneResult['sceneInfo']['suiteSummary']['S'] = 0
        sceneResult['sceneInfo']['suiteSummary']['A'] = 0
        sceneResult['sceneInfo']['suiteSummary']['B'] = 0
        sceneResult['sceneInfo']['suiteSummary']['C'] = 0
        sceneResult['sceneInfo']['suiteSummary']['D'] = 0

        tester_args.mongo_workspace = os.path.join(tester_args.mongo_workspace, "solution_filter")

        if os.path.exists(tester_args.mongo_workspace):
            shutil.rmtree(tester_args.mongo_workspace)
        os.makedirs(tester_args.mongo_workspace)

        # 资源自动下载资源
        if tester_args.mongo_ftp_downloader in [0, 1, 2]:
            try:
                ftp_download = FTPDownloader()
                if tester_args.mongo_ftp_downloader == 0:
                    ftp_download.add_download_file(tester_args.mongo_filter_config, FileType.CONFIG)
                    ftp_download.add_download_file(tester_args.mongo_project, FileType.CONFIG)
                    ftp_download.add_download_file(tester_args.mongo_case, FileType.CASE)
                    ftp_download.add_download_file(tester_args.mongo_parameterized_data, FileType.CASE)
                elif tester_args.mongo_ftp_downloader == 1:
                    ftp_download.add_download_file(tester_args.mongo_case, FileType.CASE)
                    ftp_download.add_download_file(tester_args.mongo_parameterized_data, FileType.CASE)
                elif tester_args.mongo_ftp_downloader == 2:
                    ftp_download.add_download_file(tester_args.mongo_filter_config, FileType.CONFIG)
                    ftp_download.add_download_file(tester_args.mongo_project, FileType.CONFIG)
                ftp_download.start_download()
            except Exception as e:
                print(f"❌ Download error: {str(e)}")
                exit(1)
        
        # 依赖 LCS 的工程，更新 LCS 资源的事件解析引擎
        if tester_args.mongo_environment in LCS_PROJECT_ENVIRONMENTS:
            update_lcs_event_parser([tester_args.mongo_project])

        # FILTER 模式：读取 mgo 头部 @LOOP 配置
        mgo_headers = peek_mgo_headers(tester_args.mongo_case)
        loop_config_str = mgo_headers.get("LOOP")
        if loop_config_str:
            try:
                loop_items = parse_loop_config(loop_config_str)
            except ValueError as e:
                print(f"❌ mgo @LOOP 配置解析失败: {e}")
                sys.exit(1)
        else:
            loop_items = [(0, None)]

        is_loop = len(loop_items) > 1
        loop_total = len(loop_items)

        for loop_index, loop_value in loop_items:
            suite_id_str = f"1_L{loop_index}" if is_loop else 1
            suite_name_str = tester_args.mongo_filter

            result = run_per_suite(
                root_dir=root_dir,
                tester_args=tester_args,
                environment=tester_args.mongo_environment,
                work_mode=work_mode,
                suite_id=suite_id_str,
                suite_name=suite_name_str,
                enable_suites=suite_infos,
                scene_name="FILTER",
                workspace=tester_args.mongo_workspace,
                decoder_config=tester_args.mongo_filter_config,
                testcase=tester_args.mongo_case,
                suite_tag="",
                suite_abstract="单指令执行Suite简介",
                project_config=tester_args.mongo_project,
                stdout_file=None,
                multiprocess_number=tester_args.mongo_multiprocess_number,
                parameterized_data=tester_args.mongo_parameterized_data,
                steps_data=tester_args.mongo_steps_data,
                use_valgrind=False,
                loop_index=loop_index if is_loop else None,
                loop_value=loop_value if is_loop else None,
                loop_total=loop_total if is_loop else None,
            )

            if result is None:
                print("The suite[%s] didn't generate report" % suite_name_str)
            elif result == 'ERROR':
                print(f'The suite[{suite_name_str}] and config[{tester_args.mongo_filter_config}] do not match.')

        time_info['end'] = time.time()
        check_core_file(tester_args.mongo_workspace, time_info['start'], time_info['end'])
        return

    else:
        # 配置文件下载集合
        config_set = set()
        caselist_set = set()
        solution_id = 0
        solution_jobs = []

        # 逐个解析 solution，按 solution 维度构建执行队列与并发参数
        for solution in tester_args.mongo_solution:
            solution_id += 1
            solution_name = os.path.basename(solution).split(".")[0]
            solution_workspace = os.path.join(tester_args.mongo_workspace, solution_name)
            run_suite_pool = []
            suite_order = 0
            print(solution_workspace)
            print("Begin to parse the solution file....")
            parse = YamlParse(solution, tester_args.mongo_tag, tester_args.mongo_enable, solution_workspace)
            scheduler_limits = parse.get_scheduler_limits()
            project = parse.get_project()
            tasks = parse.get_tasks()
            enable = parse.get_enable()
            disable = parse.get_disable()

            if os.path.exists(solution_workspace):
                shutil.rmtree(solution_workspace, ignore_errors=True)
            os.makedirs(solution_workspace)

            # 处理solution文件解析的define
            for define in tasks:
                if "ALL" in disable:
                    break
                if define.name in disable:
                    continue
                if define.name not in enable and "ALL" not in enable:
                    continue

                define_dir = os.path.join(solution_workspace, define.name)
                if not os.path.exists(define_dir):
                    os.makedirs(define_dir)

                # 统一将每个场景下的 suite 终端输出放到固定目录，避免日志文件散落。
                stdout_dir = os.path.join(define_dir, "terminal_output")
                os.makedirs(stdout_dir, exist_ok=True)

                for suite in define.suiteInfo:
                    if not suite:
                        continue

                    # 如果指令中存在-p指令，则覆盖solution中的配置文件
                    if tester_args.mongo_project:
                        suite.set_scenarioConfig(tester_args.mongo_project)

                    # 添加到下载列表
                    if suite.conf:
                        config_set.add(suite.conf)
                    if suite.scenario_conf:
                        config_set.add(suite.scenario_conf)
                    if suite.caseList:
                        caselist_set.add(suite.caseList)
                    
                    # 如果suite有参数化文件，也添加到下载列表
                    if suite.parameterized_data:
                        caselist_set.add(suite.parameterized_data)
                    
                    # 如果suite有动态步骤文件，也添加到下载列表
                    if suite.steps_data:
                        caselist_set.add(suite.steps_data)

                    # 确定 loop 配置：solution YAML loop 字段优先，其次 mgo @LOOP
                    loop_config_str = getattr(suite, "loop", None)
                    if not loop_config_str and suite.caseList:
                        mgo_headers = peek_mgo_headers(suite.caseList)
                        loop_config_str = mgo_headers.get("LOOP")

                    if loop_config_str:
                        try:
                            loop_items = parse_loop_config(loop_config_str)
                        except ValueError as e:
                            print(f"❌ suite '{suite.name}' loop 配置解析失败: {e}")
                            sys.exit(1)
                    else:
                        loop_items = [(0, None)]  # 无 loop，单次运行

                    is_loop = len(loop_items) > 1
                    loop_total = len(loop_items)

                    # 优先级：DEFINE内的PROJECT > solution全局PROJECT > 命令行PROJECT
                    if define.project:
                        final_project = define.project
                    elif project:
                        final_project = project
                    else:
                        final_project = tester_args.mongo_environment

                    for loop_index, loop_value in loop_items:
                        suite_id_str = f"{suite.suiteID}_L{loop_index}" if is_loop else suite.suiteID

                        run_suite = AtomicSuite(suite_id_str, suite.name, suite.tag, suite.conf, suite.caseList, suite.abstract, suite.parameterized_data, suite.steps_data)
                        run_suite.setWorkspace(solution_workspace)
                        run_suite.setScenarioInfo(define.scenarioID, define.name, suite.scenario_conf)
                        run_suite.setSolutionInfo(solution_id, solution_name)
                        run_suite.setStdoutFile(os.path.join(stdout_dir, f"log_suiteID_{suite_id_str}.txt"))
                        run_suite.setUseValgrind(define.useValgrind)
                        run_suite.setRepeatNum(define.repeatNum)
                        run_suite.setMainTag(getattr(suite, "main_tag", None))
                        run_suite.setRetryCount(getattr(suite, "retry", 0))
                        # setXdistWorkers 内部会同时推导 requiredSlots
                        run_suite.setXdistWorkers(getattr(suite, "xdist_workers", 0))
                        suite_order += 1
                        run_suite.setOrderIndex(suite_order)
                        run_suite.setNluRes(None)
                        run_suite.setproject(final_project)
                        if is_loop:
                            run_suite.setLoopInfo(loop_index, loop_value, loop_total)
                        run_suite_pool.append(run_suite)

            solution_jobs.append(
                {
                    "solution_name": solution_name,
                    "run_suite_pool": run_suite_pool,
                    "scheduler_limits": scheduler_limits,
                }
            )
        
        # 资源自动下载资源
        if tester_args.mongo_ftp_downloader in [0, 1, 2]:
            try:
                ftp_download = FTPDownloader()
                if tester_args.mongo_ftp_downloader == 0:
                    for config in config_set:
                        ftp_download.add_download_file(config, FileType.CONFIG)
                    for case in caselist_set:
                        ftp_download.add_download_file(case, FileType.CASE)
                    ftp_download.add_download_file(tester_args.mongo_parameterized_data, FileType.CASE)
                elif tester_args.mongo_ftp_downloader == 1:
                    for case in caselist_set:
                        ftp_download.add_download_file(case, FileType.CASE)
                        ftp_download.add_download_file(tester_args.mongo_parameterized_data, FileType.CASE) 
                elif tester_args.mongo_ftp_downloader == 2:
                    for config in config_set:
                        ftp_download.add_download_file(config, FileType.CONFIG)
                ftp_download.start_download()
            except Exception as e:
                print(f"❌ Download error: {str(e)}")
                exit(1)

        # 依赖 LCS 的工程，更新 LCS 资源的事件解析引擎
        if tester_args.mongo_environment in LCS_PROJECT_ENVIRONMENTS:
            update_lcs_event_parser(list(config_set))

        for job in solution_jobs:
            print(f"Begin to run solution: {job['solution_name']} with scheduler limits: {job['scheduler_limits']}")
            _run_solution_suites(
                root_dir=root_dir,
                tester_args=tester_args,
                work_mode=work_mode,
                suite_infos=suite_infos,
                solution_name=job["solution_name"],
                run_suite_pool=job["run_suite_pool"],
                scheduler_limits=job["scheduler_limits"],
            )

    time_info['end'] = time.time()
    # solutions = resuce_report(tester_args, time_info)
    # saveResult(solutions, tester_args.mongo_workspace)
    # generate_allure_report(tester_args)

    generate_allure_environment()
    for solution in tester_args.mongo_solution:
        solution_workspace = os.path.join(tester_args.mongo_workspace, os.path.splitext(os.path.basename(solution))[0])
        check_core_file(solution_workspace, time_info['start'], time_info['end'])


def saveResult(solution, mongo_work_space):
    with open("%s/solution.json" % mongo_work_space, 'w') as fp:
        result = json.dumps(solution, ensure_ascii=False)
        fp.write(result)


def run_per_suite(root_dir, tester_args, environment, work_mode, suite_id, suite_name, enable_suites, scene_name, workspace,
                      decoder_config, testcase, suite_tag, suite_abstract, project_config, stdout_file,
                      multiprocess_number, retry_count=0, parameterized_data=None, steps_data=None, use_valgrind=False,
                      loop_index=None, loop_value=None, loop_total=None):
    """
    :param root_dir: 项目运行根目录
    :param tester_args: 自动化运行参数
    :param environment: 运行环境输入
    :param work_mode: 运行工作模式
    :param suite_id: Suite的ID
    :param suite_name: 输出的Suite名称
    :param enable_suites: 可支持的Suite列表
    :param scene_name: 场景名称
    :param workspace: 工作路径
    :param decoder_config: SpeechEngine的配置文件
    :param testcase: 测试用例
    :param suite_tag: 测试用例
    :param suite_abstract: suite简介
    :param project_config: LCS配置文件
    :param stdout_file: 终端执行重定向
    :param multiprocess_number: 并发路数（整数或 None，不再接受 "auto" 字符串）
    :param use_valgrind: 是否使用valgrind
    :return:
    """
    # 判断传入的suite name是否是可支持范围内
    if suite_name not in enable_suites.keys():
        return 'ERROR'

    suite_path = enable_suites[suite_name]["SuitePath"]

    if not os.path.exists(suite_path):
        print("The suite file does not found: {suite_path}, pls check.")
        return 'ERROR'

    if not os.path.exists(decoder_config):
        print(f"The decoder config file does not exit: {decoder_config}, pls check.")
        return 'ERROR'

    if not os.path.exists(testcase):
        print(f"The testcase file does not exit: {testcase}, pls check.")
        return 'ERROR'

    if environment in LCS_PROJECT_ENVIRONMENTS and (not project_config or not os.path.exists(project_config)):
        print(f"The lcs config file does not exit: {project_config}, pls check.")
        return 'ERROR'

    command = [
        "python3", "-m", "pytest", 
        "--capture=no", 
        "-r", "sfE", 
        "-vs", 
        "--color=yes"
    ]

    # 获取重试次数，支持动态调整
    effective_retry_count = tester_args.mongo_retry_count if tester_args.mongo_retry_count is not None else retry_count
    if effective_retry_count and int(effective_retry_count) > 0:
        command.extend(["--reruns", str(effective_retry_count), "--reruns-delay", "0.1"])

    # xdist 并发：multiprocess_number 只接受整数（解析阶段已禁止 "auto"）。
    # 命令行传入的 tester_args.mongo_multiprocess_number 优先级高于 suite 配置。
    # 只有 >= 2 时才真正启用 xdist；0 和 1 退化为单进程执行。
    effective_xdist_workers = tester_args.mongo_multiprocess_number if tester_args.mongo_multiprocess_number is not None else multiprocess_number
    if effective_xdist_workers is not None:
        try:
            xdist_workers = int(effective_xdist_workers)
        except (ValueError, TypeError):
            xdist_workers = 0
        if xdist_workers >= 2:
            command.extend(["--dist", "worksteal", "-n", str(xdist_workers)])

    # ⚡ 为每个Suite创建独立的环境变量副本，避免多线程并发时的竞态条件
    # 所有环境变量都写入suite_env，不再直接修改os.environ
    suite_env = os.environ.copy()

    # 注入 loop 环境变量（仅 loop 模式下有值）
    if loop_index is not None:
        suite_env["LOOP_INDEX"] = str(loop_index)
        suite_env["LOOP_VALUE"] = str(loop_value) if loop_value is not None else ""
        suite_env["LOOP_TOTAL"] = str(loop_total) if loop_total is not None else "1"

    # GDB开关
    if "GDB" in work_mode:
        tester_args.mongo_detail_version = True
        suite_env["GDB_OPTION"] = "1" if "GDB" in work_mode else "0"

    # 是否使用valgrind
    suite_env["VALGRIND_OPTION"] = "1" if use_valgrind else "0"

    # 如果不存在-V，则不现实详细错误信息
    if not tester_args.mongo_detail_version:
        command.append("--tb=no")
    
    # 处理音频数据延迟时间
    if tester_args.mongo_docker is not None:
        suite_env["DockerMode"] = "True" if tester_args.mongo_docker else "False"

    # 处理音频数据延迟时间
    if tester_args.mongo_delay_option is not None:
        suite_env["DELAY_OPTION"] = str(tester_args.mongo_delay_option)

    # 处理TSAP策略
    if tester_args.mongo_strategy_option is not None:
        suite_env["STRATEGY_OPTION"] = str(tester_args.mongo_strategy_option)

    # 报告日志保存开关
    if tester_args.mongo_log_save_option:
        suite_env["SAVE_LOG_OPTION"] = str(tester_args.mongo_log_save_option)

    # Case行过滤指令
    if tester_args.mongo_filter_case_line:
        command.append(f"--mongo_filter_case_line={tester_args.mongo_filter_case_line}")
    
    # 添加参数化文件
    if parameterized_data:
        command.append(f"--mongo_parameterized_data={parameterized_data}")
    
    # 添加参数化文件行过滤
    if tester_args.mongo_parameterized_data_filter:
        command.append(f"--mongo_parameterized_data_filter={tester_args.mongo_parameterized_data_filter}")
    
    # 添加动态步骤参数化文件
    if steps_data:
        command.append(f"--mongo_steps_data={steps_data}")
    
    lib_path = mango_config.get_project_lib_path(environment)
    if lib_path:
        command.append(f"--mongo_lib_path={lib_path}")

    # 创建工作目录
    suite_dir = os.path.join(workspace, scene_name, str(suite_id))
    if not os.path.exists(suite_dir):
        os.makedirs(suite_dir)
    # 将MONGO_SUITE_DIR写入独立的环境变量副本，而非共享的os.environ
    suite_env["MONGO_SUITE_DIR"] = str(suite_dir)

    # 为每个Suite指定独立的缓存目录，防止并发执行时缓存污染，-o 和 cache_dir=... 必须是两个独立参数，否则argparse无法正确解析
    pytest_cache_dir = os.path.join(suite_dir, ".pytest_cache")
    command.extend(["-o", f"cache_dir={pytest_cache_dir}"])

    report_path = os.path.join(suite_dir, f"{suite_id}_report_{suite_name}")
    command.append(f"--mongo_report={report_path}")
    command.append(f"--mongo_root_dir={root_dir}")
    command.append(f"--mongo_config={decoder_config}")
    command.append(f"--mongo_project={project_config}")
    command.append(f"--mongo_case_list={testcase}")
    command.append(f"--mongo_suite_name={suite_name}")
    command.append(f"--mongo_scene_name={scene_name}")
    command.append(f"--mongo_suite_abstract={suite_abstract}")
    command.append(f"--mongo_suite_tag={suite_tag}")
    command.append(f"--mongo_suite_id={suite_id}")
    command.append(f"--mongo_environment={environment}")
    command.append(f"--mongo_workspace={workspace}")
    command.append(f"--alluredir={os.path.join(workspace, 'allure_result')}")
    command.append(f"--basetemp={suite_dir}/data")
    command.append(f"--mongo_suite_dir={suite_dir}")
    command.append(suite_path)

    print("===============================================")
    print(" ".join(command))
    print("===============================================")

    # 使用独立的 suite_env 传给子进程，避免多线程竞态条件污染环境变量。
    # 若提供 stdout_file，则将当前 suite 的 pytest 输出统一落到日志文件；否则保持终端直出。
    if stdout_file:
        os.makedirs(os.path.dirname(stdout_file) or ".", exist_ok=True)
        tee_command = f"set -o pipefail; {shlex.join(command)} 2>&1 | tee {shlex.quote(stdout_file)}"
        result = subprocess.run(
            ["bash", "-lc", tee_command],
            stdin=sys.stdin,
            stdout=sys.stdout,
            stderr=sys.stderr,
            env=suite_env
        ).returncode
    else:
        result = subprocess.run(command, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr, env=suite_env).returncode

    if -11 == result:
        print(f"Execution scene[{scene_name}] suite_name[{suite_name}] suite_id[{suite_id}] crashed!!!")

    if os.path.isfile(report_path):
        return report_path
    else:
        saveCrashInfo(suite_name, suite_id, suite_tag, decoder_config, testcase, scene_name, project_config, report_path)
        return report_path


def saveCrashInfo(suite, suite_id, suite_tag, config, suite_case_list, scene, scenario_config, reportNameRe):
    result = {'suiteName': suite, 'suiteID': suite_id, 'suiteTag': suite_tag, 'suiteConfig': config,
              'suiteCaseList': suite_case_list, 'suiteAbstract': "no result, maybe the current suite execution crashed"}

    result_summary = {'totalTime': 0, 'caseNum': 0, 'failedNum': 0, 'S': 0, 'A': 0, 'B': 0, 'C': 0, 'passed': "no"}
    result['summary'] = result_summary

    result_caseInfo = []
    result['caseInfo'] = result_caseInfo

    with open(reportNameRe, 'w') as fp:
        _result = json.dumps(result, ensure_ascii=False)
        fp.write(_result)


def get_resource_info(config, project_config):
    if not config and not project_config:
        return "Can't found the TSAP_VERSION."

    if len(project_config) == 0 or project_config is None:
        return "Can't found the TSAP_VERSION."

    lcs_config_reader = FileReader(project_config)
    lcs_resource = lcs_config_reader.get_config("LCS_RES_PATH")
    version = os.path.join(lcs_resource, 'ClientRes/cmn/VERSION')
    if os.path.exists(version):
        with open(version, mode='r') as f:
            for i in f.readlines():
                if 'VERSION' in i:
                    return f'TSAP_{i}'
                else:
                    continue
    return ""


def generate_allure_environment():
    """
    生成 Allure environment.properties，展示当前执行指令。
    """
    tester_args = _LAST_TESTER_ARGS
    if tester_args is None:
        return

    allure_result_dirs = []
    if getattr(tester_args, "mongo_solution", None):
        for solution in tester_args.mongo_solution:
            solution_name = os.path.splitext(os.path.basename(solution))[0]
            allure_result_dirs.append(os.path.join(tester_args.mongo_workspace, solution_name, "allure_result"))
    else:
        allure_result_dirs.append(os.path.join(tester_args.mongo_workspace, "allure_result"))

    if not allure_result_dirs:
        return

    launcher = ["python3"]
    if sys.argv:
        launcher.extend(sys.argv)

    full_command = " ".join(shlex.quote(str(arg)) for arg in launcher)

    command_value = ""
    if len(launcher) >= 2:
        command_value = " ".join(str(arg) for arg in launcher[:2])
    elif launcher:
        command_value = str(launcher[0])

    option_lines = []
    idx = 2
    while idx < len(launcher):
        token = str(launcher[idx])
        if token.startswith("-"):
            if idx + 1 < len(launcher) and not str(launcher[idx + 1]).startswith("-"):
                option_lines.append((token, str(launcher[idx + 1])))
                idx += 2
            else:
                option_lines.append((token, "true"))
                idx += 1
        else:
            option_lines.append((f"arg_{idx - 1}", token))
            idx += 1

    env_lines = []
    env_lines.append(f"Command={command_value}\n")
    for key, value in option_lines:
        env_lines.append(f"{key}={value}\n")
    env_lines.append(f"FullCommand={full_command}\n")

    for allure_result_dir in allure_result_dirs:
        os.makedirs(allure_result_dir, exist_ok=True)
        env_file = os.path.join(allure_result_dir, "environment.properties")
        with open(env_file, "w", encoding="utf-8") as f:
            f.writelines(env_lines)


def generate_allure_report(tester_args):
    try:
        aibs_version, lcs_version = None, None
        if tester_args.mongo_library_downloader:
            aibs_version, lcs_version = tester_args.mongo_library_downloader.split('-')

        solutions = tester_args.mongo_solution
        for solution in solutions.split("-"):
            solution_name = solution.split("/")[-1]
            solution_path = os.path.join(tester_args.mongo_work_space, solution_name)
            allure_report_path = os.path.join(solution_path, 'allure_report')
            allure_result_path = os.path.join(solution_path, 'allure_result')
            environment_config = os.path.join(allure_result_path, "environment.properties")
            tsap_version = get_resource_info(tester_args.mongo_filter_config, tester_args.mongo_project)
            with open(environment_config, mode='w+') as f:
                f.write('SystemVersion: linux-x86\n')
                f.write(f"SolutionFile: {solution}\n")
                f.write(f"AibsVersion : {aibs_version}\n")
                f.write(f"LCSVersion  : {lcs_version}\n")
                f.write(f"TSAPVersion  : {tsap_version}\n")

            print(f"Begin to generate allure report: {solution_path} start....")
            allure_cmd = ['allure', 'generate', allure_result_path, '-o', allure_report_path]
            subprocess.run(allure_cmd)
            print(f"Generate allure report:{solution_path} complete....\n")

            # 将 allure_result/mango_report/ 拷贝到 allure_report/mango-reports/，供前端 Tab 读取
            src_mango = os.path.join(allure_result_path, 'mango_report')
            dst_mango = os.path.join(allure_report_path, 'mango-reports')
            if os.path.exists(src_mango):
                if os.path.exists(dst_mango):
                    shutil.rmtree(dst_mango)
                shutil.copytree(src_mango, dst_mango)
                print(f"Mango reports copied: {src_mango} -> {dst_mango}")
            else:
                print(f"No mango_report directory found, skipping copy: {src_mango}")

            print(f"Run command:\nallure open {allure_report_path} -p 8889")
            print(f"See the online report:\n\thttp://10.54.1.15:8889")

            if tester_args.mongo_message_wechat:
                # 发送企业微信通知
                message = SendMessage()
                message.run_start(solution_path, aibs_version, lcs_version)
    except Exception as e:
        print("generate report error: ", e)
