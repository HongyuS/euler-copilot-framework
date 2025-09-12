# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""大模型提供商：OpenAI"""

import logging
from collections.abc import AsyncGenerator
from typing import Any

from openai import AsyncOpenAI
from typing_extensions import override

from apps.models.llm import LLMType
from apps.schemas.llm import LLMChunk

from .base import BaseProvider

_logger = logging.getLogger(__name__)

class OpenAIProvider(BaseProvider):
    """OpenAI大模型客户端"""

    @override
    def _check_type(self) -> None:
        """检查模型能力"""
        if LLMType.VISION in self.config.llmType:
            err = "[OpenAIProvider] 当前暂不支持视觉模型"
            _logger.error(err)
            raise RuntimeError(err)

    @override
    def _init_client(self) -> None:
        """初始化模型API客户端"""
        if not self.config.apiKey:
            self._client = AsyncOpenAI(
                base_url=self.config.baseUrl,
            )
        else:
            self._client = AsyncOpenAI(
                base_url=self.config.baseUrl,
                api_key=self.config.apiKey,
            )
        # 初始化Token计数
        self.input_tokens = 0
        self.output_tokens = 0

    @override
    async def chat(
        self, messages: list[dict[str, str]],
        *, include_thinking: bool = False,
    ) -> AsyncGenerator[LLMChunk, None]:
        stream = self._client.chat.completions.create(
            model=self.config.modelName,
            messages=messages,  # type: ignore[]
            max_tokens=self.config.maxToken,
            temperature=self.config.temperature,
            stream=True,
            stream_options={"include_usage": True},
        )

        # 流式返回响应
        async for chunk in stream:
            if hasattr(chunk, "choices") and chunk.choices:
                if (
                    hasattr(chunk.choices[0].delta, "reasoning_content") and
                    chunk.choices[0].delta.reasoning_content and
                    include_thinking
                ):
                    yield LLMChunk(reasoning_content=chunk.choices[0].delta.reasoning_content)

                if (
                    hasattr(chunk.choices[0].delta, "content") and
                    chunk.choices[0].delta.content
                ):
                    yield LLMChunk(content=chunk.choices[0].delta.content)

            # 处理最后一个Chunk的usage（仅在最后一个chunk会出现）
            if getattr(chunk, "usage", None):
                try:
                    # 使用服务端统计的token计数
                    self.input_tokens = chunk.usage.prompt_tokens
                    self.output_tokens = chunk.usage.completion_tokens
                except Exception as exc:  # noqa: BLE001
                    # 忽略异常，保持已有的token统计逻辑
                    _logger.warning("[OpenAIProvider] 解析usage失败: %s", exc)

    @override
    async def embedding(self, text: list[str]) -> list[list[float]]:
        # 使用 AsyncOpenAI 客户端的 embedding 功能
        response = await self._client.embeddings.create(
            input=text,
            model=self.config.modelName,
        )
        return [data.embedding for data in response.data]

    @override
    async def tool_call(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        return ""
