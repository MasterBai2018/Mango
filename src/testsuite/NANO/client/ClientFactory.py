#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2025/09/28
# @Author  : baihuidong
# @File    : ClientFactory.py
# @Software: PyCharm
# @Mail    : baihuidong@pachiratech.com
import os
from loguru import logger
from src.testsuite.NANO.client.AIBSClient import AIBSClient
from src.testsuite.NANO.client.NissanAIBSClient import NissanAIBSClient
from src.testsuite.NANO.client.SpeechEngineClient import SpeechEngineClient
from src.testsuite.NANO.client.PSTTClient import PSTTClientServer
from src.testsuite.NANO.client.AITiTan import TiTanService
from src.testsuite.NANO.client.CarPlayClient import CarPlayClient
from src.testsuite.NANO.client.EcnrClient import ECNRClient
from src.testsuite.NANO.client.PISALLMClient import PISALLMClient
from src.testsuite.NANO.client.TSSClient import TSSClient

class ClientFactory:
    """客户端工厂类"""
    @staticmethod
    def create_client(client_name: str, lib_path: str, config=None):
        """
        根据客户端名称创建对应的客户端实例
        
        Args:
            client_name: 客户端名称 (TSA, VOI, HWK等)
            lib_path: 动态库所在目录
            config: pytest config对象（可选，主要用于PST客户端）
            
        Returns:
            具体的客户端实例
        """
        # AIBS 客户端 (TSA, SET, VOI, OMS, TTS)
        if client_name in ["TSA", "SET", "VOI", "OMS", "TTS"]:
            return AIBSClient(client_name, lib_path, config)
        
        # NISSAN 客户端 (NIS, NSE)
        if client_name in ["NIS", "NSE"]:
            return NissanAIBSClient(client_name, lib_path, config)
        
        # SpeechEngineClient客户端
        elif client_name == "HWK":
            return SpeechEngineClient(client_name, lib_path)
        
        # PSTT客户端
        elif client_name == "PST":
            return PSTTClientServer(client_name, lib_path, config)
        
        # AI能力平台客户端工具
        elif client_name == "TIA":
            return TiTanService(client_name)
        
        # CarPlay客户端
        elif client_name == "CPL":
            return CarPlayClient(client_name, lib_path)
        
        # ECNR客户端
        elif client_name == "ENR":
            return ECNRClient(client_name, lib_path, config)

        # PISA 大模型全双工 WebSocket 客户端（集成 AIBS 降噪）
        elif client_name == "PIS":
            return PISALLMClient(client_name, lib_path, config)
        
        # TSS客户端
        elif client_name == "TSS":
            return TSSClient(client_name, lib_path, config)

        else:
            logger.error(f"创建客户端失败, 未知的客户端类型:{client_name}")
            return None
