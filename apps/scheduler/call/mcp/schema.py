# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP Call相关的数据结构"""

from typing import Any

from pydantic import Field

from apps.scheduler.call.core import DataBase


class MCPInput(DataBase):
    """MCP Call输入"""

    mcp_ids: list[str] = Field(description="MCP Server的ID列表")


class MCPOutput(DataBase):
    """MCP Call输出"""

    message: str = Field(description="MCP Server的自然语言输出")
    data: dict[str, Any] = Field(description="MCP Server的数据输出")
