# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP 相关数据结构"""

from enum import Enum

from pydantic import BaseModel, Field

from apps.models.mcp import MCPType


class MCPStatus(str, Enum):
    """MCP 状态"""

    UNINITIALIZED = "uninitialized"
    RUNNING = "running"
    STOPPED = "stopped"


class MCPBasicConfig(BaseModel):
    """MCP 基本配置"""

    env: dict[str, str] = Field(description="MCP 服务器环境变量", default={})
    auto_approve: list[str] = Field(description="自动批准的MCP工具ID列表", default=[], alias="autoApprove")
    disabled: bool = Field(description="MCP 服务器是否禁用", default=False)
    auto_install: bool = Field(description="是否自动安装MCP服务器", default=True, alias="autoInstall")


class MCPServerStdioConfig(MCPBasicConfig):
    """MCP 服务器配置"""

    command: str = Field(description="MCP 服务器命令")
    args: list[str] = Field(description="MCP 服务器命令参数")


class MCPServerSSEConfig(MCPBasicConfig):
    """MCP 服务器配置"""

    url: str = Field(description="MCP 服务器地址", default="")


class MCPServerConfig(BaseModel):
    """MCP 服务器配置"""

    name: str = Field(description="MCP 服务器自然语言名称", default="")
    overview: str = Field(description="MCP 服务器概述", default="")
    description: str = Field(description="MCP 服务器自然语言描述", default="")
    type: MCPType = Field(description="MCP 服务器类型", default=MCPType.STDIO)
    author: str = Field(description="MCP 服务器上传者", default="")
    config: MCPServerStdioConfig | MCPServerSSEConfig = Field(description="MCP 服务器配置")


class MCPSelectResult(BaseModel):
    """MCP选择结果"""

    mcp_id: str = Field(description="MCP Server的ID")


class MCPToolSelectResult(BaseModel):
    """MCP工具选择结果"""

    name: str = Field(description="工具名称")


class MCPPlanItem(BaseModel):
    """MCP 计划"""

    content: str = Field(description="计划内容")
    tool: str = Field(description="工具名称")
    instruction: str = Field(description="工具指令")


class MCPPlan(BaseModel):
    """MCP 计划"""

    plans: list[MCPPlanItem] = Field(description="计划列表")
