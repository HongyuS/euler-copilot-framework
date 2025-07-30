# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Node实体类"""

from typing import Any

from pydantic import BaseModel, Field


class APINodeInput(BaseModel):
    """API节点覆盖输入"""

    query: dict[str, Any] | None = Field(description="API节点输入参数Schema", default=None)
    body: dict[str, Any] | None = Field(description="API节点输入请求体Schema", default=None)


class APINodeOutput(BaseModel):
    """API节点覆盖输出"""

    result: dict[str, Any] | None = Field(description="API节点输出Schema", default=None)
