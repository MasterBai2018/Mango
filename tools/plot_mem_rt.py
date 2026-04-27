#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用pyecharts绘制多个版本的内存和DRT对比曲线

使用方法:
    python3 plot_mem_rt.py [日志文件...]

文件命名格式:
    - 内存日志: mem-{版本号}.log (例如: mem-5.5.1.28.log, mem-pstt-5.6.0.8.log)
    - RT日志:   rt-{版本号}.log  (例如: rt-5.5.1.28.log, rt-pstt-5.6.0.8.log)

示例:
    # 绘制两个版本的内存和DRT对比
    python3 plot_mem_rt.py mem-5.5.1.28.log mem-5.6.0.8.log rt-5.5.1.28.log rt-5.6.0.8.log

    # 只绘制RT对比
    python3 plot_mem_rt.py rt-5.5.1.28.log rt-5.6.0.8.log

    # 只绘制内存对比
    python3 plot_mem_rt.py mem-5.5.1.28.log mem-5.6.0.8.log

    # 绘制多个版本对比
    python3 plot_mem_rt.py mem-v1.log mem-v2.log mem-v3.log rt-v1.log rt-v2.log rt-v3.log
"""

import re
import os
import sys
import argparse
from pyecharts import options as opts
from pyecharts.charts import Line, Page
from pyecharts.globals import ThemeType


def parse_args():
    """
    解析命令行参数
    """
    parser = argparse.ArgumentParser(
        description="使用pyecharts绘制多个版本的内存和DRT对比曲线",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
文件命名格式:
  - 内存日志: mem-{版本号}.log (例如: mem-5.5.1.28.log, mem-pstt-5.6.0.8.log)
  - RT日志:   rt-{版本号}.log  (例如: rt-5.5.1.28.log, rt-pstt-5.6.0.8.log)

示例:
  # 绘制两个版本的内存和DRT对比
  python3 plot_mem_rt.py mem-5.5.1.28.log mem-5.6.0.8.log rt-5.5.1.28.log rt-5.6.0.8.log

  # 只绘制RT对比
  python3 plot_mem_rt.py rt-5.5.1.28.log rt-5.6.0.8.log

  # 只绘制内存对比
  python3 plot_mem_rt.py mem-5.5.1.28.log mem-5.6.0.8.log

  # 绘制多个版本对比
  python3 plot_mem_rt.py mem-v1.log mem-v2.log mem-v3.log rt-v1.log rt-v2.log rt-v3.log
        """
    )
    
    parser.add_argument(
        'files',
        nargs='+',
        help='日志文件列表，以 mem- 开头的为内存日志，以 rt- 开头的为RT日志'
    )
    
    parser.add_argument(
        '-o', '--output',
        default='mem_drt_comparison.html',
        help='输出HTML文件名 (默认: mem_drt_comparison.html)'
    )
    
    parser.add_argument(
        '--no-open',
        action='store_true',
        help='生成后不自动打开浏览器'
    )
    
    return parser.parse_args()


def extract_version_from_filename(filename):
    """
    从文件名中提取版本号
    支持格式: mem-{version}.log, rt-{version}.log, mem-pstt-{version}.log, rt-pstt-{version}.log
    """
    basename = os.path.basename(filename)
    
    # 去掉 .log 后缀
    name = basename.replace('.log', '')
    
    # 去掉 mem- 或 rt- 前缀
    if name.startswith('mem-'):
        name = name[4:]
    elif name.startswith('rt-'):
        name = name[3:]
    
    return name


def classify_files(files):
    """
    将文件分类为内存日志和RT日志
    返回: (mem_files, rt_files)
    """
    mem_files = []
    rt_files = []
    
    for f in files:
        basename = os.path.basename(f).lower()
        if basename.startswith('mem-'):
            mem_files.append(f)
        elif basename.startswith('rt-'):
            rt_files.append(f)
        else:
            print(f"警告: 无法识别文件类型 '{f}'，跳过。文件名应以 'mem-' 或 'rt-' 开头。")
    
    return mem_files, rt_files


def parse_mem_file(filepath):
    """
    解析内存日志文件，提取时间和内存数据
    返回: [(时间索引, RES内存值(GB)), ...]
    """
    mem_data = []
    current_time = None
    
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    for line in lines:
        line = line.strip()
        
        # 匹配时间行，如 "Mon Feb  2 10:16:01 AM CST 2026"
        time_match = re.match(r'^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+\w+\s+\d+\s+\d+:\d+:\d+\s+\w+\s+\w+\s+\d+', line)
        if time_match:
            current_time = line
            continue
        
        # 匹配进程行，提取RES内存（第6列，带g后缀）
        # 格式: PID USER PR NI VIRT RES SHR S %CPU %MEM TIME+ COMMAND
        # 例如: 4040187 liangke+  20   0   31.8g  15.9g  22016 S  2554   6.3  10:21.90 pstt
        proc_match = re.match(r'^\d+\s+\S+\s+\d+\s+\d+\s+[\d.]+g\s+([\d.]+)g', line)
        if proc_match:
            res_mem = float(proc_match.group(1))
            if current_time:
                mem_data.append((len(mem_data), res_mem, current_time))
    
    return mem_data


