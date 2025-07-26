# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP 默认配置"""

import logging
import uuid

from apps.schemas.mcp import (
    MCPServerConfig,
    MCPServerSSEConfig,
    MCPServerStdioConfig,
    MCPType,
)

logger = logging.getLogger(__name__)
DEFAULT_STDIO = MCPServerConfig(
    name="MCP服务_" + uuid.uuid4().hex[:6],
    description="MCP服务描述",
    mcp_type=MCPType.STDIO,
    config=MCPServerStdioConfig(
        command="uvx",
        args=[
            "your_package",
        ],
        env={
            "EXAMPLE_ENV": "example_value",
        },
    ),
)
"""默认的Stdio协议MCP Server配置"""

DEFAULT_SSE = MCPServerConfig(
    name="MCP服务_" + uuid.uuid4().hex[:6],
    description="MCP服务描述",
    mcp_type=MCPType.SSE,
    config=MCPServerSSEConfig(
        url="http://test.domain/sse",
        env={
            "EXAMPLE_HEADER": "example_value",
        },
    ),
)
"""默认的SSE协议MCP Server配置"""


async def get_default(mcp_type: MCPType) -> MCPServerConfig:
    """
    用于获取默认的 MCP 配置

    :param MCPType mcp_type: MCP类型
    :return: MCP配置
    :rtype: MCPConfig
    :raises ValueError: 未找到默认的 MCP 配置
    """
    if mcp_type == MCPType.STDIO:
        return DEFAULT_STDIO
    if mcp_type == MCPType.SSE:
        return DEFAULT_SSE
    err = f"未找到默认的 MCP 配置: {mcp_type}"
    logger.error(err)
    raise ValueError(err)
