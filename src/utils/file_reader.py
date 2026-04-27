#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2023/3/20 20:34
# @Author  : huidong.bai
# @File    : file_reader.py
# @Software: PyCharm
# @Mail    : MasterBai2018@outlook.com

import yaml


class FileReader:
    def __init__(self, filename):
        self.filename = filename
        self.format = None
        self.common_path = None
        self.common_param = None

    def read_lines(self, tag=None):
        lines = []
        if tag:
            start, end = [int(i) for i in tag.split("-")]
        else:
            start, end = 0, 20000
        with open(self.filename, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            num = len(lines)
            infos = []
            # pdb.set_trace()
            for count, line in enumerate(lines):
                if "@FORMAT:" in line:
                    self.format = len(line.split("@FORMAT:")[1].split())
                elif "@COMMON_PATH:" in line:
                    self.common_path = line.split("@COMMON_PATH:")[1].split('\n')[0]
                elif "@COMMON_PARAM:" in line:
                    self.common_param = line.split("@COMMON_PARAM:")[1].split('\n')[0]
                info = line.split("\n")[0]
                if len(info)==0 or info[0] == "#" or info[:2] == "//" or info[0] == "@":
                    pass
                elif start <= count+1 <= end:
                    if "COMMON_PATH" in info and self.common_path:
                        info = info.replace("COMMON_PATH",self.common_path)
                    isNew = True
                    if count+1<num and lines[count+1] != '\n' and lines[count+1][0] !='#' and lines[count+1][0] !='//' and lines[count+1][0] !='@':
                        if ("isNew:0" in info and "isNew:1" in lines[count+1]) or ("isNew:0" in info and "isNew:0" not in lines[count+1] and "isNew:1" in self.common_param and "default" in lines[count+1]):
                            isNew = False
                        elif ("isNew:1" in info and "isNew:0" in lines[count+1]) or ("default" in info and "isNew:0" in lines[count+1] and "isNew:1" in self.common_param):
                            isNew = False
                    case = {"line": count+1, "data": info, "format":self.format, "common_param":self.common_param, "isNewStop":isNew}
                    infos.append(case)
        return infos

    def read_yaml(self, tag=None):
        if tag:
            start, end = [int(i) for i in tag.split("-")]
        else:
            start, end = 1, 20000
        case_list = []
        with open(self.filename, 'r') as fp:
            lines = fp.readlines()[start-1:end]
            length = len(lines)
            result = []
            for index in range(length - 1, -1, -1):
                data = lines[index]
                if data.isspace() or data[0] == "#" or data[:2] == "//":
                    continue
                result.append({'line': index + start, 'data': data})
                if 'testcase' in data:
                    datas = result[::-1]
                    load_list = []
                    for j in datas:
                        load_list.append(j['data'])
                    yaml_data = yaml.safe_load(''.join(load_list))
                    for item in yaml_data:
                        testcase = item['testcase']
                        expects = item['expects']
                        testcase['line'] = f"{datas[0]['line']}-{datas[-1]['line']}"
                        testcase['expects'] = expects
                        case_list.append(testcase)
                    result.clear()
        return case_list[::-1]

    def get_config(self, key):
        if not self.filename:
            print(f'Error: Filename:[{self.filename}] is not exists!')
            return ""
        with open(self.filename, 'r', encoding='utf-8') as f:
            line = f.readline()
            while line:
                info = line.strip()
                if line.isspace() or info[0] == "#" or info[:2] == "//":
                    pass
                else:
                    # 处理逻辑
                    if key in info:
                        try:
                            value = info.split('#')[0].split('=')[1].strip().replace('"', '').replace("'", '').replace(
                                ";", '')
                            return value
                        except Exception as e:
                            print(f'解析配置文件失败: [info], 异常：{e}')
                            return ""
                line = f.readline()
        return ""
