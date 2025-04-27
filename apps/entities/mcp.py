"""
MCP 相关数据结构

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

from enum import Enum

from pydantic import BaseModel, Field


class MCPServerConfig(BaseModel):
    """MCP 服务器配置"""

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
    ] = Field(description="MCP 服务器配置")


class MCPType(str, Enum):
    """MCP 类型"""

    SSE = "sse"
    STDIO = "stdio"
    STREAMABLE = "stream"


class MCPMessageType(str, Enum):
    """MCP 消息类型"""

    INIT = "initialize"
    TOOL_LIST = "tools/list"
    TOOL_CALL = "tools/call"
    PING = "ping"
