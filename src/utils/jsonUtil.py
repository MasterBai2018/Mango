#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2023/8/2 14:11
# @Author  : huidong.bai
# @File    : jsonUtil.py
# @Software: PyCharm
# @Mail    : MasterBai2018@outlook.com
import json
from queue import Queue


class JsonUtil:
    @classmethod
    def __parse_json(cls, dict_data: dict, key_list: Queue):
        if key_list.empty():
            return dict_data
        key = key_list.get()
        if key == "0":
            tmp = dict_data[0]
        else:
            tmp = dict_data.get(key)
        return cls.__parse_json(tmp, key_list)

    @classmethod
    def parse(cls, data: dict, path: str) -> object:
        if not data:
            return "None"
        
        if path == "None":
            return data
        
        try:
            key_list = Queue()
            for key in path.split('.'):
                key_list.put(key)
            result = cls.__parse_json(data, key_list)
            if isinstance(result, bool):
                return str(result).lower()
            return result
        except Exception as e:
            return "None"
