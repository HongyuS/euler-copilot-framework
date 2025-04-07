"""提取事实工具"""

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Annotated, Any, ClassVar, Self

from pydantic import Field

from apps.entities.enum_var import CallOutputType
from apps.entities.scheduler import CallOutputChunk, CallVars
from apps.llm.patterns.domain import Domain
from apps.llm.patterns.facts import Facts
from apps.manager.user_domain import UserDomainManager
from apps.scheduler.call.core import CoreCall
from apps.scheduler.call.facts.schema import FactsInput, FactsOutput

if TYPE_CHECKING:
    from apps.entities.task import Task
    from apps.scheduler.executor.step import StepExecutor


class FactsCall(CoreCall, input_type=FactsInput, output_type=FactsOutput):
    """提取事实工具"""

    name: ClassVar[Annotated[str, Field(description="工具名称", exclude=True, frozen=True)]] = "提取事实"
    description: ClassVar[Annotated[str, Field(description="工具描述", exclude=True, frozen=True)]] = (
        "从对话上下文和文档片段中提取事实。"
    )

    answer: str = Field(description="用户输入")

    @classmethod
    async def init(cls, **kwargs: Any) -> Self:
        """初始化工具"""
        task: Task = kwargs["task"]
        return cls(answer=task.runtime.answer, **kwargs)

    async def _init(self, syscall_vars: CallVars) -> dict[str, Any]:
        """初始化工具"""
        await super()._init(syscall_vars)

        # 组装必要变量
        message = [
            {"role": "user", "content": syscall_vars.question},
            {"role": "assistant", "content": self.answer},
        ]

        return FactsInput(
            task_id=syscall_vars.task_id,
            user_sub=syscall_vars.user_sub,
            message=message,
        ).model_dump(exclude_none=True, by_alias=True)

    async def _exec(self, input_data: dict[str, Any]) -> AsyncGenerator[CallOutputChunk, None]:
        """执行工具"""
        data = FactsInput(**input_data)
        # 提取事实信息
        facts = await Facts().generate(data.task_id, conversation=data.message)
        # 更新用户画像
        domain_list = await Domain().generate(data.task_id, conversation=data.message)
        for domain in domain_list:
            await UserDomainManager.update_user_domain_by_user_sub_and_domain_name(data.user_sub, domain)

        yield CallOutputChunk(
            type=CallOutputType.DATA,
            content=FactsOutput(
                facts=facts,
                domain=domain_list,
            ).model_dump(by_alias=True, exclude_none=True),
        )

    async def exec(self, executor: "StepExecutor", input_data: dict[str, Any]) -> AsyncGenerator[CallOutputChunk, None]:
        """执行工具"""
        async for chunk in self._exec(input_data):
            content = chunk.content
            if not isinstance(content, dict):
                err = "[FactsCall] 工具输出格式错误"
                raise TypeError(err)
            executor.task.runtime.facts = FactsOutput.model_validate(content).facts
            yield chunk
