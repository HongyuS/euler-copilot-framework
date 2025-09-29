# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""总结上下文工具"""

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any, Self

from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment
from pydantic import Field

from apps.models import LanguageType, NodeInfo
from apps.scheduler.call.core import CoreCall, DataBase
from apps.schemas.enum_var import CallOutputType
from apps.schemas.scheduler import (
    CallInfo,
    CallOutputChunk,
    CallVars,
    ExecutorBackground,
)

from .prompt import SUMMARY_PROMPT
from .schema import SummaryOutput

if TYPE_CHECKING:
    from apps.scheduler.executor.step import StepExecutor



class Summary(CoreCall, input_model=DataBase, output_model=SummaryOutput):
    """总结工具"""

    context: ExecutorBackground = Field(description="对话上下文")

    @classmethod
    def info(cls, language: LanguageType = LanguageType.CHINESE) -> CallInfo:
        """返回Call的名称和描述"""
        i18n_info = {
            LanguageType.CHINESE: CallInfo(name="理解上下文", description="使用大模型，理解对话上下文"),
            LanguageType.ENGLISH: CallInfo(
                name="Understand Context",
                description="Use LLM to understand the conversation context",
            ),
        }
        return i18n_info[language]

    @classmethod
    async def instance(cls, executor: "StepExecutor", node: NodeInfo | None, **kwargs: Any) -> Self:
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
        # 创建 Jinja2 环境
        env = SandboxedEnvironment(
            loader=BaseLoader(),
            autoescape=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # 使用模板生成提示词
        template = env.from_string(SUMMARY_PROMPT[self._sys_vars.language])
        prompt = template.render(
            conversation=self.context.conversation,
            facts=self.context.facts,
        )

        # 调用 LLM 生成总结
        summary = ""
        async for chunk in self._llm([
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ]):
            summary += chunk

        yield CallOutputChunk(type=CallOutputType.TEXT, content=summary)


    async def exec(self, executor: "StepExecutor", input_data: dict[str, Any]) -> AsyncGenerator[CallOutputChunk, None]:
        """执行工具"""
        async for chunk in self._exec(input_data):
            content = chunk.content
            if not isinstance(content, str):
                err = "[SummaryCall] 工具输出格式错误"
                raise TypeError(err)
            executor.task.runtime.reasoning = content
            yield chunk
