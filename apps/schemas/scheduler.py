# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""插件、工作流、步骤相关数据结构定义"""

import uuid
from typing import Any

from pydantic import BaseModel, Field

from apps.llm.embedding import Embedding
from apps.llm.function import FunctionLLM
from apps.llm.reasoning import ReasoningLLM
from apps.models.task import ExecutorHistory

from .enum_var import CallOutputType, LanguageType


class LLMConfig(BaseModel):
    """LLM配置"""

    reasoning: ReasoningLLM = Field(description="推理LLM")
    function: FunctionLLM | None = Field(description="函数LLM")
    embedding: Embedding | None = Field(description="Embedding")


class CallInfo(BaseModel):
    """Call的名称和描述"""

    name: str = Field(description="Call的名称")
    description: str = Field(description="Call的描述")


class CallIds(BaseModel):
    """Call的ID，来自于Task"""

    task_id: uuid.UUID = Field(description="任务ID")
    executor_id: str = Field(description="Flow ID")
    session_id: str | None = Field(description="当前用户的Session ID")
    app_id: uuid.UUID = Field(description="当前应用的ID")
    user_sub: str = Field(description="当前用户的用户ID")


class CallVars(BaseModel):
    """由Executor填充的变量，即“系统变量”"""

    summary: str = Field(description="上下文信息")
    question: str = Field(description="改写后的用户输入")
    history: dict[str, ExecutorHistory] = Field(description="Executor中历史工具的结构化数据", default={})
    history_order: list[str] = Field(description="Executor中历史工具的顺序", default=[])
    ids: CallIds = Field(description="Call的ID")
    language: LanguageType = Field(description="语言", default=LanguageType.CHINESE)


class ExecutorBackground(BaseModel):
    """Executor的背景信息"""

    conversation: list[dict[str, str]] = Field(description="对话记录", default=[])
    facts: list[str] = Field(description="当前Executor的背景信息", default=[])


class CallError(Exception):
    """Call错误"""

    def __init__(self, message: str, data: dict[str, Any]) -> None:
        """获取Call错误中的数据"""
        self.message = message
        self.data = data


class CallOutputChunk(BaseModel):
    """Call的输出"""

    type: CallOutputType = Field(description="输出类型")
    content: str | dict[str, Any] = Field(description="输出内容")


class TopFlow(BaseModel):
    """最匹配用户输入的Flow"""

    choice: str = Field(description="最匹配用户输入的Flow的名称")
