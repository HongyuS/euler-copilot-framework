"""
MCP工具

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

from apps.entities.scheduler import CallInfo
from apps.scheduler.call.core import CoreCall
from apps.scheduler.call.mcp.schema import MCPInput, MCPOutput


class MCP(CoreCall, input_model=MCPInput, output_model=MCPOutput):
    """MCP工具"""

    @classmethod
    def info(cls) -> CallInfo:
        """返回Call的名称和描述"""
        return CallInfo(name="MCP", description="调用MCP Server，执行工具")


