#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2023/3/21 18:50
# @Author  : huidong.bai
# @File    : process_result.py
# @Software: PyCharm
# @Mail    : MasterBai2018@outlook.com
import os
import subprocess
import json

from src.userInterface.mongo_assert import AssertionFactory
from src.userInterface.parse_config import Parse


def process_valgrind_info(valgrindInfo, valgrindReport, suite):
    if os.path.isfile(valgrindInfo):
        actual = ""
        conclusion = ""
        failedNum = 0
        bugGrade = "A"
        with open(valgrindInfo, 'r') as fp:
            line = fp.readlines()
            actual = line[len(line) - 1].split("== ")[1].replace('\n', '')
            conclusion = "the detail info in file:%s" % valgrindInfo
        fp.close()
        # for i in range(0, (line))
        for _line in line:
            if 'Invalid read' in _line or 'Invalid write' in _line:
                failedNum = 1
                break

        report = {"suiteName": suite}
        summary = {"caseNum": 1,
                   "totalTime": 0,
                   "failedNum": failedNum,
                   "S": 0, "A": 1, "B": 0, "C": 0, "D": 0,
                   "conclusion": conclusion}
        report["summary"] = summary

        report["caseInfo"] = []
        caseInfo = {"caseName": suite, "bugGrade": bugGrade, "errInfo": []}

        errInfo = {"input": "run valgrind --leak-check=full --track-origins=yes --show-leak-kinds=all",
                   "actual": actual,
                   "expect": "no invalid write info"
                   }
        caseInfo["errInfo"].append(errInfo)
        report["caseInfo"].append(caseInfo)

        with open(valgrindReport, 'w') as file_object:
            json.dump(report, file_object)
        file_object.close()

        return True
    else:
        return False


def merge_result(result, suites_info, suites_summary):
    if os.path.exists(result):
        size = os.path.getsize(result)
        if size <= 0:
            return
    try:
        with open(result, 'r') as fp:
            data = fp.read()
            try:
                suite_info = json.loads(data)
            except Exception as e:
                print(f"error: {e}")
                data = data.encode("utf-8")
                suite_info = json.loads(data)
    except IOError:
        print("The file:%s does not exist." % result)
    else:
        suites_info.append(suite_info)
        suites_summary['suiteNum'] += 1
        if suite_info['summary']['failedNum'] == 0:
            suites_summary['passedNum'] += 1
        suites_summary['totalTime'] += suite_info['summary']['totalTime']
        suites_summary['caseNum'] += suite_info['summary']['caseNum']
        suites_summary['failedNum'] += suite_info['summary']['failedNum']
        suites_summary['S'] += suite_info['summary']['S']
        suites_summary['A'] += suite_info['summary']['A']
        suites_summary['B'] += suite_info['summary']['B']
        suites_summary['C'] += suite_info['summary']['C']
        suites_summary['D'] += suite_info['summary']['D']
    fp.close()


def disk_report():
    p = subprocess.Popen("df -h", shell=True, stdout=subprocess.PIPE)
    # print p.stdout.readlines()
    return p.stdout.readlines()


def writeFile(fp, data, toltalLen, starLength, dataLength):
    i = 1
    _data = ""
    fillData = False
    while i < toltalLen:
        if i <= starLength:
            _data += '*'
            i += 1
        elif i <= (starLength + 4):
            _data += ' '
            i += 1
        elif i <= (starLength + 4 + dataLength + 4):
            if fillData is False:
                _data += data
                i += len(data)
                fillData = True
            else:
                _data += ' '
                i += 1
        else:
            _data += '*'
            i += 1
    fp.write('%s\n' % _data)


