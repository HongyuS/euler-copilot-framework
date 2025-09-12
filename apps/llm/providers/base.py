# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""大模型服务平台 基类"""

import logging
from abc import abstractmethod
from collections.abc import AsyncGenerator
from typing import Any

from apps.models.llm import LLMData
from apps.schemas.llm import LLMChunk

_logger = logging.getLogger(__name__)

class BaseProvider:
    """大模型服务平台 基类"""

    @staticmethod
    def _validate_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
        """验证消息格式是否正确"""
        if messages[0]["role"] != "system":
            # 添加默认系统消息
            messages.insert(0, {"role": "system", "content": "You are a helpful assistant."})

        if messages[-1]["role"] != "user":
            err = f"消息格式错误，最后一个消息必须是用户消息：{messages[-1]}"
            raise ValueError(err)

        return messages


    def __init__(self, llm_config: LLMData | None = None) -> None:
        """保存LLMConfig"""
        if not llm_config:
            err = "未设置大模型配置"
            _logger.error(err)
            raise RuntimeError(err)

        self.config: LLMData = llm_config
        self._check_type()
        self._init_client()

    @abstractmethod
    def _check_type(self) -> None:
        """检查大模型的类型"""
        raise NotImplementedError

    @abstractmethod
    def _init_client(self) -> None:
        """初始化模型API客户端"""

    async def chat(
        self, messages: list[dict[str, str]],
        *, include_thinking: bool = False,
    ) -> AsyncGenerator[LLMChunk, None]:
        """聊天"""
        raise NotImplementedError


    async def embedding(self, text: list[str]) -> list[list[float]]:
        """向量化"""
        raise NotImplementedError


    async def tool_call(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """工具调用"""
        raise NotImplementedError
