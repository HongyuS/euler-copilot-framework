# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""大模型返回的chunk"""

from typing import Any

from pydantic import BaseModel, Field


class LLMChunk(BaseModel):
    """大模型返回的chunk"""

    reasoning_content: str | None = None
    content: str | None = None
    tool_call: dict[str, Any] | None = None


class LLMFunctions(BaseModel):
    """大模型可选调用的函数"""

    name: str = Field(description="函数名称")
    description: str = Field(description="函数描述")
    param_schema: dict[str, Any] = Field(description="函数参数的JSON Schema")
