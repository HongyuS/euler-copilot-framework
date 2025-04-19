"""参数填充工具"""

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any, Self

import jinja2
from pydantic import Field

from apps.entities.enum_var import CallOutputType
from apps.entities.pool import NodePool
from apps.entities.scheduler import CallInfo, CallOutputChunk, CallVars
from apps.llm.patterns.json_gen import Json
from apps.manager.task import TaskManager
from apps.scheduler.call.core import CoreCall
from apps.scheduler.call.slot.schema import SlotInput, SlotOutput
from apps.scheduler.slot.slot import Slot as SlotProcessor

if TYPE_CHECKING:
    from apps.scheduler.executor.step import StepExecutor


class Slot(CoreCall, input_model=SlotInput, output_model=SlotOutput):
    """参数填充工具"""

    data: dict[str, Any] = Field(description="当前输入", default={})
    current_schema: dict[str, Any] = Field(description="当前Schema", default={})
    summary: str = Field(description="背景信息总结", default="")
    facts: list[str] = Field(description="事实信息", default=[])
    step_num: int = Field(description="历史步骤数", default=1)


    @classmethod
    def info(cls) -> CallInfo:
        """返回Call的名称和描述"""
        return CallInfo(name="参数自动填充", description="根据步骤历史，自动填充参数")


    async def _llm_slot_fill(self, remaining_schema: dict[str, Any]) -> dict[str, Any]:
        """使用LLM填充参数"""
        conversation = [
            {"role": "user", "content": rf"""
                背景信息摘要: {self.summary}

                事实信息: {self.facts}

                历史输出（JSON）: {self._flow_history}
            """},
        ]

        return await Json().generate(
            self._task_id,
            conversation=conversation,
            spec=remaining_schema,
        )

    @classmethod
    async def instance(cls, executor: "StepExecutor", node: NodePool | None, **kwargs: Any) -> Self:
        """实例化Call类"""
        obj = cls(
            name=executor.step.step.name,
            description=executor.step.step.description,
            facts=executor.background.facts,
            summary=executor.task.runtime.summary,
            node=node,
            **kwargs,
        )
        await obj._set_input(executor)
        return obj


    async def _init(self, call_vars: CallVars) -> SlotInput:
        """初始化"""
        self._task_id = call_vars.ids.task_id
        self._flow_history = await TaskManager.get_flow_history_by_task_id(self._task_id, self.step_num)

        if not self.current_schema:
            return SlotInput(
                remaining_schema={},
            )

        self._processor = SlotProcessor(self.current_schema)
        remaining_schema = self._processor.check_json(self.data)

        return SlotInput(
            remaining_schema=remaining_schema,
        )


    async def _exec(self, input_data: dict[str, Any]) -> AsyncGenerator[CallOutputChunk, None]:
        """执行参数填充"""
        data = SlotInput(**input_data)

        # 使用LLM填充参数
        if not data.remaining_schema:
            yield CallOutputChunk(
                type=CallOutputType.DATA,
                content=SlotOutput(
                    slot_data=input_data,
                    remaining_schema={},
                ).model_dump(by_alias=True, exclude_none=True),
            )
            return
        slot_data = await self._llm_slot_fill(data.remaining_schema)

        # 再次检查
        remaining_schema = self._processor.check_json(slot_data)
        yield CallOutputChunk(
            type=CallOutputType.DATA,
            content=SlotOutput(
                slot_data=slot_data,
                remaining_schema=remaining_schema,
            ).model_dump(by_alias=True, exclude_none=True),
        )
