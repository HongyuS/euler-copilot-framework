"""
MCP工具 数据结构

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

from typing import Any

from pydantic import Field

from apps.scheduler.call.core import DataBase


class MCPInput(DataBase):
    """MCP工具输入"""

    mcp_ids: list[str] = Field(description="MCP Server的ID列表")


class MCPOutput(DataBase):
    """MCP工具输出"""

    message: str = Field(description="MCP Server的自然语言输出")
    data: dict[str, Any] = Field(description="MCP Server的数据输出")
