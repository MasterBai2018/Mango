import os
import csv
import json
import asyncio
import fcntl
import threading
from typing import List, Union, Optional, Callable, Dict, Any
from io import StringIO

class Reporter:
    def __init__(self, report_dir: str, report_name: str, report_type: str = "txt", delimiter: str = "\t", encoding: str = "utf-8", buffer_size: int = 1024):
        """
        初始化Report类
        :param report_dir: 报告目录
        :param report_name: 报告名称
        :param report_type: 报告类型，支持"txt", "csv", "both", "jsonl"
        :param delimiter: 分隔符，默认"\t"
        :param encoding: 文件编码，默认"utf-8"
        :param buffer_size: 缓冲区大小，默认1024字节
        """
        self._report_dir = report_dir
        self._report_name = report_name
        self._report_type = report_type
        self.delimiter = delimiter
        self.encoding = encoding
        self.buffer_size = buffer_size
        self.header: Optional[List[str]] = None
        self._ensure_dir()
        self.validator: Optional[Callable[[List[str]], bool]] = None
        self._txt_buffer = StringIO()
        self._csv_buffer = StringIO()
        self._jsonl_buffer = StringIO()

    @property
    def report_dir(self) -> str:
        return self._report_dir

    @report_dir.setter
    def report_dir(self, value: str):
        self._report_dir = value
        self._ensure_dir()

    @property
    def report_name(self) -> str:
        return self._report_name

    @report_name.setter
    def report_name(self, value: str):
        self._report_name = value

    @property
    def report_type(self) -> str:
        return self._report_type

    @report_type.setter
    def report_type(self, value: str):
        self._report_type = value

    @property
    def txt_path(self) -> str:
        return os.path.join(self._report_dir, f"{self._report_name}.txt")

    @property
    def csv_path(self) -> str:
        return os.path.join(self._report_dir, f"{self._report_name}.csv")

    @property
    def jsonl_path(self) -> str:
        return os.path.join(self._report_dir, f"{self._report_name}.jsonl")

    def _ensure_dir(self):
        """确保报告目录存在"""
        if not os.path.exists(self._report_dir):
            os.makedirs(self._report_dir)

    def _flush_buffers(self):
        """将缓冲区数据写入文件"""
        if self._report_type in ["txt", "both"]:
            with open(self.txt_path, "a", encoding=self.encoding) as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                f.write(self._txt_buffer.getvalue())
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            self._txt_buffer = StringIO()
        if self._report_type in ["csv", "both"]:
            with open(self.csv_path, "a", newline="", encoding=self.encoding) as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                writer = csv.writer(f, delimiter=self.delimiter)
                for row in csv.reader(StringIO(self._csv_buffer.getvalue()), delimiter=self.delimiter):
                    writer.writerow(row)
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            self._csv_buffer = StringIO()
        if self._report_type == "jsonl":
            with open(self.jsonl_path, "a", encoding=self.encoding) as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                f.write(self._jsonl_buffer.getvalue())
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            self._jsonl_buffer = StringIO()

    def set_header(self, header: List[str]):
        """
        设置报告Header
        :param header: 一维数据列表
        """
        self.header = header
        if self._report_type in ["txt", "both"]:
            with open(self.txt_path, "w", encoding=self.encoding) as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                f.write(self.delimiter.join(header) + "\n")
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        if self._report_type in ["csv", "both"]:
            with open(self.csv_path, "w", newline="", encoding=self.encoding) as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                writer = csv.writer(f, delimiter=self.delimiter)
                writer.writerow(header)
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def write_row(self, row: List[str]):
        """
        按行写入数据
        :param row: 一维数据列表
        """
        if self.validator and not self.validator(row):
            raise ValueError("数据格式校验失败")
        if self._report_type in ["txt", "both"]:
            self._txt_buffer.write(self.delimiter.join(row) + "\n")
            if self._txt_buffer.tell() >= self.buffer_size:
                self._flush_buffers()
        if self._report_type in ["csv", "both"]:
            output = StringIO()
            writer = csv.writer(output, delimiter=self.delimiter)
            writer.writerow(row)
            self._csv_buffer.write(output.getvalue())
            if self._csv_buffer.tell() >= self.buffer_size:
                self._flush_buffers()

    def write_rows(self, rows: List[List[str]]):
        """
        统一写入多行数据
        :param rows: 二维数据表
        """
        if self.validator:
            for row in rows:
                if not self.validator(row):
                    raise ValueError(f"数据格式校验失败: {row}")
        if self._report_type in ["txt", "both"]:
            for row in rows:
                self._txt_buffer.write(self.delimiter.join(row) + "\n")
            if self._txt_buffer.tell() >= self.buffer_size:
                self._flush_buffers()
        if self._report_type in ["csv", "both"]:
            output = StringIO()
            writer = csv.writer(output, delimiter=self.delimiter)
            writer.writerows(rows)
            self._csv_buffer.write(output.getvalue())
            if self._csv_buffer.tell() >= self.buffer_size:
                self._flush_buffers()

    def clear(self):
        """清空报告内容"""
        if self._report_type in ["txt", "both"]:
            with open(self.txt_path, "w", encoding=self.encoding) as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                if self.header:
                    f.write(self.delimiter.join(self.header) + "\n")
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        if self._report_type in ["csv", "both"]:
            with open(self.csv_path, "w", newline="", encoding=self.encoding) as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                writer = csv.writer(f, delimiter=self.delimiter)
                if self.header:
                    writer.writerow(self.header)
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        # jsonl 无 header 概念，clear 时直接清空文件内容
        if self._report_type == "jsonl":
            with open(self.jsonl_path, "w", encoding=self.encoding) as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def get_path(self) -> str:
        """
        获取报告文件路径
        :return: 文件路径
        """
        if self._report_type == "txt":
            return self.txt_path
        elif self._report_type == "csv":
            return self.csv_path
        elif self._report_type == "both":
            return self.txt_path
        elif self._report_type == "jsonl":
            return self.jsonl_path
        else:
            raise ValueError("不支持的报告类型")

    def write_json_row(self, data: Dict[str, Any]):
        """
        按行写入一条 JSON 数据（仅 report_type="jsonl" 时有效）
        :param data: 待写入的字典数据
        """
        if self._report_type != "jsonl":
            raise ValueError("write_json_row 仅支持 report_type='jsonl'")
        self._jsonl_buffer.write(json.dumps(data, ensure_ascii=False) + "\n")
        if self._jsonl_buffer.tell() >= self.buffer_size:
            self._flush_buffers()

    def write_json_rows(self, rows: List[Dict[str, Any]]):
        """
        批量写入多条 JSON 数据（仅 report_type="jsonl" 时有效）
        :param rows: 待写入的字典列表
        """
        if self._report_type != "jsonl":
            raise ValueError("write_json_rows 仅支持 report_type='jsonl'")
        for data in rows:
            self._jsonl_buffer.write(json.dumps(data, ensure_ascii=False) + "\n")
        if self._jsonl_buffer.tell() >= self.buffer_size:
            self._flush_buffers()

    async def write_json_row_async(self, data: Dict[str, Any]):
        """
        异步按行写入一条 JSON 数据（仅 report_type="jsonl" 时有效）
        :param data: 待写入的字典数据
        """
        if self._report_type != "jsonl":
            raise ValueError("write_json_row_async 仅支持 report_type='jsonl'")
        async with asyncio.Lock():
            self._jsonl_buffer.write(json.dumps(data, ensure_ascii=False) + "\n")
            if self._jsonl_buffer.tell() >= self.buffer_size:
                self._flush_buffers()

    async def write_json_rows_async(self, rows: List[Dict[str, Any]]):
        """
        异步批量写入多条 JSON 数据（仅 report_type="jsonl" 时有效）
        :param rows: 待写入的字典列表
        """
        if self._report_type != "jsonl":
            raise ValueError("write_json_rows_async 仅支持 report_type='jsonl'")
        async with asyncio.Lock():
            for data in rows:
                self._jsonl_buffer.write(json.dumps(data, ensure_ascii=False) + "\n")
            if self._jsonl_buffer.tell() >= self.buffer_size:
                self._flush_buffers()

    def set_validator(self, validator: Callable[[List[str]], bool]):
        """
        设置数据格式校验函数
        :param validator: 校验函数，接收一维数据列表，返回布尔值
        """
        self.validator = validator

    async def write_row_async(self, row: List[str]):
        """
        异步按行写入数据
        :param row: 一维数据列表
        """
        if self.validator and not self.validator(row):
            raise ValueError("数据格式校验失败")
        if self._report_type in ["txt", "both"]:
            async with asyncio.Lock():
                self._txt_buffer.write(self.delimiter.join(row) + "\n")
                if self._txt_buffer.tell() >= self.buffer_size:
                    self._flush_buffers()
        if self._report_type in ["csv", "both"]:
            async with asyncio.Lock():
                output = StringIO()
                writer = csv.writer(output, delimiter=self.delimiter)
                writer.writerow(row)
                self._csv_buffer.write(output.getvalue())
                if self._csv_buffer.tell() >= self.buffer_size:
                    self._flush_buffers()

    async def write_rows_async(self, rows: List[List[str]]):
        """
        异步统一写入多行数据
        :param rows: 二维数据表
        """
        if self.validator:
            for row in rows:
                if not self.validator(row):
                    raise ValueError(f"数据格式校验失败: {row}")
        if self._report_type in ["txt", "both"]:
            async with asyncio.Lock():
                for row in rows:
                    self._txt_buffer.write(self.delimiter.join(row) + "\n")
                if self._txt_buffer.tell() >= self.buffer_size:
                    self._flush_buffers()
        if self._report_type in ["csv", "both"]:
            async with asyncio.Lock():
                output = StringIO()
                writer = csv.writer(output, delimiter=self.delimiter)
                writer.writerows(rows)
                self._csv_buffer.write(output.getvalue())
                if self._csv_buffer.tell() >= self.buffer_size:
                    self._flush_buffers()

    @staticmethod
    def merge_reports(reports: List["Report"], output_report: "Report"):
        """
        合并多个报告
        :param reports: 待合并的报告列表
        :param output_report: 输出报告
        """
        if not reports:
            return
        # 合并Header
        headers = [r.header for r in reports if r.header]
        if headers:
            output_report.set_header(headers[0])
        # 合并数据
        for report in reports:
            if report._report_type in ["txt", "both"]:
                with open(report.txt_path, "r", encoding=report.encoding) as f:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                    lines = f.readlines()
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                    if report.header:
                        lines = lines[1:]  # 跳过Header
                    with open(output_report.txt_path, "a", encoding=output_report.encoding) as out_f:
                        fcntl.flock(out_f.fileno(), fcntl.LOCK_EX)
                        out_f.writelines(lines)
                        fcntl.flock(out_f.fileno(), fcntl.LOCK_UN)
            if report._report_type in ["csv", "both"]:
                with open(report.csv_path, "r", newline="", encoding=report.encoding) as f:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                    reader = csv.reader(f, delimiter=report.delimiter)
                    rows = list(reader)
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                    if report.header:
                        rows = rows[1:]  # 跳过Header
                    with open(output_report.csv_path, "a", newline="", encoding=output_report.encoding) as out_f:
                        fcntl.flock(out_f.fileno(), fcntl.LOCK_EX)
                        writer = csv.writer(out_f, delimiter=output_report.delimiter)
                        writer.writerows(rows)
                        fcntl.flock(out_f.fileno(), fcntl.LOCK_UN)

    def flush(self):
        """强制将缓冲区数据写入文件"""
        if self._report_type in ["txt", "both"]:
            if self._txt_buffer.tell() > 0:
                with open(self.txt_path, "a", encoding=self.encoding) as f:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                    f.write(self._txt_buffer.getvalue())
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                self._txt_buffer = StringIO()
        if self._report_type in ["csv", "both"]:
            if self._csv_buffer.tell() > 0:
                with open(self.csv_path, "a", newline="", encoding=self.encoding) as f:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                    writer = csv.writer(f, delimiter=self.delimiter)
                    for row in csv.reader(StringIO(self._csv_buffer.getvalue()), delimiter=self.delimiter):
                        writer.writerow(row)
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                self._csv_buffer = StringIO()
        if self._report_type == "jsonl":
            if self._jsonl_buffer.tell() > 0:
                with open(self.jsonl_path, "a", encoding=self.encoding) as f:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                    f.write(self._jsonl_buffer.getvalue())
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                self._jsonl_buffer = StringIO()