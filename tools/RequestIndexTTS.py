#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2025/8/28 13:48
# @Author  : liutianwei
# @File    : RequestIndexTts.py
# @Software: PyCharm


import argparse
import os.path
import concurrent.futures
import random
import re
import subprocess
import sys
import uuid
import librosa
import soundfile as sf
import requests
import base64
import numpy as np
from pydub import AudioSegment


class RequestVoxCPM:
    def __init__(self, output_path, is_scp, silence, retry):
        self._output_path = output_path
        self._is_scp = is_scp
        self._is_random = False
        self.audio_base64 = None
        self.audio_file = None
        self.prompt_text = None
        self.silence = silence
        self.retry = retry
        self.base_url = "http://192.168.128.32:9876"  # VoxCPM API 地址

    def set_reference(self, reference_path, prompt_text=None):
        """设置参考音频和参考文本"""
        if os.path.exists(reference_path):
            with open(reference_path, "rb") as f:
                audio_base64 = base64.b64encode(f.read()).decode('utf-8')
            self.audio_base64 = audio_base64
            self.audio_file = reference_path
            # 如果没有提供参考文本，使用默认文本
            self.prompt_text = prompt_text or "这是一个参考音频"
        else:
            if reference_path == "random":
                self._is_random = True
                # 为随机参考音频设置默认文本
                self.prompt_text = "这是一个随机参考音频"
            else:
                self.audio_file = f"../seed_audios/{reference_path}_seed.wav"
                # 为种子音频设置默认文本
                self.prompt_text = "这是一个种子参考音频"

    def convert_24k_to_16k_librosa(self, input_file, output_file=None):
        """将音频转换为16kHz并添加前后静音"""
        if output_file is None:
            output_file = input_file

        try:
            # 检查输入文件的采样率
            y, sr = librosa.load(input_file, sr=None, mono=True)

            # 计算静音样本数（基于目标采样率16000）
            silence_samples = int(round(self.silence / 1000 * 16000))
            silence = np.zeros(silence_samples, dtype=y.dtype)

            # 如果已经是16kHz，直接添加静音
            if sr == 16000:
                print(f"✓ 输入文件已经是16kHz，直接添加静音: {os.path.basename(input_file)}")
                # 移除末尾100ms（如果需要）
                remove_samples = int(round(100 / 1000 * 16000))
                if remove_samples < len(y):
                    y_trimmed = y[:-remove_samples]
                else:
                    y_trimmed = y

                # 添加前后静音
                y_final = np.concatenate([silence, y_trimmed, silence])

            else:
                # 如果不是16kHz，先重采样再添加静音
                if sr != 24000:
                    print(f"警告: 输入采样率 {sr} Hz, 不是预期的 24000 Hz，但仍会转换到16000 Hz")

                # 重采样到16kHz
                y_resampled = librosa.resample(y, orig_sr=sr, target_sr=16000, res_type="soxr_hq")

                # 移除末尾100ms
                remove_samples = int(round(100 / 1000 * 16000))
                if remove_samples < len(y_resampled):
                    y_trimmed = y_resampled[:-remove_samples]
                else:
                    y_trimmed = y_resampled

                # 添加前后静音
                y_final = np.concatenate([silence, y_trimmed, silence])

                print(
                    f"✓ 转换完成: {os.path.basename(input_file)} ({sr}Hz -> 16000Hz) -> {os.path.basename(output_file)}")

            # 确保输出目录存在
            os.makedirs(os.path.dirname(output_file), exist_ok=True)

            # 保存为16kHz WAV文件
            sf.write(output_file, y_final, 16000, subtype="PCM_16")
            print(f"✓ 静音添加完成: 前后各{self.silence}ms -> {os.path.basename(output_file)}")
            return True

        except Exception as e:
            print(f"✗ 处理失败 {os.path.basename(input_file)}: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    def read_file_list(self, file_path: str, max_workers=2):
        """读取文件列表并批量处理"""
        if not os.path.exists(file_path):
            print(f"✗ 文件不存在: {file_path}")
            return

        with open(file_path, "r", encoding="utf-8") as file:
            unique_lines = [line.strip() for line in file if line.strip()]

        # 根据自身配置的 retry 次数展开列表，避免依赖全局 args
        file_list = [line for line in unique_lines for _ in range(self.retry)]

        # 用线程池并发请求
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(self.request_voxcpm_api, text) for text in file_list]

            # 等待任务完成并捕获异常
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"任务执行出错: {e}")

    def request_voxcpm_api(self, text, cfg_value=2.0, inference_timesteps=10):
        """调用 VoxCPM API 进行语音合成"""
        if self._is_random:
            random_num = random.randint(1, 1000)
            self.audio_file = f"../seed_audios/{random_num}_seed.wav"
            # 为随机音频更新参考文本
            self.prompt_text = f"随机参考音频 {random_num}"

        try:
            # 准备请求数据
            data = {
                "text": text,
                "cfg_value": cfg_value,
                "inference_timesteps": inference_timesteps,
                "normalize": True,
                "denoise": True,
                "retry_badcase": True,
                "retry_badcase_max_times": 3,
                "retry_badcase_ratio_threshold": 6.0
            }

            # 如果有参考音频，必须同时提供参考文本
            if self.audio_file and os.path.exists(self.audio_file):
                data['prompt_text'] = self.prompt_text
                files = {'prompt_file': open(self.audio_file, 'rb')}
            elif self.audio_base64:
                # 如果有base64数据，先保存为临时文件
                temp_file = f"temp_prompt_{uuid.uuid4().hex[:8]}.wav"
                with open(temp_file, 'wb') as f:
                    f.write(base64.b64decode(self.audio_base64))
                data['prompt_text'] = self.prompt_text
                files = {'prompt_file': open(temp_file, 'rb')}
            else:
                # 没有参考音频，不提供 prompt_text
                files = {}

            print(f"发送请求: 文本='{text}', 参考音频={self.audio_file}, 参考文本='{self.prompt_text}'")

            # 提交任务
            response = requests.post(
                f"{self.base_url}/api/tts",
                data=data,
                files=files
            )

            # 关闭文件
            for file_obj in files.values():
                file_obj.close()

            # 清理临时文件
            if 'temp_file' in locals():
                os.remove(temp_file)

            if response.status_code != 200:
                print(f"API请求失败: {response.status_code} - {response.text}")
                return None

            task_info = response.json()
            task_id = task_info['task_id']

            # 等待任务完成
            result = self._wait_for_task_completion(task_id)

            if result and result['status'] == 'completed':
                # 下载音频文件
                download_url = f"{self.base_url}{result['result_url']}"
                download_response = requests.get(download_url)

                if download_response.status_code == 200:
                    filename = str(uuid.uuid4()).replace("-", "") + ".wav"
                    output_file = os.path.join(self._output_path, filename)

                    with open(output_file, "wb") as f:
                        f.write(download_response.content)

                    print(f"✓ {text} 生成成功！")

                    # 如果需要转换采样率
                    self.convert_24k_to_16k_librosa(output_file)

                    # 如果需要生成参考文件
                    if self._is_scp:
                        with open(f"{self._output_path}/text.scp", "a", encoding="utf-8") as f:
                            f.write(f"{output_file}\n")
                        with open(f"{self._output_path}/text.ref", "a", encoding="utf-8") as file:
                            file.write(f"{output_file}\t{text}\n")

                    return output_file
                else:
                    print(f"✗ 下载音频失败: {download_response.status_code}")
                    return None
            else:
                error_msg = result.get('error_message', '未知错误') if result else '任务状态获取失败'
                print(f"✗ {text} 生成错误: {error_msg}")
                return None

        except Exception as e:
            print(f"✗ {text} 请求异常: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    def _wait_for_task_completion(self, task_id, timeout=300, poll_interval=2):
        """等待任务完成"""
        import time

        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                response = requests.get(f"{self.base_url}/api/task/{task_id}")
                if response.status_code == 200:
                    task_status = response.json()

                    if task_status['status'] == 'completed':
                        return task_status
                    elif task_status['status'] == 'error':
                        print(f"任务失败: {task_status.get('error_message', '未知错误')}")
                        return task_status
                    elif task_status['status'] in ['pending', 'processing']:
                        print(f"任务状态: {task_status['status']}, 进度: {task_status['progress']}%")
                        time.sleep(poll_interval)
                    else:
                        print(f"未知任务状态: {task_status['status']}")
                        return None
                else:
                    print(f"查询任务状态失败: {response.status_code}")
                    time.sleep(poll_interval)

            except Exception as e:
                print(f"查询任务状态异常: {e}")
                time.sleep(poll_interval)

        print(f"任务超时，超过 {timeout} 秒")
        return None

    def request_voxcpm_quick(self, text, cfg_value=2.0, inference_timesteps=10):
        """快速合成 - 直接返回音频数据（不保存文件）"""
        try:
            # 准备请求数据
            data = {
                "text": text,
                "cfg_value": cfg_value,
                "inference_timesteps": inference_timesteps,
                "normalize": True,
                "denoise": True
            }

            # 如果有参考音频，必须同时提供参考文本
            files = {}
            if self.audio_file and os.path.exists(self.audio_file):
                data['prompt_text'] = self.prompt_text
                files['prompt_file'] = open(self.audio_file, 'rb')

            print(f"快速合成: 文本='{text}', 参考音频={self.audio_file}, 参考文本='{self.prompt_text}'")

            # 使用快速合成接口
            response = requests.post(
                f"{self.base_url}/api/tts_quick",
                data=data,
                files=files
            )

            # 关闭文件
            for file_obj in files.values():
                file_obj.close()

            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'success':
                    audio_data = base64.b64decode(result['audio_data'])
                    print(f"✓ {text} 快速合成成功！")
                    return audio_data
                else:
                    print(f"✗ 快速合成失败: {result.get('error', '未知错误')}")
                    return None
            else:
                print(f"✗ 快速合成请求失败: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            print(f"✗ {text} 快速合成异常: {str(e)}")
            return None

    def request_voxcpm_no_reference(self, text, cfg_value=2.0, inference_timesteps=10):
        """无参考音频的合成（零样本合成）"""
        try:
            # 准备请求数据 - 不提供 prompt_wav_path 和 prompt_text
            data = {
                "text": text,
                "cfg_value": cfg_value,
                "inference_timesteps": inference_timesteps,
                "normalize": True,
                "denoise": True,
                "retry_badcase": True,
                "retry_badcase_max_times": 3,
                "retry_badcase_ratio_threshold": 6.0
            }

            print(f"零样本合成: 文本='{text}' (无参考音频)")

            # 提交任务
            response = requests.post(
                f"{self.base_url}/api/tts",
                data=data
            )

            if response.status_code != 200:
                print(f"✗ API请求失败: {response.status_code} - {response.text}")
                return None

            task_info = response.json()
            task_id = task_info['task_id']

            # 等待任务完成
            result = self._wait_for_task_completion(task_id)

            if result and result['status'] == 'completed':
                download_url = f"{self.base_url}{result['result_url']}"
                download_response = requests.get(download_url)
                if download_response.status_code == 200:
                    filename = str(uuid.uuid4()).replace("-", "") + ".wav"
                    output_file = os.path.join(self._output_path, filename)
                    with open(output_file, "wb") as f:
                        f.write(download_response.content)
                    print(f"✓ {text} 零样本合成成功！")
                    # 如果需要转换采样率
                    self.convert_24k_to_16k_librosa(output_file)

                    # 如果需要生成参考文件
                    if self._is_scp:
                        with open(f"{self._output_path}/text.scp", "a", encoding="utf-8") as f:
                            f.write(f"{output_file}\n")
                        with open(f"{self._output_path}/text.ref", "a", encoding="utf-8") as file:
                            file.write(f"{output_file}\t{text}\n")

                    return output_file
                else:
                    print(f"✗ 下载音频失败: {download_response.status_code}")
                    return None
            else:
                error_msg = result.get('error_message', '未知错误') if result else '任务状态获取失败'
                print(f"✗ {text} 零样本合成错误: {error_msg}")
                return None

        except Exception as e:
            print(f"✗ {text} 零样本合成异常: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    def check_audio_sample_rate(self, file_path):
        """检查音频文件的采样率"""
        try:
            y, sr = librosa.load(file_path, sr=None)
            print(f"文件 {os.path.basename(file_path)} 的采样率为: {sr} Hz")
            return sr
        except Exception as e:
            print(f"无法检查采样率: {e}")
            return None

    def health_check(self):
        """检查服务状态"""
        try:
            response = requests.get(f"{self.base_url}/api/health")
            if response.status_code == 200:
                health = response.json()
                print(f"服务状态: {health}")
                return health.get('model_loaded', False)
            else:
                print(f"健康检查失败: {response.status_code}")
                return False
        except Exception as e:
            print(f"健康检查异常: {e}")
            return False


class RequestIndexTTS:
    def __init__(self, output_path, is_scp, silence, retry):
        self._output_path = output_path
        self._is_scp = is_scp
        self._retry = retry
        self._is_random = False
        self.audio_base64 = None
        self.audio_file = None
        self.silence = silence

    def set_reference(self, reference_path):
        if os.path.exists(reference_path):
            with open(reference_path, "rb") as f:
                audio_base64 = base64.b64encode(f.read()).decode('utf-8')
            self.audio_base64 = audio_base64
        else:
            if reference_path == "random":
                # random_num = random.randint(1, 1000)
                self._is_random = True
            else:
                self.audio_file = f"seed_audios/{reference_path}_seed.wav"

    def convert_24k_to_16k_librosa(self, input_file, output_file=None):
        if output_file is None:
            output_file = input_file
        try:
            y, sr = librosa.load(input_file, sr=None, mono=True)
            if sr != 24000:
                print(f"警告: 输入采样率 {sr} Hz, 不是预期的 24000 Hz，但仍会尝试转换")
            y_resampled = librosa.resample(y, orig_sr=sr, target_sr=16000, res_type="soxr_hq")
            remove_samples = int(round(100 / 1000 * 16000))  # 100ms对应的样本数
            if remove_samples < len(y_resampled):
                y_trimmed = y_resampled[:-remove_samples]
            else:
                y_trimmed = y_resampled

            # 添加前后800毫秒静音
            silence_samples = int(round(800 / 1000 * 16000))  # 800ms对应的样本数
            silence = np.zeros(silence_samples, dtype=y_trimmed.dtype)
            y_final = np.concatenate([silence, y_trimmed, silence])
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            sf.write(output_file, y_final, 16000, subtype="PCM_16")
            print(f"✓ 转换完成: {os.path.basename(input_file)} -> {os.path.basename(output_file)}")
            return True

        except Exception as e:
            print(f"✗ 转换失败 {os.path.basename(input_file)}: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    def read_file_list(self, file_path: str, max_workers=2):
        file_list = []
        if file_path.endswith(".txt"):
            with open(file_path, "r", encoding="utf-8") as file:
                unique_lines = [line.strip() for line in file if line.strip()]
            # 按实例上的重试次数展开，避免依赖全局 args
            file_list = [line for line in unique_lines for _ in range(self._retry)]
        else:
            with open(file_path, "r", encoding="utf-8") as file:
                unique_lines = [line.strip() for line in file if line.strip()]
            row = 0
            for line in unique_lines:
                matches = re.findall(r'<(\d+)>|([^<]+)', line)
                result = []
                result.append(('row',str(row)))
                for match in matches:
                    if match[0]:
                        result.append(('number', match[0]))
                    else:
                        result.append(('text', match[1]))
                row += 1
                file_list.append(result)
        # # 用线程池并发请求
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(self.request_index_tts_api, text) for text in file_list]

            # 等待任务完成并捕获异常
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"任务执行出错: {e}")

    def get_request_data(self, text, audio_file):
        response = requests.post(
            "http://192.168.130.37:8000/api/tts",
            json={
                "text": text,
                "prompt_audio_base64": self.audio_base64,
                "prompt_audio_path": audio_file,
                "infer_mode": "普通推理"
            }
        )
        result = response.json()
        if result["success"]:
            return base64.b64decode(result["audio_base64"])
        else:
            return None

    def convert_24k_to_16k(self, input_file, output_file):
        # 加载音频文件，指定原始采样率为24kHz
        audio, sr = librosa.load(input_file, sr=24000)
        # 重采样到16kHz
        audio_resampled = librosa.resample(audio, orig_sr=sr, target_sr=16000)
        # 保存为16kHz音频文件
        sf.write(output_file, audio_resampled, 16000)

    def combine_voice(self, input_files):
        if not input_files:
            print("输入文件列表为空")
            return False
        processed_audios = []
        sample_rate = 16000
        for input_file in input_files:
            try:
                if not os.path.exists(input_file):
                    print(f"✗ 文件不存在: {input_file}")
                    continue
                # 加载音频文件
                y, sr = librosa.load(input_file, sr=None, mono=True)
                # 采样率检查和转换
                y_resampled = librosa.resample(y, orig_sr=sr, target_sr=sample_rate, res_type="soxr_hq")
                remove_samples = int(round(100 / 1000 * sample_rate))  # 100ms对应的样本数
                if remove_samples < len(y_resampled):
                    y_trimmed = y_resampled[:-remove_samples]
                else:
                    y_trimmed = y_resampled
                processed_audios.append(y_trimmed)
            except Exception as e:
                print(f"✗ 转换失败 {os.path.basename(input_file)}: {str(e)}")
                import traceback
                traceback.print_exc()
                continue
        if not processed_audios:
            return False
        # 拼接所有音频
        try:
            combined_audio = np.concatenate(processed_audios)
            filename = f"combined_audio_{str(uuid.uuid4()).replace('-', '')}files.wav"
            output_file = os.path.join(self._output_path, filename)
            # 保存合并后的音频
            sf.write(output_file, combined_audio, sample_rate)
            return output_file
        except Exception as e:
            print(f"✗ 音频合并失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    def request_index_tts_api(self, text):
        if self._is_random:
            random_num = random.randint(1, 1000)
            audio_file = f"seed_audios/{random_num}_seed.wav"
        else:
            audio_file = self.audio_file

        if not isinstance(text, str):
            input_files = []
            for i in range(1, len(text)):
            # for key_text in text:
                if list(text[i])[0] == "text":
                    audio_data = self.get_request_data(list(text[i])[1], audio_file)
                    if audio_data is not None:
                        filename = f"{text[0][1]}_{list(text[i])[1]}.wav"
                        output_file = os.path.join(self._output_path, filename)
                        with open(output_file, "wb") as f:
                            f.write(audio_data)
                            print(f"{filename}生成成功！")
                        self.convert_24k_to_16k(output_file, output_file)
                        input_files.append(output_file)
                    else:
                        print(f"{list(text[i])[1]}生成失败")
            # 对音频进行拼接
            output_file = self.combine_voice(input_files)
            if self._is_scp:
                with open(f"{self._output_path}/text.scp", "a", encoding="utf-8") as f:
                    f.write(f"{output_file}\n")
                with open(f"{self._output_path}/text.ref", "a", encoding="utf-8") as file:
                    result_text = ""
                    for key_value in text:
                        if key_value[0] == "text":
                            result_text += key_value[1] + ","
                    file.write(f"{output_file}\t{result_text.strip(',')}\n")
        else:
            audio_data = self.get_request_data(text, audio_file)
            if audio_data is not None:
                filename = str(uuid.uuid4()).replace("-", "") + ".wav"
                output_file = os.path.join(self._output_path, filename)
                # audio_data = base64.b64decode(result["audio_base64"])
                with open(output_file, "wb") as f:
                    f.write(audio_data)
                print(f"{text}生成成功！")
                self.convert_24k_to_16k_librosa(output_file)
                if self._is_scp:
                    with open(f"{self._output_path}/text.scp", "a", encoding="utf-8") as f:
                        f.write(f"{output_file}\n")
                    with open(f"{self._output_path}/text.ref", "a", encoding="utf-8") as file:
                        file.write(f"{output_file}\t{text}\n")
                return output_file
            else:
                print(f"{text}生成错误")
                return None

    def check_audio_sample_rate(self, file_path):
        """检查音频文件的采样率"""
        try:
            y, sr = librosa.load(file_path, sr=None)
            print(f"文件 {os.path.basename(file_path)} 的采样率为: {sr} Hz")
            return sr
        except Exception as e:
            print(f"无法检查采样率: {e}")
            return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TTS合成接口")
    parser.add_argument("--select_model", '-m', help="选择需要生成的模型", default="index_tts", type=str, nargs='?')
    parser.add_argument("--file_list", '-f', help="选择需要生成的音频列表", type=str, nargs='?')
    parser.add_argument("--text", '-t', help="选择要生成的发话", type=str, nargs='?')
    parser.add_argument("--voice_type", '-v', help="选择需要生成的音色", type=str, nargs='?')
    parser.add_argument("--output", '-o', help="选择生成的位置", type=str, nargs='?')
    parser.add_argument("--silence", '-i', help="选择生成前后静音时长", type=int, default=800, nargs='?')
    parser.add_argument("--threads", '-n', help="开启线程数", type=int, default=2, nargs='?')
    parser.add_argument("--scp", '-s', help='是否生成参考文件', action='store_true')
    parser.add_argument("--check_rate", '-c', help='检查音频采样率', type=str, nargs='?')
    parser.add_argument("--cfg", help='CFG值', type=float, default=2.0, nargs='?')
    parser.add_argument("--timesteps", help='推理步数', type=int, default=10, nargs='?')
    parser.add_argument("--quick", help='使用快速合成模式', action='store_true')
    parser.add_argument("--prompt_text", '-p', help="参考音频对应的文本", type=str, nargs='?')
    parser.add_argument("--zero_shot", '-z', help='使用零样本合成（无参考音频）', action='store_true')
    parser.add_argument("--retry", '-r', help='重试次数', type=int, default=1, nargs='?')
    args = parser.parse_args()
    if args.select_model == "index_tts":
        if args.check_rate:
            # 检查单个文件的采样率
            RequestIndexTTS = RequestIndexTTS("", False, 800)
            RequestIndexTTS.check_audio_sample_rate(args.check_rate)
        else:
            print(f"选择需要生成的音频列表：{args.file_list}")
            print(f"选择要生成的发话：{args.text}")
            print(f"选择需要生成的音色：{args.voice_type}")
            print(f"选择生成前后静音时长：{args.silence}")
            print(f"开启线程数：{args.threads}")
            print(f"选择生成的位置：{args.output}")
            print(f"是否生成参考文件：{args.scp}")
            print(f"选择重复生成次数{args.retry}")

            RequestIndexTTS = RequestIndexTTS(args.output, args.scp, args.silence, args.retry)
            RequestIndexTTS.set_reference(args.voice_type)

            if args.file_list is not None:
                file_name = os.path.splitext(os.path.basename(args.file_list))[0]
                RequestIndexTTS.read_file_list(args.file_list, args.threads)
            elif args.text is not None:
                RequestIndexTTS.request_index_tts_api(args.text)
    elif args.select_model == "vox":
        print(f"选择需要生成的音频列表：{args.file_list}")
        print(f"选择要生成的发话：{args.text}")
        print(f"选择需要生成的音色：{args.voice_type}")
        print(f"参考音频文本：{args.prompt_text}")
        print(f"选择生成前后静音时长：{args.silence}")
        print(f"开启线程数：{args.threads}")
        print(f"选择生成的位置：{args.output}")
        print(f"是否生成参考文件：{args.scp}")
        print(f"CFG值：{args.cfg}")
        print(f"推理步数：{args.timesteps}")
        print(f"快速合成模式：{args.quick}")
        print(f"零样本合成模式：{args.zero_shot}")
        print(f"重复生成次数{args.retry}")
        # 创建输出目录
        if args.output and not os.path.exists(args.output):
            os.makedirs(args.output)
        voxcpm = RequestVoxCPM(args.output, args.scp, args.silence, args.retry)
        if not args.zero_shot:
            # 设置参考音频（如果不是零样本模式）
            voxcpm.set_reference(args.voice_type, args.prompt_text)

        # 检查服务状态
        if not voxcpm.health_check():
            print("警告: 服务可能不可用，继续执行...")

        if args.file_list is not None:
            file_name = os.path.splitext(os.path.basename(args.file_list))[0]
            if args.quick:
                def quick_synthesis(text):
                    if args.zero_shot:
                        return voxcpm.request_voxcpm_no_reference(text, args.cfg, args.timesteps)
                    else:
                        return voxcpm.request_voxcpm_quick(text, args.cfg, args.timesteps)
                with open(args.file_list, "r", encoding="utf-8") as file:
                    unique_lines = [line.strip() for line in file if line.strip()]
                file_list = [line for line in unique_lines for _ in range(args.retry)]
                with concurrent.futures.ThreadPoolExecutor(max_workers=args.threads) as executor:
                    futures = [executor.submit(quick_synthesis, text) for text in file_list]

                    for future in concurrent.futures.as_completed(futures):
                        try:
                            result = future.result()
                            if result:
                                if isinstance(result, bytes):
                                    print("快速合成成功，音频数据长度:", len(result))
                                else:
                                    print("合成成功，文件:", result)
                        except Exception as e:
                            print(f"合成任务执行出错: {e}")
            else:
                # 标准合成模式
                if args.zero_shot:
                    # 零样本批量合成
                    def zero_shot_synthesis(text):
                        return voxcpm.request_voxcpm_no_reference(text, args.cfg, args.timesteps)
                    with open(args.file_list, "r", encoding="utf-8") as file:
                        unique_lines = [line.strip() for line in file if line.strip()]
                    file_list = [line for line in unique_lines for _ in range(args.retry)]
                    with concurrent.futures.ThreadPoolExecutor(max_workers=args.threads) as executor:
                        futures = [executor.submit(zero_shot_synthesis, text) for text in file_list]
                        for future in concurrent.futures.as_completed(futures):
                            try:
                                result = future.result()
                                if result:
                                    print("零样本合成成功，文件:", result)
                            except Exception as e:
                                print(f"零样本合成任务执行出错: {e}")
                else:
                    voxcpm.read_file_list(args.file_list, args.threads)
        elif args.text is not None:
            if args.zero_shot:
                # 零样本单句合成
                result = voxcpm.request_voxcpm_no_reference(args.text, args.cfg, args.timesteps)
                if result:
                    print("零样本合成成功，文件:", result)
            elif args.quick:
                audio_data = voxcpm.request_voxcpm_quick(args.text, args.cfg, args.timesteps)
                if audio_data:
                    print("快速合成成功，音频数据长度:", len(audio_data))
            else:
                voxcpm.request_voxcpm_api(args.text, args.cfg, args.timesteps)
