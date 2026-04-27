#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2023/3/21 18:50
# @Author  : huidong.bai
# @File    : deploy_environment.py
# @Software: PyCharm
# @Mail    : MasterBai2018@outlook.com

import subprocess
import os
import sys
import pdb


def get_work_mode(cmdArgs):
    has_solution = cmdArgs.mongo_solution is not None
    has_filter = cmdArgs.mongo_filter is not None
    has_filter_config = cmdArgs.mongo_filter_config is not None
    has_case = cmdArgs.mongo_case is not None

    if not has_solution and not has_filter:
        print("You must enter solution or specify one suite when run case, the more details in help.")
        return 'INVALID'

    if has_filter and not has_case:
        print("You must input a case file while used filter work mode.")
        return 'INVALID'

    if has_solution and has_filter:
        if has_filter_config:
            print("Only process the suite specified by '--mongo_filter' when both solution and filter are provided.")
            return 'GDB_FILTER' if cmdArgs.mongo_gdb else 'FILTER'
        return 'OVERALL'

    if not has_solution:
        if has_filter_config:
            return 'GDB_FILTER' if cmdArgs.mongo_gdb else 'FILTER'
        print("You must enter solution for the suite specified by '--mongo_filter'.")
        return 'INVALID'

    return 'OVERALL'


def resource_deploy(branch, root_dir):
    if branch == 'null':
        return
    res_branch = branch.split('-')[0]
    case_branch = branch.split('-')[1]
    if not os.path.exists("TestResource"):
        try:
            subprocess.check_call("git clone git@192.168.129.110:asr/TestResource.git", shell=True)
            print("clone TestResource success")
        except subprocess.CalledProcessError as exc:
            print("clone TestResource failed")
            print('returncode:', exc.returncode)
            print('cmd:', exc.cmd)
            print('output:', exc.output)

    os.chdir("TestResource")
    subprocess.call("git fetch --all", shell=True)

    try:
        subprocess.check_call("git checkout .", shell=True)
        subprocess.check_call("git checkout %s " % res_branch, shell=True)
        print("git checkout %s success " % res_branch)
        subprocess.check_call("git pull", shell=True)
    except subprocess.CalledProcessError as exc:
        print("git checkout %s failed " % res_branch)
        print('returncode:', exc.returncode)
        print('cmd:', exc.cmd)
        print('output:', exc.output)

        subprocess.check_call("python2 generate_resource.py lexus_resource.script", shell=True)

    os.chdir(root_dir)

    if not os.path.exists("TestCase"):
        try:
            subprocess.check_call("git clone git@192.168.129.110:asr/TestCase.git", shell=True)
            print("clone TestCase success")
        except subprocess.CalledProcessError as exc:
            print("clone TestCase failed")
            print('returncode:', exc.returncode)
            print('cmd:', exc.cmd)
            print('output:', exc.output)

    os.chdir("TestCase")
    subprocess.call("git fetch --all", shell=True)

    try:
        subprocess.check_call("git checkout .", shell=True)
        subprocess.check_call("git checkout %s " % case_branch, shell=True)
        print("git checkout %s success " % case_branch)
        subprocess.check_call("git pull", shell=True)
    except subprocess.CalledProcessError as exc:
        print("git checkout %s failed " % case_branch)
        print('returncode:', exc.returncode)
        print('cmd:', exc.cmd)
        print('output:', exc.output)

    os.chdir(root_dir)
