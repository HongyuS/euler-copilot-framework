# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""大模型返回的chunk"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class LLMChunk(BaseModel):
    """大模型返回的chunk"""

    reasoning_content: str | None = None
    content: str | None = None
    tool_call: dict[str, Any] | None = None


class LLMType(str, Enum):
    """大模型类型"""

    CHAT = "chat"
    """模型支持Chat"""
    FUNCTION = "function"
    """模型支持Function Call"""
    EMBEDDING = "embedding"
    """模型支持Embedding"""
    VISION = "vision"
    """模型支持图片理解"""
    THINKING = "thinking"
    """模型支持思考推理"""


class LLMProvider(str, Enum):
    """Function Call后端"""

    OLLAMA = "ollama"
    """Ollama"""
    OPENAI = "openai"
    """OpenAI"""
    TEI = "tei"
    """TEI"""


class LLMFunctions(BaseModel):
    """大模型可选调用的函数"""

    name: str = Field(description="函数名称")
    description: str = Field(description="函数描述")
    param_schema: dict[str, Any] = Field(description="函数参数的JSON Schema")
