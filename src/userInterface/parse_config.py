#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2023/3/21 18:50
# @Author  : huidong.bai
# @File    : parse_config.py
# @Software: PyCharm
# @Mail    : MasterBai2018@outlook.com


import pdb
import copy
import sys
import os
import subprocess
import json
import string
import re
import datetime
from enum import Enum
from src.utils.common import mango_config


class MongoConfig:
    emailReceiver = []
    emailTitle = None
    emailContent = None
    mongoConfig = None
    testDataDate = None
    emailOption = None

    def __init__(self, mongoConfig):
        self.reset()
        self.mongoConfig = mongoConfig
        self.parse()

    def reset(self):
        self.emailReceiver = None
        self.emailTitle = None
        self.emailContent = None
        self.testDataDate = None
        self.emailOption = None

    def get_emailOption(self):
        return self.emailOption

    def get_emailReceiver(self):
        return self.emailReceiver

    def get_emailTitle(self):
        return self.emailTitle

    def get_emailContent(self):
        return self.emailContent

    def getTestDataDate(self):
        return self.testDataDate

    def isDateMatch(self, caselist):
        if self.testDataDate is None:
            return True
        caseDate = caselist.split("/")[-1][0:10]
        if len(caseDate.split("-")) >= 3:
            beginDate = self.testDataDate.split("~")[0]
            endDate = self.testDataDate.split("~")[1]
            difference = self.__getDifference(beginDate, caseDate)
            difference_ = self.__getDifference(caseDate, endDate)
            if difference >= 0 and difference_ >= 0:
                return True
        return False

    def __getDifference(self, begin_date, end_date):
        date1 = datetime.datetime.strptime(begin_date, "%Y-%m-%d")
        date2 = datetime.datetime.strptime(end_date, "%Y-%m-%d")
        difference = (date2 - date1).days
        return difference

    def parse(self):
        try:
            with open(self.mongoConfig, 'r') as fp:
                lines = fp.readlines()
        except Exception as e:
            print(f'Error: {e} : The path [{self.mongoConfig}] is not exists')
        else:
            for line in lines:
                data = line.replace('\n', '')
                if '#' in data:
                    continue
                if 'RECEIVER' in data:
                    emailReceiver = data.split('=')[-1]
                    for i in range(0, len(emailReceiver)):
                        if emailReceiver[i] != ' ':
                            self.emailReceiver = emailReceiver[i:].replace(' ', '').split(',')
                            break
                if 'TITLE' in data:
                    emailTitle = data.split('=')[-1]
                    for j in range(0, len(emailTitle)):
                        if emailTitle[j] != ' ':
                            self.emailTitle = emailTitle[j:]
                            break
                if 'CONTENT' in data:
                    emailContent = data.split('=')[-1]
                    for k in range(0, len(emailContent)):
                        if emailContent[k] != ' ':
                            self.emailContent = emailContent[k:]
                            break
                if 'TEST_DATA_DATE' in data:
                    testDataDate = data.split('=')[-1]
                    for l in range(0, len(testDataDate)):
                        if testDataDate[l] != ' ':
                            self.testDataDate = testDataDate[l:]
                            if "~" not in self.testDataDate:
                                currentDate = datetime.datetime.now().strftime('%Y-%m-%d')
                                currentYear = currentDate.split("-")[0]
                                currentMonth = currentDate.split("-")[1]
                                month = int(currentMonth) - int(self.testDataDate)
                                if month <= 0:
                                    month_ = month + 12
                                    year = int(currentYear) - 1
                                    self.testDataDate = currentDate.replace(currentMonth, '0' + str(month_)).replace(
                                        currentYear, str(year))
                                elif month > 0:
                                    self.testDataDate = currentDate.replace(currentMonth, '0' + str(month))
                                self.testDataDate += '~' + currentDate
                            break
                if 'EMAIL_OPTION' in data:
                    emailOption = data.split('=')[-1]
                    for m in range(0, len(emailOption)):
                        if emailOption[m] != ' ':
                            self.emailOption = emailOption[m:]
                            break


class AssertLevel(Enum):
    SCENARIO = 0
    SUITE = 1
    CASE = 2


class Assertion:
    level = AssertLevel.CASE
    info = None

    def __init__(self, level, info):
        self.level = level
        self.info = info
        return


class Suite:
    suiteCounter = 0
    suiteID = 0
    name = None
    conf = None
    tag = None
    caseList = None
    parameterized_data = None  # 参数化数据文件路径（-P参数）
    steps_data = None  # 动态步骤数据文件路径（-S参数）
    scenario_conf = None
    repeatNum = 1
    realTime = False
    abstract = None
    assertion = None
    main_tag = None

    def __init__(self, ID, name, conf, _tag, caseList, parameterized_data=None, steps_data=None):
        # pdb.set_trace()
        self.suiteID = ID
        self.name = name
        self.conf = conf
        if _tag is not None:
            # self.tag = copy.deepcopy(_tag.replace('[', '').split(']')[0:-1])
            self.tag = _tag
        self.caseList = caseList
        self.parameterized_data = parameterized_data  # 保存参数化文件路径
        self.steps_data = steps_data  # 保存动态步骤文件路径
        Suite.suiteCounter += 1
        self.assertion = None
        self.main_tag = None

    def set_repeatNum(self, number):
        self.repeatNum = number

    def set_isRealTime(self, flag):
        if flag.lower() == "true":
            self.isRealTime = True
        else:
            self.isRealTime = False

    def set_abstract(self, data):
        self.abstract = data

    def set_scenarioConfig(self, config):
        self.scenario_conf = config

    def set_assertion(self, assertion):
        self.assertion = Assertion(AssertLevel.SUITE, assertion)


