# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Node实体类"""

from typing import Any

from pydantic import BaseModel, Field

from apps.schemas.pool import NodePool


class APINodeInput(BaseModel):
    """API节点覆盖输入"""

    query: dict[str, Any] | None = Field(description="API节点输入参数Schema", default=None)
    body: dict[str, Any] | None = Field(description="API节点输入请求体Schema", default=None)


class APINodeOutput(BaseModel):
    """API节点覆盖输出"""

    result: dict[str, Any] | None = Field(description="API节点输出Schema", default=None)


class APINode(NodePool):
    """API节点"""

    call_id: str = "API"
    override_input: APINodeInput | None = Field(description="API节点输入覆盖", default=None)
    override_output: APINodeOutput | None = Field(description="API节点输出覆盖", default=None)
