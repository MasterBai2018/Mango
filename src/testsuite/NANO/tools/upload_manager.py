#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2025/10/20
# @Author  : baihuidong
# @File    : upload_manager.py
# @Software: PyCharm
# @Mail    : MasterBai2018@outlook.com

import os
import re
import json
from typing import Any, Optional
from loguru import logger


class UploadManager:
    """文件重加载管理器 - 支持JSON、LINE、REPLACE、DELETE四种类型的文件内容更新"""

    @staticmethod
    def upload_json(file_path: str, field_path: str, new_value: Any) -> bool:
        """
        更新JSON文件的指定字段值
        
        Args:
            file_path: JSON文件路径
            field_path: 字段路径，支持嵌套路径和数组索引
                       例如: "data.text.start" 或 "data.[0].text.start"
            new_value: 新值，支持字符串、数字、布尔值等类型
        
        Returns:
            bool: 是否更新成功
        """
        try:
            if not os.path.exists(file_path):
                logger.error(f"JSON文件不存在: {file_path}")
                return False

            # 读取JSON文件
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 解析字段路径并更新值
            if not UploadManager._update_json_field(data, field_path, new_value):
                logger.error(f"更新JSON字段失败: {file_path}, 路径: {field_path}")
                return False

            # 写回文件
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                logger.info(f"JSON文件已写入: {file_path}")
            except Exception as e:
                logger.error(f"写入JSON文件失败: {file_path}, 错误: {e}")
                return False

            return True

        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {file_path}, 错误: {e}")
            return False
        except Exception as e:
            logger.error(f"更新JSON文件异常: {file_path}, 错误: {e}")
            return False

    @staticmethod
    def _update_json_field(data: dict, field_path: str, new_value: Any) -> bool:
        """
        递归更新JSON字段值
        
        Args:
            data: JSON数据对象
            field_path: 字段路径，例如: "data.text.start" 或 "data.[0].text.start"
            new_value: 新值
        
        Returns:
            bool: 是否更新成功
        """
        try:
            # 解析字段路径
            parts = UploadManager._parse_field_path(field_path)
            if not parts:
                return False

            # 遍历到目标字段的父节点
            current = data
            for i, part in enumerate(parts[:-1]):
                if isinstance(part, int):
                    # 数组索引
                    if not isinstance(current, list) or part >= len(current) or part < 0:
                        logger.error(f"数组索引越界: {field_path}, 索引: {part}, 数组长度: {len(current) if isinstance(current, list) else 'N/A'}")
                        return False
                    current = current[part]
                else:
                    # 对象键
                    if not isinstance(current, dict) or part not in current:
                        logger.error(f"字段不存在: {field_path}, 字段: {part}, 当前类型: {type(current).__name__}, 可用键: {list(current.keys()) if isinstance(current, dict) else 'N/A'}")
                        return False
                    current = current[part]

            # 更新最后一个字段的值
            last_part = parts[-1]
            old_value = None
            if isinstance(last_part, int):
                if not isinstance(current, list) or last_part >= len(current) or last_part < 0:
                    logger.error(f"数组索引越界: {field_path}, 索引: {last_part}, 数组长度: {len(current) if isinstance(current, list) else 'N/A'}")
                    return False
                old_value = current[last_part]
                converted_value = UploadManager._convert_value(new_value)
                current[last_part] = converted_value
                logger.info(f"更新数组元素: [{last_part}] = {converted_value} (原值: {old_value})")
            else:
                if not isinstance(current, dict):
                    logger.error(f"目标不是字典类型: {field_path}, 当前类型: {type(current).__name__}")
                    return False
                old_value = current.get(last_part)
                converted_value = UploadManager._convert_value(new_value)
                current[last_part] = converted_value
                logger.info(f"更新字段: {last_part} = {converted_value} (原值: {old_value})")

            return True

        except Exception as e:
            logger.error(f"更新JSON字段异常: {field_path}, 错误: {e}")
            return False

    @staticmethod
    def _parse_field_path(field_path: str) -> list:
        """
        解析字段路径，支持数组索引和对象键
        
        Args:
            field_path: 字段路径，例如: "data.text.start" 或 "data.[0].text.start" 或 "modules.[0].status"
        
        Returns:
            list: 解析后的路径列表，包含字符串键和整数索引
        """
        parts = []
        # 按点号分割，然后处理每个部分
        segments = field_path.split('.')
        
        for segment in segments:
            segment = segment.strip()
            if not segment:
                continue
                
            # 检查是否是数组索引格式 [数字]
            if segment.startswith('[') and segment.endswith(']'):
                try:
                    index = int(segment[1:-1])
                    parts.append(index)
                except ValueError:
                    logger.error(f"无效的数组索引: {segment}")
                    return []
            else:
                # 对象键（允许字母、数字、下划线）
                if segment:
                    parts.append(segment)
        
        logger.debug(f"解析字段路径: {field_path} -> {parts}")
        return parts

    @staticmethod
    def _convert_value(value: Any) -> Any:
        """
        转换字符串值为适当的数据类型
        
        Args:
            value: 原始值（可能是字符串）
        
        Returns:
            转换后的值（数字、布尔值或字符串）
        """
        if isinstance(value, (int, float, bool, type(None))):
            return value
        
        if isinstance(value, str):
            # 尝试转换为数字
            try:
                # 尝试整数
                if value.isdigit() or (value.startswith('-') and value[1:].isdigit()):
                    return int(value)
            except:
                pass
            
            try:
                # 尝试浮点数
                return float(value)
            except ValueError:
                pass
            
            # 尝试布尔值
            if value.lower() in ('true', 'yes', '1'):
                return True
            elif value.lower() in ('false', 'no', '0'):
                return False
            
            # 保持原字符串
            return value
        
        return value

    @staticmethod
    def upload_line(file_path: str, key: str, new_value: Any) -> bool:
        """
        更新配置文件中的某一行
        
        Args:
            file_path: 配置文件路径
            key: 配置项的键名（用于匹配行）
            new_value: 新值，支持字符串和数字
        
        Returns:
            bool: 是否更新成功
        """
        try:
            if not os.path.exists(file_path):
                logger.error(f"配置文件不存在: {file_path}")
                return False

            # 读取文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # 转换新值为字符串
            new_value_str = str(new_value)
            
            # 查找并替换匹配的行
            # 改进的正则表达式：精确匹配值部分
            # 支持两种格式：
            # 1. 带引号的值："value" 或 'value'
            # 2. 不带引号的值：value
            # group(1): 前导空白, group(2): 分隔符, group(3): 值部分, group(4): 分号和注释
            pattern = re.compile(
                r'^(\s*)' + re.escape(key) + r'(\s*[=:]\s*)'
                r'(?:'
                r'(".*?"|\'.*?\')'  # 匹配带引号的值（双引号或单引号）
                r'|'
                r'([^\s;#]+(?:[^\s;#])*)'  # 匹配不带引号的值
                r')'
                r'(\s*[;#].*)?$',
                re.IGNORECASE
            )
            
            updated = False
            for i, line in enumerate(lines):
                original_line = line.rstrip('\n\r')
                match = pattern.match(original_line)
                if match:
                    # 保持原有的缩进和格式
                    prefix = match.group(1)  # 前导空白
                    separator = match.group(2)  # 分隔符（=或:）
                    # group(3)或group(4)其中一个会有值：group(3)是带引号的，group(4)是不带引号的
                    old_value_part = match.group(3) if match.group(3) else match.group(4)
                    comment_part = match.group(5) if match.group(5) else ""  # 分号和注释部分
                    
                    # 去除旧值部分的首尾空白
                    old_value_clean = old_value_part.strip() if old_value_part else ""
                    
                    # 智能处理引号：如果原值有引号，检查新值是否需要加引号
                    old_has_quotes = (old_value_clean.startswith('"') and old_value_clean.endswith('"')) or \
                                   (old_value_clean.startswith("'") and old_value_clean.endswith("'"))
                    new_has_quotes = (new_value_str.startswith('"') and new_value_str.endswith('"')) or \
                                   (new_value_str.startswith("'") and new_value_str.endswith("'"))
                    
                    # 确定最终的新值格式
                    if old_has_quotes and not new_has_quotes:
                        # 原值有引号，新值没有引号，需要给新值加引号（使用原值的引号类型）
                        quote_char = '"' if old_value_clean.startswith('"') else "'"
                        final_value = f'{quote_char}{new_value_str}{quote_char}'
                    elif not old_has_quotes and new_has_quotes:
                        # 原值没有引号，新值有引号，去掉引号
                        final_value = new_value_str.strip('"\'')
                    else:
                        # 两种情况：都有引号或都没有引号，保持新值的格式
                        final_value = new_value_str
                    
                    # 构建新行，保持原格式
                    new_line = f"{prefix}{key}{separator}{final_value}{comment_part}\n"
                    lines[i] = new_line
                    updated = True
                    logger.info(f"找到并更新配置行: {key} = {final_value}")
                    logger.debug(f"原行: {original_line}")
                    logger.debug(f"新行: {new_line.rstrip()}")
                    break

            if not updated:
                logger.warning(f"未找到匹配的配置项: {key}, 文件: {file_path}")
                # 如果没找到，可以选择在文件末尾添加（可选功能）
                # 这里暂时只记录警告，不自动添加
                return False

            # 写回文件
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)

            logger.info(f"配置文件更新成功: {file_path}, {key} = {new_value_str}")
            return True

        except Exception as e:
            logger.error(f"更新配置文件异常: {file_path}, 错误: {e}")
            return False

    @staticmethod
    def upload_replace(file_path: str, old_value: str, new_value: str) -> bool:
        """
        全局替换文件中的字符串
        
        Args:
            file_path: 文件路径
            old_value: 要替换的旧字符串
            new_value: 替换后的新字符串
        
        Returns:
            bool: 是否替换成功
        """
        try:
            if not os.path.exists(file_path):
                logger.error(f"文件不存在: {file_path}")
                return False

            # 读取文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 全局替换
            if old_value not in content:
                logger.warning(f"文件中未找到要替换的字符串: {old_value}, 文件: {file_path}")
                return False

            new_content = content.replace(old_value, new_value)
            
            # 计算替换次数
            replace_count = content.count(old_value)
            logger.info(f"替换字符串: {old_value} -> {new_value}, 替换次数: {replace_count}")

            # 写回文件
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)

            logger.info(f"文件替换成功: {file_path}, 共替换 {replace_count} 次")
            return True

        except Exception as e:
            logger.error(f"替换文件内容异常: {file_path}, 错误: {e}")
            return False

    @staticmethod
    def upload_delete(file_path: str, key: str) -> bool:
        """
        删除配置文件中指定键对应的整行配置

        规则：
        1. 未匹配到配置项：跳过并返回True
        2. 仅匹配到1行：删除该行并返回True
        3. 匹配到多行：报错并返回False（不修改文件）

        Args:
            file_path: 配置文件路径
            key: 配置项键名（用于匹配行）

        Returns:
            bool: 是否执行成功
        """
        try:
            if not os.path.exists(file_path):
                logger.error(f"配置文件不存在: {file_path}")
                return False

            # 读取文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # 与 upload_line 保持一致的键值匹配规则
            pattern = re.compile(
                r'^(\s*)' + re.escape(key) + r'(\s*[=:]\s*)'
                r'(?:'
                r'(".*?"|\'.*?\')'
                r'|'
                r'([^\s;#]+(?:[^\s;#])*)'
                r')'
                r'(\s*[;#].*)?$',
                re.IGNORECASE
            )

            matched_indices = []
            for i, line in enumerate(lines):
                original_line = line.rstrip('\n\r')
                if pattern.match(original_line):
                    matched_indices.append(i)

            # 未匹配：按需求 pass
            if len(matched_indices) == 0:
                logger.info(f"DELETE未找到配置项，跳过: {key}, 文件: {file_path}")
                return True

            # 多匹配：按需求报错且不改文件
            if len(matched_indices) > 1:
                logger.error(
                    f"DELETE匹配到多个配置项，拒绝删除: {key}, 文件: {file_path}, 匹配数量: {len(matched_indices)}"
                )
                return False

            # 单匹配：删除对应行并写回
            delete_index = matched_indices[0]
            deleted_line = lines[delete_index].rstrip('\n\r')
            del lines[delete_index]

            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)

            logger.info(f"DELETE删除配置成功: {key}, 文件: {file_path}")
            logger.debug(f"删除行内容: {deleted_line}")
            return True

        except Exception as e:
            logger.error(f"删除配置文件异常: {file_path}, 错误: {e}")
            return False

