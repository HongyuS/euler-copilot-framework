"""参数填充工具"""
from collections.abc import AsyncGenerator
from typing import Annotated, Any, ClassVar

from pydantic import Field

from apps.entities.enum_var import CallOutputType
from apps.entities.scheduler import CallOutputChunk, CallVars
from apps.scheduler.call.core import CoreCall
from apps.scheduler.call.slot.schema import SlotInput, SlotOutput
from apps.scheduler.slot.slot import Slot as SlotProcessor


class Slot(CoreCall, input_type=SlotInput, output_type=SlotOutput):
    """参数填充工具"""

    name: ClassVar[Annotated[str, Field(description="Call的名称", exclude=True)]] = "参数自动填充"
    description: ClassVar[Annotated[str, Field(description="Call的描述", exclude=True)]] = "根据步骤历史，自动填充参数"

    data: dict[str, Any] = Field(description="当前输入", default={})
    current_schema: dict[str, Any] = Field(description="当前Schema", default={})
    summary: str = Field(description="背景信息总结", default="")
    facts: list[str] = Field(description="事实信息", default=[])
    step_num: int = Field(description="历史步骤数", default=1)


    async def _llm_slot_fill(self, remaining_schema: dict[str, Any]) -> dict[str, Any]:
        """使用LLM填充参数"""
        ...


    async def _init(self, call_vars: CallVars) -> dict[str, Any]:
        """初始化"""
        self._task_id = call_vars.task_id

        if not self.current_schema:
            return SlotInput(
                remaining_schema={},
            ).model_dump(by_alias=True, exclude_none=True)

        self._processor = SlotProcessor(self.current_schema)
        remaining_schema = self._processor.check_json(self.data)

        return SlotInput(
            remaining_schema=remaining_schema,
        ).model_dump(by_alias=True, exclude_none=True)


    async def _exec(self, input_data: dict[str, Any]) -> AsyncGenerator[CallOutputChunk, None]:
        """执行参数填充"""
        data = SlotInput(**input_data)

        # 使用LLM填充参数
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