def parse_rt_file(filepath):
    """
    解析RT日志文件，提取时间和drt数据
    返回: [(时间索引, drt值), ...]
    """
    rt_data = []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    current_time = None
    for line in lines:
        line = line.strip()
        
        # 匹配时间行
        time_match = re.match(r'^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+\w+\s+\d+\s+\d+:\d+:\d+\s+\w+\s+\w+\s+\d+', line)
        if time_match:
            current_time = line
            continue
        
        # 匹配drt数据行
        # 格式: audio_time:xxx decoder_time:xxx process_time:xxx ... drt:0.150 prt:0.269
        drt_match = re.search(r'drt:([\d.]+)', line)
        if drt_match:
            drt_value = float(drt_match.group(1))
            rt_data.append((len(rt_data), drt_value, current_time))
    
    return rt_data


def create_memory_chart(mem_data_dict):
    """
    创建内存对比曲线图
    mem_data_dict: {版本名: [(索引, 内存值, 时间), ...], ...}
    """
    # 计算最大数据点数
    max_len = max(len(data) for data in mem_data_dict.values())
    x_data = [str(i) for i in range(max_len)]
    
    line = Line(init_opts=opts.InitOpts(
        width="1400px", 
        height="600px",
        theme=ThemeType.MACARONS
    ))
    line.add_xaxis(x_data)
    
    # 构建副标题信息
    subtitle_parts = []
    
    for version, data in mem_data_dict.items():
        y_data = [mem for _, mem, _ in data]
        
        # 计算统计信息
        avg_val = sum(y_data) / len(y_data) if y_data else 0
        max_val = max(y_data) if y_data else 0
        min_val = min(y_data) if y_data else 0
        
        subtitle_parts.append(f"{version}: {len(y_data)}点")
        
        line.add_yaxis(
            f"{version} (平均:{avg_val:.2f}GB, 最大:{max_val:.2f}GB, 最小:{min_val:.2f}GB)",
            y_data,
            is_smooth=True,
            symbol_size=4,
            linestyle_opts=opts.LineStyleOpts(width=2),
        )
    
    line.set_global_opts(
        title_opts=opts.TitleOpts(
            title="内存使用对比 (RES内存)",
            subtitle=f"数据点数: {', '.join(subtitle_parts)}"
        ),
        tooltip_opts=opts.TooltipOpts(trigger="axis"),
        xaxis_opts=opts.AxisOpts(
            name="采样点序号",
            type_="category",
            axislabel_opts=opts.LabelOpts(rotate=0, interval='auto'),
        ),
        yaxis_opts=opts.AxisOpts(
            name="内存 (GB)",
            type_="value",
            splitline_opts=opts.SplitLineOpts(is_show=True),
        ),
        legend_opts=opts.LegendOpts(
            pos_top="8%",
            orient="horizontal"
        ),
        datazoom_opts=[
            opts.DataZoomOpts(
                is_show=True,
                type_="slider",
                range_start=0,
                range_end=100,
                pos_bottom="3%"
            ),
            opts.DataZoomOpts(
                is_show=True,
                type_="inside",
                range_start=0,
                range_end=100,
            ),
        ],
        toolbox_opts=opts.ToolboxOpts(
            is_show=True,
            feature={
                "dataZoom": {"yAxisIndex": "none"},
                "restore": {},
                "saveAsImage": {},
            }
        ),
    )
    
    return line


def create_drt_chart(rt_data_dict):
    """
    创建DRT对比曲线图
    rt_data_dict: {版本名: [(索引, drt值, 时间), ...], ...}
    """
    # 计算最大数据点数
    max_len = max(len(data) for data in rt_data_dict.values())
    x_data = [str(i) for i in range(max_len)]
    
    line = Line(init_opts=opts.InitOpts(
        width="1400px", 
        height="600px",
        theme=ThemeType.MACARONS
    ))
    line.add_xaxis(x_data)
    
    # 构建副标题信息
    subtitle_parts = []
    
    for version, data in rt_data_dict.items():
        y_data = [drt for _, drt, _ in data]
        
        # 计算统计信息
        avg_val = sum(y_data) / len(y_data) if y_data else 0
        max_val = max(y_data) if y_data else 0
        min_val = min(y_data) if y_data else 0
        
        subtitle_parts.append(f"{version}: {len(y_data)}点")
        
        line.add_yaxis(
            f"{version} (平均:{avg_val:.4f}, 最大:{max_val:.4f}, 最小:{min_val:.4f})",
            y_data,
            is_smooth=True,
            symbol_size=4,
            linestyle_opts=opts.LineStyleOpts(width=2),
        )
    
    line.set_global_opts(
        title_opts=opts.TitleOpts(
            title="DRT (Decoder Real-Time Factor) 对比",
            subtitle=f"数据点数: {', '.join(subtitle_parts)}"
        ),
        tooltip_opts=opts.TooltipOpts(trigger="axis"),
        xaxis_opts=opts.AxisOpts(
            name="采样点序号",
            type_="category",
            axislabel_opts=opts.LabelOpts(rotate=0, interval='auto'),
        ),
        yaxis_opts=opts.AxisOpts(
            name="DRT",
            type_="value",
            splitline_opts=opts.SplitLineOpts(is_show=True),
        ),
        legend_opts=opts.LegendOpts(
            pos_top="8%",
            orient="horizontal"
        ),
        datazoom_opts=[
            opts.DataZoomOpts(
                is_show=True,
                type_="slider",
                range_start=0,
                range_end=100,
                pos_bottom="3%"
            ),
            opts.DataZoomOpts(
                is_show=True,
                type_="inside",
                range_start=0,
                range_end=100,
            ),
        ],
        toolbox_opts=opts.ToolboxOpts(
            is_show=True,
            feature={
                "dataZoom": {"yAxisIndex": "none"},
                "restore": {},
                "saveAsImage": {},
            }
        ),
    )
    
    return line


