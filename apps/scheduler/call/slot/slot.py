# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""自动参数填充工具"""

import json
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any, Self

from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment
from pydantic import Field

from apps.llm.function import FunctionLLM
from apps.models.node import NodeInfo
from apps.scheduler.call.core import CoreCall
from apps.scheduler.slot.slot import Slot as SlotProcessor
from apps.schemas.enum_var import CallOutputType, LanguageType
from apps.schemas.scheduler import CallInfo, CallOutputChunk, CallVars

from .prompt import SLOT_GEN_PROMPT
from .schema import SlotInput, SlotOutput

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
    def info(cls, language: LanguageType = LanguageType.CHINESE) -> CallInfo:
        """返回Call的名称和描述"""
        i18n_info = {
            LanguageType.CHINESE: CallInfo(name="参数自动填充", description="根据步骤历史，自动填充参数"),
            LanguageType.ENGLISH: CallInfo(
                name="Parameter Auto-Filling",
                description="Automatically fill parameters based on step history.",
            ),
        }
        return i18n_info[language]


    async def _llm_slot_fill(self, remaining_schema: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """使用大模型填充参数；若大模型解析度足够，则直接返回结果"""
        env = SandboxedEnvironment(
            loader=BaseLoader(),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        template = env.from_string(SLOT_GEN_PROMPT[self._sys_vars.language])

        conversation = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": template.render(
                current_tool={
                    "name": self.name,
                    "description": self.description,
                },
                schema=remaining_schema,
                history_data=self._flow_history,
                summary=self.summary,
                question=self._question,
                facts=self.facts,
            )},
        ]

        # 使用大模型进行尝试
        answer = ""
        async for chunk in self._llm(messages=conversation, streaming=True):
            answer += chunk
        answer = await FunctionLLM.process_response(answer)
        try:
            data = json.loads(answer)
        except Exception:  # noqa: BLE001
            data = {}
        return answer, data

    async def _function_slot_fill(self, answer: str, remaining_schema: dict[str, Any]) -> dict[str, Any]:
        """使用FunctionCall填充参数"""
        conversation = [
            {"role": "user", "content": self._question},
            {"role": "assistant", "content": answer},
        ]
        return await self._json(messages=conversation, schema=remaining_schema)

    @classmethod
    async def instance(cls, executor: "StepExecutor", node: NodeInfo | None, **kwargs: Any) -> Self:
        """实例化Call类"""
        obj = cls(
            name=executor.step.step.name,
            description=executor.step.step.description,
            facts=executor.background.facts,
            summary=executor.task.runtime.reasoning,
            node=node,
            **kwargs,
        )
        await obj._set_input(executor)
        return obj


    async def _init(self, call_vars: CallVars) -> SlotInput:
        """初始化"""
        self._flow_history = []
        self._question = call_vars.question
        for key in call_vars.step_order[:-self.step_num]:
            self._flow_history += [call_vars.step_data[key]]

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
        answer, slot_data = await self._llm_slot_fill(data.remaining_schema)

        slot_data = self._processor.convert_json(slot_data)
        remaining_schema = self._processor.check_json(slot_data)
        if remaining_schema:
            slot_data = await self._function_slot_fill(answer, remaining_schema)
            slot_data = self._processor.convert_json(slot_data)
            remaining_schema = self._processor.check_json(slot_data)

        # 再次检查
        remaining_schema = self._processor.check_json(slot_data)
        yield CallOutputChunk(
            type=CallOutputType.DATA,
            content=SlotOutput(
                slot_data=slot_data,
                remaining_schema=remaining_schema,
            ).model_dump(by_alias=True, exclude_none=True),
        )
