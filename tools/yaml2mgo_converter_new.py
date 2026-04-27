#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
YAML到MGO格式转换器

将老版本NLU测试用例(YAML格式)转换为新版本MGO格式

使用方法:
    python yaml2mgo_converter.py <input_yaml> <output_mgo> [--lang cmn] [--appid xxx]
    
示例:
    python yaml2mgo_converter.py nlu/cmn/NAVI/NAVI_cx/Offline/查询当前位置_Offline.yaml output.mgo
    python yaml2mgo_converter.py nlu/cmn/QueryWeather/Offline/查询天气.Offline.yaml weather.mgo --lang cmn

Author: Claude
Date: 2025-12-27
"""

import os
import re
import sys
import json
import argparse
import sqlite3
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.utils.common import timer


@dataclass
class DialogStep:
    """对话步骤"""
    step_type: str  # 'inputEvent', 'text', 'callbackEvent', 'voice', 'fileEvent', 'eventList'
    content: str    # 主要内容（text文本、事件名、音频文件路径等）
    params: Dict[str, str] = field(default_factory=dict)  # 参数（strategy, dialog等）
    expect: str = ""  # NLP期望结果（第一个期望）
    expects: List[str] = field(default_factory=list)  # 多个期望结果列表
    assertions: List[str] = field(default_factory=list)  # 断言列表（[SWU], [LASR], [API]等）


@dataclass
class TestCase:
    """测试用例"""
    comment: str = ""  # 注释
    steps: List[DialogStep] = field(default_factory=list)
    strategy: str = "0"  # 默认策略
    input_events: List[str] = field(default_factory=list)  # 输入事件列表
    event_params: Dict[str, str] = field(default_factory=dict)  # 事件参数映射，格式: {event_name: "param1:value1;param2:value2"}


class YamlToMgoConverter:
    """YAML到MGO格式转换器"""
    
    def __init__(self, lang: str = "cmn", appid: str = "com.autoai.vr.service_vrassistant"):
        self.lang = lang
        self.appid = appid
        self.default_channel = "0"
        self.default_msgtype = "NLP"
        self.default_cartype = "0"  # 默认车类型，0: 雷克萨斯；1:一丰；2:广丰
        self.case_brief = ""
        self.db_path = None
        self.db_connection = None
        # 源 YAML 所在目录，用于解析 eventList 等相对路径
        self._yaml_base_dir = ""
        # 工程根目录（tools 的上一级），用于解析 TestCase/... 这类路径
        self._project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self._init_database()

    def _is_supported_assertion_type(self, assertion_type: str) -> bool:
        """判断是否是已支持的断言类型。"""
        return assertion_type in ['SWU', 'LASR', 'API', 'HIC']

    def _parse_assertion_line(self, assertion_line: str) -> Optional[Tuple[str, str]]:
        """
        解析断言行，支持:
        - [HIC]source:SpeechEngine;text:小艺小艺
        - [0][HIC]source:SpeechEngine;text:小艺小艺
        返回: (断言类型, 断言内容)
        """
        text = assertion_line.strip()
        match = re.match(r'^(?:\[(\d+)\])?\[([^\]]+)\](.*)$', text)
        if not match:
            return None

        channel, assertion_type, assertion_content = match.groups()
        assertion_type = assertion_type.strip()
        assertion_content = assertion_content.strip()

        if not self._is_supported_assertion_type(assertion_type):
            return None

        # 保留断言中的通道信息，后续生成 EXP 时不再重复补通道
        if channel is not None:
            assertion_content = f"[{channel}]{assertion_content}" if assertion_content else f"[{channel}]"

        return assertion_type, assertion_content
    
    def _init_database(self):
        """初始化数据库连接"""
        # 数据库路径
        db_path = os.path.join(os.path.dirname(__file__), '..', 'TestAudio', 'llm_asr_data', 'audio_data.db')
        if os.path.exists(db_path):
            self.db_path = db_path
            try:
                self.db_connection = sqlite3.connect(db_path, check_same_thread=False)
            except Exception as e:
                print(f"⚠️ 无法连接数据库 {db_path}: {e}")
                self.db_connection = None
        else:
            # 尝试绝对路径
            abs_db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'TestAudio', 'llm_asr_data', 'audio_data.db'))
            if os.path.exists(abs_db_path):
                self.db_path = abs_db_path
                try:
                    self.db_connection = sqlite3.connect(abs_db_path, check_same_thread=False)
                except Exception as e:
                    print(f"⚠️ 无法连接数据库 {abs_db_path}: {e}")
                    self.db_connection = None
    
    def _query_voice_path(self, text: str) -> Optional[str]:
        """
        从数据库查询voice_path
        
        Args:
            text: 音频文本
            
        Returns:
            voice_path 或 None
        """
        if not self.db_connection:
            return None
        
        try:
            cursor = self.db_connection.cursor()
            cursor.execute("SELECT voice_path FROM tts_audio WHERE text = ?", (text,))
            result = cursor.fetchone()
            if result:
                return result[0]
        except Exception as e:
            print(f"⚠️ 查询数据库失败: {e}")
        
        return None
    
    def __del__(self):
        """关闭数据库连接"""
        if self.db_connection:
            self.db_connection.close()
        
    def parse_yaml_file(self, yaml_path: str) -> List[TestCase]:
        """解析YAML文件，返回测试用例列表"""
        if not os.path.exists(yaml_path):
            raise FileNotFoundError(f"YAML文件不存在: {yaml_path}")
        
        self._yaml_base_dir = os.path.dirname(os.path.abspath(yaml_path))
        
        with open(yaml_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        return self._parse_lines(lines)
    
    def _parse_lines(self, lines: List[str]) -> List[TestCase]:
        """解析文件行，提取测试用例"""
        cases = []
        current_case: Optional[TestCase] = None
        current_comment = ""
        in_multi_turn_dialog = False  # 是否在多轮对话中（dialog:start 到 dialog:end 之间）
        
        i = 0
        while i < len(lines):
            line = lines[i].rstrip('\n\r')
            stripped = line.strip()
            
            # 跳过空行
            if not stripped:
                i += 1
                continue
            
            # 解析文件头元数据
            if stripped.startswith('@DEFAULT_CHANNEL:'):
                self.default_channel = stripped.split(':', 1)[1].strip()
                i += 1
                continue
            elif stripped.startswith('@DEFAULT_MSGTYPE:'):
                self.default_msgtype = stripped.split(':', 1)[1].strip()
                i += 1
                continue
            elif stripped.startswith('@DEFAULT_CARTYPE:'):
                # 提取值，去掉可能的注释
                value = stripped.split(':', 1)[1].strip()
                if '#' in value:
                    value = value.split('#')[0].strip()
                self.default_cartype = value
                i += 1
                continue
            elif stripped.startswith('@CASE_BREF:'):
                self.case_brief = stripped.split(':', 1)[1].strip()
                i += 1
                continue
            
            # 解析注释
            if stripped.startswith('#'):
                current_comment = stripped[1:].strip()
                i += 1
                continue
            
            # 解析指令行（*开头）
            if stripped.startswith('*'):
                step, params = self._parse_instruction_line(stripped)
                
                if step:
                    # 判断是否是新Case的开始
                    is_new_case = False
                    
                    # 检查是否开始新的多轮对话（dialog:start）
                    if params.get('dialog') == 'start':
                        is_new_case = True
                        in_multi_turn_dialog = True
                    
                    # 如果不在多轮对话中
                    elif not in_multi_turn_dialog:
                        # voice / eventList 指令总是开始新Case
                        if step.step_type == 'voice' or step.step_type == 'eventList':
                            is_new_case = True
                        # 如果当前没有Case，创建新Case
                        elif current_case is None:
                            is_new_case = True
                        # 如果前一个Case已经结束（dialog:end），创建新Case
                        elif current_case and current_case.steps:
                            last_step = current_case.steps[-1]
                            if last_step.params.get('dialog') == 'end':
                                is_new_case = True
                            # 对于简单的单轮Case（没有dialog标记），每个*text或*inputEvent都是新Case
                            else:
                                is_new_case = True
                    
                    # 如果在多轮对话中，不创建新Case，继续添加到当前Case
                    # （这里不需要额外代码，is_new_case 保持 False）
                    
                    if is_new_case:
                        # 保存前一个Case
                        if current_case and current_case.steps:
                            cases.append(current_case)
                        
                        # 创建新Case
                        current_case = TestCase(comment=current_comment)
                        current_comment = ""
                        
                        # 设置策略
                        if 'strategy' in params:
                            current_case.strategy = params['strategy']
                        
                        # 设置输入事件
                        if step.step_type == 'inputEvent' and step.content:
                            current_case.input_events = self._parse_event_list(step.content)
                            # 提取带事件名前缀的参数（如 MediaStatus.data.mediaType:6）
                            event_params_map = self._extract_event_params(params, current_case.input_events)
                            current_case.event_params.update(event_params_map)
                    
                    # 添加步骤到当前Case
                    if current_case:
                        # 合并params，保留之前设置的text等字段
                        step.params.update(params)
                        current_case.steps.append(step)
                        
                        # 更新策略
                        if 'strategy' in params:
                            current_case.strategy = params['strategy']
                        
                        # 标记是否是中间的inputEvent（不是Case开头的）
                        if step.step_type == 'inputEvent' and not is_new_case:
                            step.params['is_mid_event'] = True
                    
                    # 检查多轮对话是否结束（dialog:end）
                    if params.get('dialog') == 'end':
                        in_multi_turn_dialog = False
                    
                    # 如果是voice指令，继续解析后续的断言和期望
                    if step.step_type == 'voice':
                        i += 1
                        i = self._consume_step_tail_lines(lines, i, step)
                        continue
                    
                    # *event / *eventList 后续断言语行（含 tts:）
                    if step.step_type == 'fileEvent' or step.step_type == 'eventList':
                        i += 1
                        i = self._consume_step_tail_lines(lines, i, step)
                        continue
                
                i += 1
                continue
            
            # 解析期望行
            # 格式1: [NLP]skill:xxx;intention:xxx;...
            # 格式2: skill:xxx;intention:xxx;... （不以*、#、@开头的普通行，默认是上一个*指令的断言）
            is_expect_line = False
            expect_content = ""
            
            if stripped.startswith('[NLP]') or stripped.startswith('[' + self.default_msgtype + ']'):
                # 显式[NLP]开头的断言
                expect_content = stripped.split(']', 1)[1] if ']' in stripped else stripped
                is_expect_line = True
            elif stripped.startswith('skill:') or stripped.startswith('intention:') or stripped.startswith('tts:'):
                # 隐式断言（以 skill:/intention:/tts: 开头，没有[NLP]前缀）
                expect_content = stripped
                is_expect_line = True
            
            if is_expect_line:
                # 将期望关联到最后一个步骤
                if current_case and current_case.steps:
                    current_case.steps[-1].expect = expect_content.strip()
                
                i += 1
                continue
            
            # 其他未识别的行，跳过
            i += 1
        
        # 保存最后一个Case
        if current_case and current_case.steps:
            cases.append(current_case)
        
        return cases
    
    def _consume_step_tail_lines(self, lines: List[str], i: int, step: DialogStep) -> int:
        """解析 *voice / *fileEvent / *eventList 后续断言语与期望行，返回下一条待处理行下标。"""
        while i < len(lines):
            next_line = lines[i].rstrip('\n\r')
            next_stripped = next_line.strip()
            
            if not next_stripped or next_stripped.startswith('*') or next_stripped.startswith('#'):
                break
            
            if next_stripped.startswith('[') and ']' in next_stripped:
                if self._parse_assertion_line(next_stripped):
                    step.assertions.append(next_stripped)
                    i += 1
                    continue
            
            is_expect_line = (next_stripped.startswith('text:') or
                             next_stripped.startswith('skill:') or
                             next_stripped.startswith('asr:') or
                             next_stripped.startswith('tts:') or
                             (next_stripped.startswith('[') and ']' in next_stripped and
                              (']text:' in next_stripped or ']skill:' in next_stripped or
                               ']asr:' in next_stripped or ']tts:' in next_stripped)))
            
            if is_expect_line:
                if step.expect:
                    if step.expect not in step.expects:
                        step.expects.append(step.expect)
                    step.expects.append(next_stripped)
                    step.expect = ""
                else:
                    step.expect = next_stripped
                i += 1
                continue
            
            i += 1
        
        return i
    
    def _parse_instruction_line(self, line: str) -> Tuple[Optional[DialogStep], Dict[str, str]]:
        """
        解析指令行
        
        格式示例:
        *inputEvent:[NaviLocationStatus,NavigateStatus];text:我在哪	strategy:0;dialog:start
        *text:今天天气怎么样    strategy:0
        *text:请问北京天气怎么样	skill:OffLine;intention:OffLine;...	strategy:0
        *callbackEvent:[default]    default.data.result.code:0;dialog:end
        """
        # 去掉开头的*
        line = line[1:].strip()
        
        # 使用制表符或多个空格分隔主内容和参数
        parts = re.split(r'\t+|\s{2,}', line)
        main_part = parts[0].strip()
        
        step = None
        params = {}
        inline_expect = ""  # 内联的expect
        
        # 解析主内容
        if main_part.startswith('audioText:'):
            # 解析audioText格式
            # 格式: audioText:全部添加		asr:全部添加	strategy:1;delay:0;freeWakeup:1;vrLang:cmn;hmi:TestCase/caselist/MongoCase/events/InputEvent/HMI/k_sing_1.json
            audio_text = main_part[10:].strip()  # 去掉 'audioText:' 前缀
            
            # 从数据库查询voice_path
            voice_path = self._query_voice_path(audio_text)
            
            if voice_path:
                # 创建voice类型的步骤（这样会生成[TSA]DATA命令）
                step = DialogStep(
                    step_type='voice',
                    content=voice_path
                )
            else:
                # 如果数据库中没有找到，创建text类型的步骤（降级处理）
                print(f"⚠️ 数据库中未找到文本 '{audio_text}' 的音频路径，使用TEXT模式")
                step = DialogStep(
                    step_type='text',
                    content=audio_text
                )
            
            # 解析后续部分
            # parts[0] 是主部分（audioText:...）
            # parts[1] 可能是期望结果（asr:...）
            # parts[2] 是参数（strategy:1;delay:0;freeWakeup:1;hmi:...）
            if len(parts) > 1:
                # 检查第二部分是否是期望结果（asr:...）
                expect_part = parts[1].strip()
                if expect_part.startswith('asr:'):
                    # 保持asr:格式，不转换为text:
                    step.expect = expect_part
                    # 如果有第三部分，解析为参数
                    if len(parts) > 2:
                        params.update(self._parse_params(parts[2]))
                else:
                    # 第二部分是参数
                    params.update(self._parse_params(expect_part))
        
        elif main_part.startswith('ttsLang:'):
            # 解析ttsLang:audioText格式
            # 格式: ttsLang:cmn;audioText:下一首	asr:下一首				strategy:0;delay:0;freeWakeup:1;hmi:TestCase/caselist/MongoCase/events/InputEvent/HMI/HmiMusic.json
            # 提取ttsLang和audioText
            tts_lang_match = re.search(r'ttsLang:(\w+)', main_part)
            audio_text_match = re.search(r'audioText:([^;]+)', main_part)
            
            if tts_lang_match and audio_text_match:
                tts_lang = tts_lang_match.group(1)
                audio_text = audio_text_match.group(1).strip()
                
                # 创建text类型的步骤（因为这是文本输入）
                step = DialogStep(
                    step_type='text',
                    content=audio_text
                )
                
                # 解析后续部分
                # parts[0] 是主部分（ttsLang:...;audioText:...）
                # parts[1] 可能是期望结果（asr:...）
                # parts[2] 是参数（strategy:0;delay:0;freeWakeup:1;hmi:...）
                if len(parts) > 1:
                    # 检查第二部分是否是期望结果（asr:...）
                    expect_part = parts[1].strip()
                    if expect_part.startswith('asr:'):
                        # 保持asr:格式，不转换为text:
                        step.expect = expect_part
                        # 如果有第三部分，解析为参数
                        if len(parts) > 2:
                            params.update(self._parse_params(parts[2]))
                    else:
                        # 第二部分是参数
                        params.update(self._parse_params(expect_part))
                
                # 保存ttsLang到params中（如果需要）
                step.params['ttsLang'] = tts_lang
        
        elif main_part.startswith('voice:'):
            # 解析voice指令
            # 格式: voice:音频文件路径	text:你好小悦;skill:WakeUp;...	freeWakeup:1;vrLang:cmn;strategy:0
            voice_path = main_part[6:].strip()  # 去掉 'voice:' 前缀
            step = DialogStep(
                step_type='voice',
                content=voice_path
            )
            
            # 对于voice指令，parts[1]可能是期望结果（text:...;skill:...;asr:...），parts[2]是参数
            if len(parts) > 1:
                # 检查第二部分是否是期望结果（包含text:、skill:或asr:）
                expect_part = parts[1].strip()
                if expect_part.startswith('text:') or expect_part.startswith('skill:') or expect_part.startswith('asr:'):
                    inline_expect = expect_part
                    # 如果有第三部分，解析为参数
                    if len(parts) > 2:
                        params.update(self._parse_params(parts[2]))
                elif expect_part.startswith('[') and ']' in expect_part:
                    if self._parse_assertion_line(expect_part):
                        step.assertions.append(expect_part)
                        if len(parts) > 2:
                            params.update(self._parse_params(parts[2]))
                    else:
                        # 第二部分是参数
                        params.update(self._parse_params(expect_part))
                else:
                    # 第二部分是参数
                    params.update(self._parse_params(expect_part))
            
            # 设置内联期望
            if inline_expect:
                step.expect = inline_expect
        
        elif main_part.startswith('event:'):
            # *event:JSON路径 — 生成 [TSA]EVENT；可与 ;voice: 等同行组合（统一用 _parse_event_bundle_keys）
            chunks = self._parse_event_bundle_keys(main_part)
            event_path = (chunks.get('event') or '').strip()
            step = DialogStep(
                step_type='fileEvent',
                content=event_path
            )
            if chunks.get('voice'):
                params['event_voice'] = chunks['voice'].strip()
            if len(parts) > 1:
                params.update(self._parse_params(parts[1]))
        
        elif main_part.startswith('eventList:'):
            # *eventList:列表；可选同顺序 ;event:单 JSON 文件 ;voice:wav（依次 EVENT → EVENT → DATA）
            chunks = self._parse_event_bundle_keys(main_part)
            list_path = (chunks.get('eventList') or '').strip()
            step = DialogStep(
                step_type='eventList',
                content=list_path
            )
            if chunks.get('event'):
                params['chained_event_path'] = chunks['event'].strip()
            if chunks.get('voice'):
                params['event_voice'] = chunks['voice'].strip()
            if len(parts) > 1:
                params.update(self._parse_params(parts[1]))
        
        elif main_part.startswith('inputEvent:'):
            # 解析inputEvent，可能带text或callbackEvent
            # 格式1: inputEvent:[Event1,Event2];text:内容
            # 格式2: inputEvent:[Event1];callbackEvent:[default]
            
            # 先提取events
            event_match = re.match(r'inputEvent:\[([^\]]*)\]', main_part)
            if event_match:
                events = event_match.group(1)
                remaining = main_part[event_match.end():]
                
                step = DialogStep(
                    step_type='inputEvent',
                    content=events
                )
                
                # 检查是否有text
                text_match = re.search(r';text:(.+?)(?:;|$)', remaining)
                if text_match:
                    step.params['text'] = text_match.group(1).strip()
                
                # 检查是否有callbackEvent
                callback_match = re.search(r';callbackEvent:\[([^\]]*)\]', remaining)
                if callback_match:
                    step.params['has_callback'] = True
                    step.params['callback_name'] = callback_match.group(1)
            
            # 处理其他指令的剩余部分：可能是参数、也可能是inline expect
            for i, part in enumerate(parts[1:], 1):
                part = part.strip()
                if not part:
                    continue
                
                # 检查是否是inline expect（以skill:开头的部分）
                if part.startswith('skill:'):
                    inline_expect = part
                elif part.startswith('[') and ']' in part:
                    if step and self._parse_assertion_line(part):
                        step.assertions.append(part)
                    else:
                        # 非已支持断言仍按参数处理
                        params.update(self._parse_params(part))
                else:
                    # 解析为参数
                    params.update(self._parse_params(part))
            
            # 设置内联期望
            if inline_expect:
                step.expect = inline_expect
        
        elif main_part.startswith('text:'):
            text = main_part[5:].strip()
            step = DialogStep(
                step_type='text',
                content=text
            )
            
            # 处理其他指令的剩余部分：可能是参数、也可能是inline expect
            for i, part in enumerate(parts[1:], 1):
                part = part.strip()
                if not part:
                    continue
                
                # 检查是否是inline expect（以skill:开头的部分）
                if part.startswith('skill:'):
                    inline_expect = part
                elif part.startswith('[') and ']' in part:
                    if step and self._parse_assertion_line(part):
                        step.assertions.append(part)
                    else:
                        # 非已支持断言仍按参数处理
                        params.update(self._parse_params(part))
                else:
                    # 解析为参数
                    params.update(self._parse_params(part))
            
            # 设置内联期望
            if inline_expect:
                step.expect = inline_expect
        
        elif main_part.startswith('callbackEvent:'):
            # 格式: callbackEvent:[default] 或 callbackEvent:[EventName]
            match = re.match(r'callbackEvent:\[([^\]]*)\]', main_part)
            if match:
                callback_name = match.group(1)
                step = DialogStep(
                    step_type='callbackEvent',
                    content=callback_name
                )
            
            # 处理其他指令的剩余部分：可能是参数、也可能是inline expect
            for i, part in enumerate(parts[1:], 1):
                part = part.strip()
                if not part:
                    continue
                
                # 检查是否是inline expect（以skill:开头的部分）
                if part.startswith('skill:'):
                    inline_expect = part
                elif part.startswith('[') and ']' in part:
                    if step and self._parse_assertion_line(part):
                        step.assertions.append(part)
                    else:
                        # 非已支持断言仍按参数处理
                        params.update(self._parse_params(part))
                else:
                    # 解析为参数
                    params.update(self._parse_params(part))
            
            # 设置内联期望
            if inline_expect:
                step.expect = inline_expect
        
        return step, params
    
    def _parse_params(self, param_str: str) -> Dict[str, str]:
        """解析参数字符串"""
        params = {}
        
        # 分割参数（使用;分隔）
        parts = param_str.split(';')
        for part in parts:
            part = part.strip()
            if ':' in part:
                key, value = part.split(':', 1)
                params[key.strip()] = value.strip()
        
        return params
    
    def _parse_event_bundle_keys(self, main_part: str) -> Dict[str, str]:
        """
        从主段解析 eventList / event / voice 的路径片段。
        使用分号分隔的 key:value；按出现顺序截取各 key 的值（到下一已知 key 之前）。
        正则中 eventList 优先匹配，避免与 event 冲突。
        """
        out: Dict[str, str] = {}
        pattern = re.compile(r'(?:^|;)(eventList|event|voice):')
        matches = list(pattern.finditer(main_part))
        for i, m in enumerate(matches):
            key = m.group(1)
            val_start = m.end()
            val_end = matches[i + 1].start() if i + 1 < len(matches) else len(main_part)
            out[key] = main_part[val_start:val_end].strip()
        return out
    
    def _resolve_aux_resource_path(self, path_str: str) -> str:
        """解析用例中的相对路径（eventList 列表文件等），优先已存在文件路径。"""
        if not path_str:
            return path_str
        if os.path.isabs(path_str) and os.path.isfile(path_str):
            return path_str
        candidates = [
            path_str,
            os.path.join(self._yaml_base_dir, path_str) if self._yaml_base_dir else path_str,
            os.path.join(self._project_root, path_str),
        ]
        for c in candidates:
            if c and os.path.isfile(c):
                return c
        return os.path.join(self._project_root, path_str)
    
    def _read_event_list_lines(self, list_path: str) -> List[str]:
        """读取 eventList 文件，返回非空行（每行一条 EVENT 负载）。"""
        resolved = self._resolve_aux_resource_path(list_path)
        if not os.path.isfile(resolved):
            raise FileNotFoundError(f"eventList 文件不存在: {list_path}（解析路径: {resolved}）")
        out: List[str] = []
        with open(resolved, 'r', encoding='utf-8') as ef:
            for line in ef:
                s = line.strip()
                if s:
                    out.append(s)
        return out
    
    def _delay_for_audio(self, strategy: str, step_params: Dict[str, str]) -> str:
        """
        送音频 delay：YAML 显式 delay 优先；
        strategy 为 1 或 2（在线）时为 1，离线(0 等)为 0。
        """
        if 'delay' in step_params and step_params['delay'] != '':
            return str(step_params['delay'])
        s = str(strategy).strip()
        if s in ('1', '2'):
            return '1'
        return '0'
    
    def _parse_event_list(self, event_str: str) -> List[str]:
        """解析事件列表字符串"""
        # 格式: Event1,Event2,Event3
        events = [e.strip() for e in event_str.split(',')]
        return [e for e in events if e]
    
    def _extract_event_params(self, params: Dict[str, str], events: List[str]) -> Dict[str, str]:
        """
        从参数字典中提取带事件名前缀的参数
        
        例如: MediaStatus.data.mediaType:6 -> 映射到 MediaStatus 事件，参数为 data.mediaType:6
        
        Returns:
            Dict[str, str]: {event_name: "param1:value1;param2:value2"}
        """
        event_params_map = {}
        
        for key, value in params.items():
            # 跳过非事件参数（如 strategy, dialog 等）
            if key in ['strategy', 'dialog', 'text', 'has_callback', 'callback_name']:
                continue
            
            # 检查是否是带事件名前缀的参数（格式: EventName.xxx:value）
            if '.' in key:
                parts = key.split('.', 1)  # 分割成事件名和参数名
                event_name = parts[0]
                param_name = parts[1]  # 包含 data.mediaType 等
                
                # 检查事件名是否在事件列表中
                if event_name in events:
                    # 构建参数字符串（格式: param_name:value）
                    param_str = f"{param_name}:{value}"
                    
                    # 如果该事件已有参数，追加；否则创建新条目
                    if event_name in event_params_map:
                        event_params_map[event_name] += f";{param_str}"
                    else:
                        event_params_map[event_name] = param_str
        
        return event_params_map
    
    def _convert_tts_to_ttsinfo(self, expect_str: str, lang: str, strategy: str) -> str:
        """
        将期望结果中的 tts 相关字段转换为 ttsInfo 格式
        
        例如:
        输入: skill:Media;intention:playWireless;tts:收音机已经在播放了;displayNotify:None;ttsID:BFSYJ-01;datavpa:AW-TTS-2
        输出: skill:Media;intention:playWireless;ttsInfo:BFSYJ-01,cmn,online
        
        Args:
            expect_str: 原始期望结果字符串
            lang: 对话语言（来自 SETVRCONFIG DIALOGUE_LANGUAGE，或默认 self.lang）
            strategy: 策略值，'1' 视为 online，其它视为 offline
            
        Returns:
            转换后的期望结果字符串
        """
        if not expect_str:
            return expect_str
        
        # 分割成字段列表
        parts = [p.strip() for p in expect_str.split(';') if p.strip()]
        
        # 先仅扫描是否存在 ttsID
        tts_id = None
        for part in parts:
            if part.startswith('ttsID:'):
                tts_id = part.split(':', 1)[1].strip()
                break
        
        # 【兼容逻辑 / 方式 2】
        # 如果没有配置 ttsID，则保留原始期望串（包括 tts、displayNotify、datavpa）
        if not tts_id:
            return expect_str
        
        # 如果有 ttsID，则走原有的 ttsInfo 收敛逻辑：
        # - 移除 tts / displayNotify / datavpa / ttsID
        # - 追加 ttsInfo:ID,lang,type
        result_parts = []
        for part in parts:
            # 跳过 ttsID 自身
            if part.startswith('ttsID:'):
                continue
            # 跳过旧式 tts / displayNotify / datavpa 字段
            if part.startswith('tts:') or part.startswith('displayNotify:') or part.startswith('datavpa:'):
                continue
            # 其余字段保留
            result_parts.append(part)
        
        # 添加 ttsInfo 字段: ttsInfo:ID,lang,type
        tts_type = "online" if str(strategy) == "1" else "offline"
        result_parts.append(f"ttsInfo:{tts_id},{lang},{tts_type}")
        
        return ';'.join(result_parts)
    
    def _collect_nlp_expect_strings(self, step: DialogStep) -> List[str]:
        if step.expects:
            return list(step.expects)
        if step.expect:
            return [step.expect]
        return []

    def _normalize_expect_prefix(self, expect: str) -> str:
        """
        规范化期望前缀：
        - [NLP]skill:... -> skill:...
        - [VOI]asr:... -> asr:...
        - [0][NLP]skill:... -> [0]skill:...
        保留通道前缀 [0]/[1] 等，不保留消息类型前缀。
        """
        s = expect.strip()
        if not s.startswith('[') or ']' not in s:
            return s

        known_msg_types = {'NLP', 'VOI', self.default_msgtype}

        # 形态1: [MSG]payload
        m1 = re.match(r'^\[([^\]]+)\](.*)$', s)
        if m1:
            head, tail = m1.groups()
            if head in known_msg_types:
                return tail.strip()

        # 形态2: [ch][MSG]payload
        m2 = re.match(r'^(\[\d+\])\[([^\]]+)\](.*)$', s)
        if m2:
            channel, msg_type, tail = m2.groups()
            if msg_type in known_msg_types:
                return f"{channel}{tail}".strip()

        return s
    
    def _emit_step_nlp_expects(self, lines: List[str], step: DialogStep, lang: str, strategy: str) -> None:
        # 连续多条 NLP/ASR 期望时，仅第一条带 timeout（与手工 MGO 习惯一致）
        pending: List[Tuple[str, str]] = []  # ('ASR'|'NLP', 行内容)
        for raw_expect in self._collect_nlp_expect_strings(step):
            expect = self._normalize_expect_prefix(raw_expect)
            is_expect = (expect.startswith('skill:') or
                        expect.startswith('text:') or
                        expect.startswith('tts:') or
                        expect.startswith('asr:') or
                        (expect.startswith('[') and ']' in expect and
                         (']text:' in expect or ']skill:' in expect or ']asr:' in expect or
                          ']tts:' in expect)))
            if not is_expect:
                continue
            if expect.startswith('asr:') or (expect.startswith('[') and ']asr:' in expect):
                pending.append(('ASR', expect))
            else:
                converted_expect = self._convert_tts_to_ttsinfo(expect, lang, strategy)
                pending.append(('NLP', converted_expect))
        for i, (kind, content) in enumerate(pending):
            if i == 0:
                if kind == 'ASR':
                    asr_expect_type = "ASRInputResult" if self.default_msgtype == "VOI" else "ASRResult"
                    lines.append(f"[EXP]{asr_expect_type}    {content}    <timeout=5>")
                else:
                    lines.append(f"[EXP]NLPResult    {content}    <timeout=5>")
            else:
                if kind == 'ASR':
                    asr_expect_type = "ASRInputResult" if self.default_msgtype == "VOI" else "ASRResult"
                    lines.append(f"[EXP]{asr_expect_type}    {content}")
                else:
                    lines.append(f"[EXP]NLPResult    {content}")

    def _build_voi_open_voice_input_payload(self, step_params: Dict[str, str]) -> str:
        """根据 step 参数生成 VOI OPEN_VOICE_INPUT JSON。"""
        payload = {
            "name": step_params.get("voiScene", "poi"),
            "channelID": int(step_params.get("voiChannel", self.default_channel)),
            "mode": int(step_params.get("voiMode", "1")),
            "silDuration": int(step_params.get("voiSilDuration", "5000")),
        }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    def _emit_multi_turn_voice_preamble(
        self,
        lines: List[str],
        step: DialogStep,
        default_lang: str,
        case_strategy: str,
        last_emitted_vr_lang: Optional[str],
    ) -> Tuple[str, Optional[str]]:
        """
        多轮 dialog:start / dialog:end 中，每一段 *voice 前只下发「该行」自带的 VR 参数，
        避免合并全 case 后末行 vrWakeupWord 覆盖首行（与 YAML 单行语义一致）。
        顺序与单行 case 一致：DIALOGUE_LANGUAGE → WAKEUP_KEYWORD_OPTION → WAKEUP_ALIAS
        → WAKEUP_ENABLE → FREEWAKEUP（若本行有）→ STRATEGY。
        若本行 vrLang 与上一处已下发的 DIALOGUE_LANGUAGE 相同则不再重复 SET。
        返回 (本步 NLP 期望用的语言, 更新后的 last_emitted_vr_lang)。
        """
        vr_lang = step.params.get('vrLang')
        new_last = last_emitted_vr_lang

        if vr_lang is not None:
            if vr_lang != last_emitted_vr_lang:
                lines.append(f"[SET]SETVRCONFIG  DIALOGUE_LANGUAGE {vr_lang}")
                new_last = vr_lang
            lang_to_use = vr_lang
        else:
            lang_to_use = last_emitted_vr_lang if last_emitted_vr_lang else default_lang

        if 'vrSceneOption' in step.params:
            lines.append(f"[SET]SETVRCONFIG  WAKEUP_KEYWORD_OPTION {step.params['vrSceneOption']}")
        if 'vrWakeupAlias' in step.params:
            lines.append(
                f"[SET]SETVRCONFIG  WAKEUP_ALIAS {step.params['vrWakeupAlias']} {lang_to_use}"
            )
        if 'vrWakeupWord' in step.params:
            lines.append(
                f"[SET]SETVRCONFIG  WAKEUP_ENABLE {step.params['vrWakeupWord']} {lang_to_use}"
            )
        if 'freeWakeup' in step.params:
            lines.append(f"[TSA]FREEWAKEUP   {step.params['freeWakeup']}")

        strat = step.params.get('strategy', case_strategy)
        lines.append(f"[TSA]STRATEGY     {strat}")

        return lang_to_use, new_last
    
    def generate_mgo(self, cases: List[TestCase], output_path: str = None) -> str:
        """生成MGO格式内容"""
        lines = []
        
        # 添加文件头注释
        lines.append("#" * 70)
        if self.case_brief:
            lines.append(f"# {self.case_brief}")
        lines.append(f"# 由yaml2mgo_converter自动生成")
        lines.append(f"# 语言: {self.lang}")
        lines.append(f"# Case数量: {len(cases)}")
        lines.append("#" * 70)
        lines.append("")
        
        # 生成SETUP块
        lines.append(">>> SETUP")
        lines.append(f'[SYS]PULL         AIBSServer {self.lang} {{"brand":"{self.default_cartype}"}}')
        lines.append(f'[SYS]PULL         LCSEngine {self.lang}')
        lines.append(f'[SYS]PULL         SpeechEngine {self.lang}')

        lines.append(f"[TSA]CREATE       {self.lang} {self.appid}")
        lines.append(f"[SET]CREATE       {self.lang} com.autoai.vrsetting")
        if self.default_msgtype == "VOI":
            lines.append(f"[VOI]CREATE       {self.lang} com.toyota.agentservice")
        lines.append(f"[SET]SETVRCONFIG  DIALOGUE_LANGUAGE {self.lang}")
        lines.append("<<<")
        lines.append("")
        
        # 生成TEARDOWN块
        lines.append(">>> TEARDOWN")
        # lines.append("[TSA]FREE")
        # lines.append("[SET]FREE")
        lines.append("[SYS]KILL   SpeechEngine")
        lines.append("[SYS]KILL   LCSEngine")
        lines.append("[SYS]KILL   AIBSServer")
        lines.append("<<<")
        lines.append("")
        
        # 生成每个Case
        for idx, case in enumerate(cases):
            # Case注释
            if case.comment:
                lines.append(f"# Case {idx + 1}: {case.comment}")
            else:
                lines.append(f"# Case {idx + 1}")
            
            lines.append(">>>")
            
            # 获取shape参数，计算通道数（默认1）
            channel_count = 1
            shape_param = None
            for step in case.steps:
                # voice 与 *event;voice 场景下的 DATA 均需按 shape 算通道数
                uses_shape = (
                    step.step_type == 'voice'
                    or (step.step_type == 'fileEvent' and step.params.get('event_voice'))
                    or (step.step_type == 'eventList' and step.params.get('event_voice'))
                )
                if uses_shape and 'shape' in step.params:
                    shape_param = step.params['shape']
                    # 解析shape数组，格式如[1,1,1,1]
                    if shape_param.startswith('[') and shape_param.endswith(']'):
                        inner = shape_param[1:-1]
                        items = [item.strip() for item in inner.split(',') if item.strip()]
                        channel_count = len(items) if items else 1
                    break
            
            # 基础指令：START → SETVRCONFIG（固定顺序）→ FREEWAKEUP → STRATEGY
            lines.append(f"[TSA]START        {channel_count}")

            is_multi_turn = any(step.params.get('dialog') == 'end' for step in case.steps)

            lang_to_use = self.lang
            link_type = None

            if is_multi_turn:
                # 多轮：不在 case 头合并 vr*；每段 voice 前由 _emit_multi_turn_voice_preamble 按行输出
                pass
            else:
                # 单轮 / 单 case 单段：保留原逻辑（从全部 step 收集 VR，兼容旧 YAML）
                free_wakeup = "0"
                for step in case.steps:
                    if step.step_type == 'voice' and 'freeWakeup' in step.params:
                        free_wakeup = step.params['freeWakeup']
                        break

                vr_wakeup_alias = None
                vr_wakeup_word = None
                vr_lang = None
                vr_scene_option = None
                vr_scene_option_seen = False

                for step in case.steps:
                    if 'vrWakeupAlias' in step.params:
                        vr_wakeup_alias = step.params['vrWakeupAlias']
                    if 'vrWakeupWord' in step.params:
                        vr_wakeup_word = step.params['vrWakeupWord']
                    if 'vrLang' in step.params:
                        vr_lang = step.params['vrLang']
                    if 'vrSceneOption' in step.params:
                        vr_scene_option = step.params['vrSceneOption']
                        vr_scene_option_seen = True
                    if step.step_type == 'voice' and 'linkType' in step.params and link_type is None:
                        link_type = step.params['linkType']

                lang_to_use = vr_lang if vr_lang else self.lang

                if vr_lang:
                    lines.append(f"[SET]SETVRCONFIG  DIALOGUE_LANGUAGE {vr_lang}")
                if vr_scene_option_seen:
                    lines.append(f"[SET]SETVRCONFIG  WAKEUP_KEYWORD_OPTION {vr_scene_option}")
                if vr_wakeup_alias:
                    lines.append(f"[SET]SETVRCONFIG  WAKEUP_ALIAS {vr_wakeup_alias} {lang_to_use}")
                if vr_wakeup_word:
                    lines.append(f"[SET]SETVRCONFIG  WAKEUP_ENABLE {vr_wakeup_word} {lang_to_use}")

                if link_type is not None:
                    lines.append(f"[SET]LINK_TYPE    {link_type}")

                lines.append(f"[TSA]FREEWAKEUP   {free_wakeup}")
                lines.append(f"[TSA]STRATEGY     {case.strategy}")
            
            # 检查是否有vrSeatSignal参数
            vr_seat_signal = None
            for step in case.steps:
                if step.step_type == 'voice' and 'vrSeatSignal' in step.params:
                    vr_seat_signal = step.params['vrSeatSignal']
                    break
            
            # 如果有vrSeatSignal参数，添加SET_PARAM指令（放在SETVRCONFIG之后）
            if vr_seat_signal:
                lines.append(f"[TSA]SET_PARAM    AIBS_PARAM_SEAT_SIGNAL {vr_seat_signal}")
            
            # 输入事件（如果有）
            if case.input_events:
                for event in case.input_events:
                    # 检查是否有该事件的参数
                    event_params = case.event_params.get(event, "")
                    if event_params:
                        lines.append(f"[TSA]INPUTEVENT   {event}    {event_params}")
                    else:
                        lines.append(f"[TSA]INPUTEVENT   {event}")
            
            # 检查是否有voice步骤
            has_voice_step = any(step.step_type == 'voice' for step in case.steps)
            
            multi_turn_stop_emitted = False
            # 已在步骤循环内输出过 [TSA]STOP（如 *event、*voice 单轮），避免末尾再补一条重复 STOP
            case_inner_stop_emitted = False
            # 多轮：记录最近一次下发的 DIALOGUE_LANGUAGE，避免与 *event 行重复 SET
            multi_turn_last_vr_lang: Optional[str] = None
            # 记录最近一次下发的连接类型，避免重复 LINK_TYPE
            last_link_type: Optional[str] = link_type
            
            # 处理每个步骤
            for idx, step in enumerate(case.steps):
                if step.step_type == 'voice':
                    if 'linkType' in step.params:
                        step_link_type = step.params['linkType']
                        if step_link_type != last_link_type:
                            lines.append(f"[SET]LINK_TYPE    {step_link_type}")
                            last_link_type = step_link_type

                    # 处理断言（[SWU], [LASR], [API]等）
                    # 先检查是否需要添加GET_VR_CONFIG指令（在第一个VRConfig断言之前）
                    need_get_vr_config = False
                    for assertion in step.assertions:
                        parsed_assertion = self._parse_assertion_line(assertion)
                        if parsed_assertion:
                            assert_type, assert_content = parsed_assertion
                            if assert_type == 'API' and 'wakeupWordList' in assert_content:
                                need_get_vr_config = True
                                break
                    
                    # 分离需要在DATA之前和之后的断言
                    pre_data_assertions = []  # 在DATA之前的断言（如setVRWakeupAliasCode）
                    post_data_assertions = []  # 在DATA之后的断言（如wakeupWordList等）
                    
                    for assertion in step.assertions:
                        # 解析断言类型和内容
                        parsed_assertion = self._parse_assertion_line(assertion)
                        if parsed_assertion:
                            assert_type, assert_content = parsed_assertion

                            # 根据断言类型映射到对应的EXP指令
                            # SWU -> SpeechWakeup, LASR -> localASRResult, API -> VRConfig, HIC -> HICARWakeup
                            assert_type_mapping = {
                                'SWU': 'SpeechWakeup',
                                'LASR': 'localASRResult',
                                'API': 'VRConfig',
                                'HIC': 'HICARWakeup'
                            }
                            
                            mapped_type = assert_type_mapping.get(assert_type, assert_type)
                            
                            # 对于API类型，如果包含多个字段（用分号分隔），需要拆分
                            if assert_type == 'API' and ';' in assert_content:
                                # 拆分成多个字段
                                fields = [f.strip() for f in assert_content.split(';')]
                                for field in fields:
                                    if field.startswith('setVRWakeupAliasCode'):
                                        # setVRWakeupAliasCode应该在DATA之前，且不添加通道号
                                        pre_data_assertions.append({
                                            'type': mapped_type,
                                            'content': field,
                                            'add_channel': False
                                        })
                                    else:
                                        # 其他字段（如wakeupWordList）在DATA之后
                                        post_data_assertions.append({
                                            'type': mapped_type,
                                            'content': field,
                                            'add_channel': True
                                        })
                            else:
                                # 单个字段的断言，根据类型决定位置
                                if assert_type == 'API' and 'setVRWakeupAliasCode' in assert_content:
                                    # setVRWakeupAliasCode在DATA之前，且不添加通道号
                                    pre_data_assertions.append({
                                        'type': mapped_type,
                                        'content': assert_content,
                                        'add_channel': False
                                    })
                                else:
                                    # 其他断言在DATA之后
                                    post_data_assertions.append({
                                        'type': mapped_type,
                                        'content': assert_content,
                                        'add_channel': True
                                    })
                    
                    # 生成DATA之前的断言
                    for assert_info in pre_data_assertions:
                        formatted_content = assert_info['content']
                        lines.append(f"[EXP]{assert_info['type']}     {formatted_content}")

                    step_nlp_lang = lang_to_use
                    if is_multi_turn:
                        step_nlp_lang, multi_turn_last_vr_lang = self._emit_multi_turn_voice_preamble(
                            lines, step, self.lang, case.strategy, multi_turn_last_vr_lang
                        )

                    # 检查是否有hmi参数，如果有，先输出EVENT命令
                    if 'hmi' in step.params:
                        hmi_file = step.params['hmi']
                        lines.append(f"[TSA]EVENT        {hmi_file}")

                    is_voi_case = (self.default_msgtype == "VOI")
                    if is_voi_case:
                        voi_payload = self._build_voi_open_voice_input_payload(step.params)
                        lines.append(f"[VOI]OPEN_VOICE_INPUT {voi_payload}")
                    
                    # 处理voice指令，转换为[TSA]DATA
                    audio_file = step.content
                    # 根据shape参数计算frame值（通道数 * 320），如果没有shape则使用默认320
                    frame_value = 320
                    if 'shape' in step.params:
                        shape_param = step.params['shape']
                        if shape_param.startswith('[') and shape_param.endswith(']'):
                            inner = shape_param[1:-1]
                            items = [item.strip() for item in inner.split(',') if item.strip()]
                            channel_count = len(items) if items else 1
                            frame_value = channel_count * 320
                    # delay：显式参数优先，否则按 strategy 在线/离线默认
                    strat_v = step.params.get('strategy', case.strategy)
                    delay_val = self._delay_for_audio(strat_v, step.params)
                    lines.append(f"[TSA]DATA         {audio_file}    frame={frame_value}    delay={delay_val}")
                    if not is_multi_turn:
                        if is_voi_case:
                            lines.append("[VOI]CLOSE_VOICE_INPUT")
                        lines.append("[TSA]STOP")
                        case_inner_stop_emitted = True
                        self._emit_step_nlp_expects(lines, step, step_nlp_lang, case.strategy)
                    else:
                        # 多轮：DATA → STOP → NLP（与手工 MGO 时序一致）
                        if is_voi_case:
                            lines.append("[VOI]CLOSE_VOICE_INPUT")
                        lines.append("[TSA]STOP")
                        case_inner_stop_emitted = True
                        multi_turn_stop_emitted = True
                        self._emit_step_nlp_expects(lines, step, step_nlp_lang, case.strategy)
                    
                    # 生成DATA之后的断言（连续 EXP 仅第一条带 timeout）
                    # 对于VRConfig类型，在第一个wakeupWordList断言前添加GET_VR_CONFIG指令
                    for post_idx, assert_info in enumerate(post_data_assertions):
                        if assert_info['type'] == 'VRConfig' and need_get_vr_config and 'wakeupWordList' in assert_info['content']:
                            lines.append("[TSA]GET_VR_CONFIG GET_WAKEUP_WORD")
                            need_get_vr_config = False  # 只添加一次
                        
                        # 为断言内容添加通道号（如果需要）
                        channel_id = self.default_channel
                        if assert_info['add_channel']:
                            # 如果断言内容已经包含通道号（如[0]text:...），则保留；否则添加通道号
                            if assert_info['content'].startswith('[') and ']' in assert_info['content']:
                                # 检查是否是通道号格式
                                content_channel_end = assert_info['content'].index(']')
                                content_channel = assert_info['content'][1:content_channel_end]
                                if content_channel.isdigit():
                                    # 已经有通道号，直接使用
                                    formatted_content = assert_info['content']
                                else:
                                    # 不是通道号，添加通道号
                                    formatted_content = f"[{channel_id}]{assert_info['content']}"
                            else:
                                # 没有通道号，添加通道号
                                formatted_content = f"[{channel_id}]{assert_info['content']}"
                        else:
                            # 不添加通道号
                            formatted_content = assert_info['content']
                        
                        timeout_suffix = "    <timeout=5>" if post_idx == 0 else ""
                        lines.append(f"[EXP]{assert_info['type']}    {formatted_content}{timeout_suffix}")
                
                elif step.step_type == 'fileEvent':
                    # *event:...;voice:... 时音频单独走 [TSA]DATA，与 EVENT 分离
                    event_voice = (step.params.get('event_voice') or '').strip()
                    strat_fe = step.params.get('strategy', case.strategy)
                    # 多轮且本步无内联 voice：EVENT → tts 期望，不在此处 STOP（留给后续 *voice）
                    if is_multi_turn and not event_voice:
                        if 'vrLang' in step.params:
                            lines.append(
                                f"[SET]SETVRCONFIG  DIALOGUE_LANGUAGE {step.params['vrLang']}"
                            )
                            multi_turn_last_vr_lang = step.params['vrLang']
                            lang_to_use = step.params['vrLang']
                        lines.append(f"[TSA]EVENT        {step.content}")
                        fe_lang = lang_to_use
                        if 'vrLang' in step.params:
                            fe_lang = step.params['vrLang']
                        self._emit_step_nlp_expects(lines, step, fe_lang, strat_fe)
                    else:
                        lines.append(f"[TSA]EVENT        {step.content}")
                        if event_voice:
                            frame_value = 320
                            if 'shape' in step.params:
                                shape_param = step.params['shape']
                                if shape_param.startswith('[') and shape_param.endswith(']'):
                                    inner = shape_param[1:-1]
                                    items = [item.strip() for item in inner.split(',') if item.strip()]
                                    ch = len(items) if items else 1
                                    frame_value = ch * 320
                            delay_val = self._delay_for_audio(strat_fe, step.params)
                            lines.append(
                                f"[TSA]DATA         {event_voice}    frame={frame_value}    delay={delay_val}"
                            )
                        lines.append("[TSA]STOP")
                        case_inner_stop_emitted = True
                        multi_turn_stop_emitted = True
                        fe_lang = lang_to_use
                        if 'vrLang' in step.params:
                            fe_lang = step.params['vrLang']
                        self._emit_step_nlp_expects(lines, step, fe_lang, strat_fe)
                
                elif step.step_type == 'eventList':
                    # 列表文件每行一条 JSON → 多条 [TSA]EVENT，可选 ;voice: 再接 DATA
                    list_path = (step.content or '').strip()
                    evt_lines: List[str] = []
                    try:
                        evt_lines = self._read_event_list_lines(list_path)
                    except FileNotFoundError as e:
                        print(f"⚠️ {e}")
                    event_voice_el = (step.params.get('event_voice') or '').strip()
                    strat_el = step.params.get('strategy', case.strategy)
                    # 单轮时 DIALOGUE_LANGUAGE 已在 Case 头合并下发，此处仅多轮需补发
                    if 'vrLang' in step.params and is_multi_turn:
                        lines.append(
                            f"[SET]SETVRCONFIG  DIALOGUE_LANGUAGE {step.params['vrLang']}"
                        )
                        lang_to_use = step.params['vrLang']
                        multi_turn_last_vr_lang = step.params['vrLang']
                    for raw_json in evt_lines:
                        lines.append(f"[TSA]EVENT        {raw_json}")
                    # 同指令行中 event: 的 JSON 文件路径，在列表 EVENT 之后追加一条 [TSA]EVENT
                    chained_ev = (step.params.get('chained_event_path') or '').strip()
                    if chained_ev:
                        lines.append(f"[TSA]EVENT        {chained_ev}")
                    if event_voice_el:
                        frame_value = 320
                        if 'shape' in step.params:
                            shape_param = step.params['shape']
                            if shape_param.startswith('[') and shape_param.endswith(']'):
                                inner = shape_param[1:-1]
                                items = [item.strip() for item in inner.split(',') if item.strip()]
                                ch = len(items) if items else 1
                                frame_value = ch * 320
                        delay_val = self._delay_for_audio(strat_el, step.params)
                        lines.append(
                            f"[TSA]DATA         {event_voice_el}    frame={frame_value}    delay={delay_val}"
                        )
                    lines.append("[TSA]STOP")
                    case_inner_stop_emitted = True
                    multi_turn_stop_emitted = True
                    el_lang = lang_to_use
                    if 'vrLang' in step.params:
                        el_lang = step.params['vrLang']
                    self._emit_step_nlp_expects(lines, step, el_lang, strat_el)
                
                elif step.step_type == 'inputEvent':
                    # 检查是否是中间的inputEvent（不在Case开头的）
                    is_mid_event = step.params.get('is_mid_event', False)
                    
                    if is_mid_event:
                        # 中间的inputEvent需要在此位置输出
                        events = self._parse_event_list(step.content)
                        # 提取带事件名前缀的参数
                        event_params_map = self._extract_event_params(step.params, events)
                        for event in events:
                            event_params = event_params_map.get(event, "")
                            if event_params:
                                lines.append(f"[TSA]INPUTEVENT   {event}    {event_params}")
                            else:
                                lines.append(f"[TSA]INPUTEVENT   {event}")
                    # 如果不是中间的inputEvent，它的事件已经在case.input_events中处理了
                    
                    # 处理关联的text
                    text_content = step.params.get('text', '')
                    if text_content:
                        lines.append(f"[TSA]TEXT         {text_content}")
                    
                    # 处理关联的callbackEvent（*inputEvent:[...];callbackEvent:[...] 格式）
                    if step.params.get('has_callback'):
                        callback_name = step.params.get('callback_name', 'default')
                        callback_data = self._build_callback_data(step.params)
                        if callback_data:
                            lines.append(f"[TSA]CALLBACK     {callback_name}    {callback_data}")
                        else:
                            lines.append(f"[TSA]CALLBACK     {callback_name}")
                    
                    if step.expect:
                        # 转换 tts 相关字段（携带语言和策略）
                        converted_expect = self._convert_tts_to_ttsinfo(step.expect, lang_to_use, case.strategy)
                        lines.append(f"[EXP]NLPResult    {converted_expect}    <timeout=5>")
                
                elif step.step_type == 'text':
                    # 检查是否有hmi参数，如果有，先输出EVENT命令
                    if 'hmi' in step.params:
                        hmi_file = step.params['hmi']
                        lines.append(f"[TSA]EVENT        {hmi_file}")
                    
                    lines.append(f"[TSA]TEXT         {step.content}")
                    if step.expect:
                        # 转换 tts 相关字段（携带语言和策略）
                        converted_expect = self._convert_tts_to_ttsinfo(step.expect, lang_to_use, case.strategy)
                        lines.append(f"[EXP]NLPResult    {converted_expect}    <timeout=5>")
                
                elif step.step_type == 'callbackEvent':
                    # 构建CALLBACK参数
                    callback_data = self._build_callback_data(step.params)
                    if callback_data:
                        lines.append(f"[TSA]CALLBACK     {step.content}    {callback_data}")
                    else:
                        lines.append(f"[TSA]CALLBACK     {step.content}")
                    
                    if step.expect:
                        # 转换 tts 相关字段（携带语言和策略）
                        converted_expect = self._convert_tts_to_ttsinfo(step.expect, lang_to_use, case.strategy)
                        lines.append(f"[EXP]NLPResult    {converted_expect}    <timeout=5>")
            
            # 结束指令
            # 如果没有voice步骤且步骤循环内未输出过 STOP，补一条 [TSA]STOP
            if not has_voice_step and not case_inner_stop_emitted:
                lines.append("[TSA]STOP")
            # 多轮对话：若尚未因 *fileEvent 输出过 STOP，则在末尾补一次
            elif is_multi_turn and not multi_turn_stop_emitted:
                lines.append("[TSA]STOP")
            # 如果有voice步骤但不是多轮对话，STOP已经在voice处理中输出了，这里不需要再输出
            lines.append("<<<")
            lines.append("")
        
        content = '\n'.join(lines)
        
        # 写入文件
        if output_path:
            os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ 成功生成MGO文件: {output_path}")
            print(f"   - Case数量: {len(cases)}")
        
        return content
    
    def _build_callback_data(self, params: Dict[str, str]) -> str:
        """
        构建CALLBACK数据参数
        
        从params中提取default.data.xxx格式的参数
        """
        callback_parts = []
        
        for key, value in params.items():
            # 跳过非数据参数
            if key in ['strategy', 'dialog']:
                continue
            
            # 处理default.data.xxx格式的参数
            if key.startswith('default.'):
                # 转换格式: default.data.result.code -> data.result.code
                short_key = key.replace('default.', '', 1)
                callback_parts.append(f"{short_key}:{value}")
        
        return ';'.join(callback_parts)
    
    def convert(self, yaml_path: str, output_path: str) -> str:
        """执行转换"""
        print(f"📖 读取YAML文件: {yaml_path}")
        cases = self.parse_yaml_file(yaml_path)
        print(f"   - 解析到 {len(cases)} 个测试用例")
        
        # 如果输出路径是目录，根据输入文件名生成输出文件名
        if os.path.isdir(output_path) or output_path.endswith('/') or output_path.endswith('\\') or output_path.endswith('.'):
            # 获取输入文件名（不含扩展名）
            input_basename = os.path.basename(yaml_path)
            input_name_without_ext = os.path.splitext(input_basename)[0]
            # 生成输出文件路径
            output_path = os.path.join(output_path.rstrip('/\\.'), f"{input_name_without_ext}.mgo")
            print(f"📝 输出路径是目录，自动生成文件名: {output_path}")
        
        return self.generate_mgo(cases, output_path)


def batch_convert(input_dir: str, output_dir: str, lang: str, appid: str):
    """
    批量转换目录下的所有YAML文件
    
    Args:
        input_dir: 输入目录路径
        output_dir: 输出目录路径
        lang: 语言代码
        appid: 应用ID
    """
    import glob
    
    # 查找所有YAML文件
    yaml_files = glob.glob(os.path.join(input_dir, '**/*.yaml'), recursive=True)
    
    if not yaml_files:
        print(f"❌ 在目录 {input_dir} 中未找到YAML文件")
        return
    
    print(f"📁 找到 {len(yaml_files)} 个YAML文件")
    
    success_count = 0
    fail_count = 0
    total_cases = 0
    
    converter = YamlToMgoConverter(lang=lang, appid=appid)
    
    for yaml_path in yaml_files:
        try:
            # 计算相对路径并生成输出路径
            rel_path = os.path.relpath(yaml_path, input_dir)
            output_path = os.path.join(output_dir, rel_path.replace('.yaml', '.mgo'))
            
            # 确保输出目录存在
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # 转换
            cases = converter.parse_yaml_file(yaml_path)
            converter.generate_mgo(cases, output_path)
            
            success_count += 1
            total_cases += len(cases)
            
        except Exception as e:
            print(f"   ⚠️ 转换失败: {yaml_path}, 错误: {e}")
            fail_count += 1
    
    print(f"\n📊 批量转换完成:")
    print(f"   - 成功: {success_count} 个文件")
    print(f"   - 失败: {fail_count} 个文件")
    print(f"   - 总Case数: {total_cases} 个")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='将老版本NLU测试用例(YAML格式)转换为新版本MGO格式',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 单文件转换
  python yaml2mgo_converter.py input.yaml output.mgo
  python yaml2mgo_converter.py nlu/cmn/NAVI/NAVI_cx/Offline/查询当前位置_Offline.yaml navi.mgo
  python yaml2mgo_converter.py input.yaml output.mgo --lang eng --appid com.custom.app
  
  # 批量转换（使用 --batch 参数）
  python yaml2mgo_converter.py nlu/cmn/ output_mgo/ --batch
  python yaml2mgo_converter.py nlu/ mgo_output/ --batch --lang cmn
        """
    )
    
    parser.add_argument('input', help='输入YAML文件或目录路径')
    parser.add_argument('output', help='输出MGO文件或目录路径')
    parser.add_argument('--lang', default='cmn', help='语言代码 (默认: cmn)')
    parser.add_argument('--appid', default='com.autoai.vr.service_vrassistant', 
                        help='应用ID (默认: com.autoai.vr.service_vrassistant)')
    parser.add_argument('--batch', action='store_true', 
                        help='批量模式：转换目录下所有YAML文件')
    
    args = parser.parse_args()
    
    try:
        if args.batch:
            # 批量转换模式
            if not os.path.isdir(args.input):
                print(f"❌ 批量模式需要输入目录，但 {args.input} 不是目录")
                sys.exit(1)
            batch_convert(args.input, args.output, args.lang, args.appid)
        else:
            # 单文件转换模式
            converter = YamlToMgoConverter(lang=args.lang, appid=args.appid)
            converter.convert(args.input, args.output)
        
        print("🎉 转换完成!")
    except Exception as e:
        print(f"❌ 转换失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

