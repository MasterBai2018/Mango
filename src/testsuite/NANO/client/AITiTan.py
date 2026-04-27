#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2025/4/28 13:56
# @Author  : liutianwei
# @File    : ASRPlanBTool.py
# @Software: PyCharm
import sys
import os
import time
import json
import websockets
import asyncio
import configparser
import argparse
from loguru import logger
from copy import deepcopy
from src.testsuite.NANO.dsl_engine import Status, DSLCommand
from src.utils.common import join_with_spaces_if_english
from urllib.parse import urlencode
from tqdm import tqdm


def parse_titan_result(audio_path: str, tmp_message: dict, audio_time: float) -> dict:
    try:
        logger.info(f"titan result: {tmp_message}")
        recognize_text = tmp_message.get("recognizeText")
        decided = tmp_message.get("decided")
        confidence = tmp_message.get("confidence")
        language = tmp_message.get("language")
        
        # 安全获取 emotions、genders、ages，处理 None 或空列表的情况
        emotions = tmp_message.get("emotions")
        emotion = emotions[0].get("type") if emotions and len(emotions) > 0 else None
        
        genders = tmp_message.get("genders")
        gender = genders[0].get("type") if genders and len(genders) > 0 else None
        
        ages = tmp_message.get("ages")
        age = ages[0].get("type") if ages and len(ages) > 0 else None

        tmp_text = "|".join([item['word'] for item in recognize_text])

        # 帧转毫秒
        start_mts = recognize_text[0].get('begin', 0) * 10
        end_mts = recognize_text[-1].get('end', 0) * 10

        real_text = join_with_spaces_if_english(tmp_text).replace(" 's", "'s").strip()
        
        result = {
            "source": "AITiTan",
            "type": "TiTanASRResult" if decided else "TiTanASRResultTemp",
            "audio": audio_path,
            "audiotime": round(audio_time, 2),
            "asr": real_text,
            "channelId": 0,
            "start": start_mts,
            "end": end_mts,
            "lang": language,
            "confidence": confidence,
            "emotion": emotion,
            "gender": gender,
            "age": age
        }
        return result

    except Exception as e:
        logger.warning(f"解析 titan 结果失败: {e}")
        return None


