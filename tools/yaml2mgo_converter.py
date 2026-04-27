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
import argparse
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field


@dataclass
class DialogStep:
    """对话步骤"""
    step_type: str  # 'inputEvent', 'text', 'callbackEvent'
    content: str    # 主要内容（text文本、事件名等）
    params: Dict[str, str] = field(default_factory=dict)  # 参数（strategy, dialog等）
    expect: str = ""  # NLP期望结果


@dataclass
class TestCase:
    """测试用例"""
    comment: str = ""  # 注释
    steps: List[DialogStep] = field(default_factory=list)
    strategy: str = "0"  # 默认策略
    input_events: List[str] = field(default_factory=list)  # 输入事件列表


class YamlToMgoConverter:
    """YAML到MGO格式转换器"""
    
    def __init__(self, lang: str = "cmn", appid: str = "com.autoai.vr.service_vrassistant"):
        self.lang = lang
        self.appid = appid
        self.default_channel = "0"
        self.default_msgtype = "NLP"
        self.case_brief = ""
        
    def parse_yaml_file(self, yaml_path: str) -> List[TestCase]:
        """解析YAML文件，返回测试用例列表"""
        if not os.path.exists(yaml_path):
            raise FileNotFoundError(f"YAML文件不存在: {yaml_path}")
        
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
                    
                    # 如果不在多轮对话中，根据其他规则判断
                    elif not in_multi_turn_dialog:
                        # 如果当前没有Case，创建新Case
                        if current_case is None:
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
            elif stripped.startswith('skill:') or stripped.startswith('intention:'):
                # 隐式断言（以skill:或intention:开头，没有[NLP]前缀）
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
        
        # 处理剩余部分：可能是参数、也可能是inline expect
        for i, part in enumerate(parts[1:], 1):
            part = part.strip()
            if not part:
                continue
            
            # 检查是否是inline expect（以skill:开头的部分）
            if part.startswith('skill:'):
                inline_expect = part
            else:
                # 解析为参数
                params.update(self._parse_params(part))
        
        # 解析主内容
        if main_part.startswith('inputEvent:'):
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
        
        elif main_part.startswith('text:'):
            text = main_part[5:].strip()
            step = DialogStep(
                step_type='text',
                content=text,
                expect=inline_expect  # 设置内联expect
            )
        
        elif main_part.startswith('callbackEvent:'):
            # 格式: callbackEvent:[default] 或 callbackEvent:[EventName]
            match = re.match(r'callbackEvent:\[([^\]]*)\]', main_part)
            if match:
                callback_name = match.group(1)
                step = DialogStep(
                    step_type='callbackEvent',
                    content=callback_name
                )
        
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
    
    def _parse_event_list(self, event_str: str) -> List[str]:
        """解析事件列表字符串"""
        # 格式: Event1,Event2,Event3
        events = [e.strip() for e in event_str.split(',')]
        return [e for e in events if e]
    
    def _filter_expect_fields(self, expect: str) -> str:
        """
        过滤expect字符串中的指定字段
        
        过滤掉: displayNotify, ttsID, datavpa 这三个字段
        
        Args:
            expect: 原始expect字符串，格式如 "skill:xxx;intention:xxx;displayNotify:xxx;..."
            
        Returns:
            过滤后的expect字符串
        """
        if not expect:
            return expect
        
        # 需要过滤的字段列表
        filter_fields = ['displayNotify', 'ttsID', 'datavpa']
        
        # 按分号分割键值对
        parts = expect.split(';')
        filtered_parts = []
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
            # 检查是否是需要过滤的字段
            should_filter = False
            for field_name in filter_fields:
                if part.startswith(f"{field_name}:"):
                    should_filter = True
                    break
            
            if not should_filter:
                filtered_parts.append(part)
        
        return ';'.join(filtered_parts)
    
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
        lines.append(f'[SYS]PULL         AIBSServer {self.lang}' + ' {"brand":"0"}')
        lines.append(f'[SYS]PULL         LCSEngine {self.lang}')
        lines.append(f'[SYS]PULL         SpeechEngine {self.lang}')

        lines.append(f"[TSA]CREATE       {self.lang} {self.appid}")
        lines.append(f"[SET]CREATE       {self.lang} com.autoai.vrsetting")
        lines.append(f"[SET]SETVRCONFIG  DIALOGUE_LANGUAGE {self.lang}")
        lines.append("<<<")
        lines.append("")
        
        # 生成TEARDOWN块
        lines.append(">>> TEARDOWN")
        lines.append("[TSA]FREE")
        lines.append("[SET]FREE")
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
            
            # 基础指令
            lines.append("[TSA]START        1")
            lines.append("[TSA]FREEWAKEUP   1")
            lines.append(f"[TSA]STRATEGY     {case.strategy}")
            
            # 输入事件（如果有）
            if case.input_events:
                for event in case.input_events:
                    lines.append(f"[TSA]INPUTEVENT   {event}")
            
            # 处理每个步骤
            for step in case.steps:
                if step.step_type == 'inputEvent':
                    # 检查是否是中间的inputEvent（不在Case开头的）
                    is_mid_event = step.params.get('is_mid_event', False)
                    
                    if is_mid_event:
                        # 中间的inputEvent需要在此位置输出
                        events = self._parse_event_list(step.content)
                        for event in events:
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
                        filtered_expect = self._filter_expect_fields(step.expect)
                        lines.append(f"[EXP]NLPResult    {filtered_expect}    <timeout=2>")
                
                elif step.step_type == 'text':
                    lines.append(f"[TSA]TEXT         {step.content}")
                    if step.expect:
                        filtered_expect = self._filter_expect_fields(step.expect)
                        lines.append(f"[EXP]NLPResult    {filtered_expect}    <timeout=2>")
                
                elif step.step_type == 'callbackEvent':
                    # 构建CALLBACK参数
                    callback_data = self._build_callback_data(step.params)
                    if callback_data:
                        lines.append(f"[TSA]CALLBACK     {step.content}    {callback_data}")
                    else:
                        lines.append(f"[TSA]CALLBACK     {step.content}")
                    
                    if step.expect:
                        filtered_expect = self._filter_expect_fields(step.expect)
                        lines.append(f"[EXP]NLPResult    {filtered_expect}    <timeout=2>")
            
            # 结束指令
            lines.append("[TSA]STOP")
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

