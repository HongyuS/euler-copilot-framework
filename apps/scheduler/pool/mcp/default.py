# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP 默认配置"""

import logging
import random

from sqids.sqids import Sqids

from apps.entities.mcp import (
    MCPConfig,
    MCPServerSSEConfig,
    MCPServerStdioConfig,
    MCPType,
)

logger = logging.getLogger(__name__)
sqids = Sqids(min_length=10)
DEFAULT_STDIO = MCPServerStdioConfig(
    name="MCP服务名称",
    description="MCP服务描述",
    type=MCPType.STDIO,
    command="uvx",
    args=[
        "your_package",
    ],
    env={
        "EXAMPLE_ENV": "example_value",
    },
)
"""默认的Stdio协议MCP Server配置"""

DEFAULT_SSE = MCPServerSSEConfig(
    name="MCP服务名称",
    description="MCP服务描述",
    type=MCPType.SSE,
    url="http://test.domain/sse",
    env={
        "EXAMPLE_HEADER": "example_value",
    },
)
"""默认的SSE协议MCP Server配置"""


async def get_default(mcp_type: MCPType) -> MCPConfig:
    """
    用于获取默认的 MCP 配置

    :param MCPType mcp_type: MCP类型
    :return: MCP配置
    :rtype: MCPConfig
    :raises ValueError: 未找到默认的 MCP 配置
    """
    random_list = [random.randint(0, 1000000) for _ in range(5)]  # noqa: S311
    if mcp_type == MCPType.STDIO:
        return MCPConfig(
            mcpServers={
                sqids.encode(random_list): DEFAULT_STDIO,
            },
        )
    if mcp_type == MCPType.SSE:
        return MCPConfig(
            mcpServers={
                sqids.encode(random_list): DEFAULT_SSE,
            },
        )
    err = f"未找到默认的 MCP 配置: {mcp_type}"
    logger.error(err)
    raise ValueError(err)
