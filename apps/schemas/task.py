# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Task相关数据结构定义"""

from typing import Any

from pydantic import BaseModel, Field

from .flow import Step
from .mcp import MCPPlan


class CheckpointExtra(BaseModel):
    """Executor额外数据"""

    current_input: dict[str, Any] = Field(description="当前输入数据", default={})
    error_message: str = Field(description="错误信息", default="")
    retry_times: int = Field(description="当前步骤重试次数", default=0)


class TaskExtra(BaseModel):
    """任务额外数据"""

    temporary_plans: MCPPlan | None = Field(description="临时计划列表", default=None)


class StepQueueItem(BaseModel):
    """步骤栈中的元素"""

    step_id: str = Field(description="步骤ID")
    step: Step = Field(description="步骤")
    enable_filling: bool | None = Field(description="是否启用填充", default=None)
    to_user: bool | None = Field(description="是否输出给用户", default=None)
