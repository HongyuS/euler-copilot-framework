"""
问答大模型调用

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionChunk

from apps.common.config import Config
from apps.constants import REASONING_BEGIN_TOKEN, REASONING_END_TOKEN
from apps.llm.token import TokenCalculator
from apps.manager.task import TaskManager

logger = logging.getLogger(__name__)


@dataclass
class ReasoningContent:
    """推理内容处理类"""

    content: str = ""
    is_reasoning: bool = False
    reasoning_type: str = ""
    is_first_chunk: bool = True

    def process_first_chunk(self, chunk: ChatCompletionChunk) -> tuple[str, str]:
        """处理第一个chunk"""
        reason = ""
        text = ""

        if hasattr(chunk.choices[0].delta, "reasoning_content"):
            reason = "<think>" + chunk.choices[0].delta.reasoning_content or "" # type: ignore[attr-defined]
            self.reasoning_type = "args"
            self.is_reasoning = True
        else:
            for token in REASONING_BEGIN_TOKEN:
                if token == (chunk.choices[0].delta.content or ""):
                    reason = "<think>"
                    self.reasoning_type = "tokens"
                    self.is_reasoning = True
                    break

        self.is_first_chunk = False
        return reason, text

    def process_chunk(self, chunk: ChatCompletionChunk) -> tuple[str, str]:
        """处理普通chunk"""
        reason = ""
        text = ""

        if not self.is_reasoning:
            text = chunk.choices[0].delta.content or ""
            return reason, text

        if self.reasoning_type == "args":
            if hasattr(chunk.choices[0].delta, "reasoning_content"):
                reason = chunk.choices[0].delta.reasoning_content or ""   # type: ignore[attr-defined]
            else:
                self.is_reasoning = False
                reason = "</think>"
        elif self.reasoning_type == "tokens":
            for token in REASONING_END_TOKEN:
                if token == (chunk.choices[0].delta.content or ""):
                    self.is_reasoning = False
                    reason = "</think>"
                    text = ""
                    break
            if self.is_reasoning:
                reason = chunk.choices[0].delta.content or ""

        return reason, text


class ReasoningLLM:
    """调用用于问答的大模型"""

    def __init__(self) -> None:
        """判断配置文件里用了哪种大模型；初始化大模型客户端"""
        self._config = Config().get_config()
        self._init_client()

    def _init_client(self) -> None:
        """初始化OpenAI客户端"""
        if not self._config.llm.key:
            self._client = AsyncOpenAI(
                base_url=self._config.llm.endpoint,
            )
            return

        self._client = AsyncOpenAI(
            api_key=self._config.llm.key,
            base_url=self._config.llm.endpoint,
        )

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

    async def _create_stream(
        self,
        messages: list[dict[str, str]],
        max_tokens: int | None,
        temperature: float | None,
    ) -> AsyncGenerator[ChatCompletionChunk, None]:
        """创建流式响应"""
        return await self._client.chat.completions.create(
            model=self._config.llm.model,
            messages=messages,  # type: ignore[]
            max_tokens=max_tokens or self._config.llm.max_tokens,
            temperature=temperature or self._config.llm.temperature,
            stream=True,
        )  # type: ignore[]

    async def call(  # noqa: PLR0913
        self,
        task_id: str,
        messages: list[dict[str, str]],
        max_tokens: int | None = None,
        temperature: float | None = None,
        *,
        streaming: bool = True,
        result_only: bool = True,
    ) -> AsyncGenerator[str, None]:
        """调用大模型，分为流式和非流式两种"""
        try:
            input_tokens = TokenCalculator().calculate_token_length(messages)
            msg_list = self._validate_messages(messages)
        except ValueError as e:
            err = "消息格式错误"
            logger.exception(err)
            raise ValueError(err) from e

        stream = await self._create_stream(msg_list, max_tokens, temperature)
        reasoning = ReasoningContent()
        reasoning_content = ""
        result = ""

        try:
            async for chunk in stream:
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
            output_tokens = TokenCalculator().calculate_token_length(
                [{"role": "assistant", "content": result}], pure_text=True,
            )
            await TaskManager.update_token_summary(task_id, input_tokens, output_tokens)

        except Exception as e:
            err = "调用大模型失败"
            logger.exception(err)
            raise RuntimeError(err) from e
