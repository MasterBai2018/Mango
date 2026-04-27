#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2025/09/28
# @Author  : baihuidong
# @File    : NANOClientManager.py
# @Software: PyCharm
# @Mail    : baihuidong@pachiratech.com
from loguru import logger
from src.testsuite.NANO.client.ClientFactory import ClientFactory

class NANOClientManager:
    """
    NANO客户端管理器 - 纯粹的实例容器
    
    职责：
    1. 创建和缓存客户端实例（Python对象）
    2. 提供实例查找功能
    3. 管理回调函数注入
    4. 实例移除和清理
    
    注意：
    - 本类不调用客户端的业务方法（create/start/stop/free等）
    - 业务方法由 NANORunner 调用，传入 DSLCommand 参数
    - 资源释放由 Runner 在调用 client.free(command) 后通过 remove_client() 完成
    """

    def __init__(self, lib_path: str, config=None):
        self.clients = {}  # client_type -> Client实例
        self.lib_path = lib_path
        self.config = config  # pytest config对象，用于传递配置信息
        self.aibs_callback = None     # AIBSClient回调函数指针
        self.nissan_callback = None   # NissanAIBSClient回调函数指针
        self.speech_callback = None   # SpeechEngineClient回调函数指针
        self.pstt_callback = None     # PSTTClient回调函数指针
        self.titan_callback = None    # TitanClient回调函数指针
        self.carplay_callback = None  # CarPlayClient回调函数指针
        self.pis_callback = None      # PISALLMClient回调函数指针
        self.tss_callback = None      # TSSClient回调函数指针
    def set_client_callback(self, aibs_callback=None, nissan_callback=None, speech_callback=None, pstt_callback=None, titan_callback=None, carplay_callback=None, pis_callback=None, tss_callback=None):
        """
        设置默认回调处理函数
        """
        self.aibs_callback = aibs_callback
        self.nissan_callback = nissan_callback
        self.speech_callback = speech_callback
        self.pstt_callback = pstt_callback
        self.titan_callback = titan_callback
        self.carplay_callback = carplay_callback
        self.pis_callback = pis_callback
        self.tss_callback = tss_callback
    def create_client(self, client_type: str):
        """
        创建客户端实例（如果已存在则直接返回）
        
        注意：此方法只创建 Python 对象实例，不调用 client.create() 方法
        实际的引擎创建由 Runner 调用 client.create(command) 完成
        
        Args:
            client_type: 客户端类型 (TSA, SET, VOI, OMS, TTS, HWK, PST)
            
        Returns:
            客户端实例
        """
        if client_type in self.clients:
            logger.debug(f"客户端 {client_type} 已存在，直接返回现有实例")
            return self.clients[client_type]
        
        # 通过工厂创建客户端实例
        client = ClientFactory.create_client(client_type, self.lib_path, self.config)
        
        # 自动根据类型注入回调函数
        if client_type in ["TSA", "SET", "VOI", "OMS", "TTS"]:
            client.set_callback(self.aibs_callback)
        elif client_type in ["NIS", "NSE"]:
            client.set_callback(self.nissan_callback)
        elif client_type == "HWK":
            client.set_callback(self.speech_callback)
        elif client_type == "PST":
            client.set_callback(self.pstt_callback)
        elif client_type == "TIA":
            client.set_callback(self.titan_callback)
        elif client_type == "CPL":
            client.set_callback(self.carplay_callback)
        elif client_type == "PIS":
            client.set_callback(self.pis_callback)
        elif client_type == "TSS":
            client.set_callback(self.tss_callback)

        # 缓存实例
        self.clients[client_type] = client
        logger.info(f"创建客户端实例: {client_type}")
        
        return client

    def get_client(self, client_type: str):
        """
        获取已创建的客户端实例
        
        Args:
            client_type: 客户端类型
            
        Returns:
            客户端实例
            
        Raises:
            ValueError: 如果客户端不存在，提示先执行 CREATE 指令
        """
        if client_type not in self.clients:
            raise ValueError(
                f"客户端 {client_type} 不存在，请先执行 CREATE 指令。"
                f"已创建的客户端: {list(self.clients.keys())}"
            )
        return self.clients[client_type]
    
    def has_client(self, client_type: str) -> bool:
        """
        检查客户端是否已创建
        
        Args:
            client_type: 客户端类型
            
        Returns:
            True 如果已创建，False 否则
        """
        return client_type in self.clients

    def remove_client(self, client_type: str):
        """
        从管理器中移除客户端实例
        
        注意：此方法不调用 client.free()，只是从字典中删除引用
        实际的资源释放应由 Runner 先调用 client.free(command) 完成
        
        Args:
            client_type: 客户端类型
        """
        if client_type in self.clients:
            del self.clients[client_type]
            logger.info(f"从管理器移除客户端: {client_type}")
        else:
            logger.warning(f"客户端 {client_type} 不存在，无法移除")

    def cleanup_all(self):
        """
        清理所有客户端实例（用于测试结束时）
        
        注意：此方法不调用 free()，只是清空字典
        如果需要释放资源，应该在调用此方法前先调用每个 client.free(command)
        """
        client_types = list(self.clients.keys())
        self.clients.clear()
        logger.info(f"清理所有客户端实例: {client_types}")
    
    def get_all_client_types(self) -> list:
        """
        获取所有已创建的客户端类型列表
        
        Returns:
            客户端类型列表，如 ['TSA', 'SET']
        """
        return list(self.clients.keys())