def print_statistics(mem_data_dict, rt_data_dict):
    """
    打印统计信息
    """
    print("\n" + "=" * 60)
    print("数据统计摘要:")
    print("=" * 60)
    
    if mem_data_dict:
        print("\n【内存统计】")
        for version, data in mem_data_dict.items():
            mem_values = [m for _, m, _ in data]
            print(f"\n  {version}:")
            print(f"    数据点数: {len(mem_values)}")
            print(f"    平均值: {sum(mem_values)/len(mem_values):.2f} GB")
            print(f"    最大值: {max(mem_values):.2f} GB")
            print(f"    最小值: {min(mem_values):.2f} GB")
    
    if rt_data_dict:
        print("\n【DRT统计】")
        for version, data in rt_data_dict.items():
            drt_values = [d for _, d, _ in data]
            print(f"\n  {version}:")
            print(f"    数据点数: {len(drt_values)}")
            print(f"    平均值: {sum(drt_values)/len(drt_values):.4f}")
            print(f"    最大值: {max(drt_values):.4f}")
            print(f"    最小值: {min(drt_values):.4f}")


def main():
    # 解析命令行参数
    args = parse_args()
    
    # 分类文件
    mem_files, rt_files = classify_files(args.files)
    
    if not mem_files and not rt_files:
        print("错误: 没有找到有效的日志文件！")
        print("文件名应以 'mem-' 或 'rt-' 开头。")
        sys.exit(1)
    
    print("=" * 60)
    print("开始解析日志文件...")
    print("=" * 60)
    
    # 解析内存数据
    mem_data_dict = {}
    if mem_files:
        print(f"\n找到 {len(mem_files)} 个内存日志文件:")
        for f in mem_files:
            version = extract_version_from_filename(f)
            print(f"  解析: {f} -> 版本: {version}")
            data = parse_mem_file(f)
            print(f"    数据点数: {len(data)}")
            mem_data_dict[version] = data
    
    # 解析RT数据
    rt_data_dict = {}
    if rt_files:
        print(f"\n找到 {len(rt_files)} 个RT日志文件:")
        for f in rt_files:
            version = extract_version_from_filename(f)
            print(f"  解析: {f} -> 版本: {version}")
            data = parse_rt_file(f)
            print(f"    数据点数: {len(data)}")
            rt_data_dict[version] = data
    
    # 创建图表
    print("\n创建图表...")
    
    page = Page(layout=Page.SimplePageLayout)
    
    # 添加内存对比图（如果有内存数据）
    if mem_data_dict:
        mem_chart = create_memory_chart(mem_data_dict)
        page.add(mem_chart)
        print("  ✓ 内存对比图已创建")
    
    # 添加DRT对比图（如果有RT数据）
    if rt_data_dict:
        drt_chart = create_drt_chart(rt_data_dict)
        page.add(drt_chart)
        print("  ✓ DRT对比图已创建")
    
    # 确定输出文件路径
    output_file = args.output
    if not os.path.isabs(output_file):
        # 如果是相对路径，放在当前工作目录
        output_file = os.path.join(os.getcwd(), output_file)
    
    # 保存图表
    page.render(output_file)
    
    print(f"\n图表已保存到: {output_file}")
    print("=" * 60)
    
    # 打印统计信息
    print_statistics(mem_data_dict, rt_data_dict)
    
    print("\n" + "=" * 60)
    print("完成！")
    print("=" * 60)
    
    # 自动打开浏览器（除非指定了 --no-open）
    if not args.no_open:
        import subprocess
        try:
            if sys.platform == 'darwin':  # macOS
                subprocess.run(['open', output_file], check=True)
            elif sys.platform == 'win32':  # Windows
                os.startfile(output_file)
            else:  # Linux
                subprocess.run(['xdg-open', output_file], check=True)
        except Exception as e:
            print(f"无法自动打开浏览器: {e}")
            print(f"请手动打开文件: {output_file}")


if __name__ == "__main__":
    main()