class Scenario:
    scenarioCounter = 0
    scenarioID = 0
    suiteNum = 0
    curSuiteNum = 0
    suiteInfo = []
    curSuite = None
    stdoutFile = None
    isParallel = False
    useValgrind = False
    config = None
    repeatNum = 1
    assertion = None
    owner = None
    project = None  # DEFINE块内的独立project配置

    def __init__(self, name):
        self.name = name
        self.suiteNum = 0
        self.curSuiteNum = 0
        self.suiteInfo = []
        self.curSuite = None
        self.stdoutFile = None
        Scenario.scenarioCounter += 1
        self.scenarioID = Scenario.scenarioCounter
        self.assertion = None
        self.owner = None
        self.project = None

    def set_useValgrind(self, flag):
        if flag.lower() == "true":
            self.useValgrind = True
        elif flag.lower() == "false":
            self.useValgrind = False
        else:
            self.useValgrind = False
            print(f"the parameter:{flag} of 'VALGRIND' in config:{self.config} is error")

    def set_isParallel(self, flag):
        if flag.lower() == "true":
            self.isParallel = True
        elif flag.lower() == "false":
            self.isParallel = False
        else:
            self.isParallel = False
            print("the parameter:%s of 'PARALLEL' in config:%s is error" % flag, self.config)

    def set_repeatNum(self, number):
        self.repeatNum = number

    def set_purposeData(self, data):
        self.purposeData = data

    def set_stdoutFile(self, stdoutFile):
        self.stdoutFile = stdoutFile

    def set_suite(self, suiteName, suiteConf, suiteTag, caseList, parameterized_data=None, steps_data=None):
        # pdb.set_trace()
        if self.curSuiteNum != 0:
            self.suiteInfo.append(self.curSuite)
        self.curSuiteNum += 1
        self.curSuite = Suite(self.curSuiteNum, suiteName, suiteConf, suiteTag, caseList, parameterized_data, steps_data)
        self.suiteNum = Suite.suiteCounter

    def set_suiteParam(self, param, data):
        if param == "ARG_REPEAT":
            self.curSuite.set_repeatNum(int(data))
        elif param == "ARG_PARALLEL":
            self.curSuite.set_isRealTime(data)
        elif param == "ARG_ABSTRACT":
            self.curSuite.set_abstract(data)
        elif param == "ARG_ASSERT":
            self.curSuite.set_assertion(data)

    def set_scenarioConf(self, config):
        self.config = config

    def set_scenarioOwner(self, owner):
        self.owner = owner.split(',')[:]

    def set_scenarioAssertion(self, assertion):
        self.assertion = Assertion(AssertLevel.SCENARIO, assertion)

    def set_project(self, project_value):
        """设置DEFINE块内的project配置，使用与全局PROJECT相同的解析逻辑"""
        if project_value not in mango_config.get_all_project_names():
            print(f"ERROR : The project name is not valid. Please check: {project_value}")
            sys.exit(0)
        self.project = project_value.lower()

    def end(self):
        if self.curSuite is None:
            return
        self.suiteInfo.append(self.curSuite)
        for suite in self.suiteInfo:
            suite.set_scenarioConfig(self.config)


