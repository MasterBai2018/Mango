#!/usr/bin/env python
# -*- coding: utf-8 -*-
import numpy as np
import os
import subprocess
import wave
import soundfile as sf


def process_audio(audio_path, sample_rate, bit_width, channels):
    """
    处理音频文件：如果是WAV则验证参数，否则转换为WAV。

    参数:
    audio_path (str): 音频文件路径
    sample_rate (int): 期望的采样率（Hz）
    bit_width (int): 期望的位宽（比特，如16, 24）
    channels (int): 期望的声道数

    返回:
    str: 处理后的WAV文件路径

    异常:
    ValueError: 参数不匹配或文件扩展名无效
    RuntimeError: sox转换失败
    """
    # 检查文件是否存在
    if not os.path.isfile(audio_path):
        raise FileNotFoundError(f"音频文件不存在: {audio_path}")

    # 获取文件扩展名并转换为小写
    ext = os.path.splitext(audio_path)[1].lower()

    # 处理WAV文件
    if ext == '.wav':
        try:
            # 使用soundfile获取音频信息
            info = sf.info(audio_path)
            actual_params = {
                'sample_rate': info.samplerate,
                'channels': info.channels
            }

            # 解析位宽信息
            if 'PCM_16' in info.subtype:
                actual_params['bit_width'] = 16
            elif 'PCM_24' in info.subtype:
                actual_params['bit_width'] = 24
            elif 'PCM_32' in info.subtype:
                actual_params['bit_width'] = 32
            elif 'PCM_U8' in info.subtype or 'PCM_8' in info.subtype:
                actual_params['bit_width'] = 8
            else:
                # 尝试从子类型中提取位宽
                if 'PCM_' in info.subtype:
                    try:
                        # 尝试从子类型字符串中提取位宽数字
                        actual_params['bit_width'] = int(info.subtype.split('PCM_')[1])
                    except:
                        raise ValueError(f"无法解析位宽信息: {info.subtype}")
                else:
                    raise ValueError(f"不支持的音频子类型: {info.subtype}")

        except Exception as e:
            raise ValueError(f"无法读取WAV文件: {str(e)}") from e

        expected_params = {
            'sample_rate': sample_rate,
            'bit_width': bit_width,
            'channels': channels
        }

        # 检查参数是否匹配
        mismatches = []
        for param, expected_val in expected_params.items():
            actual_val = actual_params[param]
            if actual_val != expected_val:
                mismatches.append(
                    f"{param}: 期望 {expected_val}, 实际 {actual_val}"
                )

        if mismatches:
            raise ValueError("WAV参数不匹配:\n" + "\n".join(mismatches))

        return audio_path

    # 处理PCM文件
    elif ext in ('.pcm', '.raw'):
        # 构建输出路径（相同目录，扩展名改为.wav）
        output_path = os.path.splitext(audio_path)[0] + '.wav'

        # 根据位宽确定编码类型
        encoding = 'unsigned-integer' if bit_width == 8 else 'signed-integer'

        # 构建sox命令
        command = [
            'sox',
            '--type', 'raw',  # 输入类型为原始PCM
            '--rate', str(sample_rate),
            '--bits', str(bit_width),
            '--channels', str(channels),
            '--encoding', encoding,
            '--endian', 'little',  # 假设小端字节序（常见格式）
            audio_path,
            '--type', 'wav',  # 输出类型为WAV
            output_path
        ]

        # 执行转换
        try:
            result = subprocess.run(
                command,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            # 检查sox输出中是否有错误
            if result.stderr:
                print(f"sox警告: {result.stderr.decode('utf-8')}")
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode('utf-8') if e.stderr else str(e)
            raise RuntimeError(f"sox转换失败: {error_msg}") from e
        except FileNotFoundError:
            raise RuntimeError("未找到sox工具，请先安装sox")

        return output_path

    # 不支持的文件类型
    else:
        raise ValueError(f"不支持的音频格式: {ext} (仅支持.wav/.pcm/.raw)")


def calculate_total_rms_dbfs(audio_data):
    rms_level = 20 * np.log10(np.sqrt(np.mean(audio_data ** 2)) + 1.0e-9)  # 计算总 RMS 并转换为 dBFS
    return rms_level


def calculate_max_rms_dbfs(audio_data, window_size):
    rms_values = []
    for start in range(0, len(audio_data), window_size):
        end = min(start + window_size, len(audio_data))
        window = audio_data[start:end]
        if len(window) > 0:
            rms = 20 * np.log10(np.sqrt(np.mean(window ** 2)) + 1.0e-9)
            rms_values.append(rms)
    return np.max(rms_values) if rms_values else -np.inf  # 返回 -inf 如果没有 RMS 值


def calculate_min_rms_dbfs(audio_data, window_size):
    rms_values = []
    for start in range(0, len(audio_data), window_size):
        end = min(start + window_size, len(audio_data))
        window = audio_data[start:end]
        if len(window) > 0:
            rms = 20 * np.log10(np.sqrt(np.mean(window ** 2)) + 1.0e-9)
            rms_values.append(rms)
    return np.min(rms_values) if rms_values else -np.inf


def calculate_avg_rms_dbfs(audio_data, window_size):
    rms_values = []
    for start in range(0, len(audio_data), window_size):
        end = min(start + window_size, len(audio_data))
        window = audio_data[start:end]
        if len(window) > 0:
            rms = 20 * np.log10(np.sqrt(np.mean(window ** 2)) + 1.0e-9)
            rms_values.append(rms)
    return np.mean(rms_values) if rms_values else -np.inf


def calculate_peak_amplitude(audio_data):
    return 20 * np.log10(np.max(np.abs(audio_data)) + 1.0e-9)


def extract_voice_regions(audio_data, sample_rate, mic_num, ref_num, voice_regions):
    """
    提取指定麦克风声道的语音区域
    """
    # 分离麦克风声道
    mic_channels = audio_data[:, :mic_num]

    # 为每个麦克风声道提取语音区域
    result = {}
    for region in voice_regions:
        label = region["label"]
        ch = region["channel"]
        start = region["start"]
        end = region["end"]

        # 只处理麦克风声道
        if ch >= mic_num:
            continue

        # 转换为采样点索引
        start_idx = int(start * sample_rate)
        end_idx = int(end * sample_rate)

        # 确保索引在有效范围内
        start_idx = max(0, start_idx)
        end_idx = min(len(audio_data), end_idx)

        if start_idx >= end_idx:
            continue

        # 提取该区域的音频
        segment = mic_channels[start_idx:end_idx, ch]

        label_key = f"{label} Channel {ch}"

        if label_key not in result:
            result[label_key] = []
        result[label_key].append(segment)

    # 把所有label相同的并且channel相同的，都合并同一声道所有语音片段
    for label_key in list(result.keys()):
        result[label_key] = np.concatenate(result[label_key])

    return result


def analyze_audio_data(audio_data, sample_rate, window_duration=0.05):
    """
    分析单声道音频数据
    """
    window_size = int(window_duration * sample_rate)

    total_rms_dbfs = calculate_total_rms_dbfs(audio_data)
    max_rms_dbfs = calculate_max_rms_dbfs(audio_data, window_size)
    min_rms_dbfs = calculate_min_rms_dbfs(audio_data, window_size)
    avg_rms_dbfs = calculate_avg_rms_dbfs(audio_data, window_size)
    peak_amplitude = calculate_peak_amplitude(audio_data)

    return {
        "total_rms_dbfs": total_rms_dbfs,
        "max_rms_dbfs": max_rms_dbfs,
        "min_rms_dbfs": min_rms_dbfs,
        "avg_rms_dbfs": avg_rms_dbfs,
        "peak_amplitude": peak_amplitude
    }


def _read_audio_samples(audio_path, sample_rate):
    """
    读取音频为 float32，范围[-1,1]，形状为 [samples, channels]。
    优先使用 soundfile；若失败且是 WAV，则回退到内置 wave。
    """
    try:
        audio_data, sr = sf.read(audio_path, dtype='float32', always_2d=True)
    except Exception as sf_error:
        ext = os.path.splitext(audio_path)[1].lower()
        if ext != '.wav':
            raise RuntimeError(f"读取音频失败: {audio_path}, 错误: {sf_error}") from sf_error

        # WAV 回退路径，避免第三方解码器异常时整体失败
        try:
            with wave.open(audio_path, 'rb') as wav_file:
                sr = wav_file.getframerate()
                channels = wav_file.getnchannels()
                sample_width = wav_file.getsampwidth()
                frames = wav_file.readframes(wav_file.getnframes())

            if sample_width == 1:
                pcm = np.frombuffer(frames, dtype=np.uint8).astype(np.float32)
                pcm = (pcm - 128.0) / 128.0
            elif sample_width == 2:
                pcm = np.frombuffer(frames, dtype=np.int16).astype(np.float32)
                pcm = pcm / 32768.0
            elif sample_width == 4:
                pcm = np.frombuffer(frames, dtype=np.int32).astype(np.float32)
                pcm = pcm / 2147483648.0
            else:
                raise ValueError(f"wave回退不支持的位宽: {sample_width * 8} bit")

            if channels <= 0:
                raise ValueError("WAV声道数无效")
            audio_data = pcm.reshape(-1, channels)
        except Exception as wave_error:
            raise RuntimeError(
                f"读取音频失败（soundfile与wave均失败）: {audio_path}, "
                f"soundfile错误: {sf_error}, wave错误: {wave_error}"
            ) from wave_error

    if sr != sample_rate:
        raise ValueError(f"采样率不匹配: 期望 {sample_rate}, 实际 {sr}, 文件: {audio_path}")

    return audio_data


def analyze_audio_rms(file, sample_rate, bit_width, mic_num, ref_num, voice_regions, window_duration=0.05):
    """
    分析音频文件，提取指定麦克风声道的语音区域
    """
    audio_path = process_audio(file, sample_rate, bit_width, mic_num + ref_num)

    # 加载音频文件（soundfile/wave），返回形状 [samples, channels]
    audio_data = _read_audio_samples(audio_path, sample_rate)

    # 转换为原始位宽（当前数据范围为[-1,1]）
    max_val = 2 ** (bit_width - 1)
    audio_data = audio_data * max_val

    # 提取语音区域
    voice_data = extract_voice_regions(audio_data, sample_rate, mic_num, ref_num, voice_regions)

    # 分析每个麦克风声道的语音区域
    results = {}
    for label, data in voice_data.items():
        # 归一化到[-1,1]范围进行分析
        data_norm = data / max_val
        results[label] = analyze_audio_data(data_norm, sample_rate, window_duration)

    return results


def print_analysis_results(results):
    """
    打印分析结果
    """
    for ch, metrics in results.items():
        print(f"\nChannel {ch} Voice Region Analysis:")
        print(f"Total RMS (dBFS): {metrics['total_rms_dbfs']:.2f}")
        print(f"Max RMS (dBFS): {metrics['max_rms_dbfs']:.2f}")
        print(f"Min RMS (dBFS): {metrics['min_rms_dbfs']:.2f}")
        print(f"Avg RMS (dBFS): {metrics['avg_rms_dbfs']:.2f}")
        print(f"Peak Amplitude (dBFS): {metrics['peak_amplitude']:.2f}")


if __name__ == "__main__":
    # 示例参数
    audio = '/data1/liutianwei/mango_new/mango_develop/mango/workspace/solution_filter/FILTER/1/data/nr_audios/C1_1.pcm'
    samplerate = 16000  # 示例采样率
    bit = 16  # 示例位宽
    mic = 4  # 麦克风声道数
    ref = 0  # 参考声道数

    voice_region = [
        # 注意：start 必须小于 end，否则会导致切片为空，最终结果为 {}
        {"label": "1", "channel": 0, "start": 8, "end": 11}
    ]

    # 分析音频
    result = analyze_audio_rms(audio, samplerate, bit, mic, ref, voice_region)
    print(result)
    # 打印结果
    print_analysis_results(result)

