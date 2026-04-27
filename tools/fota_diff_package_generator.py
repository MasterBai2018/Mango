#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FOTA差量更新包生成工具

用于生成SpeechEngine的差量FOTA更新包，支持正向和损坏两种类型的测试用例。

使用方法:
    python3 fota_diff_package_generator.py <source_dir> <lcs_zip> <output_dir> [--count N] [--corrupt-ratio R]

参数说明:
    source_dir: SpeechEngine源资源目录路径
    lcs_zip: lcs.zip文件路径
    output_dir: 输出目录路径
    --count: 生成压缩包的数量（默认10）
    --corrupt-ratio: 损坏case的比例（0-1之间，默认0.5，即50%为损坏case）
    
注意:
    - 每个包随机选择1或2个文件夹
    - 如果目录组合已生成过，会自动跳过
    - vdata文件名格式: vdata_目录组合_正向.zip 或 vdata_目录组合_反向.zip

示例:
    python fota_diff_package_generator.py /data1/NFS_DATA/TestAudio/FOTA/T2/nano/SpeechEngine /data1/NFS_DATA/TestAudio/FOTA/T2/nano/lcs.zip /data1/NFS_DATA/TestAudio/FOTA/T2/output --count 20 --corrupt-ratio 0.5

Author: AI Assistant
Date: 2025-12-27
"""

import os
import sys
import shutil
import random
import zipfile
import argparse
import json
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from datetime import datetime


class FOTADiffPackageGenerator:
    """FOTA差量更新包生成器"""
    
    # 可选的资源目录结构
    RESOURCE_DIRS = [
        'cmn/asr',
        'cmn/wakeup',
        'cmn/common',
        'cmn/sre',
        'cmn/ved',
        'eng/asr',
        'eng/wakeup',
        'eng/common',
        'eng/sre',
        'eng/ved',
        'fuzzy_res'
    ]
    
    # 文件损坏操作类型
    CORRUPT_OPERATIONS = [
        'prepend',      # 开头追加"123456789"
        'append',       # 末尾追加"123456789"
        'remove_head',  # 开头删除10个字节
        'remove_tail',  # 末尾删除10个字节
        'insert_middle' # 文件中间插入"123456789"
    ]
    
    CORRUPT_MARKER = b"123456789"
    
    # 损坏操作的中文描述
    CORRUPT_DESCRIPTIONS = {
        'prepend': '开头损坏（开头追加123456789）',
        'append': '结尾损坏（末尾追加123456789）',
        'remove_head': '开头损坏（删除开头10字节）',
        'remove_tail': '结尾损坏（删除末尾10字节）',
        'insert_middle': '文件中损坏（中间插入123456789）'
    }
    
    def __init__(self, source_dir: str, lcs_zip: str, output_dir: str):
        """
        初始化生成器
        
        Args:
            source_dir: SpeechEngine源资源目录
            lcs_zip: lcs.zip文件路径
            output_dir: 输出目录路径
        """
        self.source_dir = Path(source_dir)
        self.lcs_zip = Path(lcs_zip)
        self.output_dir = Path(output_dir)
        
        # 验证源目录和lcs.zip是否存在
        if not self.source_dir.exists():
            raise ValueError(f"源目录不存在: {source_dir}")
        if not self.lcs_zip.exists():
            raise ValueError(f"lcs.zip文件不存在: {lcs_zip}")
        
        # 创建输出目录
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 记录文件，用于记录每个压缩包的详细信息
        self.record_file = self.output_dir / "package_records.json"
        self.vdata_record_file = self.output_dir / "vdata_record.txt"
        self.records = []
        
        # 记录已生成的目录组合，避免重复生成
        # 使用排序后的目录列表的元组作为key
        self.generated_combinations = set()
        
    def get_available_dirs(self) -> List[str]:
        """
        获取源目录中实际存在的资源目录
        
        Returns:
            存在的资源目录列表
        """
        available = []
        for dir_path in self.RESOURCE_DIRS:
            full_path = self.source_dir / dir_path
            if full_path.exists() and full_path.is_dir():
                available.append(dir_path)
        return available
    
    def random_select_dirs(self, available_dirs: List[str]) -> List[str]:
        """
        随机选择目录（随机选择1或2个）
        
        Args:
            available_dirs: 可用的目录列表
            
        Returns:
            选中的目录列表
        """
        if not available_dirs:
            return []
        
        # 随机选择1或2个目录
        count = random.choice([1, 2])
        
        # 如果可用目录数量少于请求数量，返回所有可用目录
        if count >= len(available_dirs):
            return available_dirs
        
        # 随机选择指定数量的目录
        return random.sample(available_dirs, count)
    
    def get_combination_key(self, dirs: List[str]) -> tuple:
        """
        获取目录组合的唯一标识（排序后的元组）
        
        Args:
            dirs: 目录列表
            
        Returns:
            排序后的目录元组
        """
        return tuple(sorted(dirs))
    
    def format_dir_name_for_filename(self, dir_path: str) -> str:
        """
        将目录路径格式化为文件名友好的格式
        
        Args:
            dir_path: 目录路径，如 'cmn/wakeup' 或 'fuzzy_res'
            
        Returns:
            格式化后的名称，如 'cmn-wakeup' 或 'fuzzy-res'
        """
        return dir_path.replace('/', '_')
    
    def copy_dirs_to_target(self, selected_dirs: List[str], target_dir: Path):
        """
        将选中的目录复制到目标目录，保留目录结构
        
        Args:
            selected_dirs: 选中的目录列表（相对路径）
            target_dir: 目标目录
        """
        target_dir.mkdir(parents=True, exist_ok=True)
        
        for dir_path in selected_dirs:
            source_path = self.source_dir / dir_path
            target_path = target_dir / dir_path
            
            if source_path.exists():
                # 复制整个目录树
                shutil.copytree(source_path, target_path, dirs_exist_ok=True)
    
    def get_all_files(self, directory: Path) -> List[Path]:
        """
        获取目录下所有文件的列表
        
        Args:
            directory: 目录路径
            
        Returns:
            文件路径列表
        """
        files = []
        for root, dirs, filenames in os.walk(directory):
            for filename in filenames:
                files.append(Path(root) / filename)
        return files
    
    def corrupt_file(self, file_path: Path, operation: str) -> bool:
        """
        损坏文件
        
        Args:
            file_path: 文件路径
            operation: 损坏操作类型
            
        Returns:
            是否成功损坏
        """
        try:
            # 读取文件内容
            with open(file_path, 'rb') as f:
                content = f.read()
            
            # 根据操作类型修改内容
            if operation == 'prepend':
                # 开头追加"123456789"
                new_content = self.CORRUPT_MARKER + content
            elif operation == 'append':
                # 末尾追加"123456789"
                new_content = content + self.CORRUPT_MARKER
            elif operation == 'remove_head':
                # 开头删除10个字节
                if len(content) > 10:
                    new_content = content[10:]
                else:
                    new_content = b""  # 如果文件小于10字节，清空
            elif operation == 'remove_tail':
                # 末尾删除10个字节
                if len(content) > 10:
                    new_content = content[:-10]
                else:
                    new_content = b""  # 如果文件小于10字节，清空
            elif operation == 'insert_middle':
                # 文件中间插入"123456789"
                if len(content) > 0:
                    middle_pos = len(content) // 2
                    new_content = content[:middle_pos] + self.CORRUPT_MARKER + content[middle_pos:]
                else:
                    new_content = self.CORRUPT_MARKER
            else:
                return False
            
            # 写回文件
            with open(file_path, 'wb') as f:
                f.write(new_content)
            
            return True
        except Exception as e:
            print(f"损坏文件失败 {file_path}: {e}")
            return False
    
    def corrupt_random_files(self, directory: Path, corrupt_ratio: float = 0.3) -> List[Dict]:
        """
        随机损坏目录中的部分文件
        
        Args:
            directory: 目录路径
            corrupt_ratio: 损坏文件的比例（0-1之间）
            
        Returns:
            损坏文件记录列表，每个记录包含文件路径和损坏操作
        """
        all_files = self.get_all_files(directory)
        if not all_files:
            return []
        
        # 计算需要损坏的文件数量
        corrupt_count = max(1, int(len(all_files) * corrupt_ratio))
        corrupt_count = min(corrupt_count, len(all_files))
        
        # 随机选择要损坏的文件
        files_to_corrupt = random.sample(all_files, corrupt_count)
        
        corrupted_records = []
        for file_path in files_to_corrupt:
            # 随机选择损坏操作
            operation = random.choice(self.CORRUPT_OPERATIONS)
            
            # 执行损坏操作
            if self.corrupt_file(file_path, operation):
                # 记录相对路径
                rel_path = file_path.relative_to(directory)
                corrupted_records.append({
                    'file': str(rel_path),
                    'operation': operation,
                    'description': self.CORRUPT_DESCRIPTIONS.get(operation, operation)
                })
        
        return corrupted_records
    
    def create_zip(self, source_dir: Path, zip_path: Path, root_name: str = "speech_engine"):
        """
        创建zip压缩包
        
        Args:
            source_dir: 源目录
            zip_path: 目标zip文件路径
            root_name: zip包内的根目录名
        """
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(source_dir):
                for file in files:
                    file_path = Path(root) / file
                    # 计算zip包内的相对路径
                    rel_path = file_path.relative_to(source_dir)
                    # 如果指定了根目录名，添加到路径前面
                    if root_name:
                        arcname = f"{root_name}/{rel_path}"
                    else:
                        arcname = str(rel_path)
                    zipf.write(file_path, arcname)
    
    def create_vdata_zip(self, speech_engine_zip: Path, vdata_zip_path: Path, description: str):
        """
        创建vdata_xxx.zip压缩包，包含lcs.zip和speech_engine.zip
        
        Args:
            speech_engine_zip: speech_engine.zip文件路径
            vdata_zip_path: 目标vdata_xxx.zip文件路径
            description: 压缩包描述（用于文件名）
        """
        with zipfile.ZipFile(vdata_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # 添加lcs.zip
            zipf.write(self.lcs_zip, 'lcs.zip')
            # 添加speech_engine.zip
            zipf.write(speech_engine_zip, 'speech_engine.zip')
    
    def generate_package(self, is_corrupt: bool = False, corrupt_ratio: float = 0.3) -> Optional[Dict]:
        """
        生成一个更新包
        
        Args:
            is_corrupt: 是否为损坏case
            corrupt_ratio: 损坏文件的比例（仅对损坏case有效）
            
        Returns:
            包信息字典，如果组合已存在则返回None
        """
        # 获取可用目录
        available_dirs = self.get_available_dirs()
        if not available_dirs:
            raise ValueError("源目录中没有找到任何可用的资源目录")
        
        # 随机选择目录（1或2个）
        selected_dirs = self.random_select_dirs(available_dirs)
        
        # 检查组合是否已生成过
        combination_key = self.get_combination_key(selected_dirs)
        if combination_key in self.generated_combinations:
            return None  # 组合已存在，跳过
        
        # 标记组合已生成
        self.generated_combinations.add(combination_key)
        
        # 创建临时工作目录
        temp_dir = self.output_dir / f"temp_{random.randint(10000, 99999)}"
        speech_engine_dir = temp_dir / "speech_engine"
        
        try:
            # 复制选中的目录
            self.copy_dirs_to_target(selected_dirs, speech_engine_dir)
            
            # 记录损坏的文件（如果是损坏case）
            corrupted_files = []
            if is_corrupt:
                corrupted_files = self.corrupt_random_files(speech_engine_dir, corrupt_ratio)
            
            # 创建speech_engine.zip
            speech_engine_zip = temp_dir / "speech_engine.zip"
            self.create_zip(speech_engine_dir, speech_engine_zip, root_name="speech_engine")
            
            # 生成目录组合名称（用于文件名）
            dir_names = [self.format_dir_name_for_filename(d) for d in sorted(selected_dirs)]
            dirs_str = '_'.join(dir_names)
            
            # 生成损坏类型标识
            corrupt_type = "反向" if is_corrupt else "正向"
            
            # 生成vdata文件名
            vdata_zip_name = f"vdata_{dirs_str}_{corrupt_type}.zip"
            vdata_zip_path = self.output_dir / vdata_zip_name
            
            # 检查文件是否已存在（避免覆盖）
            if vdata_zip_path.exists():
                # 如果文件已存在，添加序号
                counter = 1
                while vdata_zip_path.exists():
                    vdata_zip_name = f"vdata_{dirs_str}_{corrupt_type}_{counter}.zip"
                    vdata_zip_path = self.output_dir / vdata_zip_name
                    counter += 1
            
            # 生成描述信息（用于记录）
            if is_corrupt:
                description = f"损坏Case_包含{len(selected_dirs)}个目录_损坏{len(corrupted_files)}个文件"
            else:
                description = f"正向Case_包含{len(selected_dirs)}个目录"
            
            # 创建vdata_xxx.zip
            self.create_vdata_zip(speech_engine_zip, vdata_zip_path, description)
            
            # 记录包信息
            package_info = {
                'timestamp': datetime.now().isoformat(),
                'type': 'corrupt' if is_corrupt else 'normal',
                'vdata_zip': str(vdata_zip_path.name),
                'selected_dirs': selected_dirs,
                'corrupted_files': corrupted_files,
                'description': description
            }
            
            return package_info
            
        finally:
            # 清理临时目录
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
    
    def generate_batch(self, count: int, corrupt_ratio: float = 0.5):
        """
        批量生成更新包
        
        Args:
            count: 生成数量
            corrupt_ratio: 损坏case的比例（0-1之间）
        """
        print(f"开始生成 {count} 个FOTA差量更新包...")
        print(f"每个包随机选择1或2个文件夹")
        print(f"损坏case比例: {corrupt_ratio * 100:.1f}%")
        print(f"源目录: {self.source_dir}")
        print(f"输出目录: {self.output_dir}")
        print("-" * 60)
        
        generated_count = 0
        skipped_count = 0
        max_attempts = count * 10   # 最大尝试次数，避免无限循环
        attempts = 0
        
        while generated_count < count and attempts < max_attempts:
            attempts += 1
            
            # 决定是正向还是损坏case
            is_corrupt = random.random() < corrupt_ratio
            
            try:
                package_info = self.generate_package(is_corrupt=is_corrupt)
                
                if package_info is None:
                    # 组合已存在，跳过
                    skipped_count += 1
                    if skipped_count % 10 == 0:
                        print(f"[跳过重复组合] 已跳过 {skipped_count} 个重复组合...")
                    continue
                
                # 成功生成
                generated_count += 1
                self.records.append(package_info)
                
                # 显示目录组合
                dirs_str = '_'.join([self.format_dir_name_for_filename(d) for d in sorted(package_info['selected_dirs'])])
                print(f"[{generated_count}/{count}] 生成{'损坏' if is_corrupt else '正向'}case: {dirs_str} -> {package_info['vdata_zip']}")
                
            except Exception as e:
                print(f"生成失败: {e}")
        
        if attempts >= max_attempts:
            print(f"\n警告: 达到最大尝试次数 {max_attempts}，实际生成 {generated_count} 个包")
        
        if skipped_count > 0:
            print(f"\n跳过重复组合: {skipped_count} 个")
        
        # 保存记录
        self.save_records()
        
        print("-" * 60)
        print(f"生成完成！共生成 {len(self.records)} 个压缩包")
        print(f"JSON记录文件: {self.record_file}")
        print(f"TXT记录文件: {self.vdata_record_file}")
    
    def save_records(self):
        """保存记录到JSON文件和TXT文件"""
        # 保存JSON格式记录
        with open(self.record_file, 'w', encoding='utf-8') as f:
            json.dump(self.records, f, ensure_ascii=False, indent=2)
        
        # 保存TXT格式记录（vdata_record.txt）
        with open(self.vdata_record_file, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("FOTA差量更新包生成记录\n")
            f.write("=" * 80 + "\n")
            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"总数量: {len(self.records)}\n\n")
            
            for i, record in enumerate(self.records, 1):
                f.write("-" * 80 + "\n")
                f.write(f"包 #{i}: {record['vdata_zip']}\n")
                f.write(f"类型: {'反向' if record['type'] == 'corrupt' else '正向'}\n")
                f.write(f"生成时间: {record['timestamp']}\n")
                
                # 显示目录组合（格式与文件名一致）
                dir_names = [self.format_dir_name_for_filename(d) for d in sorted(record['selected_dirs'])]
                dirs_str = '_'.join(dir_names)
                f.write(f"目录组合: {dirs_str}\n")
                f.write(f"选择的目录 ({len(record['selected_dirs'])}个):\n")
                for dir_path in sorted(record['selected_dirs']):
                    f.write(f"  - {dir_path}\n")
                
                if record['type'] == 'corrupt' and record['corrupted_files']:
                    f.write(f"\n损坏的文件 ({len(record['corrupted_files'])}个):\n")
                    for corrupt_info in record['corrupted_files']:
                        f.write(f"  - 文件: {corrupt_info['file']}\n")
                        f.write(f"    损坏类型: {corrupt_info.get('description', corrupt_info['operation'])}\n")
                        f.write(f"    操作: {corrupt_info['operation']}\n")
                elif record['type'] == 'corrupt':
                    f.write("\n警告: 标记为损坏Case但未损坏任何文件\n")
                
                f.write("\n")
            
            f.write("=" * 80 + "\n")
            f.write("记录结束\n")
            f.write("=" * 80 + "\n")
    
    def print_summary(self):
        """打印生成摘要"""
        normal_count = sum(1 for r in self.records if r['type'] == 'normal')
        corrupt_count = sum(1 for r in self.records if r['type'] == 'corrupt')
        
        print("\n" + "=" * 60)
        print("生成摘要")
        print("=" * 60)
        print(f"总数量: {len(self.records)}")
        print(f"正向case: {normal_count}")
        print(f"损坏case: {corrupt_count}")
        print(f"JSON记录文件: {self.record_file}")
        print(f"TXT记录文件: {self.vdata_record_file}")
        print("=" * 60)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='FOTA差量更新包生成工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 fota_diff_package_generator.py \\
    /data1/NFS_DATA/TestAudio/FOTA/T2/nano/SpeechEngine \\
    /data1/NFS_DATA/TestAudio/FOTA/T2/nano/lcs.zip \\
    /data1/NFS_DATA/TestAudio/FOTA/T2/output \\
    --count 20 \\
    --corrupt-ratio 0.5
        """
    )
    
    parser.add_argument('source_dir', help='SpeechEngine源资源目录路径')
    parser.add_argument('lcs_zip', help='lcs.zip文件路径')
    parser.add_argument('output_dir', help='输出目录路径')
    parser.add_argument('--count', type=int, default=10, help='生成压缩包的数量（默认10）')
    parser.add_argument('--corrupt-ratio', type=float, default=0.5, 
                       help='损坏case的比例，0-1之间（默认0.5，即50%%）')
    
    args = parser.parse_args()
    
    # 验证参数
    if args.count < 1:
        print("错误: count必须大于0")
        sys.exit(1)
    
    if not 0 <= args.corrupt_ratio <= 1:
        print("错误: corrupt-ratio必须在0-1之间")
        sys.exit(1)
    
    try:
        # 创建生成器
        generator = FOTADiffPackageGenerator(
            source_dir=args.source_dir,
            lcs_zip=args.lcs_zip,
            output_dir=args.output_dir
        )
        
        # 批量生成
        generator.generate_batch(count=args.count, corrupt_ratio=args.corrupt_ratio)
        
        # 打印摘要
        generator.print_summary()
        
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

