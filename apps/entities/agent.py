# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""agent 相关数据结构"""

from pydantic import Field

from apps.entities.enum_var import (
    AppType,
    MetadataType,
)
from apps.entities.flow import Permission
from apps.entities.mcp import MCPMetadataBase


class AgentAppMetadata(MCPMetadataBase):
    """智能体App的元数据"""

    type: MetadataType = MetadataType.APP
    app_type: AppType = Field(default=AppType.AGENT, description="应用类型", frozen=True)
    published: bool = Field(description="是否发布", default=False)
    history_len: int = Field(description="对话轮次", default=3, le=10)
    mcp_service: list[str] = Field(default=[], alias="mcpService", description="MCP服务id列表")
    permission: Permission | None = Field(description="应用权限配置", default=None)
    version: str = Field(description="元数据版本")
