import os
import re
import sys
import yaml

# 定义特殊的内联字典类，用于触发单行输出
class FlowDict(dict):
    pass


HEADER = """# ===================================================================================
# Mango Solution 现代化 YAML 配置文件
# 架构: project_config，retry，xdist_workers支持三级继承 (Global -> Scenario -> Suite)
# ===================================================================================
"""


def _parse_enable_list(value):
    return [v.strip() for v in value.split(',') if v.strip()]


def _parse_owner_list(value):
    return [v.strip() for v in value.split(',') if v.strip()]


def _parse_bool_from_yes_no(value):
    return True if value.lower() == 'yes' else False


def _parse_concurrent_controller(value):
    scheduler = {
        "global_max_workers": None,
        "online_max_workers": None,
        "cp_max_workers": None,
        "offline_max_workers": None,
    }
    key_map = {
        "MAX": "global_max_workers",
        "ONLINE": "online_max_workers",
        "CP": "cp_max_workers",
        "OFFLINE": "offline_max_workers",
    }

    normalized = value.replace(";", ",")
    for item in [x.strip() for x in normalized.split(",") if x.strip()]:
        if "-" in item:
            key, raw_val = item.split("-", 1)
        elif ":" in item:
            key, raw_val = item.split(":", 1)
        else:
            continue
        mapped_key = key_map.get(key.strip().upper())
        if not mapped_key:
            continue
        raw_val = raw_val.strip()
        if mapped_key == "offline_max_workers" and raw_val.lower() == "auto":
            scheduler[mapped_key] = "auto"
        else:
            try:
                scheduler[mapped_key] = int(raw_val)
            except ValueError:
                scheduler[mapped_key] = raw_val

    return scheduler


def _ordered_scenario_dict(current_scenario):
    ordered_scenario = {}
    for key in ["name", "project_config", "owner", "retry", "xdist_workers"]:
        if key in current_scenario:
            ordered_scenario[key] = current_scenario[key]
    ordered_scenario["suites"] = current_scenario.get("suites", [])
    return ordered_scenario


def _build_initial_yaml_data():
    return {
        "global": {
            "environment": None,
            "global_max_workers": None,
            "online_max_workers": None,
            "cp_max_workers": None,
            "offline_max_workers": None,
            "enable": [],
            "project_config": None,
            "retry": 0,
            "xdist_workers": 0,
        },
        "scenarios": []
    }

