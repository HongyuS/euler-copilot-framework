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
    ERROR = "error"


class MCPBasicConfig(BaseModel):
    """MCP 基本配置"""

    env: dict[str, str] = Field(description="MCP 服务器环境变量", default={})
    autoApprove: list[str] = Field(description="自动批准的MCP权限列表", default=[])  # noqa: N815
    autoInstall: bool = Field(description="是否自动安装MCP服务器", default=True)  # noqa: N815
    timeout: int = Field(description="MCP 服务器超时时间（秒）", default=60, alias="timeout")


class MCPServerStdioConfig(MCPBasicConfig):
    """MCP 服务器配置"""

    command: str = Field(description="MCP 服务器命令")
    args: list[str] = Field(description="MCP 服务器命令参数")


class MCPServerSSEConfig(MCPBasicConfig):
    """MCP 服务器配置"""

    url: str = Field(description="MCP 服务器地址", default="")


class MCPServerItem(BaseModel):
    """MCP 服务器信息"""

    mcpServers: dict[str, MCPServerStdioConfig | MCPServerSSEConfig] = Field( # noqa: N815
        description="MCP 服务器列表",
        max_length=1,
        min_length=1,
    )


class MCPServerConfig(MCPServerItem):
    """MCP 服务器配置"""

    name: str = Field(description="MCP 服务器自然语言名称", default="")
    overview: str = Field(description="MCP 服务器概述", default="")
    description: str = Field(description="MCP 服务器自然语言描述", default="")
    mcpType: MCPType = Field(description="MCP 服务器类型", default=MCPType.STDIO)  # noqa: N815
    author: str = Field(description="MCP 服务器上传者", default="")


class GoalEvaluationResult(BaseModel):
    """MCP 目标评估结果"""

    can_complete: bool = Field(description="是否可以完成目标")
    reason: str = Field(description="评估原因")


class RestartStepIndex(BaseModel):
    """MCP重新规划的步骤索引"""

    start_index: int = Field(description="重新规划的起始步骤索引")
    reasoning: str = Field(description="重新规划的原因")


class Risk(str, Enum):
    """MCP工具风险类型"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ToolSkip(BaseModel):
    """MCP工具跳过执行结果"""

    skip: bool = Field(description="是否跳过当前步骤", default=False)


class ToolRisk(BaseModel):
    """MCP工具风险评估结果"""

    risk: Risk = Field(description="风险类型", default=Risk.LOW)
    reason: str = Field(description="风险原因", default="")


class ErrorType(str, Enum):
    """MCP工具错误类型"""

    MISSING_PARAM = "missing_param"
    DECORRECT_PLAN = "decorrect_plan"


class ToolExcutionErrorType(BaseModel):
    """MCP工具执行错误"""

    type: ErrorType = Field(description="错误类型", default=ErrorType.MISSING_PARAM)
    reason: str = Field(description="错误原因", default="")


class IsParamError(BaseModel):
    """MCP工具参数错误"""

    is_param_error: bool = Field(description="是否是参数错误", default=False)


class MCPSelectResult(BaseModel):
    """MCP选择结果"""

    mcp_id: str = Field(description="MCP Server的ID")


class MCPToolSelectResult(BaseModel):
    """MCP工具选择结果"""

    name: str = Field(description="工具名称")


class MCPToolIdsSelectResult(BaseModel):
    """MCP工具ID选择结果"""

    tool_ids: list[str] = Field(description="工具ID列表")


class MCPPlanItem(BaseModel):
    """MCP 计划"""

    step_id: str = Field(description="步骤的ID", default="")
    content: str = Field(description="计划内容")
    tool: str = Field(description="工具名称")
    instruction: str = Field(description="工具指令")


class MCPPlan(BaseModel):
    """MCP 计划"""

    plans: list[MCPPlanItem] = Field(description="计划列表", default=[])


class Step(BaseModel):
    """MCP步骤"""

    tool_id: str = Field(description="工具ID")
    description: str = Field(description="步骤描述")
