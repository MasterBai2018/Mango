import requests
import json
import configparser
import sys
import os


class SendMessage:
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config.read('conf/mongo.ini', encoding='utf-8')
        self.url = self.config.get('messageWechat','url')
        self.env = self.config.get('auto_run','env')
        self.port = self.config.get('auto_run','port')
        self.message = ''
        self.fileFlag = False

    # 获取mongo报告结果数据
    def getResult(self, solution_path, aibs_version, lcs_version):
        times = ''
        startTime = ''
        caseNum = 0
        failNum = 0
        suiteNum = 0
        suitePassNum = 0
        mongo_report = os.path.join(solution_path, "Mongo_Report.xml")
        allure_report = os.path.join(solution_path, "allure_report")
        with open(mongo_report, mode='r') as f:
            infos = f.readlines()
            for info in infos:
                if 'EXECUTION TIME' in info:
                    startTime = info.split(':',1)[-1].split('.')[0]
                if 'TOTAL SPEND TIME' in info:
                    times = info.split(':')[-1].split('>')[0]
                elif 'TOTAL SUITES NUM' in info:
                    suiteNum = int(info.split(':')[-1].split('>')[0].strip())
                elif 'TOTAL PASSED NUM' in info:
                    suitePassNum = int(info.split(':')[-1].split('>')[0].strip())
                elif 'TOTAL CASES NUM' in info:
                    caseNum = int(info.split(':')[-1].split('>')[0].strip())
                elif 'TOTAL FAILED NUM' in info:
                    failNum = int(info.split(':')[-1].split('>')[0].strip())
        self.message = f"**<font color='info'>{startTime}</font>** **开始执行，执行耗时<font color='info'>{times}</font>**，执行结果如下，请相关同学关注。\n" \
                       f"> AIBS版本信息：<font color='info'>{aibs_version}</font>\n" \
                       f"> LCS版本信息：<font color='info'>{lcs_version}</font>\n" \
                       f"> suite 总数：<font color='info'>{suiteNum}</font>\n"\
                       f"> suite pass：<font color='info'>{suitePassNum}</font>\n"\
                       f"> case 总数：<font color='info'>{caseNum}</font>\n"\
                       f"> case fail：<font color='warning'>{failNum}</font>\n"\
                       f"> 执行命令：\n`python3 {' '.join(sys.argv)}`\n"\
                       f"> allure报告：http://{self.env}:{self.port}/{allure_report}"

        if failNum > 0:
            self.fileFlag = True

    # 机器人发消息
    def send_message(self, data):
        headers = {'Content-Type': 'application/json'}
        try:
            response = requests.post(self.url, headers=headers, data=json.dumps(data))
            if response.status_code == 200:
                return True
            else:
                return False
        except Exception as e:
            print(e)

    # 上传文件
    def upload_file(self, report_path):
        try:
            files = {'file': open(report_path, 'rb')}
            response = requests.post(f"{self.url.replace('send','upload_media')}&type=file", files=files)
            return response.json().get('media_id')
        except Exception as e:
            print(e)

    # 执行总入口
    def run_start(self, solution_path, aibs_version, lcs_version):
        self.getResult(solution_path, aibs_version, lcs_version)
        # 发送文本
        data_text = {
            'msgtype': 'markdown',
            'markdown': {
                "content": self.message
            }
        }
        textFlag = self.send_message(data_text)

        data_user = {
            'msgtype': 'text',
            'text': {
                "content": ''
            }
        }
        
        if 'mentioned' in self.config.options('messageWechat'):
            data_user['text']['mentioned_list'] = self.config.get('messageWechat','mentioned').split(',')
        if 'mentioned_mobile' in self.config.options('messageWechat'):
            data_user['text']['mentioned_mobile_list'] = self.config.get('messageWechat','mentioned_mobile').split(',')
        if 'mentioned_list' in data_user['text'] or 'mentioned_mobile_list' in data_user['text']:
            userFlag = self.send_message(data_user)

        if self.fileFlag:
            # 发送报告文件
            data_file = {
                "msgtype": "file",
                "file": {
                    "media_id": self.upload_file(os.path.join(solution_path, "Mongo_Report.xml"))
                }
            }
            ret = self.send_message(data_file)

            if (self.fileFlag and textFlag and ret) or (not self.fileFlag and textFlag):
                print('wechat message success!')
            else:
                print('wechat message fail!')

    def send_text(self, text):
        data_user = {
            'msgtype': 'text',
            'text': {
                "content": text,
                "mentioned_list": "@all"
            }
        }
        self.send_message(data_user)
