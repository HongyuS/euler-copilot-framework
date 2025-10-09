# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""大模型提供商"""

from .base import BaseProvider
from .ollama import OllamaProvider
from .openai import OpenAIProvider
from .tei import TEIProvider

__all__ = [
    "BaseProvider",
    "OllamaProvider",
    "OpenAIProvider",
    "TEIProvider",
]
