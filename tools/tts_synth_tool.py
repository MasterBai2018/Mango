#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
独立的TTS合成工具脚本
功能：将文本列表转换为语音文件，支持添加前后静音
"""

import os
import uuid
import json
import base64
import argparse
import requests
import soundfile as sf
import numpy as np

# ==================== TTS API配置（固定配置） ====================
# TTS API基础配置
TTS_APPID = "2095892072"  # TTS应用ID
TTS_ACCESS_TOKEN = "iqX6FHR64esVUpVPF707Rx9KIViTQBr8"  # 访问令牌
TTS_CLUSTER = "volcano_tts"  # 集群名称
TTS_API_URL = "https://openspeech.bytedance.com/api/v1/tts"  # TTS API地址
TTS_UID = "388808087185088"  # 用户ID

# Voice type配置
VOICE_TYPE_CMN_FEMALE = "zh_female_shuangkuaisisi_emo_v2_mars_bigtts"  # 中文女声类型
VOICE_TYPE_CMN_MALE = "zh_male_yangguangqingnian_emo_v2_mars_bigtts"  # 中文男声类型
VOICE_TYPE_ENG = "en_male_adam_mars_bigtts"  # 英文声音类型
VOICE_TYPE_CHUAN = "zh_female_daimengchuanmei_moon_bigtts"  # 川话声音类型

# 默认合成参数
DEFAULT_GENDER = "female"  # 默认性别：female/male（仅对中文有效）
DEFAULT_EMOTION = "neutral"  # 默认情感：happy/sad/surprise/angry/fear/hate/excited/coldness/neutral
# ================================================================


class SimpleTTSSynthesizer:
    """简单的TTS合成器，不支持并发"""
    
    def __init__(self, appid, access_token, cluster, api_url, uid, 
                 voice_type_cmn_female="", voice_type_cmn_male="", 
                 voice_type_eng="", voice_type_chuan=""):
        """
        初始化TTS合成器
        
        Args:
            appid: TTS应用ID
            access_token: 访问令牌
            cluster: 集群名称
            api_url: TTS API地址
            uid: 用户ID
            voice_type_cmn_female: 中文女声类型
            voice_type_cmn_male: 中文男声类型
            voice_type_eng: 英文声音类型
            voice_type_chuan: 川话声音类型
        """
        self.appid = appid
        self.access_token = access_token
        self.cluster = cluster
        self.api_url = api_url
        self.uid = uid
        self.voice_type_cmn_female = voice_type_cmn_female
        self.voice_type_cmn_male = voice_type_cmn_male
        self.voice_type_eng = voice_type_eng
        self.voice_type_chuan = voice_type_chuan
        self.header = {"Authorization": f"Bearer;{self.access_token}"}
    
    def _get_voice_type(self, lang, gender="female"):
        """
        根据语言和性别获取voice_type
        
        Args:
            lang: 语言类型 (cmn/eng/chuan)
            gender: 性别 (female/male)，仅对中文有效
        
        Returns:
            voice_type字符串
        """
        if lang == "cmn" and gender == "female":
            return self.voice_type_cmn_female
        elif lang == "cmn" and gender == "male":
            return self.voice_type_cmn_male
        elif lang == "eng":
            return self.voice_type_eng
        elif lang == "chuan":
            return self.voice_type_chuan
        else:
            raise ValueError(f"不支持的语言类型: {lang}")
    
    def synthesize(self, text, lang, output_path, gender="female", 
                   emotion="neutral", silence_duration_ms=0):
        """
        合成单个文本为语音文件
        
        Args:
            text: 要合成的文本
            lang: 语言类型 (cmn/eng/chuan)
            output_path: 输出文件路径
            gender: 性别 (female/male)，仅对中文有效
            emotion: 情感类型，默认neutral
            silence_duration_ms: 前后静音时长（毫秒），默认0
        
        Returns:
            成功返回输出文件路径，失败返回None
        """
        # 获取voice_type
        voice_type = self._get_voice_type(lang, gender)
        
        # 构建请求JSON
        request_json = {
            "app": {
                "appid": self.appid,
                "token": "access_token",
                "cluster": self.cluster
            },
            "user": {
                "uid": self.uid
            },
            "audio": {
                "voice": "other",
                "voice_type": voice_type,
                "encoding": "wav",
                "speed": 10,
                "rate": 16000,
                "emotion": emotion,
                "volume": 10,
                "pitch": 10
            },
            "request": {
                "reqid": str(uuid.uuid4()),
                "text": text,
                "text_type": "plain",
                "operation": "query",
                "silence_duration": str(silence_duration_ms),
                "mute_cut_remain_ms": str(silence_duration_ms)
            }
        }
        
        try:
            # 发送TTS请求
            resp = requests.post(self.api_url, json.dumps(request_json), headers=self.header)
            
            if resp.status_code != 200:
                print(f"请求失败，状态码: {resp.status_code}")
                return None
            
            response_data = resp.json()
            if "data" not in response_data:
                error_code = response_data.get("code", "未知")
                print(f"获取语音二进制流失败，错误码: {error_code}")
                return None
            
            # 解码base64音频数据
            audio_data = base64.b64decode(response_data["data"])
            
            # 保存临时音频文件
            temp_file = output_path + ".tmp"
            with open(temp_file, "wb") as f:
                f.write(audio_data)
            
            # 添加前后静音
            if silence_duration_ms > 0:
                self._add_silence(temp_file, output_path, silence_duration_ms)
                os.remove(temp_file)  # 删除临时文件
            else:
                os.rename(temp_file, output_path)
            
            print(f"合成成功: {text} -> {output_path}")
            return output_path
            
        except Exception as e:
            print(f"合成失败: {text}, 错误: {e}")
            return None
    
    def _add_silence(self, input_file, output_file, silence_duration_ms):
        """
        为音频文件添加前后静音
        
        Args:
            input_file: 输入音频文件路径
            output_file: 输出音频文件路径
            silence_duration_ms: 静音时长（毫秒）
        """
        # 加载音频
        y, sr = sf.read(input_file)
        
        # 计算静音样本数
        silence_samples = int(float(silence_duration_ms) / 1000 * sr)
        
        # 生成前后静音
        front_silence = np.zeros(silence_samples)
        back_silence = np.zeros(silence_samples)
        
        # 拼接音频
        result = np.concatenate([front_silence, y, back_silence])
        
        # 保存结果
        sf.write(output_file, result, sr)
    
    def batch_synthesize(self, text_list, lang, output_dir, gender="female",
                         emotion="neutral", silence_duration_ms=0):
        """
        批量合成文本列表为语音文件
        
        Args:
            text_list: 文本列表
            lang: 语言类型 (cmn/eng/chuan)
            output_dir: 输出目录
            gender: 性别 (female/male)，仅对中文有效
            emotion: 情感类型，默认neutral
            silence_duration_ms: 前后静音时长（毫秒），默认0
        
        Returns:
            成功合成的文件路径列表和文本映射字典
        """
        # 创建输出目录
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, mode=0o755)
        
        success_files = []
        text_ref_data = []  # 用于记录音频文件名和文本的对应关系
        
        # 逐个合成（不支持并发）
        for text in text_list:
            # 使用全大写UUID生成唯一文件名
            filename = f"{str(uuid.uuid4()).replace('-', '').upper()}.wav"
            
            output_path = os.path.join(output_dir, filename)
            
            # 合成音频
            result = self.synthesize(
                text=text,
                lang=lang,
                output_path=output_path,
                gender=gender,
                emotion=emotion,
                silence_duration_ms=silence_duration_ms
            )
            
            if result:
                success_files.append(result)
                # 记录音频文件名和文本的对应关系
                text_ref_data.append((filename, text))
        
        # 生成text.ref文件
        ref_file_path = os.path.join(output_dir, "text.ref")
        with open(ref_file_path, "w", encoding="utf-8") as f:
            for filename, text in text_ref_data:
                f.write(f"{filename}\t{text}\n")
        
        print(f"\n批量合成完成: 成功 {len(success_files)}/{len(text_list)}")
        print(f"文本映射文件已生成: {ref_file_path}")
        return success_files


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description="独立的TTS合成工具")
    
    # 合成参数
    parser.add_argument("--list", required=True, nargs="+", dest="text_list",
                       help="要合成的文本列表，可以是多个文本参数，或者一个文本文件路径（文件中每行一个文本）")
    parser.add_argument("--lang", required=True, choices=["cmn", "eng", "chuan"], 
                       help="语言类型: cmn(中文)/eng(英文)/chuan(川话)")
    parser.add_argument("--output", required=True, dest="output_dir",
                       help="输出目录")
    parser.add_argument("--silence", type=int, default=0, dest="silence_ms",
                       help="前后静音时长（毫秒），默认0")
    
    args = parser.parse_args()
    
    # 处理文本列表：如果只有一个参数且是文件路径，则读取文件；否则直接使用参数列表
    text_list = args.text_list
    if len(text_list) == 1:
        # 检查是否是文件路径
        file_path = text_list[0]
        if os.path.isfile(file_path):
            # 读取文件，每行作为一个文本
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    text_list = [line.strip() for line in f.readlines() if line.strip()]
                print(f"从文件读取到 {len(text_list)} 条文本: {file_path}")
            except Exception as e:
                print(f"读取文件失败: {file_path}, 错误: {e}")
                return
        # 如果不是文件，则使用单个文本
        else:
            text_list = text_list
    
    if not text_list:
        print("错误: 没有要合成的文本")
        return
    
    # 创建合成器（使用脚本顶部的固定配置）
    synthesizer = SimpleTTSSynthesizer(
        appid=TTS_APPID,
        access_token=TTS_ACCESS_TOKEN,
        cluster=TTS_CLUSTER,
        api_url=TTS_API_URL,
        uid=TTS_UID,
        voice_type_cmn_female=VOICE_TYPE_CMN_FEMALE,
        voice_type_cmn_male=VOICE_TYPE_CMN_MALE,
        voice_type_eng=VOICE_TYPE_ENG,
        voice_type_chuan=VOICE_TYPE_CHUAN
    )
    
    # 批量合成
    synthesizer.batch_synthesize(
        text_list=text_list,
        lang=args.lang,
        output_dir=args.output_dir,
        gender=DEFAULT_GENDER,
        emotion=DEFAULT_EMOTION,
        silence_duration_ms=args.silence_ms
    )


if __name__ == "__main__":
    main()
