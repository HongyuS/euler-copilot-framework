"""
总结上下文工具

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any, ClassVar, Self

from pydantic import Field

from apps.entities.enum_var import CallOutputType
from apps.entities.scheduler import CallOutputChunk, CallVars, ExecutorBackground
from apps.llm.patterns.executor import ExecutorSummary
from apps.scheduler.call.core import CoreCall
from apps.scheduler.call.summary.schema import SummaryInput, SummaryOutput

if TYPE_CHECKING:
    from apps.scheduler.executor.step import StepExecutor



class Summary(CoreCall, input_type=SummaryInput, output_type=SummaryOutput):
    """总结工具"""

    name: ClassVar[str] = Field("理解上下文", exclude=True)
    description: ClassVar[str] = Field("使用大模型，理解对话上下文", exclude=True)

    context: ExecutorBackground = Field(description="对话上下文")

    @classmethod
    async def init(cls, **kwargs: Any) -> Self:
        """初始化工具"""
        return cls(context=kwargs["executor_background"], **kwargs)

    async def _init(self, syscall_vars: CallVars) -> dict[str, Any]:
        """初始化工具"""
        await super()._init(syscall_vars)

        return SummaryInput(
            task_id=syscall_vars.task_id,
        ).model_dump(by_alias=True, exclude_none=True)


    async def _exec(self, input_data: dict[str, Any]) -> AsyncGenerator[CallOutputChunk, None]:
        """执行工具"""
        data = SummaryInput(**input_data)
        summary = await ExecutorSummary().generate(data.task_id, background=self.context)
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
