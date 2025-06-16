# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP Call相关的数据结构"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from apps.scheduler.call.core import DataBase


class MCPInput(DataBase):
    """MCP Call输入"""

    avaliable_tools: dict[str, list[str]] = Field(description="MCP Server ID及其可用的工具名称列表")
    max_steps: int = Field(description="最大步骤数")


class MCPMessageType(str, Enum):
    """MCP Message类型"""

    PLAN_BEGIN = "plan_begin"
    PLAN_END = "plan_end"
    TOOL_BEGIN = "tool_begin"
    TOOL_END = "tool_end"
    EVALUATE = "evaluate"
    FINISH_BEGIN = "finish_begin"
    FINISH_END = "finish_end"


class MCPMessage(BaseModel):
    """MCP Message"""

    msg_type: MCPMessageType = Field(description="消息的类型")
    message: str = Field(description="消息的内容")
    data: dict[str, Any] = Field(description="工具的输出")


class MCPOutput(DataBase):
    """MCP Call输出"""

    message: str = Field(description="MCP Server的自然语言输出")
