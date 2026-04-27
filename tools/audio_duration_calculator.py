#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
音频时长统计工具
用于统计音频文件列表中所有音频文件的总时长
"""
import os
import wave
import sys


def get_wav_duration(file_path):
    """
    获取WAV音频文件的时长（秒）
    
    Args:
        file_path: 音频文件路径
        
    Returns:
        float: 音频时长（秒），如果文件不存在或无法读取则返回None
    """
    if not os.path.exists(file_path):
        return None
    
    try:
        with wave.open(file_path, 'rb') as wav_file:
            # 获取帧数
            frames = wav_file.getnframes()
            # 获取采样率
            sample_rate = wav_file.getframerate()
            # 计算时长（秒）
            duration = frames / float(sample_rate)
            return duration
    except Exception as e:
        print(f"警告: 无法读取文件 {file_path}: {e}", file=sys.stderr)
        return None


def calculate_total_duration(list_file_path, base_dir=None):
    """
    统计音频文件列表中的总时长
    
    Args:
        list_file_path: 音频文件列表路径
        base_dir: 音频文件的基准目录，如果为None则使用项目根目录
        
    Returns:
        tuple: (总时长（秒）, 成功统计的文件数, 失败的文件数, 详细信息列表)
    """
    # 如果没有指定基准目录，使用脚本所在目录的父目录（项目根目录）
    if base_dir is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        base_dir = os.path.dirname(script_dir)
    
    # 读取音频文件列表
    if not os.path.exists(list_file_path):
        print(f"错误: 文件列表不存在: {list_file_path}")
        return None, 0, 0, []
    
    with open(list_file_path, 'r', encoding='utf-8') as f:
        audio_files = [line.strip() for line in f if line.strip()]
    
    total_duration = 0.0
    success_count = 0
    fail_count = 0
    details = []
    
    print(f"开始统计 {len(audio_files)} 个音频文件的时长...")
    print(f"基准目录: {base_dir}\n")
    
    for idx, audio_file in enumerate(audio_files, 1):
        # 拼接完整路径
        full_path = os.path.join(base_dir, audio_file)
        
        # 获取时长
        duration = get_wav_duration(full_path)
        
        if duration is not None:
            total_duration += duration
            success_count += 1
            status = "✓"
            details.append({
                'index': idx,
                'file': audio_file,
                'duration': duration,
                'status': 'success'
            })
        else:
            fail_count += 1
            status = "✗"
            details.append({
                'index': idx,
                'file': audio_file,
                'duration': None,
                'status': 'failed'
            })
        
        # 显示进度
        duration_str = f"{duration:.2f}s" if duration else "N/A"
        print(f"[{idx:3d}/{len(audio_files)}] {status} {audio_file:<60} {duration_str:>10}")
    
    return total_duration, success_count, fail_count, details


def format_duration(seconds):
    """
    格式化时长显示
    
    Args:
        seconds: 秒数
        
    Returns:
        str: 格式化后的时长字符串
    """
    if seconds < 60:
        return f"{seconds:.2f}秒"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}分{secs:.2f}秒"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours}小时{minutes}分{secs:.2f}秒"


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python3 audio_duration_calculator.py <音频列表文件> [基准目录]")
        print("示例: python3 audio_duration_calculator.py TestCase/caselist/PSTT/VadCase/FA_FR/FA.list")
        sys.exit(1)
    
    list_file = sys.argv[1]
    base_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    # 如果提供的是相对路径，转换为绝对路径
    if not os.path.isabs(list_file):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        list_file = os.path.join(project_root, list_file)
    
    # 统计时长
    total_duration, success_count, fail_count, details = calculate_total_duration(list_file, base_dir)
    
    if total_duration is None:
        sys.exit(1)
    
    # 输出统计结果
    print("\n" + "="*80)
    print("统计结果:")
    print("="*80)
    print(f"总文件数:     {len(details)}")
    print(f"成功统计:     {success_count}")
    print(f"失败/缺失:     {fail_count}")
    print(f"总时长:       {format_duration(total_duration)} ({total_duration:.2f}秒)")
    print("="*80)
    
    # 如果有失败的文件，列出它们
    if fail_count > 0:
        print("\n失败的文件列表:")
        for detail in details:
            if detail['status'] == 'failed':
                print(f"  - {detail['file']}")


if __name__ == "__main__":
    main()

