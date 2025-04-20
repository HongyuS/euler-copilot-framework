"""
Core Call类，定义了所有Call的抽象类和基础参数。

所有Call类必须继承此类，并实现所有方法。
Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

import logging
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any, ClassVar, Self

from pydantic import BaseModel, ConfigDict, Field
from pydantic.json_schema import SkipJsonSchema

from apps.entities.enum_var import CallOutputType
from apps.entities.pool import NodePool
from apps.entities.scheduler import (
    CallIds,
    CallInfo,
    CallOutputChunk,
    CallVars,
)

if TYPE_CHECKING:
    from apps.scheduler.executor.step import StepExecutor
logger = logging.getLogger(__name__)


class DataBase(BaseModel):
    """所有Call的输入基类"""

    @classmethod
    def model_json_schema(cls, override: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
        """通过override参数，动态填充Schema内容"""
        schema = super().model_json_schema(**kwargs)
        if override:
            for key, value in override.items():
                schema["properties"][key] = value
        return schema


class CoreCall(BaseModel):
    """所有Call的父类，所有Call必须继承此类。"""

    name: SkipJsonSchema[str] = Field(description="Step的名称", exclude=True)
    description: SkipJsonSchema[str] = Field(description="Step的描述", exclude=True)
    node: SkipJsonSchema[NodePool | None] = Field(description="节点信息", exclude=True)
    input_model: ClassVar[SkipJsonSchema[type[DataBase]]] = Field(
        description="Call的输入Pydantic类型；不包含override的模板",
        exclude=True,
        frozen=True,
    )
    output_model: ClassVar[SkipJsonSchema[type[DataBase]]] = Field(
        description="Call的输出Pydantic类型；不包含override的模板",
        exclude=True,
        frozen=True,
    )

    to_user: bool = Field(description="是否需要将输出返回给用户", default=False)
    enable_filling: bool = Field(description="是否需要进行自动参数填充", default=False)

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="allow",
    )


    def __init_subclass__(cls, input_model: type[DataBase], output_model: type[DataBase], **kwargs: Any) -> None:
        """初始化子类"""
        super().__init_subclass__(**kwargs)
        cls.input_model = input_model
        cls.output_model = output_model


    @classmethod
    def info(cls) -> CallInfo:
        """返回Call的名称和描述"""
        err = "[CoreCall] 必须手动实现info方法"
        raise NotImplementedError(err)


    @staticmethod
    def _assemble_call_vars(executor: "StepExecutor") -> CallVars:
        """组装CallVars"""
        if not executor.task.state:
            err = "[CoreCall] 当前ExecutorState为空"
            logger.error(err)
            raise ValueError(err)

        return CallVars(
            ids=CallIds(
                task_id=executor.task.id,
                flow_id=executor.task.state.flow_id,
                session_id=executor.task.ids.session_id,
                user_sub=executor.task.ids.user_sub,
                app_id=executor.task.state.app_id,
            ),
            question=executor.question,
            history=executor.task.context,
            summary=executor.task.runtime.summary,
        )


    @classmethod
    async def instance(cls, executor: "StepExecutor", node: NodePool | None, **kwargs: Any) -> Self:
        """实例化Call类"""
        obj = cls(
            name=executor.step.step.name,
            description=executor.step.step.description,
            node=node,
            **kwargs,
        )

        await obj._set_input(executor)
        return obj


    async def _set_input(self, executor: "StepExecutor") -> None:
        """获取Call的输入"""
        self._sys_vars = self._assemble_call_vars(executor)
        input_data = await self._init(self._sys_vars)
        self.input = input_data.model_dump(by_alias=True, exclude_none=True)


    async def _init(self, call_vars: CallVars) -> DataBase:
        """初始化Call类，并返回Call的输入"""
        err = "[CoreCall] 初始化方法必须手动实现"
        raise NotImplementedError(err)


    async def _exec(self, input_data: dict[str, Any]) -> AsyncGenerator[CallOutputChunk, None]:
        """Call类实例的流式输出方法"""
        yield CallOutputChunk(type=CallOutputType.TEXT, content="")


    async def _after_exec(self, input_data: dict[str, Any]) -> None:
        """Call类实例的执行后方法"""


    async def exec(self, executor: "StepExecutor", input_data: dict[str, Any]) -> AsyncGenerator[CallOutputChunk, None]:
        """Call类实例的执行方法"""
        async for chunk in self._exec(input_data):
            yield chunk
        await self._after_exec(input_data)
