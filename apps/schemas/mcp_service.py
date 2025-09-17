# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP 服务相关数据结构"""

import uuid
from typing import Any

from pydantic import BaseModel, Field

from apps.models.mcp import MCPInstallStatus, MCPTools, MCPType
from apps.schemas.response_data import ResponseData


class MCPServiceCardItem(BaseModel):
    """插件中心：MCP服务卡片数据结构"""

    mcpservice_id: str = Field(..., alias="mcpserviceId", description="mcp服务ID")
    name: str = Field(..., description="mcp服务名称")
    description: str = Field(..., description="mcp服务简介")
    icon: str = Field(..., description="mcp服务图标")
    author: str = Field(..., description="mcp服务作者")
    is_active: bool = Field(default=False, alias="isActive", description="mcp服务是否激活")
    status: MCPInstallStatus = Field(default=MCPInstallStatus.INSTALLING, description="mcp服务状态")


class BaseMCPServiceOperationMsg(BaseModel):
    """插件中心：MCP服务操作Result数据结构"""

    service_id: str = Field(..., alias="serviceId", description="服务ID")


class GetMCPServiceListMsg(BaseModel):
    """GET /api/service Result数据结构"""

    current_page: int = Field(..., alias="currentPage", description="当前页码")
    services: list[MCPServiceCardItem] = Field(..., description="解析后的服务列表")


class GetMCPServiceListRsp(ResponseData):
    """GET /api/service 返回数据结构"""

    result: GetMCPServiceListMsg = Field(..., title="Result")


class UpdateMCPServiceMsg(BaseModel):
    """插件中心：MCP服务属性数据结构"""

    service_id: uuid.UUID = Field(..., alias="serviceId", description="MCP服务ID")
    name: str = Field(..., description="MCP服务名称")


class UpdateMCPServiceRsp(ResponseData):
    """POST /api/mcp_service 返回数据结构"""

    result: UpdateMCPServiceMsg = Field(..., title="Result")


class UploadMCPServiceIconMsg(BaseModel):
    """POST /api/mcp_service/icon Result数据结构"""

    service_id: str = Field(..., alias="serviceId", description="MCP服务ID")
    url: str = Field(..., description="图标URL")


class UploadMCPServiceIconRsp(ResponseData):
    """POST /api/mcp_service/icon 返回数据结构"""

    result: UploadMCPServiceIconMsg = Field(..., title="Result")


class GetMCPServiceDetailMsg(BaseModel):
    """GET /api/mcp_service/{serviceId} Result数据结构"""

    service_id: str = Field(..., alias="serviceId", description="MCP服务ID")
    icon: str = Field(description="图标", default="")
    name: str = Field(..., description="MCP服务名称")
    description: str = Field(description="MCP服务描述")
    overview: str = Field(description="MCP服务概述")
    tools: list[MCPTools] = Field(description="MCP服务Tools列表", default=[])
    status: MCPInstallStatus = Field(
        description="MCP服务状态",
        default=MCPInstallStatus.INIT,
    )


class EditMCPServiceMsg(BaseModel):
    """编辑MCP服务"""

    service_id: str = Field(..., alias="serviceId", description="MCP服务ID")
    icon: str = Field(description="图标", default="")
    name: str = Field(..., description="MCP服务名称")
    description: str = Field(description="MCP服务描述")
    overview: str = Field(description="MCP服务概述")
    data: dict[str, Any] = Field(description="MCP服务配置")
    mcp_type: MCPType = Field(alias="mcpType", description="MCP 类型")


class GetMCPServiceDetailRsp(ResponseData):
    """GET /api/service/{serviceId} 返回数据结构"""

    result: GetMCPServiceDetailMsg | EditMCPServiceMsg = Field(..., title="Result")


class DeleteMCPServiceRsp(ResponseData):
    """DELETE /api/service/{serviceId} 返回数据结构"""

    result: BaseMCPServiceOperationMsg = Field(..., title="Result")


class ActiveMCPServiceRsp(ResponseData):
    """POST /api/mcp/active/{serviceId} 返回数据结构"""

    result: BaseMCPServiceOperationMsg = Field(..., title="Result")
