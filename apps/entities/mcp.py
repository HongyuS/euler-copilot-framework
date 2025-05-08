# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP 相关数据结构"""

from enum import Enum

from lancedb.pydantic import LanceModel, Vector
from pydantic import BaseModel, Field


class MCPType(str, Enum):
    """MCP 类型"""

    SSE = "sse"
    STDIO = "stdio"
    STREAMABLE = "stream"


class MCPServerConfig(BaseModel):
    """MCP 服务器配置"""

    name: str = Field(description="MCP 服务器自然语言名称")
    description: str = Field(description="MCP 服务器自然语言描述")
    type: MCPType = Field(description="MCP 服务器类型", default=MCPType.STDIO)
    is_active: bool = Field(description="MCP 服务器是否启用", default=False, alias="isActive")
    auto_install: bool = Field(description="是否自动安装MCP服务器", default=True, alias="autoInstall")
    icon_path: str = Field(description="MCP 服务器图标路径")
    env: dict[str, str] = Field(description="MCP 服务器环境变量")


class MCPServerStdioConfig(MCPServerConfig):
    """MCP 服务器配置"""

    command: str = Field(description="MCP 服务器命令")
    args: list[str] = Field(description="MCP 服务器命令参数")


class MCPServerSSEConfig(MCPServerConfig):
    """MCP 服务器配置"""

    url: str = Field(description="MCP 服务器地址")


class MCPConfig(BaseModel):
    """MCP 配置"""

    mcp_servers: dict[
        str,
        MCPServerSSEConfig | MCPServerStdioConfig,
    ] = Field(description="MCP 服务器配置", alias="mcpServers")


class MCPCollection(BaseModel):
    """MCP相关信息，存储在MongoDB的 ``mcp`` 集合中"""

    id: str = Field(description="MCP ID", alias="_id")
    name: str = Field(description="MCP 自然语言名称")
    description: str = Field(description="MCP 自然语言描述")
    type: MCPType = Field(description="MCP 类型")
    activated: list[str] = Field(description="激活该MCP的用户ID列表")


class MCPVector(LanceModel):
    """MCP向量化数据，存储在LanceDB的 ``mcp`` 表中"""

    id: str = Field(description="MCP ID")
    embedding: Vector(dim=1024) = Field(description="MCP描述的向量信息")  # type: ignore[call-arg]
