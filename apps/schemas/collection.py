# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MongoDB中的数据结构"""

import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from apps.common.config import config
from apps.templates.generate_llm_operator_config import llm_provider_dict


class Blacklist(BaseModel):
    """
    黑名单

    Collection: blacklist
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="_id")
    question: str
    answer: str
    is_audited: bool = False
    reason_type: str = ""
    reason: str | None = None
    updated_at: float = Field(default_factory=lambda: round(datetime.now(tz=UTC).timestamp(), 3))


class LLM(BaseModel):
    """
    大模型信息

    Collection: llm
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="_id")
    user_sub: str = Field(default="", description="用户ID")
    icon: str = Field(default=llm_provider_dict["ollama"]["icon"], description="图标")
    openai_base_url: str = Field(default=config.llm.endpoint)
    openai_api_key: str = Field(default=config.llm.key)
    model_name: str = Field(default=config.llm.model)
    max_tokens: int | None = Field(default=config.llm.max_tokens)
    created_at: float = Field(default_factory=lambda: round(datetime.now(tz=UTC).timestamp(), 3))
