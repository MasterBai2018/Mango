#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2025/01/XX
# @Author  : baihuidong
# @File    : yaml_wakeup_to_mgo_converter.py
# @Software: PyCharm
# @Mail    : baihuidong@pachiratech.com
"""
唤醒+ASR测试用例YAML格式转换为新格式(.mgo + CSV)工具

功能：
1. 解析唤醒+ASR测试用例YAML格式文件
2. 转换为新格式的.mgo文件和CSV步骤文件
3. 支持多通道断言
4. 自动处理参数设置（freeWakeup, strategy, vrSeatSignal等）

YAML格式说明：
- 头部配置：@DEFAULT_CHANNEL, @DEFAULT_MSGTYPE, @DEFAULT_CARTYPE等
- 测试用例：*voice:音频文件	参数列表
- 期望结果：[0]text:识别文本;skill:技能;intention:意图
- 多通道：[1]text:None;skill:None 等

新格式说明：
- .mgo文件：包含SETUP、TEARDOWN和测试步骤模板
- CSV文件：包含CaseID和StepCase（动态步骤）
"""

import os
import re
import csv
from typing import List, Dict, Tuple, Optional
from loguru import logger


class YAMLWakeupToMGOConverter:
    """唤醒+ASR测试用例YAML格式转MGO格式转换器"""
    
    def __init__(self, yaml_file: str, output_dir: str = None, client_type: str = "TSA"):
        """
        初始化转换器
        
        Args:
            yaml_file: YAML格式的测试用例文件路径
            output_dir: 输出目录（默认为YAML文件所在目录）
            client_type: 客户端类型（TSA/NIS等，默认TSA）
        """
        self.yaml_file = yaml_file
        self.client_type = client_type.upper()
        
        # 确定输出目录
        if output_dir is None:
            output_dir = os.path.dirname(yaml_file)
        self.output_dir = output_dir
        
        # 确保输出目录存在
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 生成输出文件名
        yaml_basename = os.path.splitext(os.path.basename(yaml_file))[0]
        self.mgo_file = os.path.join(output_dir, f"{yaml_basename}.mgo")
        # 不再生成CSV文件
        self.params_csv_file = None
        
        # 解析结果
        self.cases: List[Dict] = []
        self.config: Dict = {}
        
    def parse_yaml(self) -> List[Dict]:
        """
        解析YAML格式的唤醒+ASR测试用例文件
        
        Returns:
            测试用例列表
        """
        cases = []
        current_case = None
        
        with open(self.yaml_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        i = 0
        while i < len(lines):
            line = lines[i].rstrip('\n\r')
            stripped_line = line.strip()
            
            # 跳过空行和注释
            if not stripped_line or stripped_line.startswith('#') or stripped_line.startswith('//'):
                i += 1
                continue
            
            # 解析头部配置
            if stripped_line.startswith('@'):
                self._parse_config_line(stripped_line)
                i += 1
                continue
            
            # 解析测试用例：*voice:音频文件	参数列表
            if stripped_line.startswith('*voice:') or (stripped_line.startswith('*') and 'voice:' in stripped_line):
                # 如果有未完成的用例，先保存
                if current_case and current_case.get('steps'):
                    cases.append(current_case)
                
                # 创建新用例
                current_case = self._parse_voice_case_line(stripped_line)
                i += 1
                
                # 解析期望结果（后续行）
                while i < len(lines):
                    expect_line = lines[i].strip()
                    
                    # 如果遇到新的用例或注释，停止解析
                    if (expect_line.startswith('*') or 
                        expect_line.startswith('#') or 
                        not expect_line):
                        break
                    
                    # 解析期望结果：[0]text:XXX;skill:XXX
                    if expect_line.startswith('[') and ('text:' in expect_line or 'skill:' in expect_line):
                        expect = self._parse_expect_line(expect_line)
                        if expect:
                            current_case['steps'].append({
                                'type': 'EXP',
                                'command': 'NLPResult',
                                'expect': expect
                            })
                    i += 1
                continue
            
            i += 1
        
        # 保存最后一个用例
        if current_case and current_case.get('steps'):
            cases.append(current_case)
        
        self.cases = cases
        logger.info(f"解析完成，共 {len(cases)} 个测试用例")
        return cases
    
    def _parse_config_line(self, line: str):
        """解析配置行"""
        if ':' in line:
            # 移除注释
            line = line.split('#')[0].strip()
            if ':' in line:
                key, value = line[1:].split(':', 1)
                self.config[key.strip()] = value.strip()
    
    def _parse_voice_case_line(self, line: str) -> Dict:
        """
        解析音频测试用例行
        
        格式：*voice:音频文件	参数列表
        或：*inputEvent:[...];voice:音频文件	参数列表
        """
        case_data = {
            'audio_file': '',
            'input_events': [],
            'freeWakeup': None,
            'vrLang': 'cmn',
            'shape': [1],  # 默认单通道
            'strategy': '0',
            'vrSeatSignal': None,
            'parallelSR': None,
            'steps': []
        }
        
        # 解析inputEvent（如果有）
        if '*inputEvent:' in line:
            input_event_match = re.search(r'\*inputEvent:\[([^\]]+)\];', line)
            if input_event_match:
                events_str = input_event_match.group(1)
                case_data['input_events'] = [e.strip() for e in events_str.split(',')]
        
        # 解析音频文件路径
        voice_match = re.search(r'voice:([^\t]+)', line)
        if voice_match:
            case_data['audio_file'] = voice_match.group(1).strip()
        
        # 解析参数列表（用tab分隔）
        if '\t' in line:
            params_part = line.split('\t')[1]
        else:
            # 如果没有tab，尝试从行尾提取参数
            params_part = line
        
        # 解析各个参数
        # freeWakeup:0;vrLang:cmn;shape:[1,1,1,1];strategy:2;vrSeatSignal:15;parallelSR:0
        param_patterns = {
            'freeWakeup': r'freeWakeup:(\d+)',
            'vrLang': r'vrLang:(\w+)',
            'shape': r'shape:\[([^\]]+)\]',
            'strategy': r'strategy:(\d+)',
            'vrSeatSignal': r'vrSeatSignal:(\d+)',
            'parallelSR': r'parallelSR:(\d+)'
        }
        
        for param_name, pattern in param_patterns.items():
            match = re.search(pattern, params_part)
            if match:
                value = match.group(1)
                if param_name == 'shape':
                    # 解析shape数组，如[1,1,1,1]
                    case_data['shape'] = [int(x.strip()) for x in value.split(',')]
                elif param_name in ['freeWakeup', 'strategy', 'vrSeatSignal', 'parallelSR']:
                    case_data[param_name] = value
                else:
                    case_data[param_name] = value
        
        # 计算通道数（根据shape数组长度）
        case_data['channel_count'] = len(case_data['shape'])
        
        return case_data
    
    def _parse_expect_line(self, line: str) -> Optional[str]:
        """
        解析期望结果行
        
        格式：[0]text:识别文本;skill:技能;intention:意图
        或：[1]text:None;skill:None
        """
        # 移除[NLP]前缀（如果有）
        if line.startswith('[NLP]'):
            line = line[5:].strip()
        
        # 如果已经是期望格式，直接返回
        if line.startswith('[') and ('text:' in line or 'skill:' in line):
            return line
        
        return None
    
    def convert(self):
        """执行转换"""
        # 1. 解析YAML文件
        self.parse_yaml()
        
        # 2. 生成.mgo文件（包含所有用例步骤）
        self._generate_mgo_file()
        
        logger.success(f"转换完成！")
        logger.info(f"  MGO文件: {self.mgo_file}")
        logger.info(f"  共转换 {len(self.cases)} 个测试用例")
    
    def _generate_mgo_file(self):
        """生成.mgo文件"""
        client = self.client_type
        
        # 获取默认配置
        car_type = self.config.get('DEFAULT_CARTYPE', '0')
        abs_time = self.config.get('DEFAULT_ABSTIME', '0')
        
        # 生成SETUP部分
        setup_lines = [
            ">>> SETUP",
            f"[SYS]PULL         AIBSServer cmn {{\"brand\":\"{car_type}\"}}",
            f"[SYS]PULL         LCSEngine cmn",
            f"[SYS]PULL         SpeechEngine cmn",
            f"[{client}]CREATE       cmn com.autoai.vr.service_vrassistant",
        ]
        
        # 如果有车类型配置，添加CAR_TYPE设置
        if car_type != '0':
            setup_lines.append(f"[{client}]CAR_TYPE {{\"brand\":\"{car_type}\"}}")
        
        setup_lines.extend([
            "<<<",
            ""
        ])
        
        # 生成TEARDOWN部分
        teardown_lines = [
            ">>> TEARDOWN",
            f"[{client}]FREE",
            "[SYS]KILL   SpeechEngine",
            "[SYS]KILL   LCSEngine",
            "[SYS]KILL   AIBSServer",
            "<<<",
            ""
        ]
        
        # 检查所有用例的参数是否相同
        all_freeWakeup = set(case.get('freeWakeup') for case in self.cases if case.get('freeWakeup') is not None)
        all_strategy = set(case.get('strategy') for case in self.cases if case.get('strategy'))
        all_vrSeatSignal = set(case.get('vrSeatSignal') for case in self.cases if case.get('vrSeatSignal'))
        
        # 如果所有用例的参数相同，在SETUP中设置
        if len(all_freeWakeup) == 1:
            freeWakeup_value = list(all_freeWakeup)[0]
            setup_lines.insert(-2, f"[{client}]FREEWAKEUP {freeWakeup_value}")
        
        if len(all_strategy) == 1:
            strategy_value = list(all_strategy)[0]
            setup_lines.insert(-2, f"[{client}]STRATEGY {strategy_value}")
        
        if len(all_vrSeatSignal) == 1:
            vrSeatSignal_value = list(all_vrSeatSignal)[0]
            setup_lines.insert(-2, f"[{client}]SET_PARAM AIBS_PARAM_SEAT_SIGNAL {vrSeatSignal_value}")
        
        # 写入文件
        with open(self.mgo_file, 'w', encoding='utf-8') as f:
            # 写入注释
            case_bref = self.config.get('CASE_BREF', '')
            if case_bref:
                f.write(f"# {case_bref}\n")
            f.write(f"# 由 {os.path.basename(self.yaml_file)} 自动转换生成\n")
            f.write("\n")
            
            # 写入SETUP
            f.write("\n".join(setup_lines))
            f.write("\n")
            
            # 为每个用例生成独立的测试块
            for case_id, case in enumerate(self.cases):
                f.write(f">>> {case_id + 1}\n")
                
                # 写入用例步骤
                case_steps = self._generate_case_steps(case)
                for step in case_steps:
                    f.write(f"{step}\n")
                
                # 每个用例结束时STOP
                f.write(f"[{client}]STOP\n")
                f.write("<<<\n\n")
            
            # 写入TEARDOWN
            f.write("\n".join(teardown_lines))
            f.write("\n")
    
    def _generate_params_csv_file(self):
        """生成参数化CSV文件"""
        # 确定CSV表头（所有用例中出现的参数）
        csv_headers = ['AUDIO_FILE', 'CHANNEL_COUNT']
        
        # 检查哪些参数在不同用例中不同
        all_freeWakeup = set(case.get('freeWakeup') for case in self.cases if case.get('freeWakeup') is not None)
        all_strategy = set(case.get('strategy') for case in self.cases if case.get('strategy'))
        all_vrSeatSignal = set(case.get('vrSeatSignal') for case in self.cases if case.get('vrSeatSignal'))
        
        if len(all_freeWakeup) > 1:
            csv_headers.append('FREEWAKEUP')
        if len(all_strategy) > 1:
            csv_headers.append('STRATEGY')
        if len(all_vrSeatSignal) > 1:
            csv_headers.append('VR_SEAT_SIGNAL')
        
        # 收集期望结果（每个通道的期望）
        max_channels = max(case.get('channel_count', 1) for case in self.cases)
        for ch in range(max_channels):
            csv_headers.append(f'EXPECT_CH{ch}')
        
        # 写入CSV文件
        with open(self.params_csv_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(csv_headers)
            
            # 写入每个用例的参数
            for case in self.cases:
                row = []
                
                # AUDIO_FILE
                row.append(case.get('audio_file', ''))
                
                # CHANNEL_COUNT
                row.append(str(case.get('channel_count', 1)))
                
                # FREEWAKEUP（如果不同）
                if len(all_freeWakeup) > 1:
                    row.append(case.get('freeWakeup', ''))
                
                # STRATEGY（如果不同）
                if len(all_strategy) > 1:
                    row.append(case.get('strategy', ''))
                
                # VR_SEAT_SIGNAL（如果不同）
                if len(all_vrSeatSignal) > 1:
                    row.append(case.get('vrSeatSignal', ''))
                
                # 期望结果（每个通道，支持多个期望结果）
                channel_count = case.get('channel_count', 1)
                expects_by_channel = {}  # {channel: [expect1, expect2, ...]}
                for step in case.get('steps', []):
                    if step['type'] == 'EXP':
                        expect = step['expect']
                        # 提取通道号 [0]text:XXX -> channel=0
                        channel_match = re.match(r'\[(\d+)\]', expect)
                        if channel_match:
                            ch = int(channel_match.group(1))
                            if ch not in expects_by_channel:
                                expects_by_channel[ch] = []
                            expects_by_channel[ch].append(expect)
                
                # 写入每个通道的期望结果（多个期望用分号分隔）
                for ch in range(max_channels):
                    if ch < channel_count and ch in expects_by_channel:
                        # 多个期望结果用分号分隔
                        expects_str = ';'.join(expects_by_channel[ch])
                        row.append(expects_str)
                    else:
                        row.append('')  # 该通道无期望结果
                
                writer.writerow(row)
    
    def _generate_template_steps(self) -> List[str]:
        """
        生成参数化模板用例的步骤
        
        Returns:
            步骤字符串列表（包含${variable}占位符）
        """
        steps = []
        client = self.client_type
        
        # 检查哪些参数在所有用例中都相同（这些会在SETUP中设置）
        all_freeWakeup = set(case.get('freeWakeup') for case in self.cases if case.get('freeWakeup') is not None)
        all_strategy = set(case.get('strategy') for case in self.cases if case.get('strategy'))
        all_vrSeatSignal = set(case.get('vrSeatSignal') for case in self.cases if case.get('vrSeatSignal'))
        
        # 1. 设置FREEWAKEUP（如果不同用例的值不同，使用参数化）
        if len(all_freeWakeup) > 1:
            steps.append(f"[{client}]FREEWAKEUP ${{FREEWAKEUP}}")
        
        # 2. 设置STRATEGY（如果不同用例的值不同，使用参数化）
        if len(all_strategy) > 1:
            steps.append(f"[{client}]STRATEGY ${{STRATEGY}}")
        
        # 3. 设置座椅信号（如果不同用例的值不同，使用参数化）
        if len(all_vrSeatSignal) > 1:
            steps.append(f"[{client}]SET_PARAM AIBS_PARAM_SEAT_SIGNAL ${{VR_SEAT_SIGNAL}}")
        
        # 4. 设置通道数（使用参数化）
        steps.append(f"[{client}]START ${{CHANNEL_COUNT}}")
        
        # 5. 发送音频数据（使用参数化）
        steps.append(f"[{client}]DATA ${{AUDIO_FILE}}")
        
        # 6. 期望结果断言（使用参数化，根据通道数动态生成）
        # 注意：如果某个通道有多个期望结果，需要在CSV中用分号分隔，这里需要特殊处理
        max_channels = max(case.get('channel_count', 1) for case in self.cases)
        for ch in range(max_channels):
            # 使用参数化变量，支持多个期望结果（用分号分隔）
            steps.append(f"[EXP]NLPResult ${{EXPECT_CH{ch}}} <timeout=5>")
        
        return steps
    
    def _generate_case_steps(self, case: Dict) -> List[str]:
        """
        生成单个用例的步骤列表
        
        Args:
            case: 用例数据字典
            
        Returns:
            步骤字符串列表
        """
        steps = []
        client = self.client_type
        
        # 检查哪些参数在所有用例中都相同（这些会在SETUP中设置）
        all_freeWakeup = set(c.get('freeWakeup') for c in self.cases if c.get('freeWakeup') is not None)
        all_strategy = set(c.get('strategy') for c in self.cases if c.get('strategy'))
        all_vrSeatSignal = set(c.get('vrSeatSignal') for c in self.cases if c.get('vrSeatSignal'))
        
        # 1. 设置FREEWAKEUP（如果不同用例的值不同，才在每个用例中设置）
        if len(all_freeWakeup) > 1 and case.get('freeWakeup') is not None:
            steps.append(f"[{client}]FREEWAKEUP {case['freeWakeup']}")
        
        # 2. 设置STRATEGY（如果不同用例的值不同，才在每个用例中设置）
        if len(all_strategy) > 1 and case.get('strategy'):
            steps.append(f"[{client}]STRATEGY {case['strategy']}")
        
        # 3. 设置座椅信号（如果不同用例的值不同，才在每个用例中设置）
        if len(all_vrSeatSignal) > 1 and case.get('vrSeatSignal'):
            steps.append(f"[{client}]SET_PARAM AIBS_PARAM_SEAT_SIGNAL {case['vrSeatSignal']}")
        
        # 4. 设置通道数（根据shape，每个用例可能不同）
        channel_count = case.get('channel_count', 1)
        steps.append(f"[{client}]START {channel_count}")
        
        # 5. 发送INPUTEVENT（如果有）
        if case.get('input_events'):
            # 这里需要根据实际的事件格式生成INPUTEVENT指令
            # 暂时跳过，需要根据实际事件模板生成
            for event_name in case['input_events']:
                steps.append(f"[{client}]INPUTEVENT {event_name}")
        
        # 6. 发送音频数据
        audio_file = case.get('audio_file', '')
        if audio_file:
            steps.append(f"[{client}]DATA {audio_file}")
        
        # 7. 写入期望结果断言
        for step in case.get('steps', []):
            if step['type'] == 'EXP':
                expect = step['expect']
                # 确保期望结果格式正确：[0]text:XXX;skill:XXX
                if not expect.startswith('['):
                    expect = f"[0]{expect}"
                
                steps.append(f"[EXP]NLPResult {expect} <timeout=5>")
        
        return steps


def convert_yaml_wakeup_to_mgo(yaml_file: str, output_dir: str = None, client_type: str = "TSA"):
    """
    转换唤醒+ASR测试用例YAML文件为新格式
    
    Args:
        yaml_file: YAML格式的测试用例文件路径
        output_dir: 输出目录（默认为YAML文件所在目录）
        client_type: 客户端类型（TSA/NIS等，默认TSA）
    
    Returns:
        mgo_file: 输出.mgo文件路径
    """
    converter = YAMLWakeupToMGOConverter(yaml_file, output_dir, client_type)
    converter.convert()
    return converter.mgo_file


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python yaml_wakeup_to_mgo_converter.py <yaml_file> [output_dir] [client_type]")
        print("示例: python yaml_wakeup_to_mgo_converter.py guangfeng.yaml ./output TSA")
        sys.exit(1)
    
    yaml_file = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    client_type = sys.argv[3] if len(sys.argv) > 3 else "TSA"
    
    convert_yaml_wakeup_to_mgo(yaml_file, output_dir, client_type)
