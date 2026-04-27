#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2023/5/24 11:38
# @Author  : wangjiamin
# @File    : MangoDownload.py
# @Software: PyCharm
# @Mail    : wangjiamin@pachira.com
import os
import socket
import ftplib
from enum import Enum
import re
import shutil
from tqdm import tqdm
from src.utils.common import mango_config


class FileType(Enum):
    CONFIG = 0
    CASE = 1


class PathType(Enum):
    ABSOLUTE = 0
    RELATIVE = 1


class MyFTP:
    def __init__(self):
        self.file_list = None
        self.host = mango_config.get_config_value('FTPServer', 'host')
        self.port = int(mango_config.get_config_value('FTPServer', 'port'))
        self.user = mango_config.get_config_value('FTPServer', 'username')
        self.pwd = mango_config.get_config_value('FTPServer', 'passwd')
        self.remote_dir = mango_config.get_config_value('FTPServer', 'remote_dir')
        self.ftp = ftplib.FTP()
        self.ftp.encoding = "utf-8"

    def __enter__(self):
        self.login()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.ftp:
            try:
                self.ftp.quit()
            except Exception as e:
                print(f"关闭FTP连接时出错: {e}")
            finally:
                self.ftp.close()

    def login(self):
        try:
            timeout = 10000
            socket.setdefaulttimeout(timeout)
            self.ftp.set_pasv(True)
            self.ftp.connect(self.host, self.port)
            self.ftp.login(self.user, self.pwd)
            self.ftp.cwd(self.remote_dir)
            print(f'✅ 成功连接到: {self.host}:{self.remote_dir}')
        except Exception as e:
            print(f'❌ 连接或登录失败: {e}')
            raise

    @staticmethod
    def is_audio_file(file_path):
        """
        判断文件是否是音频文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            bool: 如果是音频文件返回True，否则返回False
        """
        audio_extensions = {'.wav', '.pcm', '.opus'}
        _, ext = os.path.splitext(file_path.lower())
        return ext in audio_extensions

    def get_remote_file_size(self, remote_file):
        """
        获取远程文件大小
        
        Args:
            remote_file: 远程文件路径
            
        Returns:
            int: 文件大小（字节），如果文件不存在返回-1
        """
        try:
            return self.ftp.size(remote_file)
        except Exception:
            # 文件不存在或其它FTP错误
            return -1

    def is_same_size(self, local_file, remote_file):
        try:
            remote_file_size = self.ftp.size(remote_file)
        except Exception as e:
            # 文件不存在或其它FTP错误
            remote_file_size = -1
        try:
            local_file_size = os.path.getsize(local_file)
        except Exception as e:
            # 本地文件不存在
            local_file_size = -1

        return remote_file_size == local_file_size

    def download_file(self, local_file, remote_file, pathType, file_type, progress_callback=None, progress_bar=None):
        filepath = None
        local_dir = os.path.dirname(local_file)
        if not os.path.isdir(local_dir):
            os.makedirs(local_dir)
        if pathType.value == 0:
            filepath = remote_file
        elif pathType.value == 1:
            filepath = os.path.join(local_dir, remote_file)

        # 如果是音频文件，进行特殊处理
        if self.is_audio_file(local_file):
            # 获取文件名用于显示
            filename = os.path.basename(local_file)
            
            # 检查本地文件是否存在
            if not os.path.exists(local_file):
                # 本地文件不存在，直接下载
                try:
                    # 先检查云端文件是否存在
                    remote_file_size = self.get_remote_file_size(remote_file)
                    if remote_file_size == -1:
                        # 云端文件不存在，不处理
                        if progress_bar:
                            progress_bar.set_postfix_str(f"{filename}: ⚠️ 云端不存在")
                        if progress_callback:
                            progress_callback(1)
                        return
                    # 云端文件存在，执行下载
                    if progress_bar:
                        progress_bar.set_postfix_str(f"{filename}: ⬇️ 下载中...")
                    with open(local_file, 'wb') as file_handler:
                        self.ftp.retrbinary('RETR %s' % remote_file, file_handler.write)
                    if progress_bar:
                        progress_bar.set_postfix_str(f"{filename}: ✅ 更新成功")
                    if progress_callback:
                        progress_callback(1)
                    return
                except Exception as e:
                    if progress_bar:
                        progress_bar.set_postfix_str(f"{filename}: ❌ 下载失败")
                    print(f">>>>>>>>>>文件[{filepath}]下载失败:{e}")
                    raise
            else:
                # 本地文件存在，比较大小
                try:
                    remote_file_size = self.get_remote_file_size(remote_file)
                    if remote_file_size == -1:
                        # 云端文件不存在，不处理
                        if progress_bar:
                            progress_bar.set_postfix_str(f"{filename}: ⚠️ 云端不存在")
                        if progress_callback:
                            progress_callback(1)
                        return
                    
                    local_file_size = os.path.getsize(local_file)
                    if remote_file_size == local_file_size:
                        # 大小相等，不下载
                        if progress_bar:
                            progress_bar.set_postfix_str(f"{filename}: ⏭️ 不更新（端云相等）")
                        if progress_callback:
                            progress_callback(1)
                        return
                    else:
                        # 大小不等，执行下载
                        if progress_bar:
                            progress_bar.set_postfix_str(f"{filename}: ⬇️ 下载中...")
                        with open(local_file, 'wb') as file_handler:
                            self.ftp.retrbinary('RETR %s' % remote_file, file_handler.write)
                        if progress_bar:
                            progress_bar.set_postfix_str(f"{filename}: ✅ 更新成功（端云不一致）")
                        if progress_callback:
                            progress_callback(1)
                        return
                except Exception as e:
                    if progress_bar:
                        progress_bar.set_postfix_str(f"{filename}: ❌ 下载失败")
                    print(f">>>>>>>>>>文件[{filepath}]下载失败:{e}")
                    raise

        # 非音频文件，使用原有逻辑
        if self.is_same_size(local_file, remote_file):
            if progress_callback:
                progress_callback(1)
            return
        else:
            try:
                with open(local_file, 'wb') as file_handler:
                    self.ftp.retrbinary('RETR %s' % remote_file, file_handler.write)
                if progress_callback:
                    progress_callback(1)
            except Exception as e:
                print(f">>>>>>>>>>文件[{filepath}]下载失败:{e}")
                raise  # 抛出异常

    def download_dir(self, local_dir, remote_dir, file_type, progress_callback=None, progress_bar=None):
        original_dir = self.ftp.pwd()
        try:
            self.ftp.cwd(remote_dir)
        except (IOError, ftplib.error_perm) as e:
            raise IOError(f"无法将 '{remote_dir}' 作为目录访问") from e

        try:
            if not os.path.isdir(local_dir):
                os.makedirs(local_dir)

            self.file_list = []
            self.ftp.dir(self.get_file_list)
            remote_names = self.file_list

            for item in remote_names:
                filetype = item[0]
                filename = item[1]
                local = os.path.join(local_dir, filename)
                if filetype == 'd':
                    self.download_dir(local, filename, file_type, progress_callback, progress_bar)
                elif filetype == '-':
                    self.download_file(local, filename, PathType.RELATIVE, file_type, progress_callback, progress_bar)
                elif filetype == 'l':
                    symlink_target = item[2] if len(item) > 2 else None
                    self.handle_symlink(local, filename, symlink_target, file_type, progress_callback, progress_bar)
        finally:
            try:
                self.ftp.cwd(original_dir)
            except Exception as e:
                print(f"警告: 无法返回到原始目录 '{original_dir}': {e}")


    def count_files(self, path):
        """递归统计FTP路径下的文件数量"""
        original_dir = self.ftp.pwd()
        try:
            self.ftp.cwd(path)
        except Exception:
            # 如果路径是文件，cwd会失败，我们将其计为1个文件
            try:
                self.ftp.size(path)
                return 1
            except Exception:
                return 0

        count = 0
        self.file_list = []
        self.ftp.dir(self.get_file_list)
        items = self.file_list

        for item_type, name, *target in items:
            if item_type == '-':
                count += 1
            elif item_type == 'd':
                count += self.count_files(name)
            elif item_type == 'l':
                # 软链接处理较为复杂，这里假设它指向的目标也会被正确处理
                # 一个简化的处理方式是尝试解析它
                if target:
                    resolved_target = self.resolve_symlink_path(self.ftp.pwd(), target[0])
                    if resolved_target:
                        count += self.count_files(resolved_target)

        try:
            self.ftp.cwd(original_dir)
        except Exception:
            pass
        return count


    def get_file_list(self, line):
        file_arr = self.get_file_name(line)
        if file_arr[1] not in ['.', '..']:
            self.file_list.append(file_arr)

    def resolve_symlink_path(self, current_ftp_dir, symlink_target):
        if symlink_target.startswith('/'):
            # 如果是绝对路径，尝试从配置的FTP根目录开始解析
            if symlink_target.startswith(self.remote_dir):
                return os.path.relpath(symlink_target, self.remote_dir)
            else:
                return symlink_target  # 可能是权限范围之外的绝对路径
        else:
            import posixpath
            resolved = posixpath.normpath(posixpath.join(current_ftp_dir, symlink_target))
            # 确保解析后的路径仍在FTP根目录下
            if not resolved.startswith(self.remote_dir):
                 # 尝试从当前目录角度处理
                 return posixpath.normpath(symlink_target)
            return os.path.relpath(resolved, self.remote_dir)

    def handle_symlink(self, local_path, remote_name, symlink_target, file_type, progress_callback=None, progress_bar=None):
        print(f"检测到软链接: {remote_name} -> {symlink_target}")

        if not symlink_target:
            print(f"无法解析软链接目标: {remote_name}")
            return

        current_ftp_dir = self.ftp.pwd()
        # 软链接的目标可能是绝对路径或相对路径
        is_absolute = symlink_target.startswith('/')
        target_path = symlink_target if is_absolute else remote_name

        try:
            # 尝试判断目标是目录还是文件
            self.ftp.cwd(target_path)
            self.ftp.cwd(current_ftp_dir)  # 返回原目录
            print(f"软链接 {remote_name} 指向目录: {symlink_target}")
            self.download_dir(local_path, target_path, file_type, progress_callback, progress_bar)
        except ftplib.error_perm:
            # 不是目录，尝试作为文件下载
            try:
                print(f"尝试作为文件下载软链接: {symlink_target}")
                local_file_dir = os.path.dirname(local_path)
                if not os.path.exists(local_file_dir):
                    os.makedirs(local_file_dir)
                self.download_file(local_path, target_path, PathType.ABSOLUTE, file_type, progress_callback, progress_bar)
            except Exception as file_error:
                print(f"软链接 {remote_name} 作为文件下载失败: {file_error}")
        except Exception as dir_error:
            print(f"处理软链接 {remote_name} 时发生未知错误: {dir_error}")


    @staticmethod
    def get_file_name(line):
        if line[0] == 'l':
            arrow_pos = line.find(' -> ')
            if arrow_pos != -1:
                pos = line.rfind(' ', 0, arrow_pos)
                while line[pos] != ' ':
                    pos += 1
                while line[pos] == ' ':
                    pos += 1
                filename = line[pos:arrow_pos]
                target = line[arrow_pos + 4:]
                return [line[0], filename, target]

        pos = line.rfind(' ')
        while line[pos] != ' ':
            pos += 1
        while line[pos] == ' ':
            pos += 1
        file_arr = [line[0], line[pos:]]
        return file_arr


