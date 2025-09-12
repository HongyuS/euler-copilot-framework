# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""大模型提供商：VLLM"""

import logging
from collections.abc import AsyncGenerator

from typing_extensions import override

from apps.models.llm import LLMType
from apps.schemas.llm import LLMChunk

from .base import BaseProvider

_logger = logging.getLogger(__name__)


class VLLMProvider(BaseProvider):
    """VLLM提供商"""

    @override
    def _init_client(self) -> None:
        """初始化模型API客户端"""
        pass

    @override
    async def chat(
        self, messages: list[dict[str, str]],
        *, include_thinking: bool = False,
    ) -> AsyncGenerator[LLMChunk, None]:
        pass

    @override
    def _check_type(self) -> None:
        """检查模型能力是否包含Vision"""
        if LLMType.VISION in self.config.llmType:
            err = "[VLLMProvider] 当前暂不支持视觉模型"
            _logger.error(err)
            raise RuntimeError(err)
