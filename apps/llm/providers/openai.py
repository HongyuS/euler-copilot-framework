# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""大模型提供商：OpenAI"""

import logging
from collections.abc import AsyncGenerator

from openai import AsyncOpenAI, AsyncStream
from openai.types.chat import ChatCompletionChunk
from typing_extensions import override

from apps.llm.token import TokenCalculator
from apps.schemas.llm import LLMChunk, LLMFunctions, LLMType

from .base import BaseProvider

_logger = logging.getLogger(__name__)

class OpenAIProvider(BaseProvider):
    """OpenAI大模型客户端"""

    _client: AsyncOpenAI
    input_tokens: int
    output_tokens: int
    _allow_chat: bool
    _allow_function: bool
    _allow_embedding: bool

    @override
    def _check_type(self) -> None:
        """检查模型能力"""
        if LLMType.VISION in self.config.llmType:
            err = "[OpenAIProvider] 当前暂不支持视觉模型"
            _logger.error(err)
            raise RuntimeError(err)

        if LLMType.CHAT not in self.config.llmType:
            self._allow_chat = False
        else:
            self._allow_chat = True
        if LLMType.FUNCTION not in self.config.llmType:
            self._allow_function = False
        else:
            self._allow_function = True
        if LLMType.EMBEDDING not in self.config.llmType:
            self._allow_embedding = False
        else:
            self._allow_embedding = True

    @override
    def _init_client(self) -> None:
        """初始化模型API客户端"""
        if not self.config.apiKey:
            self._client = AsyncOpenAI(
                base_url=self.config.baseUrl,
                timeout=self._timeout,
            )
        else:
            self._client = AsyncOpenAI(
                base_url=self.config.baseUrl,
                api_key=self.config.apiKey,
                timeout=self._timeout,
            )
        # 初始化Token计数
        self.input_tokens = 0
        self.output_tokens = 0

    def _handle_usage_chunk(self, chunk: ChatCompletionChunk | None, messages: list[dict[str, str]]) -> None:
        """处理包含usage信息的chunk"""
        if chunk and getattr(chunk, "usage", None):
            try:
                # 使用服务端统计的token计数
                usage = chunk.usage
                if usage and hasattr(usage, "prompt_tokens") and hasattr(usage, "completion_tokens"):
                    self.input_tokens = usage.prompt_tokens
                    self.output_tokens = usage.completion_tokens
            except Exception:  # noqa: BLE001
                # 忽略异常，保持已有的token统计逻辑
                _logger.warning("[OpenAIProvider] 推理框架未返回使用数据，使用本地估算逻辑")

        # 如果没有从服务端获取到token计数，使用本地估算
        if not self.input_tokens or not self.output_tokens:
            self.input_tokens = TokenCalculator().calculate_token_length(messages)
            self.output_tokens = TokenCalculator().calculate_token_length([{
                "role": "assistant",
                "content": "<think>" + self.full_thinking + "</think>" + self.full_answer,
            }])

    @override
    async def chat(
        self, messages: list[dict[str, str]],
        *, include_thinking: bool = False,
    ) -> AsyncGenerator[LLMChunk, None]:
        """聊天"""
        if not self._allow_chat:
            err = "[OpenAIProvider] 当前模型不支持Chat"
            _logger.error(err)
            raise RuntimeError(err)

        # 检查消息
        messages = self._validate_messages(messages)

        stream: AsyncStream[ChatCompletionChunk] = self._client.chat.completions.create(
            model=self.config.modelName,
            messages=messages,  # type: ignore[]
            max_tokens=self.config.maxToken,
            temperature=self.config.temperature,
            stream=True,
            stream_options={"include_usage": True},
            **self.config.extraConfig,
        )

        # 流式返回响应
        last_chunk = None
        async for chunk in stream:
            last_chunk = chunk
            if hasattr(chunk, "choices") and chunk.choices:
                delta = chunk.choices[0].delta
                if (
                    hasattr(delta, "reasoning_content") and
                    getattr(delta, "reasoning_content", None) and
                    include_thinking
                ):
                    reasoning_content = getattr(delta, "reasoning_content", "")
                    self.full_thinking += reasoning_content
                    yield LLMChunk(reasoning_content=reasoning_content)

                if (
                    hasattr(chunk.choices[0].delta, "content") and
                    chunk.choices[0].delta.content
                ):
                    self.full_answer += chunk.choices[0].delta.content
                    yield LLMChunk(content=chunk.choices[0].delta.content)

        # 处理最后一个Chunk的usage（仅在最后一个chunk会出现）
        self._handle_usage_chunk(last_chunk, messages)

    @override
    async def embedding(self, text: list[str]) -> list[list[float]]:
        if not self._allow_embedding:
            err = "[OpenAIProvider] 当前模型不支持Embedding"
            _logger.error(err)
            raise RuntimeError(err)

        # 使用 AsyncOpenAI 客户端的 embedding 功能
        response = await self._client.embeddings.create(
            input=text,
            model=self.config.modelName,
        )
        return [data.embedding for data in response.data]

    @override
    async def tool_call(self, messages: list[dict[str, str]], tools: list[LLMFunctions]) -> str:
        if not self._allow_function:
            info = "[OpenAIProvider] 当前模型不支持Function Call，将使用模拟方式"
            _logger.error(info)
            return ""

        # 检查消息
        messages = self._validate_messages(messages)

        # 实现tool_call功能
        return ""


