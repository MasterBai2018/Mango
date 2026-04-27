#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2025/11/15 17:04
# @Author  : huidong.bai
# @File    : ConfigParser.py.py
# @Software: PyCharm
# @Mail    : MasterBai2018@outlook.com
"""配置文件解析器"""
import configparser
import os
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass


@dataclass
class JenkinsConfig:
    """Jenkins服务器配置"""
    name: str
    user: str
    password: str
    url: str


@dataclass
class ArtifactConfig:
    """Artifact配置"""
    name: str
    jenkins_name: str
    artifacts: List[str]


@dataclass
class ProjectConfig:
    """项目配置"""
    name: str
    lib_path: str
    dependencies: List[str]


class ConfigParser:
    """配置文件解析器"""

    def __init__(self, config_file: str = 'conf/jenkins.ini'):
        if not os.path.exists(config_file):
            raise FileNotFoundError(f"配置文件不存在: {config_file}")

        self.parser = configparser.ConfigParser(interpolation=None)
        self.parser.optionxform = str
        self.parser.read(config_file, encoding='utf-8')

        self._jenkins_configs: Dict[str, JenkinsConfig] = {}
        self._artifact_configs: Dict[str, ArtifactConfig] = {}
        self._project_configs: Dict[str, ProjectConfig] = {}

        self._parse_all_configs()
        self._validate_configs()

    def _parse_list_value(self, value: str) -> List[str]:
        """解析逗号分隔的列表值"""
        if not value:
            return []
        value = value.replace('\\\n', ' ').replace('\n', ' ')
        return [item.strip() for item in value.split(',') if item.strip()]

    def _parse_all_configs(self):
        """解析所有配置节"""
        for section_name in self.parser.sections():
            if section_name.startswith('jenkins:'):
                name = section_name.replace('jenkins:', '', 1)
                section = self.parser[section_name]
                self._jenkins_configs[name] = JenkinsConfig(
                    name=name,
                    user=section.get('user', '').strip(),
                    password=section.get('password', '').strip(),
                    url=section.get('url', '').strip()
                )

            elif section_name.startswith('artifact:'):
                name = section_name.replace('artifact:', '', 1)
                section = self.parser[section_name]
                self._artifact_configs[name] = ArtifactConfig(
                    name=name,
                    jenkins_name=section.get('jenkins', '').strip(),
                    artifacts=self._parse_list_value(section.get('artifacts', ''))
                )

            elif section_name.startswith('project:'):
                name = section_name.replace('project:', '', 1)
                section = self.parser[section_name]
                self._project_configs[name] = ProjectConfig(
                    name=name,
                    lib_path=section.get('lib_path', '').strip(),
                    dependencies=self._parse_list_value(section.get('dependencies', ''))
                )

    def _validate_configs(self):
        """验证配置完整性"""
        errors = []
        for name, cfg in self._artifact_configs.items():
            if cfg.jenkins_name not in self._jenkins_configs:
                errors.append(f"Artifact [{name}] 引用的Jenkins [{cfg.jenkins_name}] 不存在")

        for name, cfg in self._project_configs.items():
            for dep in cfg.dependencies:
                if dep not in self._artifact_configs:
                    errors.append(f"Project [{name}] 引用的Artifact [{dep}] 不存在")

        if errors:
            raise ValueError("配置验证失败:\n" + "\n".join(f"  - {e}" for e in errors))

    # Jenkins配置访问
    def get_jenkins_config(self, name: str) -> Optional[JenkinsConfig]:
        return self._jenkins_configs.get(name)

    def has_jenkins(self, name: str) -> bool:
        return name in self._jenkins_configs

    # Artifact配置访问
    def get_artifact_config(self, name: str) -> Optional[ArtifactConfig]:
        return self._artifact_configs.get(name)

    # Project配置访问
    def get_project_config(self, name: str) -> Optional[ProjectConfig]:
        return self._project_configs.get(name)

    def has_project(self, name: str) -> bool:
        return name in self._project_configs

    def get_all_project_names(self) -> List[str]:
        """获取所有项目名称列表"""
        return list(self._project_configs.keys())

    def get_project_lib_path(self, name: str) -> Optional[str]:
        cfg = self.get_project_config(name)
        return cfg.lib_path if cfg else None

    # 依赖关系解析
    def get_project_dependencies(self, project_name: str) -> List[ArtifactConfig]:
        """获取项目依赖的所有Artifact配置"""
        project = self.get_project_config(project_name)
        if not project:
            raise ValueError(f"项目配置不存在: {project_name}")
        return [self._artifact_configs[dep] for dep in project.dependencies if dep in self._artifact_configs]

    # 通用配置访问
    def get_config_value(self, section: str, key: str, default=None):
        """获取配置值"""
        try:
            return self.parser.get(section, key) if self.parser.has_section(section) else default
        except:
            return default

    def get_config_int(self, section: str, key: str, default=None):
        """获取整数配置值"""
        try:
            return int(self.get_config_value(section, key))
        except:
            return default

    def get_config_section(self, section: str) -> Optional[Dict[str, str]]:
        """获取整个配置节"""
        return dict(self.parser.items(section)) if self.parser.has_section(section) else None