class TiTanWebSocketClient:
    def __init__(self, config_dict=None, delay=0.0, callback=None):
        """
        初始化TiTan WebSocket客户端
        :param config_dict: 配置参数字典，如果为None则使用默认值
        :param callback: 回调函数，格式: callback(client_name: str, status: int, result_data: dict)
        """
        if config_dict is None:
            config_dict = {}
        self.url = config_dict.pop("url")
        self.config_dict = config_dict
        self.result = None
        self.delay = delay      # 存储当前发送音频的时延系数
        self.audio_path = None  # 存储当前处理的音频路径
        self.audio_time = 0.0   # 存储当前处理的音频时间
        self.callback = callback  # 回调函数

    async def run(self, audio):
        self.result = None
        self.audio_path = audio  # 保存音频路径，用于后续打印关联
        self.audio_time = 0.0    # 重置音频进度
        config = deepcopy(self.config_dict)
        # 处理特殊字段
        config["speechId"] = int(time.time() * 1000000)
        config["realTimeSilStep"] = int(self.config_dict["realTimeSilStep"])
        
        params = urlencode(config).encode('utf-8')
        logger.success(f"titan url: {self.url}\nparams: {params}")
        # 创建事件锁，等待服务器确认
        param_latch = asyncio.Event()
        end_latch = asyncio.Event()
        last_latch = asyncio.Event()  # 等待服务器返回 last=True 的事件

        try:
            # 增加连接超时控制（10秒）
            async with websockets.connect(self.url, open_timeout=10) as ws:
                await ws.send(params)
                
                # 先启动接收任务（等待服务器确认消息）
                receive_task = asyncio.create_task(self._receive_messages(ws, param_latch, end_latch, last_latch))
                
                # 等待收到第一条消息（服务器确认），增加超时保护（10秒）
                try:
                    await asyncio.wait_for(param_latch.wait(), timeout=10.0)
                except asyncio.TimeoutError:
                    logger.error(f"等待服务器首包响应超时 [{os.path.basename(audio)}]")
                    receive_task.cancel()
                    return
                
                # 并发执行发送音频和接收消息，增加整体超时保护（300秒）
                send_task = asyncio.create_task(self._send_audio(ws, audio, end_latch))
                try:
                    await asyncio.wait_for(asyncio.gather(send_task, receive_task), timeout=300.0)
                except asyncio.TimeoutError:
                    logger.error(f"音频处理整体超时 [{os.path.basename(audio)}]")
                    send_task.cancel()
                    receive_task.cancel()
                    return
                
                # 关闭连接之前，等待服务器返回 last=True，或者超时5秒
                try:
                    await asyncio.wait_for(last_latch.wait(), timeout=5.0)
                    logger.debug(f"收到 last=True 信号，准备关闭连接")
                except asyncio.TimeoutError:
                    logger.warning(f"等待 last=True 超时(5秒)，强制关闭连接")
        except websockets.exceptions.ConnectionClosed as e:
            if e.code != 1000:
                print(f"连接异常关闭: {e}")
        except Exception as e:
            print(f"错误: {e}")

    async def _send_audio(self, ws, audio, end_latch):
        """发送音频数据"""
        try:
            self.audio_time = 0.0
            with open(audio, 'rb') as stream:
                data = stream.read(320)
                while data:
                    await ws.send(data)
                    if self.delay > 0:
                        await asyncio.sleep(0.01 * float(self.delay))  # 使用异步sleep
                    data = stream.read(320)
                    self.audio_time += 0.01
            await ws.send('{"status":"end"}')
        except Exception as e:
            # 在错误信息中包含音频路径，方便定位问题
            audio_name = os.path.basename(self.audio_path) if self.audio_path else audio
            print(f"发送音频时出错 [{audio_name}]: {e}")
            end_latch.set()
            raise

    async def _receive_messages(self, ws, param_latch, end_latch, last_latch):
        """接收消息"""
        try:
            async for message in ws:
                # 处理字节消息
                if isinstance(message, bytes):
                    message = message.decode('utf-8')
                
                # 收到第一条消息时，设置param_latch（允许开始发送音频）
                if not param_latch.is_set():
                    param_latch.set()
                
                # 处理识别结果
                if message and "recognizeText" in message:
                    try:
                        tmp_message = json.loads(message)
                        logger.info(f"titan result: {tmp_message}")
                        
                        # 检测 last=True，退出接收循环
                        if tmp_message.get("last") is True and not last_latch.is_set():
                            last_latch.set()
                            logger.debug(f"检测到 last=True，设置 last_latch")
                            return  # 收到 last=True 后退出接收循环
                        
                        if tmp_message.get("recognizeText") is not None and len(tmp_message.get("recognizeText")) > 0:
                            parsed_result_data = parse_titan_result(self.audio_path, tmp_message, self.audio_time)
                            if parsed_result_data is not None:
                                self.result = parsed_result_data.get("asr")
                                
                                # 调用回调函数，实时传递识别结果
                                if self.callback:
                                    try:
                                        # 判断是最终结果还是临时结果
                                        status = 0 if parsed_result_data.get("type") == "TiTanASRResult" else 1
                                        self.callback("TIA", status, parsed_result_data)
                                    except Exception as e:
                                        # 回调执行失败不影响主流程
                                        print(f"回调执行失败: {e}")
                            else:
                                self.result = None
                    except json.JSONDecodeError:
                        self.result = None
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            # 连接关闭时，设置end_latch（允许结束发送任务）
            end_latch.set()


