# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""总结上下文工具"""

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any, Self

from pydantic import Field

from apps.llm.patterns.executor import ExecutorSummary
from apps.scheduler.call.core import CoreCall, DataBase
from apps.schemas.enum_var import CallOutputType
from apps.schemas.pool import NodePool
from apps.schemas.scheduler import (
    CallInfo,
    CallOutputChunk,
    CallVars,
    ExecutorBackground,
)

from .schema import SummaryOutput

if TYPE_CHECKING:
    from apps.scheduler.executor.step import StepExecutor



class Summary(CoreCall, input_model=DataBase, output_model=SummaryOutput):
    """总结工具"""

    context: ExecutorBackground = Field(description="对话上下文")

    @classmethod
    def info(cls) -> CallInfo:
        """返回Call的名称和描述"""
        return CallInfo(name="理解上下文", description="使用大模型，理解对话上下文")

    @classmethod
    async def instance(cls, executor: "StepExecutor", node: NodePool | None, **kwargs: Any) -> Self:
        """实例化工具"""
        obj = cls(
            context=executor.background,
            name=executor.step.step.name,
            description=executor.step.step.description,
            node=node,
            **kwargs,
        )
        await obj._set_input(executor)
        return obj


    async def _init(self, call_vars: CallVars) -> DataBase:
        """初始化工具，返回输入"""
        return DataBase()


    async def _exec(self, _input_data: dict[str, Any]) -> AsyncGenerator[CallOutputChunk, None]:
        """执行工具"""
        summary_obj = ExecutorSummary()
        summary = await summary_obj.generate(background=self.context)
        self.tokens.input_tokens += summary_obj.input_tokens
        self.tokens.output_tokens += summary_obj.output_tokens

        yield CallOutputChunk(type=CallOutputType.TEXT, content=summary)


    async def exec(self, executor: "StepExecutor", input_data: dict[str, Any]) -> AsyncGenerator[CallOutputChunk, None]:
        """执行工具"""
        async for chunk in self._exec(input_data):
            content = chunk.content
            if not isinstance(content, str):
                err = "[SummaryCall] 工具输出格式错误"
                raise TypeError(err)
            executor.task.runtime.summary = content
            yield chunk
