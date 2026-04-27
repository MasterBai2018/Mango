#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2025/1/XX
# @Author  : huidong.bai
# @File    : JenkinsDownloader.py
# @Software: PyCharm
# @Mail    : MasterBai2018@outlook.com
"""
Jenkins依赖下载器
支持根据项目依赖和构建号下载Jenkins artifact
"""
"""Jenkins依赖下载器"""
import os
import json
import subprocess
import fnmatch
import re
import shutil
import tarfile
from urllib.parse import urlparse
from typing import List, Dict, Tuple, Optional
from src.utils.ConfigParser import ConfigParser, JenkinsConfig, ArtifactConfig


class JenkinsDownloadError(Exception):
    """Jenkins下载异常"""
    pass


class JenkinsDownloader:
    """Jenkins依赖下载器"""

    def __init__(self, config_file: str = 'conf/mango.ini'):
        self.config_parser = ConfigParser(config_file)

    def _parse_build_numbers(self, build_spec: str, jenkins_count: int) -> List[Optional[int]]:
        """解析构建号字符串，返回构建号列表（None表示使用最新）"""
        if not build_spec:
            return [None] * jenkins_count

        parts = [p.strip() for p in build_spec.split('-')]
        if len(parts) != jenkins_count:
            raise ValueError(f"构建号数量不匹配: 需要{jenkins_count}个，提供了{len(parts)}个")

        return [None if p.lower() in ['new', 'latest'] else int(p) for p in parts]

    def _get_latest_build_number(self, jenkins_config: JenkinsConfig) -> int:
        """获取Jenkins最新成功构建号"""
        parsed = urlparse(jenkins_config.url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        job_path = self._get_job_path_from_url(jenkins_config.url)
        api_url = f"{base_url}/job/{job_path}/api/json?tree=lastSuccessfulBuild[number]"

        curl_cmd = ['curl', '-sS', '-f', '-g', '--user', f'{jenkins_config.user}:{jenkins_config.password}', api_url]

        try:
            result = subprocess.run(curl_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=30)
            data = json.loads(result.stdout)
            return data['lastSuccessfulBuild']['number']
        except Exception as e:
            raise JenkinsDownloadError(f"获取{jenkins_config.name}最新构建号失败: {e}")

    def _get_job_path_from_url(self, url: str) -> str:
        """从Jenkins URL中提取job路径（支持多级job）"""
        parsed = urlparse(url)
        path = parsed.path.rstrip('/')

        # 提取/job/之后的路径
        if '/job/' in path:
            job_start = path.find('/job/')
            job_path = path[job_start + 5:]
            return job_path.split('/')[0] if '/' not in job_path[1:] else job_path

        # 从view路径推断
        path_parts = [p for p in path.split('/') if p]
        if 'view' in path_parts:
            view_idx = path_parts.index('view')
            if view_idx + 2 < len(path_parts):
                return path_parts[view_idx + 2]

        return path_parts[-1] if path_parts else None

    def _get_build_artifacts(self, jenkins_config: JenkinsConfig, build_number: int) -> List[Dict]:
        """获取构建的artifact列表"""
        parsed = urlparse(jenkins_config.url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        job_path = self._get_job_path_from_url(jenkins_config.url)
        api_url = f"{base_url}/job/{job_path}/{build_number}/api/json?tree=artifacts[fileName,relativePath]"

        curl_cmd = ['curl', '-sS', '-f', '-g', '--user',
                    f'{jenkins_config.user}:{jenkins_config.password}', api_url]

        try:
            result = subprocess.run(curl_cmd, check=True, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, universal_newlines=True, timeout=30)
            return json.loads(result.stdout).get('artifacts', [])
        except Exception as e:
            raise JenkinsDownloadError(f"获取{jenkins_config.name}构建{build_number}的artifact列表失败: {e}")

    def _match_artifact_pattern(self, pattern: str, artifact_path: str, exclude_patterns: List[str] = None) -> bool:
        """匹配artifact路径是否匹配通配符模式"""
        if not re.match(fnmatch.translate(pattern), artifact_path):
            return False

        if exclude_patterns:
            for exclude_pattern in exclude_patterns:
                if re.match(fnmatch.translate(exclude_pattern), artifact_path):
                    return False
        return True

    def _resolve_artifact_paths(self, jenkins_config: JenkinsConfig, build_number: int,
                                artifact_pattern: str) -> List[str]:
        """解析artifact路径模式，返回匹配的实际路径列表"""
        # 无通配符直接返回
        if '*' not in artifact_pattern and '?' not in artifact_pattern:
            return [artifact_pattern]

        # 解析排除模式
        exclude_patterns = []
        if '|' in artifact_pattern:
            artifact_pattern, exclude_str = artifact_pattern.split('|', 1)
            artifact_pattern = artifact_pattern.strip()
            exclude_patterns = [p.strip() for p in exclude_str.split(',') if p.strip()]

        # 处理artifact/前缀
        pattern_has_prefix = artifact_pattern.startswith('artifact/')
        match_pattern = artifact_pattern[9:] if pattern_has_prefix else artifact_pattern

        # 获取并匹配artifact
        artifacts = self._get_build_artifacts(jenkins_config, build_number)
        matched_paths = []
        for artifact in artifacts:
            path = artifact.get('relativePath', '')
            if path and self._match_artifact_pattern(match_pattern, path, exclude_patterns):
                matched_paths.append(f"artifact/{path}" if pattern_has_prefix else path)

        return matched_paths

    def _build_artifact_url(self, jenkins_config: JenkinsConfig, build_number: int, artifact_path: str) -> str:
        """构建artifact下载URL
        
        根据artifact_path的前缀决定URL格式：
        - ws/开头：workspace路径，不拼接构建号
        - artifact/开头或其他：artifact路径，需要拼接构建号
        """
        parsed = urlparse(jenkins_config.url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        job_path = self._get_job_path_from_url(jenkins_config.url)
        
        # ws路径不需要拼接构建号
        if artifact_path.startswith('ws/'):
            return f"{base_url}/job/{job_path}/{artifact_path}"
        # artifact路径或其他路径需要拼接构建号
        else:
            return f"{base_url}/job/{job_path}/{build_number}/{artifact_path}"

    def _download_file(self, url: str, local_path: str, jenkins_config: JenkinsConfig) -> (bool, str):
        """下载单个文件"""
        os.makedirs(os.path.dirname(local_path), exist_ok=True)

        curl_cmd = ['curl', '-sS', '-f', '-L', '-g', '--user', f'{jenkins_config.user}:{jenkins_config.password}', '-o', local_path, url]

        try:
            subprocess.run(curl_cmd, check=True, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, universal_newlines=True, timeout=300)
            return True, "Success"
        except subprocess.TimeoutExpired:
            return False, f"下载超时: {url}"
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else str(e)
            return False, error_msg

    def _download_artifacts_for_jenkins(self, jenkins_config: JenkinsConfig, build_number: int,
                                        artifact_configs: List[ArtifactConfig],
                                        project_lib_path: str) -> Tuple[int, int]:
        """下载指定Jenkins的所有artifact"""
        success_count = 0
        total_count = 0

        for artifact_config in artifact_configs:
            for artifact_pattern in artifact_config.artifacts:
                try:
                    resolved_paths = self._resolve_artifact_paths(jenkins_config, build_number, artifact_pattern)
                except Exception as e:
                    print(f"  解析artifact模式失败: {artifact_pattern}, 错误: {e}")
                    continue

                if not resolved_paths:
                    print(f"  警告: 没有找到匹配的artifact: {artifact_pattern}")
                    continue

                for artifact_path in resolved_paths:
                    total_count += 1
                    artifact_url = self._build_artifact_url(jenkins_config, build_number, artifact_path)
                    artifact_filename = os.path.basename(artifact_path)
                    local_path = os.path.join(project_lib_path, artifact_filename)

                    result, message = self._download_file(artifact_url, local_path, jenkins_config)

                    if result:
                        print(f"✅下载成功: {artifact_url}")
                        success_count += 1
                        
                        # 如果下载的是.tar.gz文件，自动解压
                        if local_path.endswith('.tar.gz'):
                            try:
                                extract_dir = os.path.dirname(local_path)
                                with tarfile.open(local_path, 'r:gz') as tar:
                                    tar.extractall(path=extract_dir)
                                # 拷贝解压之后的文件夹中的某个文件到self.path中
                                shutil.copy(os.path.join(extract_dir, 'lcs/bin/LCSEngine'), extract_dir)
                                # 删除压缩包
                                os.remove(local_path)
                                shutil.rmtree(os.path.join(extract_dir, 'lcs'))
                                print(f"✅解压成功: {local_path}")
                            except Exception as e:
                                print(f"⚠️解压失败: {local_path}, 错误: {e}")
                    else:
                        print(f"❌下载失败: {artifact_url}: {message}")

        return success_count, total_count

    def run_jenkins_download(self, project_name: str, build_spec: str) -> bool:
        """执行Jenkins依赖下载"""
        # 获取项目配置
        if not self.config_parser.has_project(project_name):
            raise ValueError(f"项目配置不存在: {project_name}")

        project_config = self.config_parser.get_project_config(project_name)
        artifact_configs = self.config_parser.get_project_dependencies(project_name)

        if not artifact_configs:
            print(f"项目 {project_name} 没有配置依赖")
            return True

        # 构建Jenkins到artifact的映射（保持顺序）
        jenkins_order: List[str] = []
        jenkins_artifact_map: Dict[str, List[ArtifactConfig]] = {}

        for artifact_config in artifact_configs:
            jenkins_name = artifact_config.jenkins_name
            if jenkins_name not in jenkins_artifact_map:
                jenkins_artifact_map[jenkins_name] = []
                jenkins_order.append(jenkins_name)
            jenkins_artifact_map[jenkins_name].append(artifact_config)

        # 解析构建号
        build_numbers = self._parse_build_numbers(build_spec, len(jenkins_order))

        # 准备下载列表
        jenkins_builds: List[Tuple[JenkinsConfig, int, List[ArtifactConfig]]] = []
        for i, jenkins_name in enumerate(jenkins_order):
            jenkins_config = self.config_parser.get_jenkins_config(jenkins_name)
            if not jenkins_config:
                raise JenkinsDownloadError(f"Jenkins配置不存在: {jenkins_name}")

            build_number = build_numbers[i]
            if build_number is None:
                build_number = self._get_latest_build_number(jenkins_config)

            jenkins_builds.append((jenkins_config, build_number, jenkins_artifact_map[jenkins_name]))

        # 执行下载
        total_success = 0
        total_files = 0
        for jenkins_config, build_number, artifact_configs_for_jenkins in jenkins_builds:
            success, total = self._download_artifacts_for_jenkins(jenkins_config, build_number, artifact_configs_for_jenkins, project_config.lib_path)
            total_success += success
            total_files += total

        if total_success < total_files:
            print(f"warning: {total_files - total_success} files download failed!")
            return False

        print("download all files successfully!")
        return True


# 主程序入口
if __name__ == '__main__':
    try:
        downloader = JenkinsDownloader()
        downloader.run_jenkins_download('24mm', '1390-60')
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