class ConcurrentASRTool:
    """并发ASR处理工具"""
    def __init__(self, max_workers=10, config_dict=None, delay=0.0, callback=None):
        """
        初始化并发ASR工具
        :param max_workers: 最大并发数
        :param config_dict: 配置参数字典
        :param callback: 回调函数，格式: callback(client_name: str, status: int, result_data: dict)
        """
        self.max_workers = max_workers
        self.config_dict = config_dict
        self.delay = delay
        self.callback = callback  # 回调函数
        self.semaphore = None

    async def _process_single_audio(self, audio_path, index, total, pbar=None):
        """处理单个音频文件"""
        async with self.semaphore:  # 控制并发数
            try:
                client = TiTanWebSocketClient(config_dict=deepcopy(self.config_dict), delay=self.delay, callback=self.callback)
                await client.run(audio_path)
                if pbar:
                    pbar.set_postfix_str(f"✓ {os.path.basename(audio_path)}:{client.result}")
            except Exception as e:
                if pbar:
                    pbar.set_postfix_str(f"✗ {os.path.basename(audio_path)}: 错误 - {str(e)}")
            finally:
                # 更新进度条
                if pbar:
                    pbar.update(1)

    async def process_audios(self, audio_list):
        """
        并发处理多个音频文件
        :param audio_list: 音频文件路径列表
        :return: 处理结果列表
        """
        self.semaphore = asyncio.Semaphore(self.max_workers)
        total = len(audio_list)
        
        # 创建进度条
        pbar = tqdm(
            total=total,
            desc=f"处理音频文件 (并发数: {self.max_workers})",
            unit="个",
            ncols=180,
            bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}] {postfix}'
        )
        
        # 创建所有任务
        tasks = [
            self._process_single_audio(audio, idx + 1, total, pbar)
            for idx, audio in enumerate(audio_list)
        ]
        
        # 并发执行所有任务
        await asyncio.gather(*tasks)
        
        # 关闭进度条
        pbar.close()


