#!/usr/bin/env python
# -*- coding: utf-8 -*-

import wave
import time


class AudioDataMixin:
    """DATA音频处理公共能力：读取、切片、分包发送"""

    def _load_pcm_and_meta(self, audio_path: str, frame_size: int):
        """
        自动识别WAV/PCM并读取原始PCM数据与音频元信息
        返回: (pcm_data, meta)
        meta字段: audio_type, channels, sample_width, sample_rate, block_align
        """
        is_wav = False
        channels = 1
        sample_width = 2
        sample_rate = 16000
        pcm_data = b""

        try:
            with wave.open(audio_path, "rb") as wav_file:
                channels = wav_file.getnchannels()
                sample_width = wav_file.getsampwidth()
                sample_rate = wav_file.getframerate()
                pcm_data = wav_file.readframes(wav_file.getnframes())
                is_wav = True
        except (wave.Error, EOFError):
            # 不是标准WAV时按PCM处理：直接读取原始字节
            with open(audio_path, "rb") as pcm_file:
                pcm_data = pcm_file.read()

            # PCM默认规则：16k采样率、16bit位宽，声道数由frame_size推导
            channels = int(frame_size / 320)
            if channels <= 0:
                channels = 1
            sample_width = 2
            sample_rate = 16000

        block_align = channels * sample_width
        if block_align <= 0 or sample_rate <= 0:
            raise ValueError(
                f"无效音频格式: channels={channels}, sample_width={sample_width}, sample_rate={sample_rate}"
            )

        # 统一去除尾部不完整采样字节，保证后续切片和发送都对齐
        valid_len = len(pcm_data) - (len(pcm_data) % block_align)
        pcm_data = pcm_data[:valid_len]

        meta = {
            "audio_type": "WAV" if is_wav else "PCM",
            "channels": channels,
            "sample_width": sample_width,
            "sample_rate": sample_rate,
            "block_align": block_align,
        }
        return pcm_data, meta

    def _slice_pcm_by_time(
        self,
        pcm_data: bytes,
        sample_rate: int,
        block_align: int,
        start_time: float,
        end_time: float,
    ):
        """
        根据start_time/end_time对原始PCM进行精确切片
        返回: (sliced_pcm, start_frame_idx, end_frame_idx)
        """
        total_frames = len(pcm_data) // block_align
        total_duration = total_frames / float(sample_rate) if sample_rate > 0 else 0.0

        clipped_start = max(0.0, float(start_time))
        clipped_end = total_duration if end_time < 0 else min(float(end_time), total_duration)
        if clipped_end < clipped_start:
            clipped_end = clipped_start

        # 使用round避免浮点精度导致的1字节错位
        start_frame_idx = min(total_frames, int(round(clipped_start * sample_rate)))
        end_frame_idx = min(total_frames, int(round(clipped_end * sample_rate)))
        if end_frame_idx < start_frame_idx:
            end_frame_idx = start_frame_idx

        start_byte = start_frame_idx * block_align
        end_byte = end_frame_idx * block_align
        sliced_pcm = pcm_data[start_byte:end_byte]

        return sliced_pcm, start_frame_idx, end_frame_idx

    def _send_pcm_chunks(self, pcm_data: bytes, frame_size: int, block_align: int, sample_rate: int, delay: float):
        """
        将PCM按块发送到引擎，发送块与采样边界对齐
        子类需要实现 _process_pcm_chunk() 返回 delta_ms
        """
        send_chunk_size = frame_size - (frame_size % block_align)
        if send_chunk_size <= 0:
            send_chunk_size = block_align

        # 使用整数余量累计，避免逐包round导致的时间戳累计误差
        # remainder_units 的单位是 "frame*1000"
        remainder_units = 0
        offset = 0
        total_len = len(pcm_data)
        while offset < total_len:
            chunk_end = min(offset + send_chunk_size, total_len)
            data_chunk = pcm_data[offset:chunk_end]
            if not data_chunk:
                break

            # 双保险：每块发送前再做一次采样边界对齐
            valid_len = len(data_chunk) - (len(data_chunk) % block_align)
            if valid_len <= 0:
                break
            if valid_len != len(data_chunk):
                data_chunk = data_chunk[:valid_len]

            sent_frames = valid_len // block_align
            if sent_frames <= 0:
                break

            units = sent_frames * 1000 + remainder_units
            delta_ms = units // sample_rate
            remainder_units = units % sample_rate

            # 兜底保证时间戳单调推进，避免极小包导致0ms
            if delta_ms <= 0:
                delta_ms = 1
                remainder_units = 0

            self._process_pcm_chunk(data_chunk, delta_ms)

            if float(delay) > 0.0:
                time.sleep((delta_ms / 1000.0) * float(delay))

            offset += valid_len

    def _process_pcm_chunk(self, data_chunk: bytes, delta_ms: int):
        """
        子类实现：将data_chunk送入各自引擎并按delta_ms推进时间戳
        """
        raise NotImplementedError("_process_pcm_chunk must be implemented by subclass")
