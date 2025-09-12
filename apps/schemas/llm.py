# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""大模型返回的chunk"""

from pydantic import BaseModel


class LLMChunk(BaseModel):
    """大模型返回的chunk"""

    reasoning_content: str | None = None
    content: str | None = None
