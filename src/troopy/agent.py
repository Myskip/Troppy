"""
Agent.py - 基于OpenAI兼容LLM的Agent实现

这个模块实现了一个基础的Agent类，具有消息收发接口。
"""

import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from abc import ABC, abstractmethod
import requests
import time
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError


@dataclass
class Message:
    """消息数据类"""
    role: str  # "user", "assistant", "system"
    content: str
    timestamp: float = time.time()


class LLMClient(ABC):
    """LLM客户端抽象基类"""

    @abstractmethod
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """发送聊天请求并返回响应"""
        pass

    @abstractmethod
    def cancel_request(self):
        pass

class OpenAICompatibleClient(LLMClient):
    """OpenAI兼容的LLM客户端"""

    def __init__(self, api_base: str, api_key: str, model: str = "gpt-3.5-turbo"):
        """
        初始化OpenAI兼容客户端

        Args:
            api_base: API基础URL
            api_key: API密钥
            model: 模型名称
        """
        self.api_base = api_base.rstrip('/')
        self.api_key = api_key
        self.model = model
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        self.logger = logging.getLogger(__name__)
        self._cancel_event = threading.Event()
        self._executor = ThreadPoolExecutor(max_workers=1)

    def cancel_request(self) -> None:
        """取消当前请求"""
        self._cancel_event.set()

    def _reset_cancel(self):
        """重置取消标志"""
        self._cancel_event.clear()

    def _do_request(self, url: str, payload: dict) -> str:
        """实际执行HTTP请求的内部方法（在线程中运行）"""
        response = requests.post(url, headers=self.headers, json=payload, timeout=300)
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        发送聊天请求

        Args:
            messages: 消息列表
            **kwargs: 其他参数

        Returns:
            模型响应内容

        Raises:
            Exception: API请求失败时抛出异常
        """
        self._reset_cancel()
        url = f"{self.api_base}/chat/completions"

        payload = {
            "model": kwargs.get("model", self.model),
            "messages": messages,
            "temperature": kwargs.get("temperature", 1.0),
            "max_tokens": kwargs.get("max_tokens", 4096*16),
            "top_p": kwargs.get("top_p", 1.0),
            "stream": False,
            "thinking": {
                "type": "disabled",
                "clear_thinking": True
            }
        }

        try:
            self.logger.info(f"发送请求到: {url}")

            # 在线程池中执行请求
            future = self._executor.submit(self._do_request, url, payload)

            # 轮询取消事件和请求完成
            while not future.done():
                if self._cancel_event.is_set():
                    # 取消请求（注意：这不会立即停止底层HTTP请求，但会取消future）
                    future.cancel()
                    raise Exception("请求已被取消")
                # 短暂休眠避免CPU占用过高
                time.sleep(0.05)

            # 获取结果
            content = future.result()
            self.logger.info("请求成功完成")
            return content

        except Exception as e:
            if self._cancel_event.is_set():
                raise Exception("请求已被取消")
            self.logger.error(f"API请求失败: {str(e)}")
            raise Exception(f"API请求失败: {str(e)}")


class Agent:
    """基础Agent类"""

    def __init__(self, llm_client: LLMClient, system_message: str = ""):
        """
        初始化Agent

        Args:
            llm_client: LLM客户端实例
            system_message: 系统消息，用于设置Agent的初始角色
        """
        self.llm_client = llm_client
        self.system_message = system_message
        self.conversation_history: List[Dict[str, str]] = []
        self.logger = logging.getLogger(__name__)

        # 添加系统消息到对话历史
        if self.system_message:
            self.conversation_history.append({
                "role": "system",
                "content": self.system_message
            })

    def add_message(self, role: str, content: str) -> None:
        """
        添加消息到对话历史

        Args:
            role: 消息角色 ("user", "assistant", "system")
            content: 消息内容
        """
        message = {
            "role": role,
            "content": content
        }
        self.conversation_history.append(message)
        self.logger.info(f"添加消息: {role} - {content[:50]}...")

    def send_message(self, user_message: str, **kwargs) -> str:
        """
        发送用户消息并获取响应

        Args:
            user_message: 用户消息
            **kwargs: 其他参数传递给LLM客户端

        Returns:
            Agent的响应
        """
        # 添加用户消息
        self.add_message("user", user_message)

        try:
            # 调用LLM客户端获取响应
            response = self.llm_client.chat(
                self.conversation_history, **kwargs)

            # 添加响应到对话历史
            self.add_message("assistant", response)

            return response

        except Exception as e:
            self.logger.error(f"发送消息失败: {str(e)}")
            raise Exception(f"发送消息失败: {str(e)}")

    def get_conversation_history(self) -> List[Dict[str, str]]:
        """
        获取对话历史

        Returns:
            对话历史列表
        """
        return self.conversation_history.copy()

    def clear_conversation(self) -> None:
        """清除对话历史（保留系统消息）"""
        system_msg = None
        for msg in self.conversation_history:
            if msg["role"] == "system":
                system_msg = msg
                break

        self.conversation_history = []
        if system_msg:
            self.conversation_history.append(system_msg)

        self.logger.info("对话历史已清除")

    def cancel_request(self) -> None:
        """取消当前消息收发请求"""
        if hasattr(self.llm_client, 'cancel_request'):
            self.llm_client.cancel_request()
            self.logger.info("请求取消已发送")

    def save_conversation(self, filepath: str) -> None:
        """
        保存对话到文件

        Args:
            filepath: 保存路径
        """
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.conversation_history, f,
                          ensure_ascii=False, indent=2)
            self.logger.info(f"对话已保存到: {filepath}")
        except Exception as e:
            self.logger.error(f"保存对话失败: {str(e)}")
            raise Exception(f"保存对话失败: {str(e)}")

    def load_conversation(self, filepath: str) -> None:
        """
        从文件加载对话

        Args:
            filepath: 文件路径
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                self.conversation_history = json.load(f)
            self.logger.info(f"对话已从 {filepath} 加载")
        except Exception as e:
            self.logger.error(f"加载对话失败: {str(e)}")
            raise Exception(f"加载对话失败: {str(e)}")


class TroopyAgent(Agent):
    """Troopy的Agent类"""

    def __init__(self, name: str, role: str, llm_client: LLMClient, system_message: str = ""):
        """
        初始化Troopy的Agent

        Args:
            llm_client: LLM客户端实例
            system_message: 系统消息，用于设置Agent的初始角色
        """
        super().__init__(llm_client, system_message)
        self.logger = logging.getLogger(__name__)
        self.name = name
        self.role = role
        self.id = uuid.uuid4()
