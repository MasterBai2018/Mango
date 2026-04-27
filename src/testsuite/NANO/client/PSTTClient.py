#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2025/01/XX
# @Author  : baihuidong
# @File    : PSTTClient.py
# @Software: PyCharm
# @Mail    : baihuidong@pachiratech.com
import os
import re
import json
import subprocess
import threading
from loguru import logger
from copy import deepcopy
from src.utils.common import load_yaml_config, uuid, join_with_spaces_if_english
from src.testsuite.NANO.dsl_engine import DSLCommand, Status


array_emotion_mapping = {"Sad": "sad", "Hpy": "happy", "Neu": "neutral", "Ag": "angry"}
array_sex_mapping = {"M": "male", "F": "female"}
array_age_mapping = {"儿童": "child", "少年": "youth", "青年": "teenage", "中年": "middleage"}


class PSTTClientServer():
    """PSTTClientServer ASR服务类 - 封装配置加载和音频处理功能，供NANORunner调用"""

    def __init__(self, client_name, lib_path: str, pyconfig):
        """
        初始化PSTTClientServer服务
        :param client_name: 客户端名称
        :param lib_path: 动态库所在目录
        :param config: pytest config对象，用于获取base_dir等配置信息
        """
        pstt_client_path = os.path.join(lib_path, "pstt_client")
        if not os.path.exists(pstt_client_path):
            raise FileNotFoundError(f"pstt_client不存在: {pstt_client_path}")

        pstt_client_qa_path = os.path.join(lib_path, "pstt_client_qa")
        if not os.path.exists(pstt_client_qa_path):
            raise FileNotFoundError(f"pstt_client_qa不存在: {pstt_client_qa_path}")

        pstt_ctrl = os.path.join(lib_path, "pstt_ctrl")
        if not os.path.exists(pstt_ctrl):
            raise FileNotFoundError(f"pstt_ctrl不存在: {pstt_ctrl}")

        self.pstt_client_path = pstt_client_path
        self.pstt_ctrl = pstt_ctrl
        self.pstt_client_qa_path = pstt_client_qa_path
        self.pyconfig = pyconfig     # 保存pytestconfig对象

        # 创建HMI的文件夹，使用config.base_dir
        hmi_path = os.path.join(self.pyconfig.base_dir, "hmi")
        os.makedirs(hmi_path, exist_ok=True)
        self.hmi_path = hmi_path

        self.client_name = client_name
        self.config_path = None
        self.config_dict = None
        self.m_callback = None
        self.hmi_text_dir = None
        self.current_lang = None
        # 配置参数映射表和跳过配置项（在create方法中初始化）
        self.cmd_args = []
        self.config_param_map = None
        self.skip_configs = None

    def set_callback(self, callback_func):
        """设置外部回调函数"""
        self.m_callback = callback_func

    def create(self, command: DSLCommand, default_config: str):
        # 加载通用配置文件
        try:
            # 参数解析
            self.config_path = command.params[0] if len(command.params) > 0 else default_config
            
            # 检查配置文件是否存在
            if not os.path.exists(self.config_path):
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] 配置文件不存在: {self.config_path}'
                logger.error(command.message)
                return -1
            
            # 加载配置文件
            try:
                self.config_dict = self._load_config_file(self.config_path)
                if self.config_dict is None:
                    command.status = Status.ERROR
                    command.message = f'[{self.client_name}] 配置文件为空: {self.config_dict}'
                    logger.error(command.message)
                    return -1

                # 初始化配置参数映射表和跳过配置项
                self._init_config_mapping()
                # 构建pstt_client命令参数
                self.cmd_args = ["stdbuf", "-oL", self.pstt_client_path]
                
                # 根据config_dict构建命令参数（使用create方法中初始化的映射表）
                for config_key, config_value in self.config_dict.items():
                    # 跳过空值和特殊配置项
                    if not config_value or config_value.strip() == '':
                        continue
                    if config_key in self.skip_configs:
                        continue

                    # 查找对应的命令行参数
                    param_flag = self.config_param_map.get(config_key)
                    if param_flag:
                        self.cmd_args.extend([param_flag, str(config_value)])
                    else:
                        # 如果配置key不在映射表中，记录调试信息但不影响执行
                        logger.debug(f"[{self.client_name}] 未映射的配置项: {config_key}={config_value}")
                    
                # 通过pstt_ctrl获取token
                token = self._get_token()
                if token:
                    self.cmd_args.extend(['-tk', token])
                else:
                    command.status = Status.ERROR
                    command.message = f'[{self.client_name}] 获取token失败'
                    logger.error(command.message)
                    return -1

                logger.info(f"[{self.client_name}] CREATE成功: config={self.config_path}")
                command.return_code = 0
                command.status = Status.PASSED
                return 0
            except Exception as e:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] 加载配置文件失败: {e}'
                logger.error(command.message)
                return -1
                
        except Exception as e:
            logger.error(f"[{self.client_name}] CREATE异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] CREATE异常: {e}'
            return -1
    
    def _get_token(self) -> str:
        """
        通过pstt_ctrl获取token
        :return: token
        """
        try:
            token = None
            ip = self.config_dict.get("SERVER_IP")
            cport = self.config_dict.get("SERVER_CPORT")
            for i in range(5):
                process = subprocess.Popen([self.pstt_ctrl, ip, cport, "token"], stdout=subprocess.PIPE)
                out, err = process.communicate()
                __token = out.decode().split("get the token:")[-1].strip()
                if __token and __token.isdigit():
                    token = __token
                    print(f"获取到{ip}:{cport} token:", token)
                    break
            return token
        except Exception as e:
            logger.error(f"[{self.client_name}] 获取token失败: {e}")
            return None

    def _init_config_mapping(self):
        """
        初始化配置参数映射表和跳过配置项
        在create方法加载配置后调用
        """
        # 配置参数映射表：配置文件key（大写）-> 命令行参数
        self.config_param_map = {
            # 服务器配置
            'SERVER_IP': '-i',
            'SERVER_PORT': '-p',
            # 音频配置
            'AUDIO_TYPE': '-t',
            'AUDIO_RATE': '-r',
            'AUDIO_BIT': '-b',
            # 结果配置
            'REC_RES_TYPE': '-m',
            'ROLE': '-s',  # 服务类型 [asr|spk|emo|spkem]
            'VERSIONS': '-v',
            # 功能开关（布尔值需要转换）
            'IS_ASK_BUTTERFLY': '-bf',
            'IS_ASK_ADD_PUNCT': '-ap',
            'IS_ASK_TRANS_DIGIT': '-td',
            'IS_SEND_FILE_NAME': '-sf',  # 发送文件名
            # 参数配置
            'ASK_SIL_DURATION': '-sl',  # 静音断句时长
            'EVERY_SEND_BYTES': '-sb',  # 每包音频流大小
            'EVERY_SEND_DELAY': '-sd',  # 每包delay时长
            # 检测服务开关
            'GENDER_OPTION': '-g',
            'EMOTION_OPTION': '-e',
            'AGE_OPTION': '-a',
            'OVERLAP_OPTION': '-ol',
            # 其他参数
            'LATENCY_LEVEL': '-ll',
            'MIN_WORD_COUNT': '-mc',
            'SILENCE_TIMEOUT': '-st',
            # 注意：SILENCE_STEP不在命令行参数中，跳过处理
            'HMI_PART_OPTION': '-pt',  # HMI部分匹配选项
            'FILTER_PERSONALITY_TAG': '-ft',
            'GAE_ASYNC': '-gae_async',
            # 语言模型名称
            'RESOURCE_NAME': '-n',
            # 车机主语种
            'PRIMARY_LANG': '-primaryLang',
        }
        
        # 需要跳过的配置项（不在命令行参数中，或需要特殊处理）
        self.skip_configs = {
            'SERVER_CPORT',  # 控制端口，不在pstt_client参数中
            'REC_RES_FILE',  # 结果文件，单跑工具不适用
            'AUDIO_LIST_FILE',  # 音频列表，单跑工具不适用
            'REC_LOOP_NUM',  # 循环次数，单跑工具不适用
            'THREAD_NUM',  # 并发数，单跑工具不适用
            'HMI',  # HMI文件路径，使用hmi_text_dir代替
            'NEUTRAL_THRESHOLD',  # 情绪阈值，不在命令行参数中
            'SILENCE_STEP',  # 静音步长，不在命令行参数中
            'DELAY',  # delay参数单独处理
            'NLU_PARAM_FILE', # NLU参数文件，不在命令行参数中
            'TOKEN', # token，不在命令行参数中
        }
    
    def hmi(self, command: DSLCommand) -> int:
        """
        hmi指令
        :param command: DSLCommand对象
        :return: 0表示成功，-1表示失败
        """
        # 参数解析
        try:
            hmi_file = command.params[0] if len(command.params) > 0 else None
            if hmi_file is None:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] hmi文件不存在: {hmi_file}'
                logger.error(command.message)
                return -1
            
            # 读取HMI文件加载到内存中，然后更新字典，再重定向
            with open(hmi_file, 'r', encoding='utf-8') as fp:
                json_dir = json.load(fp)["data"]
                pstt_hmi_data_json = json.dumps(json_dir, ensure_ascii=False, separators=(',', ':'))
            
            hmi_tag = uuid()
            hmi_json_dir = os.path.join(self.hmi_path, f"hmi_{hmi_tag}.json")
            with open(hmi_json_dir, "w", encoding="utf-8") as fp:
                fp.write(pstt_hmi_data_json)
            
            self.hmi_text_dir = os.path.join(self.hmi_path, f"hmi_{hmi_tag}.txt")
            with open(self.hmi_text_dir, "w", encoding="utf-8") as fp:
                fp.write(f"100\t{hmi_json_dir}\n")
            
            command.status = Status.PASSED
            return 0
        except Exception as e:
            logger.error(f"[{self.client_name}] 加载HMI文件异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] 加载HMI文件异常: {e}'
            return -1

    def process_single_audio(self, command: DSLCommand) -> int:
        """
        处理单个音频文件（同步方法）
        根据self.config_dict配置构建pstt_client命令并执行
        
        :param command: DSLCommand对象，params[0]为音频文件路径
        :return: 执行状态码
        """
        # 检查是否已创建客户端（已加载配置）
        if self.config_dict is None:
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] 客户端未创建，请先执行 CREATE 指令'
            logger.error(command.message)
            return -1
        
        # 解析音频文件路径
        audio_path = command.params[0] if len(command.params) > 0 else None
        if not audio_path or len(audio_path) == 0 or not os.path.exists(audio_path):
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] 音频文件不存在: {audio_path}'
            logger.error(command.message)
            return -1

        # 添加音频文件路径（必须参数）
        cmder = deepcopy(self.cmd_args)
        cmder.extend(['-f', audio_path])

        # 如果设置了HMI，添加hmi参数
        if self.hmi_text_dir and os.path.exists(self.hmi_text_dir):
            cmder.extend(['-hmi', self.hmi_text_dir])

        # 执行pstt_client命令
        try:
            logger.success(f"[{self.client_name}] 执行命令: {' '.join(cmder)}")
            
            process = subprocess.Popen(cmder, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            for line in process.stdout:
                datas = line.decode(encoding="utf-8", errors="ignore").strip()
                if not datas:
                    continue
                logger.info(f"pstt_client result: {datas}")
                result = self._callback_result(datas)
                if result is not None and self.m_callback:
                    self.m_callback("PST", 0, result)
            process.wait()

            command.status = Status.PASSED
            return 0
        except Exception as e:
            logger.error(f"[{self.client_name}] 执行pstt_client异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] 执行pstt_client异常: {e}'
            return -1
    
    def _callback_result(self, line):
        if "Wave Time:" in line:
            audio_time = float(line.split("Wave Time:")[1])/1000
        else:
            audio_time = 0.0

        if ", lang:" in line:
            self.current_lang = line.split(", lang:")[1]

        # 使用正则表达式匹配 pstt_client 输出格式（处理制表符和空格混用的情况）
        # 格式: (TYPE) 音频路径.wav ASR文本 数字 Delay:... Wave Time:...
        line_match = re.match(
            r'\s*\((REAL SHOW|NORMOAL|FINAL)\)\s+'  # 类型
            r'(\S+\.wav)\s+'                   # 音频路径
            r'(.+?)\s+'                        # ASR文本（非贪婪）
            r'(\d+)\s+'                        # 数字
            r'(?:rj:\d+\s+)?'                  # 新版本(pstt_client_v2)可选的rj字段，老版本无此字段
            r'Delay:',                         # Delay标记
            line
        )
        
        if line_match:
            result_type = line_match.group(1)  # REAL SHOW 或 NORMOAL 或 FINAL
            audio_path = line_match.group(2)
            text = line_match.group(3).strip()
            
            # 提取start和end时间戳（单位：帧，需要除以100转换为秒）
            start_mts = 0.0
            end_mts = 0.0
            # 匹配所有的时间戳模式：[start-end/confidence]
            time_matches = re.findall(r'\[(\d+)-(\d+)/\d+\]', text)
            if time_matches:
                # 第一个词的start时间
                start_frames = int(time_matches[0][0])
                # 最后一个词的end时间
                end_frames = int(time_matches[-1][1])
                # 转换为毫秒
                start_mts = int(start_frames * 10)
                end_mts = int(end_frames * 10)
            
            # 根据传入的语言替换所有 [] 中的内容
            temp_text = re.sub(r'\[.*?\]', "|", text)
            processed_text = join_with_spaces_if_english(temp_text)
            asr_result = processed_text.replace(" 's", "'s").strip()
            
            emotion = None
            gender = None
            age = None

            # 查找并解析文本前面的 []（情绪/年龄/性别信息）
            match = re.match(r'^\[(.*?)\]', text)
            if match:
                try:
                    emotion, _, age, _, sex = match.group(1).split("/")
                    emotion = array_emotion_mapping.get(emotion)
                    gender = array_sex_mapping.get(sex)
                    age = array_age_mapping.get(age)
                except Exception as e:
                    pass
            
            # 判断是否为最终识别结果
            # NORMOAL: 最终结果
            # FINAL: 如果 asr 不为空，也是最终结果
            # REAL SHOW: 临时结果
            decided = False
            if result_type == "NORMOAL":
                decided = True
            elif result_type == "FINAL" and asr_result:
                decided = True
        
            result = {
                "source": "PSTTClient",
                "type": "PSTTASRResult" if decided else "PSTTASRResultTemp",
                "audio": audio_path,
                "audiotime": round(audio_time, 2),
                "asr": asr_result,
                "channelId": 0,
                "start": start_mts,
                "end": end_mts,
                "lang": self.current_lang,
                "confidence": 1,
                "emotion": emotion,
                "gender": gender,
                "age": age
            }

            # 重置语种信息
            if decided:
                self.current_lang = None

            return result

    
    def process_audio_list(self, command: DSLCommand):
        """
        使用 pstt_client_qa 处理音频列表文件（批量并发）

        支持传参方式：[PST]CASELIST case=<audio_list_file> model=<model_name> bref=<testset_name> thread=<n>

        说明：
        - pstt_client_qa 的并发由配置项 THREAD_NUM; 若传入 thread，会动态写回当前 conf 的 THREAD_NUM；
        - 结果文件路径固定写入 suite_dir/result_file 目录：
          RESULT_FILE=full_result.txt, REC_RES_FILE=testset_result.txt；
        - 每次执行前会刷新一次 TOKEN，避免 token 过期导致批量失败。
        """

        # 检查是否已创建客户端（已加载配置）
        if self.config_dict is None or not self.config_path:
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] 客户端未创建，请先执行 CREATE 指令'
            logger.error(command.message)
            return -1

        # 解析参数
        audio_list_file = None
        thread_num = None
        bref = None
        for param in command.params:
            if '=' not in param:
                command.status = Status.ERROR
                command.message = (
                    f'[{self.client_name}] CASELIST参数格式错误: {param}。'
                    f'请使用 case=<audio_list_file> bref=<testset_name> [thread=<n>]'
                )
                logger.error(command.message)
                return -1

            key, value = param.split('=', 1)
            key = key.strip().lower()
            value = value.strip()
            if not value:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] CASELIST参数值不能为空: {param}'
                logger.error(command.message)
                return -1

            if key == "thread":
                try:
                    thread_num = int(value)
                except ValueError:
                    command.status = Status.ERROR
                    command.message = f'[{self.client_name}] 线程参数格式错误: {param}'
                    logger.error(command.message)
                    return -1
            elif key == "case":
                audio_list_file = value
            elif key == "model":
                model = value
            elif key == "bref":
                bref = value
            else:
                command.status = Status.ERROR
                command.message = (
                    f'[{self.client_name}] CASELIST不支持的参数: {key}。'
                    f'仅支持 case / bref / thread'
                )
                logger.error(command.message)
                return -1

        # 严格校验必填参数
        if not audio_list_file:
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] CASELIST缺少必填参数: case=<audio_list_file>'
            logger.error(command.message)
            return -1
        if not bref:
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] CASELIST缺少必填参数: bref=<testset_name>'
            logger.error(command.message)
            return -1

        # 参数回写配置文件（按需）
        if not os.path.exists(audio_list_file):
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] 音频列表文件不存在: {audio_list_file}'
            logger.error(command.message)
            return -1
        self._update_config_value("AUDIO_LIST_FILE", audio_list_file)

        if thread_num is not None:
            if thread_num <= 0:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] THREAD_NUM 必须大于0: {thread_num}'
                logger.error(command.message)
                return -1
            self._update_config_value("THREAD_NUM", str(thread_num))

        # 如果传入了model，更新配置文件
        if model is not None:
            self._update_config_value("RESOURCE_NAME", model)

        # 结果文件固定输出到 suite_dir/result_file，避免外部传入路径导致口径不一致
        result_dir = self._get_qa_result_dir()
        bref_tag = self._sanitize_filename_component(bref)
        result_file, rec_res_file = self._build_unique_result_paths(result_dir, bref_tag)
        self._update_config_value("RESULT_FILE", result_file)
        self._update_config_value("REC_RES_FILE", rec_res_file)

        # 批量跑前刷新 token，避免复用过期 token
        token = self._get_token()
        if not token:
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] 获取token失败，无法执行CASELIST'
            logger.error(command.message)
            return -1
        self._update_config_value("TOKEN", str(token))
        self._update_config_value("SHOWINFO", "false") # 关闭详细输出

        # 执行 pstt_client_qa
        qa_cmd = [self.pstt_client_qa_path, "-f", self.config_path]
        try:
            logger.success(f"[{self.client_name}] 执行批量命令: {' '.join(qa_cmd)}")
            process = subprocess.Popen(qa_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0)
            pending = ""
            while True:
                chunk = process.stdout.read(4096)
                if not chunk:
                    break
                pending += chunk.decode(encoding="utf-8", errors="ignore")
                parts = re.split(r'[\r\n]+', pending)
                pending = parts.pop() if parts else ""
                for text in parts:
                    text = text.strip()
                    if text.startswith("Progress ["):
                        print(f"\r{text}", end="", flush=True)

            # flush 末尾残留内容
            if pending:
                text = pending.strip()
                if text:
                    print("")
                    logger.info(f"pstt_client_qa: {text}")

            process.wait()
            print("")

            if process.returncode != 0:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] pstt_client_qa执行失败，返回码: {process.returncode}'
                logger.error(command.message)
                return -1

            command.status = Status.PASSED
            command.message = (
                f'[{self.client_name}] CASELIST执行完成, '
                f'RESULT_FILE={result_file}, REC_RES_FILE={rec_res_file}'
            )
            command.return_code = 0
            return 0
        except Exception as e:
            logger.error(f"[{self.client_name}] 执行pstt_client_qa异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] 执行pstt_client_qa异常: {e}'
            return -1

    def _get_qa_result_dir(self) -> str:
        """
        获取 QA 结果目录：suite_dir/result_file（不存在则自动创建）
        """
        base_dir = getattr(self.pyconfig, "suite_dir", None) or self.pyconfig.base_dir
        result_dir = os.path.join(base_dir, "result_file")
        os.makedirs(result_dir, exist_ok=True)
        return result_dir

    @staticmethod
    def _sanitize_filename_component(value: str) -> str:
        """
        将 bref 转换为安全文件名片段。
        """
        text = str(value or "").strip()
        text = re.sub(r'[\\/:*?"<>|]+', '_', text)
        text = re.sub(r'\s+', '_', text)
        text = re.sub(r'_+', '_', text).strip('_')
        return text or "unknown"

    def _build_unique_result_paths(self, result_dir: str, bref_tag: str):
        """
        为 result/testset 结果文件生成唯一文件名，避免同 bref 覆盖历史产物。
        命名规则：
        - 首选: {bref}_full.txt / {bref}_testset.txt
        - 冲突: {bref}__2_full.txt / {bref}__2_testset.txt (依次递增)
        """
        base_result_file = os.path.join(result_dir, f"{bref_tag}_full.txt")
        base_rec_res_file = os.path.join(result_dir, f"{bref_tag}_testset.txt")
        if not os.path.exists(base_result_file) and not os.path.exists(base_rec_res_file):
            return base_result_file, base_rec_res_file

        idx = 2
        while True:
            result_file = os.path.join(result_dir, f"{bref_tag}__{idx}_full.txt")
            rec_res_file = os.path.join(result_dir, f"{bref_tag}__{idx}_testset.txt")
            if not os.path.exists(result_file) and not os.path.exists(rec_res_file):
                logger.warning(
                    f"[{self.client_name}] bref={bref_tag} 对应结果文件已存在，"
                    f"自动避重为: {os.path.basename(result_file)}"
                )
                return result_file, rec_res_file
            idx += 1

    def _update_config_value(self, key: str, value: str):
        """
        更新 conf 文件中的单个配置项，并同步到内存配置字典。
        """
        if not self.config_path or not os.path.exists(self.config_path):
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")

        formatted = self._format_conf_value(value)
        key_pattern = re.compile(rf'^(\s*{re.escape(key)}\s*=\s*)(.*?)(\s*;\s*)$')

        with open(self.config_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        replaced = False
        new_lines = []
        for line in lines:
            m = key_pattern.match(line)
            if m:
                newline = f"{m.group(1)}{formatted};\n"
                new_lines.append(newline)
                replaced = True
            else:
                new_lines.append(line)

        if not replaced:
            new_lines.append(f'{key:<25} =   {formatted};\n')

        with open(self.config_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)

        # 保持内存配置与文件一致
        if self.config_dict is None:
            self.config_dict = {}
        self.config_dict[key] = str(value)
        logger.info(f"[{self.client_name}] 配置更新: {key}={value}")

    @staticmethod
    def _format_conf_value(value: str) -> str:
        """
        将 Python 字符串格式化为 conf 值：
        - 数字/true/false 保持原样
        - 其他内容自动加双引号
        """
        if value is None:
            return '""'

        text = str(value).strip()
        if re.fullmatch(r'-?\d+(\.\d+)?', text):
            return text
        if text.lower() in ('true', 'false'):
            return text.lower()
        return f'"{text}"'

    def _parse_result(self, stdout: str, stderr: str) -> str:
        """
        解析pstt_client的输出结果
        
        Args:
            stdout: 标准输出
            stderr: 标准错误输出
            
        Returns:
            识别结果文本，如果解析失败返回None
        """
        try:
            # 如果有错误输出，记录日志
            if stderr and stderr.strip():
                logger.warning(f"[{self.client_name}] pstt_client stderr: {stderr}")
            
            # 如果没有标准输出，返回None
            if not stdout or not stdout.strip():
                logger.warning(f"[{self.client_name}] pstt_client stdout为空")
                return None
            
            # 尝试解析JSON格式的结果
            # pstt_client默认输出格式为json（根据-m参数，默认是json）
            try:
                result_json = json.loads(stdout.strip())
                
                # 根据pstt_client的输出格式提取识别文本
                # 常见的JSON格式可能包含以下字段：
                # - text: 识别文本
                # - result: 识别结果
                # - asr: ASR结果
                # - recognizeText: 识别文本
                # - data.text: 嵌套结构中的文本
                
                # 尝试多种可能的字段名
                text = None
                if isinstance(result_json, dict):
                    # 直接字段
                    text = result_json.get('text') or result_json.get('result') or result_json.get('asr') or result_json.get('recognizeText')
                    
                    # 嵌套结构 data.text
                    if not text and 'data' in result_json:
                        data = result_json['data']
                        if isinstance(data, dict):
                            text = data.get('text') or data.get('result') or data.get('asr')
                    
                    # 如果还是没有找到，尝试获取第一个字符串值
                    if not text:
                        for value in result_json.values():
                            if isinstance(value, str) and value.strip():
                                text = value
                                break
                
                if text:
                    logger.debug(f"[{self.client_name}] 识别结果: {text}")
                    return text
                else:
                    # 如果无法提取文本，返回整个JSON的字符串表示
                    logger.warning(f"[{self.client_name}] 无法从JSON中提取文本，返回原始JSON: {result_json}")
                    return json.dumps(result_json, ensure_ascii=False)
                    
            except json.JSONDecodeError:
                # 如果不是JSON格式，直接返回原始输出（可能是纯文本或其他格式）
                logger.debug(f"[{self.client_name}] 输出不是JSON格式，返回原始文本")
                return stdout.strip()
                
        except Exception as e:
            logger.error(f"[{self.client_name}] 解析结果异常: {e}, stdout: {stdout}, stderr: {stderr}")
            return None

    def _load_config_file(self, config_path: str) -> dict:
        """
        加载PSTT配置文件（.conf格式）
        配置文件格式: KEY = VALUE;
        所有key和value都作为字符串存储，不做类型转换
        
        Args:
            config_path: 配置文件路径
            
        Returns:
            dict: 配置参数字典，如果失败返回None
        """
        if not os.path.exists(config_path):
            logger.error(f"[{self.client_name}] 配置文件不存在: {config_path}")
            return None
        
        try:
            config = {}
            
            with open(config_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    # 去除首尾空白字符
                    line = line.strip()
                    
                    # 跳过空行和注释行
                    if not line or line.startswith('#'):
                        continue
                    
                    # 解析配置项格式: KEY = VALUE;
                    if '=' not in line:
                        continue
                    
                    # 分割键值对
                    parts = line.split('=', 1)
                    if len(parts) != 2:
                        logger.warning(f"[{self.client_name}] 配置文件第{line_num}行格式错误，跳过: {line}")
                        continue
                    
                    key = parts[0].strip()
                    value_str = parts[1].strip()
                    
                    # 移除末尾的分号
                    if value_str.endswith(';'):
                        value_str = value_str[:-1].strip()
                    
                    # 处理字符串值（双引号或单引号包围），去掉引号
                    if value_str.startswith('"') and value_str.endswith('"'):
                        value = value_str[1:-1]
                    elif value_str.startswith("'") and value_str.endswith("'"):
                        value = value_str[1:-1]
                    else:
                        value = value_str  # 保持原样
                    
                    config[key] = value
            
            logger.info(f"[{self.client_name}] 成功加载配置文件: {config_path}, 共加载{len(config)}个配置项")
            return config
            
        except Exception as e:
            logger.error(f"[{self.client_name}] 加载配置文件失败: {config_path}, 错误: {e}")
            return None