def xml_report(workspace, reportName, reportData, times):
    with open(reportName, 'w') as file_object:
        maxlen = 120
        # for i in range(1, maxlen):
        #    file_object.write('*')
        # file_object.write('\n')

        scenarioNum = len(reportData)
        suiteNum = 0
        passedNum = 0
        caseNum = 0
        failedNum = 0
        for scenario in reportData:
            suiteNum += len(scenario['sceneInfo']['suiteInfo'])
            passedNum += scenario['sceneInfo']['suiteSummary']['passedNum']
            caseNum += scenario['sceneInfo']['suiteSummary']['caseNum']
            failedNum += scenario['sceneInfo']['suiteSummary']['failedNum']

        theMaxTime = 0
        for scenario in reportData:
            for suite in scenario['sceneInfo']['suiteInfo']:
                if suite['summary']['totalTime'] > theMaxTime:
                    theMaxTime = suite['summary']['totalTime']

        '''
        data0 = "%s" % times['start_time']
        data1 = "TOTAL SCENARIOS NUM : %d" % scenarioNum
        data2 = "TOTAL SUITES NUM    : %d" % suiteNum
        data3 = "TOTAL PASSED NUM    : %d" % passedNum
        data4 = "TOTAL CASES NUM     : %d" % caseNum
        data5 = "TOTAL FAILED NUM    : %d" % failedNum
        data6 = "TOTAL SPEND TIME    : %ds" % (times['end'] - times['start'])
        data7 = "THE MAXIMUM TIME    : %ds" % theMaxTime

        dataLength = len(data0)
        if len(data1) > dataLength:
            dataLength = len(data1)
        if len(data2) > dataLength:
            dataLength = len(data2)
        if len(data3) > dataLength:
            dataLength = len(data3)
        if len(data4) > dataLength:
            dataLength = len(data4)
        if len(data5) > dataLength:
            dataLength = len(data5)
        if len(data6) > dataLength:
            dataLength = len(data6)
        if len(data7) > dataLength:
            dataLength = len(data7)

        starLength = (maxlen - (dataLength + 8)) / 2

        writeFile(file_object, data0, maxlen, starLength, dataLength)
        writeFile(file_object, data1, maxlen, starLength, dataLength)
        writeFile(file_object, data2, maxlen, starLength, dataLength)
        writeFile(file_object, data3, maxlen, starLength, dataLength)
        writeFile(file_object, data4, maxlen, starLength, dataLength)
        writeFile(file_object, data5, maxlen, starLength, dataLength)
        writeFile(file_object, data6, maxlen, starLength, dataLength)
        writeFile(file_object, data7, maxlen, starLength, dataLength)

        for i in range(1, maxlen):
            file_object.write('*')
        file_object.write('\n')
        '''

        data = "<BOLOO EXECUTION SUMMARY>\n"
        data += "    <EXECUTION TIME      : %s>\n" % times['start_time']
        data += "    <TOTAL SCENARIOS NUM : %d>\n" % scenarioNum
        data += "    <TOTAL SUITES NUM    : %d>\n" % suiteNum
        data += "    <TOTAL PASSED NUM    : %d>\n" % passedNum
        data += "    <TOTAL CASES NUM     : %d>\n" % caseNum
        data += "    <TOTAL FAILED NUM    : %d>\n" % failedNum
        data += "    <TOTAL SPEND TIME    : %ds>\n" % (times['end'] - times['start'])
        data += "    <THE MAXIMUM TIME    : %ds>\n\n\n" % theMaxTime
        file_object.write(data)

        # Get scenario infomation for reportData
        for scenario in reportData:
            doWrite(maxlen, file_object, scenario)
            file_object.write('\n\n')
            subReport = "%s/%s/Mongo_Report_%s.xml" % (workspace, scenario['sceneName'], scenario['sceneName'])
            with open(subReport, 'w') as file_sub_object:
                doWrite(maxlen, file_sub_object, scenario)
            if file_sub_object:
                file_sub_object.close()
    if file_object:
        file_object.close()