class TiTanService:
    """TiTan ASR服务类 - 封装配置加载和音频处理功能，供NANORunner调用"""
    
    def __init__(self, client_name: str):
        """
        初始化TiTan服务
        :param client_name: 客户端名称 (TIA)
        :param lib_path: 动态库所在目录（对于TIA，此参数暂不使用，保留以保持接口一致性）
        """
        self.client_name = client_name
        self.config_path = None  # 在create方法中设置
        self.config_dict = None  # 在create方法中加载
        self.delay = 0.0
        self.callback = None  # 回调函数，通过set_callback设置
    
    def set_callback(self, callback_func):
        """
        设置外部回调函数
        :param callback_func: 回调函数，格式: callback(client_name: str, status: int, result_data: dict)
        """
        self.callback = callback_func
    
    def create(self, command: DSLCommand, default_config: str):
        """
        CREATE接口 - 创建TiTan服务并加载配置
        DSL格式: [TIA]CREATE config_path [max_workers]
        
        Args:
            command: DSL指令对象，params=[config_path, max_workers(可选)]
        
        Returns:
            0: 成功, -1: 失败
        """
        try:
            # 参数解析
            self.config_path = command.params[0] if len(command.params) > 0 else default_config
            
            # 检查配置文件是否存在
            if not os.path.exists(self.config_path):
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] 配置文件不存在: {self.config_path}'
                logger.error(command.message)
                return -1
            
            # 加载配置文件
            try:
                self.config_dict = load_config_file(self.config_path)
                logger.info(f"[{self.client_name}] CREATE成功: config={self.config_path}")
                command.return_code = 0
                command.status = Status.PASSED
                return 0
            except Exception as e:
                command.status = Status.ERROR
                command.message = f'[{self.client_name}] 加载配置文件失败: {e}'
                logger.error(command.message)
                return -1
                
        except Exception as e:
            logger.error(f"[{self.client_name}] CREATE异常: {e}")
            command.status = Status.ERROR
            command.message = f'[{self.client_name}] CREATE异常: {e}'
            return -1
    
    def process_single_audio(self, audio_path: str, delay: float) -> str:
        """
        处理单个音频文件（同步方法）
        :param audio_path: 音频文件路径
        :return: 识别结果文本，如果失败返回None
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")
        
        # 使用asyncio.run执行异步任务
        result = asyncio.run(self._process_single_audio_async(audio_path, delay))
        return result
    
    async def _process_single_audio_async(self, audio_path: str, delay: float) -> str:
        """异步处理单个音频文件"""
        try:
            client = TiTanWebSocketClient(config_dict=deepcopy(self.config_dict), delay=delay, callback=self.callback)
            await client.run(audio_path)
            return client.result
        except Exception as e:
            # 记录错误但不抛出异常，返回None表示失败
            import traceback
            print(f"处理音频失败 [{os.path.basename(audio_path)}]: {e}")
            return None
    
    def process_audio_list(self, audio_list: list = None, caselist_path: str = None, delay: float = 0.0, max_workers: int = 1):
        """
        处理音频列表（同步方法）
        :param audio_list: 音频文件路径列表（直接传入）
        :param caselist_path: 音频列表文件路径（从文件读取）
        :return: None（处理结果通过进度条显示）
        """
        # 确定音频列表来源
        if caselist_path:
            if not os.path.exists(caselist_path):
                raise FileNotFoundError(f"音频列表文件不存在: {caselist_path}")
            audio_list = load_caselist_file(caselist_path)
        elif not audio_list:
            raise ValueError("必须提供audio_list或caselist_path参数")
        
        if not audio_list:
            raise ValueError("音频列表为空或所有行都被跳过")
        
        # 使用asyncio.run执行异步任务
        asyncio.run(self._process_audio_list_async(audio_list, delay, max_workers))
    
    async def _process_audio_list_async(self, audio_list: list, delay: float, max_workers: int):
        """异步处理音频列表"""
        concurrent_tool = ConcurrentASRTool(
            max_workers=max_workers, 
            config_dict=self.config_dict,
            delay=delay,
            callback=self.callback
        )
        await concurrent_tool.process_audios(audio_list)


def load_config_file(config_path):
    """
    加载配置文件（使用configparser解析INI格式，支持无section的格式）
    :param config_path: 配置文件路径
    :return: 配置参数字典
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    
    config_dict = {}
    
    try:
        # 先读取文件内容，检查是否有section
        with open(config_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查是否有section（以[开头的行）
        has_section = any(line.strip().startswith('[') and line.strip().endswith(']') 
                         for line in content.split('\n'))
        
        # 如果没有section，添加DEFAULT section
        if not has_section:
            content = '[DEFAULT]\n' + content
        
        # 使用configparser解析配置文件
        parser = configparser.ConfigParser(interpolation=None)
        # 保持原始大小写
        parser.optionxform = str
        
        # 从字符串读取配置
        parser.read_string(content)
        
        # 读取DEFAULT section（无论原文件是否有section，都从DEFAULT读取）
        for key, value in parser.items('DEFAULT'):
            # configparser会自动去除值两端的引号
            config_dict[key] = value
    except configparser.Error as e:
        raise ValueError(f"解析配置文件失败: {config_path}, 错误: {e}")
    except Exception as e:
        raise ValueError(f"读取配置文件失败: {config_path}, 错误: {e}")
    
    return config_dict


def load_caselist_file(caselist_path):
    """
    加载音频列表文件，跳过注释行和空行
    :param caselist_path: 音频列表文件路径
    :return: 音频文件路径列表
    """
    if not os.path.exists(caselist_path):
        raise FileNotFoundError(f"音频列表文件不存在: {caselist_path}")
    
    audio_list = []
    with open(caselist_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # 跳过空行
            if not line:
                continue
            # 跳过以 "#" 或 "//" 开头的注释行
            if line.startswith('#') or line.startswith('//'):
                continue
            audio_list.append(line)
    
    return audio_list


if __name__ == "__main__":
    # 使用argparse解析命令行参数
    parser = argparse.ArgumentParser(
        description="TiTan ASR语音识别工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python AITiTan.py --caselist audio_list.txt --config titan.ini
  python AITiTan.py --thread 10 --caselist audio_list.txt --config titan.ini
        """
    )
    
    parser.add_argument(
        "--thread",
        type=int,
        default=1,
        metavar="并发数",
        help="并发处理线程数，默认为1（不并发）"
    )
    
    parser.add_argument(
        "--caselist",
        type=str,
        required=True,
        metavar="音频列表文件",
        help="音频列表文件路径（必传参数）"
    )
    
    parser.add_argument(
        "--config",
        type=str,
        required=True,
        metavar="配置文件",
        help="配置文件路径（必传参数）"
    )
    
    # 解析参数
    args = parser.parse_args()
    
    # 验证并发数必须大于0
    if args.thread < 1:
        parser.error("--thread 参数值必须大于0")
    
    max_workers = args.thread
    caselist_path = args.caselist
    config_path = args.config
    
    try:
        # 创建TiTan服务实例
        print(f"加载配置文件: {config_path}")
        titan_service = TiTanService("TIA")
        
        # 处理音频列表
        print(f"加载音频列表文件: {caselist_path}")
        titan_service.process_audio_list(caselist_path=caselist_path)
    
    except FileNotFoundError as e:
        print(f"错误: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"错误: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