class FTPDownloader:
    """FTP资源下载器，负责收集、解析和下载FTP资源"""

    def __init__(self):
        self.ftp_manager = MyFTP()
        # 存储需要解析的文件：{(文件路径, 文件类型)}
        self.files_to_parse = set()
        # 存储需要下载的资源路径: {资源路径: 文件类型}
        self.resources_to_download = {}
        # 存储已下载的资源路径，避免重复下载
        self.downloaded_paths = set()

    def add_download_file(self, path, file_type):
        """
        添加需要下载的文件到解析列表
        
        Args:
            path: 需要下载的文件列表路径（配置文件或caselist）
            file_type: 文件类型（FileType.CONFIG 或 FileType.CASE）
        """
        # 检查路径是否有效
        if path is None or path == "":
            return
        
        # 检查文件是否存在
        if not os.path.exists(path):
            print(f"⚠️ 警告：文件 [{path}] 不存在，可能无法下载相关资源")
            return
        
        # 添加到待解析集合（使用set自动去重）
        file_tuple = (path, file_type)
        if file_tuple not in self.files_to_parse:
            self.files_to_parse.add(file_tuple)
            print(f"✅ 已添加待解析文件: {path} (类型: {file_type.name})")
        else:
            print(f"ℹ️ 文件已存在于解析列表中: {path}")

    def _parse_download_files(self):
        """
        解析所有收集到的文件，提取需要下载的资源路径
        """
        if not self.files_to_parse:
            print("⚠️ 没有需要解析的文件")
            return
        
        for file_path, file_type in self.files_to_parse:
            if file_type == FileType.CONFIG:
                self._parse_config_file(file_path)
            elif file_type == FileType.CASE:
                self._parse_case_list_file(file_path)
        
        print(f"✅ 解析完成，共找到 {len(self.resources_to_download)} 个需要下载的资源")

    def _parse_config_file(self, config_path):
        """
        解析配置文件，提取包含FTP_RES的路径
        
        Args:
            config_path: 配置文件路径
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as fp:
                lines = fp.readlines()
            
            for line in lines:
                if "FTP_RES" in line:
                    # 解析FTP_RES路径
                    new_line = line.split('=')[1].strip().replace('"', '').replace("'", '')
                    res_path = re.split(r'[,; \'\"#]', new_line)[0]
                    if res_path:
                        self.resources_to_download[res_path] = FileType.CONFIG

        except IOError as e:
            print(f"❌ 读取配置文件 [{config_path}] 失败: {e}")
        except Exception as e:
            print(f"❌ 解析配置文件 [{config_path}] 时发生错误: {e}")

    def _parse_case_list_file(self, case_list_path):
        """
        解析caselist文件，提取voice路径
        
        Args:
            case_list_path: caselist文件路径
        """
        try:
            with open(case_list_path, 'r', encoding='utf-8') as fp:
                lines = fp.readlines()
            
            voice_format = None
            for line in lines:
                # 解析VOICE_PATH格式定义
                if "@VOICE_PATH" in line:
                    voice_format = line.replace("@VOICE_PATH:", "").strip()
                
                # 跳过空行和注释行
                if line.isspace() or line.startswith("#") or line.startswith("//"):
                    continue
                
                voice_path = None
                
                # 方案1: 尝试匹配旧格式 voice:路径\t
                match = re.search(r'voice:(.*?)\t', line)
                if match:
                    voice_path = match.group(1).split(";")[0]
                else:
                    # 方案2: 兼容新格式 - 在整行中搜索包含FTP_RES的路径
                    # 新格式: 路径可能在任意列（第一列、中间列或最后一列）
                    # 使用正则匹配包含FTP_RES的路径（路径由非空白字符组成，可能包含斜杠、点等）
                    match_new = re.search(r'([^\s\t]*FTP_RES[^\s\t]*)', line)
                    if match_new:
                        voice_path = match_new.group(1)
                
                if voice_path:
                    # 替换VOICE_PATH占位符
                    if voice_format and "VOICE_PATH" in voice_path:
                        voice_path = voice_path.replace("VOICE_PATH", voice_format)
                    # 只下载FTP资源
                    if "FTP_RES" in voice_path:
                        self.resources_to_download[voice_path] = FileType.CASE
        
        except IOError as e:
            print(f"❌ 读取Case List [{case_list_path}] 失败: {e}")
        except Exception as e:
            print(f"❌ 解析Case List [{case_list_path}] 时发生错误: {e}")

    def start_download(self):
        """
        开始下载所有解析出的资源
        """
        # 先解析所有文件
        self._parse_download_files()
        
        # 如果没有需要下载的资源，直接返回
        if not self.resources_to_download:
            print("ℹ️ 没有需要下载的资源")
            return

        try:
            with self.ftp_manager as ftp:
                # 分类资源：case单文件 vs 其他资源
                case_single_files = []
                other_resources = []
                
                for res_path, file_type in self.resources_to_download.items():
                    if file_type == FileType.CASE:
                        # 检查是否是单个文件
                        try:
                            ftp.ftp.cwd(ftp.remote_dir)
                            total_files = ftp.count_files(res_path)
                            if total_files == 1:
                                case_single_files.append(res_path)
                            else:
                                other_resources.append(res_path)
                        except:
                            other_resources.append(res_path)
                    else:
                        other_resources.append(res_path)
                
                # 统一下载case单文件
                if case_single_files:
                    with tqdm(total=len(case_single_files), unit='file', desc=f"📥 下载Case音频文件") as pbar:
                        for res_path in case_single_files:
                            self._download_resource(ftp, res_path, progress_bar=pbar)
                
                # 下载其他资源（保持原有进度条显示）
                for res_path in other_resources:
                    self._download_resource(ftp, res_path, progress_bar=None)
                    
            print("\n✅ 所有资源下载完成！")
        except ftplib.all_errors as e:
            print(f"❌ FTP操作失败: {e}")
        except Exception as e:
            print(f"❌ 下载过程中发生未知错误: {e}")

    def _download_resource(self, ftp, res_path, progress_bar=None):
        """
        下载单个资源（文件或目录）
        
        Args:
            ftp: MyFTP实例
            res_path: 资源路径
            progress_bar: 可选的外部进度条，如果提供则使用，否则创建新进度条
        """
        # 检查是否已下载
        if res_path in self.downloaded_paths:
            if progress_bar:
                progress_bar.update(1)
            else:
                print(f"ℹ️ 资源已下载，跳过: {res_path}")
            return
        
        self.downloaded_paths.add(res_path)
        
        # 确保在FTP根目录
        try:
            ftp.ftp.cwd(ftp.remote_dir)
        except Exception as e:
            print(f"❌ 无法切换到FTP根目录 '{ftp.remote_dir}': {e}")
            return
        
        # 如果本地已存在该目录，先清除
        if os.path.exists(res_path) and os.path.isdir(res_path):
            shutil.rmtree(res_path)
            if not progress_bar:
                print(f"🧹 清除本地历史资源: {res_path}")
        
        # 统计远程文件数量
        total_files = ftp.count_files(res_path)
        if total_files == 0:
            print(f"⚠️ 远程资源为空或不存在，跳过: {res_path}")
            return
        
        # 如果提供了外部进度条，使用它；否则创建新进度条
        if progress_bar:
            # 使用外部进度条，下载完成后更新
            try:
                ftp.download_file(res_path, res_path, PathType.ABSOLUTE, 
                                FileType.CONFIG, progress_callback=lambda x: progress_bar.update(x),
                                progress_bar=progress_bar)
            except Exception as e:
                print(f"❌ 下载 '{res_path}' 失败: {e}")
        else:
            # 创建独立的进度条
            try:
                with tqdm(total=total_files, unit='file', desc=f"📥 下载 {res_path}") as pbar:
                    ftp.download_dir(res_path, res_path, FileType.CONFIG, 
                                   progress_callback=pbar.update, progress_bar=pbar)
            except (IOError, ftplib.error_perm):
                # 如果作为目录失败，尝试作为单个文件下载
                try:
                    with tqdm(total=1, unit='file', desc=f"📥 下载 {res_path}") as pbar:
                        ftp.download_file(res_path, res_path, PathType.ABSOLUTE, 
                                        FileType.CONFIG, progress_callback=pbar.update,
                                        progress_bar=pbar)
                except Exception as file_e:
                    print(f"❌ 作为文件下载也失败了 '{res_path}': {file_e}")
            except Exception as e:
                print(f"❌ 下载 '{res_path}' 期间发生未知错误: {e}")


if __name__ == '__main__':
    # 使用示例
    downloader = FTPDownloader()
    # 1. 添加需要下载的配置文件
    downloader.add_download_file("decoder.conf", FileType.CONFIG)
    # 2. 添加需要下载的caselist文件
    downloader.add_download_file("caselist/test.list", FileType.CASE)
    # 3. 开始解析和下载所有资源
    downloader.start_download()