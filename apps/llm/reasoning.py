# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""问答大模型调用"""

import logging
from collections.abc import AsyncGenerator

from apps.models.llm import LLMData

from .token import TokenCalculator

logger = logging.getLogger(__name__)


class ReasoningLLM:
    """调用用于问答的大模型"""

    input_tokens: int = 0
    output_tokens: int = 0
    timeout: float = 30.0

    def __init__(self, llm_config: LLMData | None = None) -> None:
        """判断配置文件里用了哪种大模型；初始化大模型客户端"""

    async def call(  # noqa: C901, PLR0912, PLR0913
        self,
        messages: list[dict[str, str]],
        max_tokens: int | None = None,
        temperature: float | None = None,
        *,
        streaming: bool = True,
        result_only: bool = True,
        model: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """调用大模型，分为流式和非流式两种"""
        # 检查max_tokens和temperature
        if max_tokens is None:
            max_tokens = self.config.maxToken
        if temperature is None:
            temperature = self.config.temperature
        if model is None:
            model = self.config.modelName
        stream = await self._create_stream(msg_list, max_tokens, temperature, model)
        reasoning = ReasoningContent()
        reasoning_content = ""
        result = ""

        async for chunk in stream:
            # 如果包含统计信息
            if chunk.usage:
                self.input_tokens = chunk.usage.prompt_tokens
                self.output_tokens = chunk.usage.completion_tokens
            # 如果没有Choices
            if not chunk.choices:
                continue

            # 处理chunk
            if reasoning.is_first_chunk:
                reason, text = reasoning.process_first_chunk(chunk)
            else:
                reason, text = reasoning.process_chunk(chunk)

            # 推送消息
            if streaming:
                if reason and not result_only:
                    yield reason
                if text:
                    yield text

            # 整理结果
            reasoning_content += reason
            result += text

        if not streaming:
            if not result_only:
                yield reasoning_content
            yield result

        logger.info("[Reasoning] 推理内容: %s\n\n%s", reasoning_content, result)

        # 更新token统计
        if self.input_tokens == 0 or self.output_tokens == 0:
            self.input_tokens = TokenCalculator().calculate_token_length(
                messages,
            )
            self.output_tokens = TokenCalculator().calculate_token_length(
                [{"role": "assistant", "content": result}],
                pure_text=True,
            )
