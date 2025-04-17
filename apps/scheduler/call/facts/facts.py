"""提取事实工具"""

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any, Self

from pydantic import Field

from apps.entities.enum_var import CallOutputType
from apps.entities.scheduler import CallInfo, CallOutputChunk, CallVars
from apps.llm.patterns.domain import Domain
from apps.llm.patterns.facts import Facts
from apps.manager.user_domain import UserDomainManager
from apps.scheduler.call.core import CoreCall
from apps.scheduler.call.facts.schema import FactsInput, FactsOutput

if TYPE_CHECKING:
    from apps.scheduler.executor.step import StepExecutor


class FactsCall(CoreCall, input_type=FactsInput, output_type=FactsOutput):
    """提取事实工具"""

    answer: str = Field(description="用户输入")


    @classmethod
    def cls_info(cls) -> CallInfo:
        """返回Call的名称和描述"""
        return CallInfo(name="提取事实", description="从对话上下文和文档片段中提取事实。")


    @classmethod
    async def init(cls, executor: "StepExecutor", **kwargs: Any) -> tuple[Self, dict[str, Any]]:
        """初始化工具"""
        cls_obj = cls(
            answer=executor.task.runtime.answer,
            name=executor.step.step.name,
            description=executor.step.step.description,
            **kwargs,
        )

        call_vars = cls._assemble_call_vars(executor)
        input_data = await cls_obj._init(call_vars)

        return cls_obj, input_data


    async def _init(self, call_vars: CallVars) -> dict[str, Any]:
        """初始化工具"""
        # 组装必要变量
        message = [
            {"role": "user", "content": call_vars.question},
            {"role": "assistant", "content": self.answer},
        ]

        return FactsInput(
            task_id=call_vars.ids.task_id,
            user_sub=call_vars.ids.user_sub,
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