def parse_txt_to_yaml(txt_file_path, output_yaml_path):
    if not os.path.exists(txt_file_path):
        print(f"Error: 找不到文件 {txt_file_path}")
        return

    # 初始化 YAML 数据结构
    yaml_data = _build_initial_yaml_data()

    current_scenario = None
    current_suite = None
    in_define_block = False

    with open(txt_file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    for line_num, line in enumerate(lines):
        raw_line = line.strip()
        if not raw_line or raw_line.startswith('@'):
            continue
        data = raw_line.split('@')[0].strip()
        if not data:
            continue

        # 1. 解析全局配置
        if not in_define_block and data != 'DEFINE':
            if ':' in data:
                key, value = data.split(':', 1)
                key = key.strip().lower()
                value = value.strip()
                if key == 'project':
                    yaml_data['global']['environment'] = value
                elif key == 'concurrent_controller':
                    yaml_data['global'].update(_parse_concurrent_controller(value))
                elif key == 'enable':
                    yaml_data['global']['enable'] = _parse_enable_list(value)
                elif key in ['needload', 'clean_boloo_workspace']:
                    # 这里保留解析能力，当前 YAML 结构不输出这两个字段
                    _parse_bool_from_yes_no(value)
            continue

        # 2. 场景解析块 (DEFINE ... END)
        if data == 'DEFINE':
            in_define_block = True
            current_scenario = {}
            continue

        if data == 'END':
            in_define_block = False
            if current_scenario and "name" in current_scenario:
                yaml_data['scenarios'].append(_ordered_scenario_dict(current_scenario))
            current_scenario = None
            current_suite = None
            continue

        if in_define_block:
            if data.startswith('NAME'):
                current_scenario['name'] = data.split(':', 1)[1].strip()
            elif data.startswith('CONFIG'):
                current_scenario['project_config'] = data.split(':', 1)[1].strip()
            elif data.startswith('OWNER'):
                current_scenario['owner'] = _parse_owner_list(data.split(':', 1)[1])
            
            # 解析 Suite，使用 FlowDict 来强制单行
            elif data.startswith('SUITE'):
                if 'suites' not in current_scenario:
                    current_scenario['suites'] = []

                suite_content = data.split(':', 1)[1].strip()
                tags = re.findall(r'\[([^\[\]]+)\]', suite_content)
                clean_content = re.sub(r'\[[^\[\]]+\]', '', suite_content).strip(',')
                parts = [p.strip() for p in clean_content.split(',') if p.strip()]
                
                current_suite = FlowDict()
                
                # 老 solution 的第一个字段恒为 suite runner（例如 NANO），新 YAML 不再输出
                if len(parts) > 1: current_suite["config"] = parts[1]
                if len(parts) > 2: current_suite["case"] = parts[2]
                if len(parts) > 3: current_suite['parameter'] = parts[3]
                if len(parts) > 4: current_suite['steps'] = parts[4]
                if tags: current_suite['tag'] = tags

                current_scenario['suites'].append(current_suite)

            # 解析 ARG_ 附加属性
            elif data.startswith('ARG_') and current_suite is not None:
                key, value = data.split(':', 1)
                key = key.strip()
                value = value.strip()
                
                if key == 'ARG_ABSTRACT': current_suite['abstract'] = value
                elif key == 'ARG_RETRY': current_suite['retry'] = int(value)
                elif key == 'ARG_WORKERS': current_suite['xdist_workers'] = int(value)
                elif key == 'ARG_PROJECT': current_suite['project_config'] = value

    # 3. 导出并美化 YAML
    class MyDumper(yaml.Dumper):
        def increase_indent(self, flow=False, indentless=False):
            return super(MyDumper, self).increase_indent(flow, False)
            
    # 注册 FlowDict 处理器，强制在一行输出
    def flow_dict_representer(dumper, data):
        return dumper.represent_mapping('tag:yaml.org,2002:map', data, flow_style=True)
        
    def list_representer(dumper, data):
        if len(data) > 0 and isinstance(data[0], str):
            return dumper.represent_sequence('tag:yaml.org,2002:seq', data, flow_style=True)
        return dumper.represent_sequence('tag:yaml.org,2002:seq', data, flow_style=False)
        
    yaml.add_representer(FlowDict, flow_dict_representer, Dumper=MyDumper)
    yaml.add_representer(list, list_representer, Dumper=MyDumper)

    # 核心：width=float("inf") 告诉 PyYAML 永远不要自动换行
    yaml_str = yaml.dump(
        yaml_data, 
        Dumper=MyDumper, 
        default_flow_style=False, 
        allow_unicode=True, 
        sort_keys=False,
        width=float("inf")  
    )

    # ===============================
    # 排版美化微调 (满足强迫症需求)
    # ===============================
    yaml_str = yaml_str.replace('- {config:', '- { config:')
    yaml_str = yaml_str.replace('- {retry:', '- { retry:')
    yaml_str = yaml_str.replace('- {xdist_workers:', '- { xdist_workers:')
    yaml_str = yaml_str.replace('}', ' }')
    
    # 1. 在 scenarios: 上方增加一个空行，将 global 块与 scenarios 块彻底隔开
    yaml_str = yaml_str.replace('\nscenarios:', '\n\nscenarios:')
    
    # 2. 为所有的 `- name:` (场景名) 上方增加空行，用来分割不同的场景
    yaml_str = re.sub(r'\n(\s+- name:)', r'\n\n\1', yaml_str)
    
    # 3. 剔除 scenarios: 和第一个场景 `- name:` 之间被多加的空行
    yaml_str = yaml_str.replace('scenarios:\n\n  - name:', 'scenarios:\n  - name:')

    with open(output_yaml_path, 'w', encoding='utf-8') as f:
        f.write(HEADER)
        f.write(yaml_str)

    print(f"转换成功！YAML 文件已保存至: {output_yaml_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("用法: python3 tools/solution_convert.py <输入txt> <输出yaml>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]
    parse_txt_to_yaml(input_file, output_file)