def doWrite(maxlen, file_object, scenario):
    suiteSummary = scenario['sceneInfo']['suiteSummary']
    data = "<testscenario : %s>\n" % scenario['sceneName']
    data += "    <Total testsuite num=\"%d\" passed num=\"%d\">\n" % (
    suiteSummary['suiteNum'], suiteSummary['passedNum'])
    data += "    <Total testcase num=\"%d\" failed num=\"%d[S->%d A->%d B->%d C->%d D->%d]\">\n" % (
    suiteSummary['caseNum'], suiteSummary['failedNum'], \
    suiteSummary['S'], suiteSummary['A'], suiteSummary['B'], suiteSummary['C'], suiteSummary['D'])
    data += "    <total Time=\"%d\">\n" % suiteSummary['totalTime']
    file_object.write(data)

    suiteInfo = sorted(scenario['sceneInfo']['suiteInfo'], key=lambda x: x['suiteID'])
    for suite in suiteInfo:
        suite_summary = suite['summary']
        file_object.write(
            '    <testsuite_%d : name="%s" case_num="%d" failed="%d[S->%d A->%d B->%d C->%d D->%d]" passed="%s">\n' \
            % (suite['suiteID'], suite['suiteName'], suite_summary['caseNum'], suite_summary['failedNum'], \
               suite_summary['S'], suite_summary['A'], suite_summary['B'], suite_summary['C'], suite_summary['D'], suite_summary['passed']))
        file_object.write('        <abstract="%s"\n            config="%s"\n            case="%s">\n' % (
        suite['suiteAbstract'], suite['suiteConfig'], suite['suiteCaseList']))
    file_object.write('\n\n<Details of all test cases>\n')
    # Get per suite information from scenario['suiteInfo']
    # pdb.set_trace()
    for suite in suiteInfo:
        file_object.write('<testsuite_%d name="%s" config="%s"\n    case="%s" tag="%s">\n' % (
        suite['suiteID'], suite['suiteName'], suite['suiteConfig'], suite['suiteCaseList'], suite['suiteTag']))
        suite_summary = suite['summary']
        # Get per case information from scenario['suiteInfo']['caseInfo']
        for caseInfo in suite['caseInfo']:
            # To finish traversing case information
            errInfo = caseInfo['errInfo']
            if len(errInfo) > 1:
                file_object.write(
                    '    <testcase name="%s" BugGrade="%s">\n' % (caseInfo['caseName'], caseInfo['bugGrade']))
                for err in errInfo:
                    file_object.write('        <Input="%s"\n        Actual="%s"\n        Expect="%s">\n' % (
                    err['input'], err['actual'], err['expect']))
            else:
                for err in errInfo:
                    file_object.write(
                        '    <testcase name="%s"\n        Input="%s"\n        Actual="%s"\n        Expect="%s" BugGrade="%s">\n' \
                        % (caseInfo['caseName'], err['input'], err['actual'], err['expect'], caseInfo['bugGrade']))
        # Traverse suites information complete
        if 'conclusion' in suite_summary:
            file_object.write(
                '    <case_num="%d" total_time="%ds" failed_num="%d[S->%d A->%d B->%d C->%d D->%d]" passed="%s" conclusion="%s">\n' % \
                (suite_summary['caseNum'], suite_summary['totalTime'], suite_summary['failedNum'], suite_summary['S'],
                 suite_summary['A'], \
                 suite_summary['B'], suite_summary['C'], suite_summary['D'], suite_summary['passed'], suite_summary['conclusion']))
        else:
            file_object.write(
                '    <case_num="%d" total_time="%ds" failed_num="%d[S->%d A->%d B->%d C->%d D->%d]" passed="%s">\n' % (
                suite_summary['caseNum'], \
                suite_summary['totalTime'], suite_summary['failedNum'], suite_summary['S'], suite_summary['A'],
                suite_summary['B'], suite_summary['C'], suite_summary['D'], suite_summary['passed']))
        # file_object.write('\n')


def draw_row(sort, value, unit=''):
    data = '<tr>'
    data += '<td><b><p1 class="leftmargin">%s</p1></b></td>' % sort
    data += '<td><b><p1 class="leftmargin">:</p1></b></td>'
    data += '<td><p1 class="leftmargin">' + str(value) + unit + '</p1></td>'
    data += '</tr>'
    return data


