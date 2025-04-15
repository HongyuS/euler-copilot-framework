"""
Task相关数据结构定义

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from apps.entities.enum_var import StepStatus
from apps.entities.flow import Step


class FlowStepHistory(BaseModel):
    """
    任务执行历史；每个Executor每个步骤执行后都会创建

    Collection: flow_history
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="_id")
    task_id: str = Field(description="任务ID")
    flow_id: str = Field(description="FlowID")
    step_id: str = Field(description="当前步骤名称")
    status: StepStatus = Field(description="当前步骤状态")
    input_data: dict[str, Any] = Field(description="当前Step执行的输入", default={})
    output_data: dict[str, Any] = Field(description="当前Step执行后的结果", default={})
    created_at: float = Field(default_factory=lambda: round(datetime.now(tz=UTC).timestamp(), 3))


class ExecutorState(BaseModel):
    """FlowExecutor状态"""

    # 执行器级数据
    flow_id: str = Field(description="Flow ID")
    description: str = Field(description="Flow描述")
    status: StepStatus = Field(description="Flow执行状态")
    # 附加信息
    step_id: str = Field(description="当前步骤ID")
    step_name: str = Field(description="当前步骤名称")
    app_id: str = Field(description="应用ID")
    slot: dict[str, Any] = Field(description="待填充参数的JSON Schema", default={})


class TaskIds(BaseModel):
    """任务涉及的各种ID"""

    session_id: str = Field(description="会话ID")
    group_id: str = Field(description="组ID")
    conversation_id: str = Field(description="对话ID")
    record_id: str = Field(description="记录ID", default_factory=lambda: str(uuid.uuid4()))
    user_sub: str = Field(description="用户ID")


class TaskTokens(BaseModel):
    """任务Token"""

    input_tokens: int = Field(description="输入Token", default=0)
    input_delta: int = Field(description="输入Token增量", default=0)
    output_tokens: int = Field(description="输出Token", default=0)
    output_delta: int = Field(description="输出Token增量", default=0)
    time: float = Field(description="时间成本", default=0.0)
    time_delta: float = Field(description="时间成本增量", default=0.0)


class TaskRuntime(BaseModel):
    """任务运行时数据"""

    question: str = Field(description="用户问题", default="")
    answer: str = Field(description="模型回答", default="")
    facts: list[str] = Field(description="记忆", default=[])
    summary: str = Field(description="摘要", default="")
    filled: dict[str, Any] = Field(description="填充的槽位", default={})


class Task(BaseModel):
    """
    任务信息

    Collection: task
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="_id")
    ids: TaskIds = Field(description="任务涉及的各种ID")
    context: dict[str, FlowStepHistory] = Field(description="Flow的步骤执行信息", default={})
    state: ExecutorState | None = Field(description="Flow的状态", default=None)
    tokens: TaskTokens = Field(description="Token信息")
    runtime: TaskRuntime = Field(description="任务运行时数据")
    created_at: float = Field(default_factory=lambda: round(datetime.now(tz=UTC).timestamp(), 3))


class StepQueueItem(BaseModel):
    """步骤栈中的元素"""

    step_id: str = Field(description="步骤ID")
    step: Step = Field(description="步骤")
    enable_filling: bool = Field(description="是否启用填充", default=True)
    to_user: bool = Field(description="是否输出给用户", default=False)
