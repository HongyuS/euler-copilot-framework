# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""App和Service等数据库内数据结构"""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class ServiceApiInfo(BaseModel):
    """外部服务API信息"""

    filename: str = Field(description="OpenAPI文件名")
    description: str = Field(description="OpenAPI中关于API的Summary")
    path: str = Field(description="OpenAPI文件路径")


class Node(BaseModel):
    """Node合并后的信息（不存库）"""

    id: str = Field(alias="_id")
    name: str
    description: str
    created_at: float = Field(default_factory=lambda: round(datetime.now(tz=UTC).timestamp(), 3))
    service_id: str | None = Field(description="Node所属的Service ID", default=None)
    call_id: str = Field(description="所使用的Call的ID")
    params_schema: dict[str, Any] = Field(description="Node的参数schema", default={})
    output_schema: dict[str, Any] = Field(description="Node输出的完整Schema", default={})