def html_report(reportName, reportData, times):
    with open(reportName, 'w') as file_object:
        theMaxTime = 0
        scenarioNum = len(reportData)
        suiteNum = 0
        passedNum = 0
        caseNum = 0
        failedNum = 0
        for scenario in reportData:
            suiteNum += len(scenario['sceneInfo']['suiteInfo'])
            passedNum += scenario['sceneInfo']['suiteSummary']['passedNum']
            caseNum += scenario['sceneInfo']['suiteSummary']['caseNum']
            failedNum += scenario['sceneInfo']['suiteSummary']['failedNum']
        for scenario in reportData:
            for suite in scenario['sceneInfo']['suiteInfo']:
                if suite['summary']['totalTime'] > theMaxTime:
                    theMaxTime = suite['summary']['totalTime']
        # define html
        data = '<!DOCTYPE html><html lang="en"><meta charset="gbk">'
        data += '<html><head><style type="text/css">'
        data += 'p1.leftmargin {margin-left: 1cm}'
        data += 'p2.leftmargin {margin-left: 2cm}'
        data += '</style>'
        data += '</head>'
        data += '<body>'
        data += '<p>'
        file_object.write(data)
        # draw rows
        data = '<table border="0"'
        data += '<tr>'
        data += '<th><b>BOLOO EXECUTION SUMMARY</b></th>'
        data += '</tr>'
        data += draw_row('EXECUTION TIME', times['start_time'])
        data += draw_row('TOTAL SUITES NUM', suiteNum)
        data += draw_row('TOTAL PASSED NUM', passedNum)
        data += draw_row('TOTAL CASES NUM', caseNum)
        data += draw_row('TOTAL FAILED NUM', failedNum)
        data += draw_row('TOTAL SPEND TIME', int(times['end'] - times['start']), 's')
        data += draw_row('THE MAXIMUM TIME', theMaxTime, 's')
        # end draw table
        data += '</table><br>'
        file_object.write(data)
        # start to draw table
        data = '<table border="1"'
        data += '<tr>'
        data += '<th>ScenarioName</th>'
        data += '<th>Total testsuite num</th>'
        data += '<th>passed num</th>'
        data += '<th>Total testcase num</th>'
        data += '<th>failed num</th>'
        data += '<th>Total time</th>'
        data += '</tr>'
        data += '<tr>'
        for scenario in reportData:
            suiteSummary = scenario['sceneInfo']['suiteSummary']
            # table data
            data += '<td align="center"><b>%s</b></td>' % (scenario['sceneName'])
            data += '<td align="center">%d</td>' % (suiteSummary['suiteNum'])
            data += '<td align="center">%d</td>' % (suiteSummary['passedNum'])
            data += '<td align="center">%d</td>' % (suiteSummary['caseNum'])
            data += '<td align="center">%d</td>' % (suiteSummary['failedNum'])
            data += '<td align="center">%ds</td>' % (suiteSummary['totalTime'])
            data += '</tr>'
        data += '</table>'
        file_object.write(data)
        # get per suite information from scenario in reportData
        for scenario in reportData:
            suiteSummary = scenario['sceneInfo']['suiteSummary']
            data = '<br><br>'
            data += '<b>TestScenario %s</b>' % scenario['sceneName']
            data += '<table border="0"'
            data += draw_row('Total testsuite num', suiteSummary['suiteNum'])
            data += draw_row('passed num', suiteSummary['passedNum'])
            data += draw_row('Total testcase num', suiteSummary['caseNum'])
            data += draw_row('failed num', suiteSummary['failedNum'])
            data += draw_row('Total time', suiteSummary['totalTime'], 's')
            data += '</table><br>'
            file_object.write(data)
            # get per suite information from scenario['suiteInfo']
            suiteInfo = sorted(scenario['sceneInfo']['suiteInfo'], key=lambda x: x['suiteID'])
            for suite in suiteInfo:
                suite_summary = suite['summary']
                data = '<b>testsuite_%d : name="%s"</b>' % (suite['suiteID'], suite['suiteName'])
                data += '<b> case_num="%d"</b>' % suite_summary['caseNum']
                data += '<b> failed="%d[S->%d A->%d B->%d C->%d D->%d]"</b>' % \
                        (suite_summary['failedNum'], suite_summary['S'], \
                         suite_summary['A'], suite_summary['B'], suite_summary['C'], suite_summary['D'])
                data += '<b> passed="%s"</b><br>' % suite_summary['passed']
                data += '<p1 class="leftmargin">abstract="%s"</p1><br>' % (suite['suiteAbstract'])
                data += '<p2 class="leftmargin">config="%s"</p2><br>' % (suite['suiteConfig'])
                data += '<p2 class="leftmargin">case="%s"</p2><br>' % (suite['suiteCaseList'])
                file_object.write(data)
            data = '<br><br><b>Details of all test cases</b><br>'
            file_object.write(data)
            # the details of all test cases, get per suite information from scenario['suiteInfo']
            for suite in suiteInfo:
                data = '<b>testsuite_%d name="%s"</b>' % (suite['suiteID'], suite['suiteName'])
                data += '<b> config="%s"</b><br>' % suite['suiteConfig']
                data += '<p1 class="leftmargin">case="%s"</p1>' % (suite['suiteCaseList'])
                data += ' tag="%s"<br>' % suite['suiteTag']
                file_object.write(data)
                suite_summary = suite['summary']
                for caseInfo in suite['caseInfo']:
                    errInfo = caseInfo['errInfo']
                    # print failed case information
                    if len(errInfo) > 1:
                        data = '<p1 class="leftmargin">testcase name="%s" BugGrade="%s</p1><br>' % (
                        caseInfo['caseName'], caseInfo['bugGrade'])
                        for err in errInfo:
                            data += '<p2 class="leftmargin">Input="%s"</p2><br>' % (err['input'])
                            data += '<p2 class="leftmargin">Actual="%s"</p2><br>' % (err['actual'])
                            data += '<p2 class="leftmargin">Expect="%s"</p2><br>' % (err['expect'])
                    else:
                        for err in errInfo:
                            data = '<p1 class="leftmargin">testcase name="%s"</p1><br>' % (caseInfo['caseName'])
                            data += '<p2 class="leftmargin">Input="%s"</p2><br>' % (err['input'])
                            data += '<p2 class="leftmargin">Actual="%s"</p2><br>' % (err['actual'])
                            data += '<p2 class="leftmargin">Expect="%s"</p2>' % (err['expect'])
                            data += ' BugGrade="%s"<br>' % caseInfo['bugGrade']
                    file_object.write(data)
                # per suite summary
                if 'conclusion' in suite_summary:
                    data = '<p1 class="leftmargin">case_num="%d"</p1>' % (suite_summary['caseNum'])
                    data += ' total_time="%ds"' % suite_summary['totalTime']
                    data += ' failed_num="%d[S->%d A->%d B->%d C->%d D->%d]"' % \
                            (suite_summary['failedNum'], suite_summary['S'], suite_summary['A'], \
                             suite_summary['B'], suite_summary['C'], suite_summary['D'])
                    data += ' passed="%s"' % suite_summary['passed']
                    data += ' conclusion="%s"<br>' % suite_summary['conclusion']
                else:
                    data = '<p1 class="leftmargin">case_num="%d"</p1>' % (suite_summary['caseNum'])
                    data += ' total_time="%ds"' % suite_summary['totalTime']
                    data += ' failed_num="%d[S->%d A->%d B->%d C->%d D->%d]"' % \
                            (suite_summary['failedNum'], suite_summary['S'], suite_summary['A'], \
                             suite_summary['B'], suite_summary['C'], suite_summary['D'])
                    data += ' passed="%s"<br>' % suite_summary['passed']
                file_object.write(data)
        data = '</p></body></html>'
        file_object.write(data)
    file_object.close()


