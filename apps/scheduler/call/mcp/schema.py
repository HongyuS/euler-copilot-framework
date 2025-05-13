# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP Call相关的数据结构"""

from typing import Any

from pydantic import Field

from apps.scheduler.call.core import DataBase


class MCPInput(DataBase):
    """MCP Call输入"""

    avaliable_tools: dict[str, list[str]] = Field(description="MCP Server ID及其可用的工具名称列表")


class MCPOutput(DataBase):
    """MCP Call输出"""

    tool_id: str = Field(description="MCP Server的工具ID")
    tool_description: str = Field(description="MCP Server的工具描述")
    message: str = Field(description="MCP Server的自然语言输出")
    data: dict[str, Any] = Field(description="MCP Server的数据输出")
