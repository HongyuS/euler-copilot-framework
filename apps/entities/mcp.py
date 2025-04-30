"""
MCP 相关数据结构

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

from enum import Enum
from typing import Any

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


class MCPMessageType(str, Enum):
    """MCP 消息类型"""

    INIT = "initialize"
    TOOL_LIST = "tools/list"
    TOOL_CALL = "tools/call"
    PING = "ping"


class MCPRPCBase(BaseModel):
    """MCP RPC 基础"""

    jsonrpc: str = Field(description="JSON-RPC 版本", default="2.0")
    id: str = Field(description="MCP 消息 ID")


class MCPRequest(MCPRPCBase):
    """MCP 请求基础"""

    method: MCPMessageType = Field(description="MCP 消息类型")
    params: dict[str, Any] | None = Field(description="MCP 消息参数", default=None)


class MCPResponseError(BaseModel):
    """MCP 响应错误"""

    code: int = Field(description="MCP 错误码")
    message: str = Field(description="MCP 错误消息")
    data: dict[str, Any] | None = Field(description="MCP 错误数据")


class MCPResponse(BaseModel):
    """MCP 响应基础"""

    jsonrpc: str = Field(description="JSON-RPC 版本", default="2.0")
    id: str = Field(description="MCP 消息 ID")
    result: dict[str, Any] | None = Field(description="MCP 消息结果", default=None)
    error: MCPResponseError | None = Field(description="MCP 消息错误", default=None)