def resultInfo(workspace, reportData):
    with open("%s/result.txt" % workspace, 'w') as fp:
        data = '测试套件名\t'
        data += '配置文件名\t'
        data += 'case列表名\t'
        data += '测试用例数\t'
        data += '失败用例数\t'
        data += '测试套件描述\t\n'
        fp.write(data)
        for scenario in reportData:
            suiteInfo = sorted(scenario['sceneInfo']['suiteInfo'], key=lambda x: x['suiteID'])
            for suite in suiteInfo:
                suite_summary = suite['summary']
                data = '%s\t' % suite['suiteName']
                data += '%s\t' % suite['suiteConfig']
                data += '%s\t' % suite['suiteCaseList']
                data += '%d\t' % suite_summary['caseNum']
                data += '%d\t' % suite_summary['failedNum']
                if suite['suiteAbstract'] == "":
                    data += '无\t\n'
                else:
                    data += '%s\t\n' % suite['suiteAbstract']
                fp.write(data)
    fp.close()


def generate_report(workspace, reportName, _reportData, parse, times):
    bAssert = AssertionFactory(parse, _reportData, workspace)
    reportData = bAssert.doAssert()

    reportName = os.path.join(workspace, reportName)
    xml_report(workspace, os.path.join(reportName, 'report.xml'), reportData, times)
    html_report(os.path.join(reportName, 'report.html'), reportData, times)
    resultInfo(workspace, reportData)
    subprocess.call("iconv -f utf-8 -t gbk %s > %s.html" % (os.path.join(reportName, 'report.html'), os.path.join(reportName, 'report.html')), shell=True)
    subprocess.call("rm %s " % os.path.join(reportName, 'report.html'), shell=True)
    return reportData
