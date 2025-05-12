# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP工具"""
from collections.abc import AsyncGenerator
from typing import Any

from pydantic import Field

from apps.entities.enum_var import CallOutputType
from apps.entities.scheduler import (
    CallInfo,
    CallOutputChunk,
    CallVars,
)
from apps.scheduler.call.core import CoreCall
from apps.scheduler.call.mcp.schema import MCPInput, MCPOutput
from apps.scheduler.mcp.host import MCPHost
from apps.scheduler.mcp.tool import MCPToolHelper


class MCP(CoreCall, input_model=MCPInput, output_model=MCPOutput):
    """MCP工具"""

    mcp_list: list[str] = Field(description="MCP Server ID列表")

    @classmethod
    def info(cls) -> CallInfo:
        """
        返回Call的名称和描述

        :return: Call的名称和描述
        :rtype: CallInfo
        """
        return CallInfo(name="MCP", description="调用MCP Server，执行工具")

    async def _init(self, call_vars: CallVars) -> MCPInput:
        """初始化MCP"""
        # 获取MCP交互类
        mcp_host = MCPHost()
        self._mcp = await mcp_host.get_clients(call_vars.ids.user_sub, self.mcp_list)

        # 获取MCP列表
        mcp_helper = MCPToolHelper()
        task, result = await mcp_helper.select_top_mcp(call_vars.task, call_vars.query, call_vars.mcp_list)



    async def _exec(self, input_data: dict[str, Any]) -> AsyncGenerator[CallOutputChunk, None]:
        """执行MCP"""
        pass

