#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2023/8/1 21:05
# @Author  : huidong.bai
# @File    : SpeechEngineStatus.py
# @Software: PyCharm
# @Mail    : MasterBai2018@outlook.com

from ctypes import c_int


class SpeechEngineStatusCode(c_int):
    INIT_SUCCESS = 0x01
    INIT_FAILED = 0x02
