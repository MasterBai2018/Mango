#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
声纹FA（False Acceptance）测试用例生成工具
用于生成反向测试用例：用未注册用户去验证，期望结果是None（验证失败）
"""

import os
import re
import argparse
from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional
from collections import defaultdict


class FAVoicePrintCaseGenerator:
    """声纹FA测试用例生成器"""
    
    # 所有可用用户
    ALL_USERS = ['denggao', 'haijin', 'lianlian', 'mali', 'pengkun', 
                 'qingfeng', 'tangjian', 'xinyu', 'yuehan', 'zhangchao', 'zhongjing']
    
    # 音区映射
    CHANNEL_MAP = {
        'zhu': 0,
        'fu': 1,
        'left': 2,
        'right': 3
    }
    
    # 唤醒词到目录名的映射（enroll目录）
    WAKEUP_WORD_MAP = {
        '你好小悦': 'xiaoyue',
        '你好丰田': 'fengtian',
        '你好雷克萨斯': 'lexus'
    }
    
    # 唤醒词到测试用例目录名的映射
    WAKEUP_CASE_DIR_MAP = {
        '你好小悦': 'nihaoxiaoyue',
        '你好丰田': 'nihaofengtian',
        '你好雷克萨斯': 'nihaolexus'
    }
    
    # 车型配置映射
    CARTYPE_MAP = {
        'xiaoyue': 2,
        'fengtian': 1,
        'lexus': 0
    }
    
    # 性别判断（根据现有文件推断）
    GENDER_MAP = {
        'denggao': 'male',
        'haijin': 'female',
        'lianlian': 'female',
        'mali': 'female',
        'pengkun': 'male',
        'qingfeng': 'male',
        'tangjian': 'male',
        'xinyu': 'male',
        'yuehan': 'female',
        'zhangchao': 'male',
        'zhongjing': 'female'
    }
    
    def __init__(self, audio_base_path: str, project_root: str = None):
        """
        初始化生成器
        
        Args:
            audio_base_path: 音频文件根目录路径
            project_root: 项目根目录路径（用于生成相对路径）
        """
        self.audio_base_path = Path(audio_base_path)
        self.project_root = Path(project_root) if project_root else Path(__file__).parent.parent
        
        if not self.audio_base_path.exists():
            raise FileNotFoundError(f"音频路径不存在: {self.audio_base_path}")
    
    def get_wakeup_word_from_filename(self, filename: str) -> Optional[str]:
        """
        从文件名中提取唤醒词
        
        Args:
            filename: 音频文件名
            
        Returns:
            唤醒词或None
        """
        if '你好小悦' in filename:
            return '你好小悦'
        elif '你好丰田' in filename:
            return '你好丰田'
        elif '你好雷克萨斯' in filename:
            return '你好雷克萨斯'
        return None
    
    def classify_test_type(self, filename: str) -> str:
        """
        根据文件名分类测试类型
        
        Args:
            filename: 音频文件名
            
        Returns:
            测试类型：'sre_wakeup', 'sre_verify', 'sre_login'
        """
        # 登录相关文本模式
        login_patterns = [
            '登录我的个人中心', '登录我的声纹记忆', '我要登录声纹账号',
            '我要登录个人中心', '声纹登录个人中心'
        ]
        
        # 唤醒词列表
        wakeup_words = ['你好小悦', '你好丰田', '你好雷克萨斯']
        
        # 1. 纯唤醒词：只有"你好XX"（不包含其他内容）
        if re.match(r'^\d+_你好(小悦|丰田|雷克萨斯)\.wav$', filename):
            return 'sre_wakeup'
        
        # 2. 声纹验证：同时包含唤醒词+登录相关文本（优先检查）
        has_wakeup = any(word in filename for word in wakeup_words)
        has_login = any(pattern in filename for pattern in login_patterns)
        
        if has_wakeup and has_login:
            return 'sre_verify'
        
        # 3. 声纹登录：只包含登录相关文本（没有唤醒词前缀，或者唤醒词后面还有其他内容但不是登录相关）
        if has_login:
            return 'sre_login'
        
        # 4. 默认归类为登录（如果包含登录相关文本但没有唤醒词）
        return 'sre_login'
    
    def extract_verify_text(self, filename: str) -> Optional[str]:
        """
        从文件名提取验证文本
        
        Args:
            filename: 音频文件名
            
        Returns:
            验证文本或None
        """
        # 移除文件扩展名和数字前缀
        text = re.sub(r'^\d+_', '', filename)
        text = text.replace('.wav', '')
        
        # 如果文本为空，返回None
        if not text:
            return None
        
        # 添加逗号（如果包含唤醒词且后面还有其他内容）
        if '你好小悦' in text and len(text) > len('你好小悦'):
            # 检查是否已经有逗号
            if '你好小悦，' not in text:
                text = text.replace('你好小悦', '你好小悦，', 1)
        elif '你好丰田' in text and len(text) > len('你好丰田'):
            if '你好丰田，' not in text:
                text = text.replace('你好丰田', '你好丰田，', 1)
        elif '你好雷克萨斯' in text and len(text) > len('你好雷克萨斯'):
            if '你好雷克萨斯，' not in text:
                text = text.replace('你好雷克萨斯', '你好雷克萨斯，', 1)
        
        return text
    
    def scan_audio_files(self, users: List[str], channels: List[str] = None) -> Dict[str, Dict[str, List[str]]]:
        """
        扫描音频文件
        
        Args:
            users: 用户列表
            channels: 音区列表，默认['zhu', 'fu', 'left', 'right']
            
        Returns:
            嵌套字典：{用户: {音区: [音频文件列表]}}
        """
        if channels is None:
            channels = ['zhu', 'fu', 'left', 'right']
        
        audio_files = defaultdict(lambda: defaultdict(list))
        
        for user in users:
            user_dir = self.audio_base_path / user
            if not user_dir.exists():
                print(f"警告: 用户目录不存在: {user_dir}")
                continue
            
            for channel in channels:
                channel_dir = user_dir / channel
                if not channel_dir.exists():
                    continue
                
                # 扫描所有wav文件
                for wav_file in channel_dir.glob('*.wav'):
                    audio_files[user][channel].append(str(wav_file))
        
        return audio_files
    
    def generate_enroll_file(self, user: str, wakeup_word: str, audio_files: Dict[str, List[str]]) -> str:
        """
        生成注册文件内容
        
        Args:
            user: 用户名
            wakeup_word: 唤醒词
            audio_files: 该用户的音频文件字典 {音区: [文件列表]}
            
        Returns:
            注册文件内容
        """
        # 注册音频的固定顺序类型（根据现有文件格式）
        enrollment_patterns = [
            '登录我的个人中心',
            '登录我的声纹记忆',
            '我要登录声纹账号',
            '我要登录个人中心',
            '声纹登录个人中心'
        ]
        
        enroll_audios = []
        
        # 优先从zhu音区选择
        for pattern in enrollment_patterns:
            found = False
            # 先找zhu音区
            for audio_path in audio_files.get('zhu', []):
                filename = Path(audio_path).name
                if wakeup_word in filename and pattern in filename:
                    # 提取文本
                    text = self.extract_verify_text(filename)
                    channel = 0
                    user_id = user
                    index = len(enroll_audios) + 1
                    
                    # 生成相对路径
                    rel_path = self.get_relative_path(audio_path)
                    line = f"{rel_path}\ttext:{text};channel:{channel};user_id:{user_id};index:{index}"
                    enroll_audios.append(line)
                    found = True
                    break
            
            # 如果zhu音区没找到，从其他音区找
            if not found:
                for channel_name in ['fu', 'left', 'right']:
                    for audio_path in audio_files.get(channel_name, []):
                        filename = Path(audio_path).name
                        if wakeup_word in filename and pattern in filename:
                            text = self.extract_verify_text(filename)
                            channel = self.CHANNEL_MAP[channel_name]
                            user_id = user
                            index = len(enroll_audios) + 1
                            
                            rel_path = self.get_relative_path(audio_path)
                            line = f"{rel_path}\ttext:{text};channel:{channel};user_id:{user_id};index:{index}"
                            enroll_audios.append(line)
                            found = True
                            break
                    if found:
                        break
        
        return '\n'.join(enroll_audios) + '\n'
    
    def get_relative_path(self, file_path: str) -> str:
        """
        获取相对于项目根目录的路径
        
        Args:
            file_path: 绝对路径或相对路径
            
        Returns:
            相对路径
        """
        file_path_obj = Path(file_path)
        if file_path_obj.is_absolute():
            try:
                return str(file_path_obj.relative_to(self.project_root))
            except ValueError:
                # 如果不在项目根目录下，返回原路径
                return file_path
        return file_path
    
    def generate_fa_test_case(self, registered_users: List[str], wakeup_word: str, 
                             test_type: str, audio_files: Dict[str, Dict[str, List[str]]],
                             enroll_base_dir: Path = None) -> str:
        """
        生成FA测试用例CSV内容
        
        Args:
            registered_users: 已注册用户列表
            wakeup_word: 唤醒词
            test_type: 测试类型 ('sre_wakeup', 'sre_verify', 'sre_login')
            audio_files: 所有用户的音频文件字典
            enroll_base_dir: 注册文件基础目录（用于生成相对路径）
            
        Returns:
            CSV文件内容
        """
        # 获取未注册用户
        unregistered_users = [u for u in self.ALL_USERS if u not in registered_users]
        
        if not unregistered_users:
            return ""
        
        # 确定唤醒词目录名和车型
        wakeup_dir = self.WAKEUP_WORD_MAP.get(wakeup_word, 'xiaoyue')
        cartype = self.CARTYPE_MAP.get(wakeup_dir, 2)
        
        # 生成合并的注册文件路径
        register_count = len(registered_users)
        users_str = '_'.join(registered_users)
        
        # 生成注册文件的相对路径
        if enroll_base_dir:
            # 如果指定了enroll_base_dir，计算相对路径
            register_file_path = enroll_base_dir / wakeup_dir / f"register{register_count}_{users_str}.txt"
            try:
                # 尝试计算相对于项目根目录的相对路径
                register_file = str(register_file_path.relative_to(self.project_root))
            except ValueError:
                # 如果不在项目根目录下，尝试计算相对于enroll_base_dir的相对路径
                # 或者如果enroll_base_dir在项目根目录下，使用相对于项目根目录的路径
                try:
                    # 检查enroll_base_dir是否在项目根目录下
                    enroll_base_relative = enroll_base_dir.relative_to(self.project_root)
                    register_file = str(enroll_base_relative / wakeup_dir / f"register{register_count}_{users_str}.txt")
                except ValueError:
                    # 如果都不在项目根目录下，使用绝对路径
                    register_file = str(register_file_path)
        else:
            # 使用默认路径
            register_file = f"TestCase/caselist/24MM/SDK/VoicePrint/vp_multi_performance/enroll/{wakeup_dir}/register{register_count}_{users_str}.txt"
        
        # CSV头部
        lines = [
            '@delay: 0.8',
            '@frame_size: 1280',
            f'@register_list: {register_file}',
        ]
        
        # 根据测试类型添加不同的头部
        if test_type == 'sre_verify':
            lines.append('@verifyChannel: 0')
        
        lines.append(f'@cartype: {cartype}')
        
        # CSV列头
        if test_type == 'sre_wakeup':
            lines.append('audioPath\tuser_id')
        elif test_type == 'sre_verify':
            lines.append('audioPath\tverifyUser\tverifyChannel\tverifyText')
        elif test_type == 'sre_login':
            lines.append('audioPath\tuser_id')
        
        # 调试信息：统计匹配的音频文件
        matched_count = 0
        
        # 生成测试用例行
        for user in unregistered_users:
            user_audios = audio_files.get(user, {})
            
            for channel_name in ['zhu', 'fu', 'left', 'right']:
                channel_audios = user_audios.get(channel_name, [])
                
                for audio_path in channel_audios:
                    filename = Path(audio_path).name
                    
                    # 检查是否匹配测试类型
                    file_test_type = self.classify_test_type(filename)
                    if file_test_type != test_type:
                        continue
                    
                    # 对于sre_wakeup和sre_verify，必须匹配唤醒词
                    if test_type in ['sre_wakeup', 'sre_verify']:
                        if wakeup_word not in filename:
                            continue
                    # 对于sre_login，如果文件名包含唤醒词，必须匹配；如果不包含唤醒词，也可以（纯登录文本）
                    elif test_type == 'sre_login':
                        # 如果文件名包含唤醒词，必须匹配当前唤醒词
                        if any(w in filename for w in ['你好小悦', '你好丰田', '你好雷克萨斯']):
                            if wakeup_word not in filename:
                                continue
                        # 如果不包含唤醒词（纯登录文本），可以用于任何唤醒词的sre_login测试
                        # 这种情况下不需要检查唤醒词匹配
                    
                    rel_path = self.get_relative_path(audio_path)
                    channel_num = self.CHANNEL_MAP[channel_name]
                    
                    if test_type == 'sre_wakeup':
                        # 唤醒测试：FA测试期望结果是None（验证失败）
                        lines.append(f"{rel_path}\tNone")
                        matched_count += 1
                    
                    elif test_type == 'sre_verify':
                        # 验证测试：verifyUser应该是None（期望验证失败）
                        verify_text = self.extract_verify_text(filename)
                        if verify_text:
                            lines.append(f"{rel_path}\tNone\t{channel_num}\t{verify_text}")
                            matched_count += 1
                    
                    elif test_type == 'sre_login':
                        # 登录测试：FA测试期望结果是None（验证失败）
                        lines.append(f"{rel_path}\tNone")
                        matched_count += 1
        
        # 如果没有匹配的用例，返回空字符串
        if matched_count == 0:
            return ""
        
        return '\n'.join(lines) + '\n'
    
    def generate_all(self, registered_users: List[str], output_base_dir: str = None, output_root: str = None):
        """
        生成所有FA测试用例
        
        Args:
            registered_users: 注册用户列表（逗号分隔的字符串或列表）
            output_base_dir: 输出基础目录（测试用例目录，已废弃，保留兼容性）
            output_root: 输出根目录（如果指定，所有文件都生成到此目录下）
        """
        # 解析注册用户列表
        if isinstance(registered_users, str):
            registered_users = [u.strip() for u in registered_users.split(',')]
        
        # 验证用户
        invalid_users = [u for u in registered_users if u not in self.ALL_USERS]
        if invalid_users:
            raise ValueError(f"无效的用户名: {invalid_users}")
        
        if len(registered_users) == 0:
            raise ValueError("至少需要指定一个注册用户")
        
        # 扫描所有用户的音频文件
        print(f"正在扫描音频文件...")
        all_audio_files = self.scan_audio_files(self.ALL_USERS)
        
        # 确定输出目录
        if output_root:
            # 如果指定了output_root，所有文件都生成到此目录下
            output_root_path = Path(output_root)
            if not output_root_path.is_absolute():
                output_root_path = self.project_root / output_root_path
            
            # 注册文件目录：{output_root}/enroll/{wakeup_dir}/
            # 测试用例目录：{output_root}/case_nano/{test_type}/{wakeup_case_dir}/fa/
            enroll_base_dir = output_root_path / "enroll"
            case_base_dir = output_root_path / "case_nano"
        else:
            # 使用默认路径
            if output_base_dir is None:
                case_base_dir = self.project_root / "TestCase/caselist/24MM/SDK/VoicePrint/vp_multi_performance/case_nano"
            else:
                case_base_dir = Path(output_base_dir)
            enroll_base_dir = case_base_dir.parent / "enroll"
        
        # 为每个唤醒词和测试类型生成用例
        wakeup_words = ['你好小悦', '你好丰田', '你好雷克萨斯']
        test_types = ['sre_wakeup', 'sre_verify', 'sre_login']
        
        # 生成注册文件（多个用户合并到一个文件）
        print(f"正在生成注册文件...")
        for wakeup_word in wakeup_words:
            wakeup_dir = self.WAKEUP_WORD_MAP[wakeup_word]
            enroll_dir = enroll_base_dir / wakeup_dir
            enroll_dir.mkdir(parents=True, exist_ok=True)
            
            # 生成合并的注册文件名
            register_count = len(registered_users)
            users_str = '_'.join(registered_users)
            enroll_filename = f"register{register_count}_{users_str}.txt"
            enroll_file = enroll_dir / enroll_filename
            
            # 合并所有注册用户的音频
            merged_enroll_content = []
            for user in registered_users:
                user_audios = all_audio_files.get(user, {})
                user_enroll_content = self.generate_enroll_file(user, wakeup_word, user_audios)
                if user_enroll_content.strip():
                    merged_enroll_content.append(user_enroll_content.strip())
            
            # 写入合并的注册文件
            merged_content = '\n'.join(merged_enroll_content)
            if merged_content:
                merged_content += '\n'  # 文件末尾添加换行
                with open(enroll_file, 'w', encoding='utf-8') as f:
                    f.write(merged_content)
                print(f"  生成注册文件: {enroll_file} (包含 {len(registered_users)} 个用户)")
        
        # 生成FA测试用例
        print(f"正在生成FA测试用例...")
        for wakeup_word in wakeup_words:
            wakeup_dir = self.WAKEUP_WORD_MAP[wakeup_word]
            wakeup_case_dir = self.WAKEUP_CASE_DIR_MAP[wakeup_word]
            
            for test_type in test_types:
                # 确定输出目录
                fa_dir = case_base_dir / test_type / wakeup_case_dir / "fa"
                fa_dir.mkdir(parents=True, exist_ok=True)
                
                # 生成文件名（基于注册用户数量）
                register_count = len(registered_users)
                users_str = '_'.join(registered_users)
                case_filename = f"register{register_count}_{users_str}.csv"
                case_file = fa_dir / case_filename
                
                # 生成测试用例内容
                case_content = self.generate_fa_test_case(
                    registered_users, wakeup_word, test_type, all_audio_files, enroll_base_dir
                )
                
                if case_content.strip():
                    with open(case_file, 'w', encoding='utf-8') as f:
                        f.write(case_content)
                    print(f"  生成测试用例: {case_file}")
                else:
                    print(f"  警告: 未找到匹配的音频文件，跳过: {case_file}")


def main():
    parser = argparse.ArgumentParser(
        description='声纹FA（False Acceptance）测试用例生成工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 生成1个用户注册的FA测试用例
  python3 tools/generate_fa_voiceprint_cases.py --users denggao
  
  # 生成2个用户注册的FA测试用例
  python3 tools/generate_fa_voiceprint_cases.py --users denggao,haijin
  
  # 生成5个用户注册的FA测试用例
  python3 tools/generate_fa_voiceprint_cases.py --users denggao,haijin,lianlian,mali,pengkun
  
  # 指定音频路径和输出目录
  python3 tools/generate_fa_voiceprint_cases.py --users denggao,haijin \\
    --audio-path TestAudio/vp_multi_channel \\
    --output-dir TestCase/caselist/24MM/SDK/VoicePrint/vp_multi_performance/case_nano
  
  # 使用--output参数指定输出根目录（所有文件都生成到此目录下）
  python3 tools/generate_fa_voiceprint_cases.py --users denggao,haijin \\
    --output /tmp/fa_test_cases
        """
    )
    
    parser.add_argument(
        '--users',
        type=str,
        required=True,
        help='注册用户列表，逗号分隔（例如: denggao,haijin,lianlian）'
    )
    
    parser.add_argument(
        '--audio-path',
        type=str,
        default='TestAudio/vp_multi_channel',
        help='音频文件根目录路径（默认: TestAudio/vp_multi_channel）'
    )
    
    parser.add_argument(
        '--output-dir',
        type=str,
        default=None,
        help='输出目录（默认: TestCase/caselist/24MM/SDK/VoicePrint/vp_multi_performance/case_nano）'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='输出根目录（如果指定，所有文件都生成到此目录下，包括注册文件和测试用例文件）'
    )
    
    parser.add_argument(
        '--project-root',
        type=str,
        default=None,
        help='项目根目录路径（默认: 脚本所在目录的父目录）'
    )
    
    args = parser.parse_args()
    
    # 确定项目根目录
    if args.project_root:
        project_root = Path(args.project_root).resolve()
    else:
        project_root = Path(__file__).parent.parent.resolve()
    
    # 确定音频路径（相对路径转为绝对路径）
    if Path(args.audio_path).is_absolute():
        audio_path = Path(args.audio_path)
    else:
        audio_path = project_root / args.audio_path
    
    # 确定输出目录
    if args.output_dir:
        if Path(args.output_dir).is_absolute():
            output_dir = Path(args.output_dir)
        else:
            output_dir = project_root / args.output_dir
    else:
        output_dir = None
    
    # 创建生成器并生成用例
    try:
        generator = FAVoicePrintCaseGenerator(
            audio_base_path=str(audio_path),
            project_root=str(project_root)
        )
        
        print(f"项目根目录: {project_root}")
        print(f"音频路径: {audio_path}")
        print(f"注册用户: {args.users}")
        print()
        
        generator.generate_all(
            registered_users=args.users,
            output_base_dir=str(output_dir) if output_dir else None,
            output_root=str(args.output) if args.output else None
        )
        
        print()
        print("生成完成！")
        
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