class Parse:
    MAIN_TAGS = {"ONLINE", "OFFLINE", "CP"}
    user = None
    url = None
    jenkins = []
    needLoad = False
    project = None
    needCleanWorkSpace = True
    workspace = None
    concurrent_info = {}
    dataVersion = None
    pstt_server = None
    django_server = None
    sceneList = []
    enable = []
    disable = []
    tag = []
    needfullTag = []
    solutionName = None
    mongoConfig = None
    entityConfig = None
    keyWords = ['DEFINE', 'NAME', 'CONFIG', 'SUITE', 'REPEAT', 'PARALLEL', 'VALGRIND', 'PURPOSE', 'ARG_PARALLEL',
                'ARG_REPEAT', 'ARG_ASSERT', 'END', '@']
    sceneParam = ['CONFIG', 'REPEAT', 'PARALLEL', 'PURPOSE', 'STDOUT', 'VALGRIND', 'ASSERT']
    suiteParam = ['ARG_PARALLEL', 'ARG_REPEAT']

    def __init__(self, cfgFile, _tag, _enable, work):
        self.reset()
        self.workspace = work
        self.config = cfgFile
        # pdb.set_trace()
        if _tag is not None:
            self.tag = copy.deepcopy(_tag.replace('[', '').split(']')[0:-1])
            for tag_ in self.tag:
                if '+' in tag_:
                    self.needfullTag.append(tag_[1:])
        if _enable is not None:
            self.enable = _enable.split(',')
        self.solutionName = self.extractSolutionName(self.config)
        self.parse()

    def extractSolutionName(self, config):
        if config is not None:
            return config.split('/')[-1]
        return None

    def reset(self):
        self.user = None
        self.url = None
        self.jenkins = []
        self.needLoad = False
        self.project = None
        self.needCleanWorkSpace = True
        self.workspace = None
        self.concurrent_info = {}
        self.dataVersion = None
        self.pstt_server = None
        self.django_server = None
        self.sceneList = []
        self.enable = []
        self.disable = []
        self.tag = []
        self.needfullTag = []
        self.solutionName = None
        self.entityConfig = None
        self.mongoConfig = None
        self.scheduler_limits = {
            "GLOBAL_MAX_WORKERS": None,
            "ONLINE_MAX_WORKERS": None,
            "CP_MAX_WORKERS": None,
            "OFFLINE_MAX_WORKERS": None,
        }

    def get_mongoConfig(self):
        if self.entityConfig is None:
            self.entityConfig = MongoConfig(self.mongoConfig)
        return self.entityConfig

    def get_enable(self):
        return self.enable

    def get_disable(self):
        return self.disable

    def get_tasks(self):
        return self.sceneList

    def get_needLoad(self):
        return self.needLoad

    def get_project(self):
        return self.project

    def get_needCleanWorkSpace(self):
        return self.needCleanWorkSpace

    def get_concurrentCtr(self, tag):
        # 提取所有[]内的内容为key列表，查找self.concurrent_info中这些key的最小value
        keys = re.findall(r'\[([^\[\]]+)\]', str(tag))
        min_value = self.concurrent_info.get("OTHERS")
        for key in keys:
            value = self.concurrent_info.get(key)
            if value is not None:
                if min_value is None or value < min_value:
                    min_value = value
        return min_value

    def get_user(self):
        return self.user

    def get_url(self):
        return self.url

    def get_jenkins(self):
        return self.jenkins

    def get_pstt_serverInfo(self):
        return self.pstt_server

    def get_django_serverInfo(self):
        return self.django_server

    def get_scheduler_limits(self):
        return self.scheduler_limits

    def setConcurrentCtr(self, info):
        infoList = info.split(',')
        for info in infoList:
            key, value = info.split('-')
            self.concurrent_info[key] = int(value)

    def _set_scheduler_from_concurrent_controller(self, raw_value, abs_line):
        """
        支持新格式:
            CONCURRENT_CONTROLLER:MAX-20;ONLINE-2;CP-2;OFFLINE-auto
        兼容旧格式:
            CONCURRENT_CONTROLLER:ONLINE-2,CP-2,OTHERS-5
        """
        if raw_value is None:
            return

        text = raw_value.strip()
        if not text:
            return

        # 新格式：
        #   MAX-20;ONLINE-2;CP-2;OFFLINE-auto
        #   MAX-20,ONLINE-2,CP-2,OFFLINE-auto
        # 兼容同语义的冒号分隔写法（MAX:20;ONLINE:2;...）
        if any(sep in text for sep in (';', ',')) and ('-' in text or ':' in text):
            key_map = {
                "MAX": "GLOBAL_MAX_WORKERS",
                "ONLINE": "ONLINE_MAX_WORKERS",
                "CP": "CP_MAX_WORKERS",
                "OFFLINE": "OFFLINE_MAX_WORKERS",
            }
            normalized_text = text.replace(",", ";")
            items = [x.strip() for x in normalized_text.split(';') if x.strip()]
            for item in items:
                if "-" in item:
                    key, value = item.split("-", 1)
                elif ":" in item:
                    key, value = item.split(":", 1)
                else:
                    print(f"ERROR : File '{self.config}', line '{abs_line}', CONCURRENT_CONTROLLER\n\tInvalid item format: {item}")
                    sys.exit(0)
                key = key.strip().upper()
                mapped_key = key_map.get(key)
                if mapped_key is None:
                    print(f"ERROR : File '{self.config}', line '{abs_line}', CONCURRENT_CONTROLLER\n\tUnsupported key: {key}. Only MAX/ONLINE/CP/OFFLINE are allowed.")
                    sys.exit(0)
                self._set_scheduler_limit(mapped_key, value, abs_line)
            return

        # 旧格式兼容：ONLINE-2,CP-2,OTHERS-5
        if '-' in text:
            self.setConcurrentCtr(text)
            return

    def _parse_solution_kv(self, data):
        if ":" in data:
            key, value = data.split(":", 1)
            return key, value
        if "=" in data:
            key, value = data.split("=", 1)
            return key, value
        return None, None

    def _set_scheduler_limit(self, key, value, abs_line):
        key = key.upper()
        value = value.strip()
        if key in ("GLOBAL_MAX_WORKERS", "ONLINE_MAX_WORKERS", "CP_MAX_WORKERS"):
            try:
                parsed = int(value)
            except Exception:
                print(f"ERROR : File '{self.config}', line '{abs_line}', {key}\n\tThe value must be an integer.")
                sys.exit(0)
            if parsed < 0:
                print(f"ERROR : File '{self.config}', line '{abs_line}', {key}\n\tThe value must be >= 0.")
                sys.exit(0)
            if key == "GLOBAL_MAX_WORKERS" and parsed < 1:
                print(f"ERROR : File '{self.config}', line '{abs_line}', {key}\n\tThe value must be >= 1.")
                sys.exit(0)
            self.scheduler_limits[key] = parsed
            return
        if key == "OFFLINE_MAX_WORKERS":
            if value.lower() == "auto":
                self.scheduler_limits[key] = "auto"
                return
            try:
                parsed = int(value)
            except Exception:
                print(f"ERROR : File '{self.config}', line '{abs_line}', {key}\n\tThe value must be an integer or 'auto'.")
                sys.exit(0)
            if parsed < 0:
                print(f"ERROR : File '{self.config}', line '{abs_line}', {key}\n\tThe value must be >= 0 or 'auto'.")
                sys.exit(0)
            self.scheduler_limits[key] = parsed
            return

    def _validate_scheduler_limits(self):
        for key, value in self.scheduler_limits.items():
            if value is None:
                print(f"ERROR : File '{self.config}'\n\tMissing required scheduler key: {key}")
                sys.exit(0)

    def _extract_tag_tokens(self, suite_tag):
        if suite_tag is None:
            return []
        return [t.strip().upper() for t in re.findall(r'\[([^\[\]]+)\]', str(suite_tag))]

    def _validate_main_tag(self, suite_tag, abs_line, raw_line):
        tags = self._extract_tag_tokens(suite_tag)
        if not tags:
            print(f"ERROR : File '{self.config}', line '{abs_line}', {raw_line}\n\tSuite tag is required and must include one main tag in [ONLINE]/[OFFLINE]/[CP].")
            sys.exit(0)
        if len(tags) != len(set(tags)):
            print(f"ERROR : File '{self.config}', line '{abs_line}', {raw_line}\n\tDuplicated tags are not allowed.")
            sys.exit(0)
        main_tags = [tag for tag in tags if tag in self.MAIN_TAGS]
        if len(main_tags) != 1:
            print(f"ERROR : File '{self.config}', line '{abs_line}', {raw_line}\n\tSUiteTag配置错误，请保证Suite的主Tag中存在如下: [ONLINE]/[OFFLINE]/[CP].")
            sys.exit(0)
        return main_tags[0]

    def setDataVersion(self, version):
        self.dataVersion = version

    def getOwner(self, scenario):
        for s in self.sceneList:
            if s.name == scenario:
                return s.owner
        return None

    def getScenarioAssertion(self, scenarioName):
        for scenario in self.sceneList:
            if scenario.name == scenarioName:
                return scenario.assertion
        return None

    def getSuiteAssertion(self, scenarioName, suiteID):
        for scenario in self.sceneList:
            if scenario.name == scenarioName:
                for suite in scenario.suiteInfo:
                    if suite.suiteID == suiteID:
                        return suite.assertion
        return None

    def getSuiteCaseList(self, scenarioName, suiteID):
        for scenario in self.sceneList:
            if scenario.name == scenarioName:
                for suite in scenario.suiteInfo:
                    if suite.suiteID == suiteID:
                        if suite.caseList is not None:
                            return suite.caseList.split('/')[-1]
        return None

    def getMatchFile(self, dirName, fileRegular):
        matchedFile = []
        for root, dirs, files in os.walk(dirName):
            for file_ in files:
                if re.match(fileRegular, file_):
                    fileName = os.path.join(root, file_)
                    matchedFile.append(fileName)
        return matchedFile

    def checkMongoVersion(self, workspace, tools):
        if self.dataVersion is None:
            print("    The data's version is None !\n    Configure version information in secenario_config, like this:")
            print("        BOLOO_VERSION : EQ mongo-x.x.x, or")
            print("        BOLOO_VERSION : GT mongo-x.x.x, or")
            print("        BOLOO_VERSION : GE mongo-x.x.x")
            return False
        for tool in tools:
            subprocess.call("%s/%s --mongo_work_space=%s --mongo_version" % (workspace, tool, workspace), shell=True)
            try:
                with open("%s/version" % workspace, 'r') as fp:
                    data = fp.read()
                    try:
                        version_info = json.loads(data, encoding="utf-8")
                    except:
                        data = data.decode("gbk").encode("utf-8")
                        version_info = json.loads(data, encoding="utf-8")
            except IOError:
                print("%s/version does not exist." % workspace)
            else:
                version = version_info["version"]
                print("the current Mongo version:%s the data's version:%s" % (version, self.dataVersion))
                # pdb.set_trace()
                MongoVersion = version.split('.')
                dataVersion = self.dataVersion.split('-')[1].split('.')
                fp.close()
                digitLen = len(MongoVersion)
                if digitLen != len(dataVersion):
                    return False
                MongoVersion_ = int(MongoVersion[0]) * 100 + int(MongoVersion[1]) * 10 + int(MongoVersion[2])
                dataVersion_ = int(dataVersion[0]) * 100 + int(dataVersion[1]) * 10 + int(dataVersion[2])
                if 'EQ' in self.dataVersion:
                    if MongoVersion_ != dataVersion_:
                        return False
                elif 'GT' in self.dataVersion:
                    if MongoVersion_ <= dataVersion_:
                        return False
                elif 'GE' in self.dataVersion:
                    if MongoVersion_ < dataVersion_:
                        return False
                else:
                    return False
        return True

    def scanInfo(self, scenario, suiteInfoLen, suiteInfo, index, data, line):
        if suiteInfoLen < 3:
            print("ERROR : File '%s', line '%d', %s\nYou must give four params at least\n \
                  'SCAN : suitename,config,caselistdir,regular'" % (self.config, index + 1, data))
            sys.exit(0)
        else:
            matched = False
            suiteTag = None
            suiteCaseList = None
            suiteRegular = None
            caseDir = suiteInfo[2]
            suiteCaseLists = []
            if suiteInfoLen == 4:
                if '[' in suiteInfo[3] and ']' in suiteInfo[3]:
                    suiteTag = suiteInfo[3]
                elif '<' in suiteInfo[3] and '>' in suiteInfo[3]:
                    suiteRegular = suiteInfo[3]
                else:
                    print(
                        "ERROR : File '%s', line '%d', %s\nThe tag format must be '[XX]'." % (self.config, index, data))
            elif suiteInfoLen == 5:
                if '[' in suiteInfo[3] and ']' in suiteInfo[3]:
                    suiteTag = suiteInfo[3]
                elif '<' in suiteInfo[3] and '>' in suiteInfo[3]:
                    suiteRegular = suiteInfo[3]
                else:
                    print(
                        "ERROR : File '%s', line '%d', %s\nThe tag format must be '[XX]'." % (self.config, index, data))
                if '[' in suiteInfo[4] and ']' in suiteInfo[4]:
                    suiteTag = suiteInfo[4]
                elif '<' in suiteInfo[4] and '>' in suiteInfo[4]:
                    suiteRegular = suiteInfo[4]
                else:
                    print(
                        "ERROR : File '%s', line '%d', %s\nThe tag format must be '[XX]'." % (self.config, index, data))
            if len(self.tag) > 0:
                if suiteTag is None:
                    index += 1
                    return index
                suiteTagList = suiteTag.replace('[', '').split(']')[0:1]
                if '+' in suiteTagList:
                    matched = True
                elif '-' in suiteTagList:
                    matched = False
                else:
                    if len(self.needfullTag) > 0:
                        matched = True
                        for _tag in self.needfullTag:
                            if _tag not in suiteTagList:
                                matched = False
                                break
                    else:
                        for _tag in self.tag:
                            if _tag in suiteTagList:
                                matched = True
                                break
            else:
                matched = True
            if matched:
                ARG = None
                index += 1
                if index <= line[index] and 'ARG_' in line[index]:
                    ARG = line[index]
                if suiteRegular is None:
                    suiteRegular_ = ''
                else:
                    suiteRegular_ = suiteRegular.replace('<', '').replace('>', '')
                try:
                    suiteCaseLists = self.getMatchFile(caseDir, suiteRegular_)
                except Exception as e:
                    print(f"Error:{e}, please check the match regular!")
                else:
                    for suiteCaseList in suiteCaseLists:
                        if self.mongoConfig is not None:
                            matched = self.mongoConfig.isDateMatch(suiteCaseList)
                        if matched:
                            main_tag = self._validate_main_tag(suiteTag, index + 1, data)
                            scenario.set_suite(suiteInfo[0], suiteInfo[1], suiteTag, suiteCaseList)
                            scenario.curSuite.main_tag = main_tag
                        else:
                            continue
                        if ARG is not None:
                            suiteParam = ARG.split(':')
                            scenario.set_suiteParam(suiteParam[0], suiteParam[1])
            else:
                index += 1
                if 'ARG' in line[index]:
                    index += 1
                return index
        index += 1
        return index

    def PRINT(self):
        log = ""
        if os.path.exists(self.workspace) is False:
            os.makedirs(self.workspace)
        log = "%s/solution.log" % self.workspace
        with open(log, 'w') as file_log:
            for SCENARIO in self.sceneList:
                file_log.write("SCENARIO NAME:%s  CONF:%s\n" % (SCENARIO.name, SCENARIO.config))
                for SUITE in SCENARIO.suiteInfo:
                    file_log.write(
                        "    suite_id:%d  suite_name:%s  suite_tag:%s  suite_config:%s  suite_caseList:%s\n" % (
                        SUITE.suiteID, SUITE.name, SUITE.tag, SUITE.conf, SUITE.caseList))
                file_log.write("\n\n")

    def parse(self):
        try:
            with open(self.config, 'r') as fp:
                _line = fp.readlines()
        except IOError:
            print("The solution file : %s does not exist." % self.config)
            exit(0)
        else:
            '''
            for i in range(0, len(line)):
                data = line[i].expandtabs(8).strip().replace(' ', '').split('@')[0]
                line[i] = data
            '''
            absIndex = 0
            absPos = []
            line = []
            for line_ in _line:
                # remove the unnecessary indents, spaces and comments
                data = line_.expandtabs(8).strip().replace(' ', '').split('@')[0]
                absIndex += 1
                if len(data) > 0:
                    line.append(data)
                    absPos.append(absIndex)
            index = 0
            flag = 0
            while index < len(line):
                # pdb.set_trace()
                data = line[index]
                if 'DEFINE' not in data and '@' not in data:
                    key, value = self._parse_solution_kv(data)
                    if key and key.upper() in self.scheduler_limits:
                        self._set_scheduler_limit(key, value, absPos[index])
                        index += 1
                        continue
                    if "USER" in data:
                        self.user = data.split(':')[1].replace('/', ':')
                        index += 1
                        continue
                    if "URL" in data:
                        _url = data.split(':')
                        for i in range(0, len(_url)):
                            if i == 1:
                                self.url = _url[i]
                            elif i > 1:
                                self.url += ":%s" % _url[i]
                        index += 1
                        continue
                    if "JENKINS" in data:
                        self.jenkins = data.split(':')[1].split(',')
                        index += 1
                        continue
                    if "NEEDLOAD" in data:
                        if "YES" in data or "yes" in data:
                            self.needLoad = True
                        index += 1
                        continue
                    if "PROJECT" in data:
                        validate_project = data.split(':')[1].lower()
                        if len(validate_project) > 0 and validate_project not in mango_config.get_all_project_names():
                            print(f"ERROR : File '{self.config}', line '{index + 1}', {data}\n\tThe project name is not valid. Please check the project name in the config file.")
                            sys.exit(0)
                        self.project = validate_project;
                        index += 1
                        continue
                    if "CLEAN_BOLOO_WORKSPACE" in data:
                        if "NO" in data or "no" in data:
                            self.needCleanWorkSpace = False
                        index += 1
                        continue
                    if "CONCURRENT_CONTROLLER" in data:
                        controller_raw = data.split(':', 1)[1] if ':' in data else ''
                        self._set_scheduler_from_concurrent_controller(controller_raw, absPos[index])
                        index += 1
                        continue
                    if "PSTT_SERVER" in data:
                        self.pstt_server = data.split(':')[1]
                        index += 1
                        continue
                    if "DJANGO_SERVER" in data:
                        self.django_server = data.split(':')[1]
                        index += 1
                        continue
                    if "BOLOO_VERSION" in data:
                        self.setDataVersion(data.split(':')[1])
                        index += 1
                        continue
                    if "ENABLE" in data:
                        if len(self.enable) == 0:
                            self.enable = data.split(':')[1].split(',')
                        index += 1
                        continue
                    if "DISABLE" in data:
                        self.disable = data.split(':')[1].split(',')
                        index += 1
                        continue
                    if "CONFIG" in data:
                        self.mongoConfig = data.split(':')[1]
                        self.mongoConfig = self.get_mongoConfig()
                        index += 1
                        continue
                    if 0 == len(data):
                        index += 1
                        continue
                    for keyword in self.keyWords:
                        if keyword in data:
                            print(
                                f"ERROR : File '{self.config}', line '{index + 1}', {data}\n\tThe '{keyword}' is a keyWord in Mongo, it must be used between 'DEFINE' and 'END'.")
                            sys.exit(0)
                    print("WARING : File '%s', line '%d', %s" % self.config, absPos[index], data)
                    index += 1
                    continue
                # pdb.set_trace()
                if 'DEFINE' in data:
                    flag = 1
                    if len(data) > len("DEFINE"):
                        print(
                            "WARING : File '%s', line '%d', %s\n\tThere should be nothing behind 'DEFINE'." % self.config,
                            index + 1, data)
                    index += 1
                    data = line[index]
                    if 'NAME:' not in data:
                        print(
                            f"ERROR : File '{self.config}', line '{index + 1}', {data}\n\tYou must give the name of the current scene when you defined scene test.")
                        sys.exit(0)
                    sceneName = data.split(':')[1]
                    scenario = Scenario(sceneName)
                    index += 1
                    while index < len(line):
                        data = line[index]
                        if 0 == len(data):
                            index += 1
                            continue
                        if 'SCAN' in data:
                            # pdb.set_trace()
                            suiteInfo = data.split(':')[1].split(',')
                            suiteInfoLen = len(suiteInfo)
                            index = self.scanInfo(scenario, suiteInfoLen, suiteInfo, index, data, line)
                            continue
                        if 'SUITE:' in data:
                            # pdb.set_trace()
                            suiteInfo = data.split(':')[1].split(',')
                            suiteInfoLen = len(suiteInfo)
                            # print suiteInfo[0],suiteInfo[1]
                            if suiteInfoLen < 2:
                                print(
                                    "ERROR : File '%s', line '%d', %s\n\tThere must be ',' between suite and config'." % self.config,
                                    index + 1, data)
                                sys.exit(0)
                            else:
                                matched = False
                                suiteTag = None
                                suiteCaseList = None
                                parameterized_data = None  # 参数化数据文件（-P参数）
                                steps_data = None  # 动态步骤数据文件（-S参数）
                                
                                # 解析SUITE格式扩展：
                                # 格式1: NAME,CONFIG,CASELIST
                                # 格式2: NAME,CONFIG,CASELIST,[TAG]
                                # 格式3: NAME,CONFIG,CASELIST,PARAMETERIZED_DATA
                                # 格式4: NAME,CONFIG,CASELIST,PARAMETERIZED_DATA,[TAG]
                                # 格式5: NAME,CONFIG,CASELIST,PARAMETERIZED_DATA,STEPS_DATA
                                # 格式6: NAME,CONFIG,CASELIST,PARAMETERIZED_DATA,STEPS_DATA,[TAG]
                                # 
                                # suiteInfo[0] = NAME
                                # suiteInfo[1] = CONFIG
                                # suiteInfo[2] = CASELIST
                                # suiteInfo[3] = PARAMETERIZED_DATA 或 [TAG]
                                # suiteInfo[4] = STEPS_DATA 或 [TAG]
                                # suiteInfo[5] = [TAG]
                                
                                if len(self.tag) > 0:
                                    # pdb.set_trace()
                                    if suiteInfoLen == 2:
                                        index += 1
                                        continue
                                    elif suiteInfoLen == 3:
                                        # NAME,CONFIG,CASELIST 或 NAME,CONFIG,CASELIST,[TAG]
                                        suiteCaseList = suiteInfo[2]
                                        if '[' in suiteInfo[2] and ']' in suiteInfo[2]:
                                            suiteTag = suiteInfo[2]
                                            suiteCaseList = None
                                    elif suiteInfoLen == 4:
                                        # NAME,CONFIG,CASELIST,PARAMETERIZED_DATA 或 NAME,CONFIG,CASELIST,[TAG]
                                        suiteCaseList = suiteInfo[2]
                                        if '[' in suiteInfo[3] and ']' in suiteInfo[3]:
                                            # 第4个是TAG，没有参数化文件
                                            suiteTag = suiteInfo[3]
                                        else:
                                            # 第4个是参数化文件，没有TAG
                                            parameterized_data = suiteInfo[3]
                                    elif suiteInfoLen == 5:
                                        # NAME,CONFIG,CASELIST,PARAMETERIZED_DATA,STEPS_DATA 或 NAME,CONFIG,CASELIST,PARAMETERIZED_DATA,[TAG]
                                        suiteCaseList = suiteInfo[2]
                                        parameterized_data = suiteInfo[3]
                                        if '[' in suiteInfo[4] and ']' in suiteInfo[4]:
                                            # 第5个是TAG
                                            suiteTag = suiteInfo[4]
                                        else:
                                            # 第5个是STEPS_DATA
                                            steps_data = suiteInfo[4]
                                    else:
                                        # suiteInfoLen >= 6: NAME,CONFIG,CASELIST,PARAMETERIZED_DATA,STEPS_DATA,[TAG]
                                        suiteCaseList = suiteInfo[2]
                                        parameterized_data = suiteInfo[3]
                                        steps_data = suiteInfo[4]
                                        if suiteInfoLen >= 6 and '[' in suiteInfo[5] and ']' in suiteInfo[5]:
                                            suiteTag = suiteInfo[5]

                                    if suiteTag is None:
                                        print(f"ERROR : File '{self.config}', line '{absPos[index]}', {data}\n\tSuite tag is required and must include one main tag in [ONLINE]/[OFFLINE]/[CP].")
                                        sys.exit(0)

                                    suiteTagList = suiteTag.replace('[', '').split(']')[0:-1]

                                    # +在标签中，表示必须跑的suite
                                    if '+' in suiteTagList:
                                        matched = True
                                    # -在标签中，表示一定不会跑的suite
                                    elif '-' in suiteTagList:
                                        matched = False
                                    else:
                                        if len(self.needfullTag) > 0:
                                            matched = True
                                            for _tag in self.needfullTag:
                                                if _tag not in suiteTagList:
                                                    matched = False
                                                    break
                                        else:
                                            for _tag in self.tag:
                                                if _tag in suiteTagList:
                                                    matched = True
                                                    break
                                else:
                                    matched = True

                                    if suiteInfoLen == 2:
                                        suiteTag = None
                                        suiteCaseList = None
                                    elif suiteInfoLen == 3:
                                        # NAME,CONFIG,CASELIST 或 NAME,CONFIG,CASELIST,[TAG]
                                        if '[' in suiteInfo[2] and ']' in suiteInfo[2]:
                                            suiteTag = suiteInfo[2]
                                        else:
                                            suiteCaseList = suiteInfo[2]
                                    elif suiteInfoLen == 4:
                                        # NAME,CONFIG,CASELIST,PARAMETERIZED_DATA 或 NAME,CONFIG,CASELIST,[TAG]
                                        suiteCaseList = suiteInfo[2]
                                        if '[' in suiteInfo[3] and ']' in suiteInfo[3]:
                                            # 第4个是TAG
                                            suiteTag = suiteInfo[3]
                                        else:
                                            # 第4个是参数化文件
                                            parameterized_data = suiteInfo[3]
                                    elif suiteInfoLen == 5:
                                        # NAME,CONFIG,CASELIST,PARAMETERIZED_DATA,STEPS_DATA 或 NAME,CONFIG,CASELIST,PARAMETERIZED_DATA,[TAG]
                                        suiteCaseList = suiteInfo[2]
                                        parameterized_data = suiteInfo[3]
                                        if '[' in suiteInfo[4] and ']' in suiteInfo[4]:
                                            # 第5个是TAG
                                            suiteTag = suiteInfo[4]
                                        else:
                                            # 第5个是STEPS_DATA
                                            steps_data = suiteInfo[4]
                                    else:
                                        # suiteInfoLen >= 6: NAME,CONFIG,CASELIST,PARAMETERIZED_DATA,STEPS_DATA,[TAG]
                                        suiteCaseList = suiteInfo[2]
                                        parameterized_data = suiteInfo[3]
                                        steps_data = suiteInfo[4]
                                        if suiteInfoLen >= 6 and '[' in suiteInfo[5] and ']' in suiteInfo[5]:
                                            suiteTag = suiteInfo[5]

                                main_tag = self._validate_main_tag(suiteTag, absPos[index], data)
                                if matched:
                                    if self.mongoConfig is not None:
                                        matched = self.mongoConfig.isDateMatch(suiteCaseList)
                                    if matched:
                                        scenario.set_suite(suiteInfo[0], suiteInfo[1], suiteTag, suiteCaseList, parameterized_data, steps_data)
                                        scenario.curSuite.main_tag = main_tag
                                    else:
                                        index += 1
                                        continue
                                else:
                                    index += 1
                                    # print "the current suite's tag doesn't match the label"
                                    continue
                            index += 1
                            if index < len(line):
                                data = line[index]
                                while 'ARG_' in data:
                                    # pdb.set_trace()
                                    suiteParam = data.split(':')
                                    scenario.set_suiteParam(suiteParam[0], suiteParam[1])
                                    index += 1
                                    if index < len(line):
                                        data = line[index]
                                        continue
                                    else:
                                        break
                            else:
                                break
                        elif 'CONFIG:' in data or 'REPEAT:' in data or 'PARALLEL:' in data or 'PURPOSE:' in data or 'STDOUT:' in data or 'VALGRIND:' in data or 'OWNER' in data or 'PROJECT:' in data or (
                                "ASSERT" in data and "ARG_ASSERT" not in data):
                            if 'REPEAT:' in data:
                                scenario.set_repeatNum(int(data.split(':')[1]))
                                index += 1
                            elif 'PARALLEL:' in data:
                                scenario.set_isParallel(data.split(':')[1])
                                index += 1
                            elif 'PURPOSE:' in data:
                                scenario.set_purposeData(data.split(':')[1])
                                index += 1
                            elif 'STDOUT:' in data:
                                scenario.set_stdoutFile(data.split(':')[1])
                                index += 1
                            elif 'VALGRIND:' in data:
                                scenario.set_useValgrind(data.split(':')[1])
                                index += 1
                            elif 'CONFIG:' in data:
                                scenario.set_scenarioConf(data.split(':')[1])
                                index += 1
                            elif 'OWNER' in data:
                                scenario.set_scenarioOwner(data.split(':')[1])
                                index += 1
                            elif 'PROJECT:' in data:
                                # 解析DEFINE块内的PROJECT配置
                                project_value = data.split(':')[1]
                                scenario.set_project(project_value)
                                index += 1
                            elif 'ASSERT' in data:
                                scenario.set_scenarioAssertion(data.split(':')[1])
                                index += 1
                        elif 'END' in data:
                            # pdb.set_trace()
                            scenario.end()
                            self.sceneList.append(scenario)
                            flag = 2
                            break
                        else:
                            print("WARING : File '%s', line '%d', %s" % (self.config, absPos[index], data))
                            index += 1
                    index += 1
            if flag == 0:
                print("ERROR : Nothing in file '%s', " % self.config)
                sys.exit(0)
            elif flag == 1:
                print(
                    f"ERROR : File '{self.config}', line '{index}', {data}\n\tYou must give 'END' at the end the current scene.")
                sys.exit(0)
            elif flag == 2:
                self._validate_scheduler_limits()
                print("parse the solution file: '%s'  complete." % self.config)
        fp.close()
        self.PRINT()
        # return self.sceneList
