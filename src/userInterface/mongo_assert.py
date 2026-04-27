#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2023/3/21 18:50
# @Author  : huidong.bai
# @File    : mongo_assert.py
# @Software: PyCharm
# @Mail    : MasterBai2018@outlook.com


import pdb
from src.userInterface.parse_config import Parse
from src.userInterface.parse_config import AssertLevel
from collections import Counter


class AssertionFactory:
    def __init__(self, parse, result, workspace):
        self.assertion = None
        self.parse = parse
        self.result = result
        self.workspace = workspace
        self.caseList = None
        return
    
    def sceneAssert(self):
        for scenario in self.result:
            self.assertion = self.getScenarioAssertion(scenario['sceneName'])
            scenario = self.processSceneResult(scenario)

    def doAssert(self):
        self.fileName = "%s/nr.txt" % self.workspace
        self.saveResult("%s    %s    %s    %s    %s    %s    %s    %s" % \
                        ("scenario", "case", "tag", "total-num", "passed-num", "failed-num", "accuracy", "d-accuracy"), 'w')
        for scenario in self.result:
            suiteInfo = sorted(scenario['sceneInfo']['suiteInfo'], key=lambda x: x['suiteID'])
            sceneName = scenario['sceneName']
            for suite in suiteInfo:
                self.assertion = self.getSuiteAssertion(sceneName, suite['suiteID'])
                self.caseList = self.getSuiteCaseList(sceneName, suite['suiteID'])
                suite = self.processSuiteResult(suiteInfo, suite, sceneName)
        self.sceneAssert()
        self.updatePassedNum()
        return self.result

    def getSuiteAssertion(self, sceneName, suiteID):
        if self.parse is None:
            return None
        return self.parse.getSuiteAssertion(sceneName, suiteID)

    def getSuiteCaseList(self, sceneName, suiteID):
        if self.parse is None:
            return None
        return self.parse.getSuiteCaseList(sceneName, suiteID)

    def getScenarioAssertion(self, sceneName):
        if self.parse is None:
            return None
        return self.parse.getScenarioAssertion(sceneName)

    def saveResult(self, result, mode):
        if mode == 'a':
            with open(self.fileName, 'a') as fp:
                fp.write(result)
                fp.write('\n')
            fp.close()
        elif mode == 'w':
            with open(self.fileName, 'w') as fp:
                fp.write(result)
                fp.write('\n')
            fp.close()

    def processSuiteResult(self, suiteInfo, suiteResult, sceneName):
        # pdb.set_trace()
        # ignore online err
        if suiteResult['suiteTag'] is not None and ("ONLINE" in suiteResult['suiteTag'] or "CP" in suiteResult['suiteTag']):
            if suiteResult['summary']['passed'] == "no":
                try:
                    rate = 1 - suiteResult['summary']['failedNum'] / (suiteResult['summary']['caseNum'] * 1.0)
                except:
                    rate = 0
                if rate > 0.9:
                    suiteResult['summary']['passed'] = "yes"
        if self.assertion is None:
            return suiteResult
        if self.assertion.level != AssertLevel.SUITE:
            return suiteResult
        # pdb.set_trace()
        key = self.assertion.info.split('-')[0]
        value = self.assertion.info.split('-')[1]
        if key == "PASSING_RATE" or key == "PR":
            _value = float(value)
            try:
                actual = 1 - suiteResult['summary']['failedNum'] / (suiteResult['summary']['caseNum'] * 1.0)
            except:
                actual = 0
            if _value <= actual:
                suiteResult['summary']['passed'] = "yes"
            else:
                suiteResult['summary']['passed'] = "no"

            conclusion = "expect[%s] actual[%.4f] tag%s suite_id[%s]" % (self.assertion.info, actual, suiteResult['suiteTag'], suiteResult['suiteID'])
            conclusion_len = 0
            try:
                conclusion_len = len(suiteResult['summary']['conclusion'])
            except Exception as e:
                print(f"error: {e}, no conclusion data")
            if conclusion_len > 0:
                suiteResult['summary']['conclusion'] += ", %s" % conclusion
            else:
                suiteResult['summary']['conclusion'] = conclusion
            if 'nr' in suiteResult['suiteConfig']:
                curResult = "%s/%s/%d/result.txt" % (self.workspace, sceneName, suiteResult['suiteID'])
                totalPassedNum, curPassedNum, baseCorrectNum = self.computeCommErr(None, curResult)
                if suiteResult['summary']['caseNum'] != 0:
                    result = "%s\t%s\t%s\t%d\t%d\t%d\t%.4f\t-" % \
                            (sceneName, self.caseList, suiteResult['suiteTag'], suiteResult['summary']['caseNum'], \
                            totalPassedNum, suiteResult['summary']['caseNum'] - totalPassedNum, \
                            totalPassedNum / (suiteResult['summary']['caseNum'] * 1.0))
                else:
                    result = "%s\t%s\t%s\t%d\t%d\t%d\t%.4f\t-" % \
                          (sceneName, self.caseList, suiteResult['suiteTag'], suiteResult['summary']['caseNum'], \
                           totalPassedNum, suiteResult['summary']['caseNum'] - totalPassedNum, 0)
                self.saveResult(result, 'a')
        elif key == "DETERIORATION_RATE" or key == "DR":
            vlist = value.replace('(', '').replace(')', '').split(',')
            actual = 1.0
            if len(vlist) <= 0:
                print('error : DR format error, DR-(0.9,2)')
            elif len(vlist) == 1:
                try:
                    actual = 1 - suiteResult['summary']['failedNum'] / (suiteResult['summary']['caseNum'] * 1.0)
                except Exception as e:
                    print("error: ", e)
                    actual = 0
                if float(vlist[0]) <= actual:
                    suiteResult['summary']['passed'] = "yes"
                else:
                    suiteResult['summary']['passed'] = "no"
            else:
                # pdb.set_trace()
                suiteID = vlist[1]
                actual = 0

                # failedNum = self.getSuiteFailedNum(suiteInfo, string.atoi(suiteID))
                baseResult = "%s/%s/%s/result.txt" % (self.workspace, sceneName, suiteID)
                curResult = "%s/%s/%d/result.txt" % (self.workspace, sceneName, suiteResult['suiteID'])
                totalPassedNum, curPassedNum, baseCorrectNum = self.computeCommErr(baseResult, curResult)
                try:
                    # actual = 1 - (suiteResult['summary']['failedNum'] - failedNum) / ((suiteResult['summary']['caseNum'] - failedNum) * 1.0)
                    actual = curPassedNum / (baseCorrectNum * 1.0)
                except Exception as e:
                    print("data error: ", e)
                if float(vlist[0]) <= actual:
                    suiteResult['summary']['passed'] = "yes"
                else:
                    suiteResult['summary']['passed'] = "no"

            conclusion = "expect[%s] actual[%.4f] tag%s suite_id[%s]" % (self.assertion.info, actual, suiteResult['suiteTag'], suiteResult['suiteID'])
            conclusion_len = 0
            try:
                conclusion_len = len(suiteResult['summary']['conclusion'])
            except Exception as e:
                print("no conclusion data: ", e)
            if conclusion_len > 0:
                suiteResult['summary']['conclusion'] += ", %s" % conclusion
            else:
                suiteResult['summary']['conclusion'] = conclusion
            if 'nr' in suiteResult['suiteConfig']:
                if suiteResult['summary']['failedNum'] == suiteResult['summary']['caseNum']:
                    result = "%s\t%s\t%s\t%d\t%d\t%d\t%.4f\t%s" % \
                              (sceneName, self.caseList, suiteResult['suiteTag'], suiteResult['summary']['caseNum'], \
                               totalPassedNum, suiteResult['summary']['caseNum'] - totalPassedNum, \
                               totalPassedNum / (suiteResult['summary']['caseNum'] * 1.0), "0")
                else:
                    result = "%s\t%s\t%s\t%d\t%d\t%d\t%.4f\t%.4f" % \
                              (sceneName, self.caseList, suiteResult['suiteTag'], suiteResult['summary']['caseNum'], \
                               totalPassedNum, suiteResult['summary']['caseNum'] - totalPassedNum, \
                               totalPassedNum / (suiteResult['summary']['caseNum'] * 1.0), actual)
                self.saveResult(result, 'a')
        else:
            print(key)
        return suiteResult
    
    def check_repeat(self, file, data):
        line_counts = Counter(data)
        repeat_info = []
        for line, count in line_counts.items():
            if count > 1:
                repeat_info.append(f'{line} : 重复{count}次')
        if len(repeat_info) > 0:
            print(f"{file}文件中存在{len(repeat_info)}条重复数据，会影响劣化率结果，请修正！：\n{str(repeat_info)}")

    def computeCommErr(self, baseResult, curResult):
        baseCorrect = []
        curPass = []
        if baseResult is not None:
            try:
                with open(baseResult, "r") as fp_b:
                    _header = fp_b.readline()
                    datas = fp_b.readlines()
                    self.check_repeat(baseResult, datas)
                    for line in datas:
                        if line.isspace() or len(line) == 0:
                            continue
                        results = line.strip().split("\t")
                        if len(results) == 9 and "True" == results[-1]:
                            baseCorrect.append(results[4].split('/')[-1])
            except:
                print("The path : %s is not eixsts!" % baseResult)

        try:
            with open(curResult, "r") as fp_c:
                _header = fp_c.readline()
                datas = fp_c.readlines()
                self.check_repeat(curResult, datas)
                for line in datas:
                    if line.isspace() or len(line) == 0:
                        continue
                    results = line.strip().split("\t")
                    if len(results) == 9 and "True" == results[-1]:
                        curPass.append(results[4].split('/')[-1])
        except Exception as e:
            print(f"error: {e}, The path : %s is not eixsts!" % curResult)

        comPassNum = 0
        for curPassResult in curPass:
            for baseCorrectResult in baseCorrect:
                if curPassResult == baseCorrectResult:
                   comPassNum += 1
        return len(curPass), comPassNum, len(baseCorrect)

    def getSuiteFailedNum(self, suiteInfo, suiteID):
        for suite in suiteInfo:
            if suite['suiteID'] == suiteID:
                return suite['summary']['failedNum']
        return 0

    def processSceneResult(self, sceneResult):
        if self.assertion is None:
            return sceneResult
        if self.assertion.level != AssertLevel.SCENARIO:
            return sceneResult
        key = self.assertion.info.split('-')[0]
        value = self.assertion.info.split('-')[-1]
        print(key, value)
        if len(value) <= 0:
            print("CR format error! The correct format is CR-XX")
        if key == "CR" or key == "CORRECT_RATE":
            try:
                _value = float(value)
                actual = round(1 - sceneResult['sceneInfo']['suiteSummary']['failedNum'] / \
                        (sceneResult['sceneInfo']['suiteSummary']['caseNum'] * 1.0), 3)
            except Exception as e:
                print(f"data is error: {e}! caseNum is 0 or Assert value is none")
            else:
                for suiteResult in sceneResult['sceneInfo']['suiteInfo']:
                    if _value <= actual:
                        suiteResult['summary']['passed'] = "yes"
                    else:
                        suiteResult['summary']['passed'] = "no"
        else:
            print(key)
        return sceneResult

    def updatePassedNum(self):
        for scenario in self.result:
            suiteInfo = sorted(scenario['sceneInfo']['suiteInfo'], key=lambda x: x['suiteID'])
            passedNum = 0
            for suite in suiteInfo:
                if suite['summary']['passed'] == 'yes':
                    passedNum += 1
            scenario['sceneInfo']['suiteSummary']['passedNum'] = passedNum
        return
