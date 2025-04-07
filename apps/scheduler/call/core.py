"""
Core Call类，定义了所有Call的抽象类和基础参数。

所有Call类必须继承此类，并实现所有方法。
Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Annotated, Any, ClassVar, Self

from pydantic import BaseModel, ConfigDict, Field

from apps.entities.enum_var import CallOutputType
from apps.entities.scheduler import CallOutputChunk, CallVars

if TYPE_CHECKING:
    from apps.scheduler.executor.step import StepExecutor


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

    name: ClassVar[Annotated[str, Field(description="Call的名称", exclude=True)]] = ""
    description: ClassVar[Annotated[str, Field(description="Call的描述", exclude=True)]] = ""

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="allow",
    )

    input_type: ClassVar[type[BaseModel]] = Field(description="Call的输入Pydantic类型", exclude=True, frozen=True)
    """需要以消息形式输出的、需要大模型填充参数的输入信息填到这里"""
    output_type: ClassVar[type[BaseModel]] = Field(description="Call的输出Pydantic类型", exclude=True, frozen=True)
    """需要以消息形式输出的输出信息填到这里"""

    def __init_subclass__(cls, input_type: type[BaseModel], output_type: type[BaseModel], **kwargs: Any) -> None:
        """初始化子类"""
        super().__init_subclass__(**kwargs)
        cls.input_type = input_type
        cls.output_type = output_type


    @classmethod
    async def init(cls, syscall_vars: CallVars, **kwargs: Any) -> tuple[Self, dict[str, Any]]:
        """实例化Call类"""
        call_obj = cls(**kwargs)
        input_data = await call_obj._init(syscall_vars)
        return call_obj, input_data


    async def _init(self, syscall_vars: CallVars) -> dict[str, Any]:
        """实例化Call类，并返回Call的输入"""
        err = "[CoreCall] 初始化方法必须手动实现"
        raise NotImplementedError(err)


    async def _exec(self, input_data: dict[str, Any]) -> AsyncGenerator[CallOutputChunk, None]:
        """Call类实例的流式输出方法"""
        yield CallOutputChunk(type=CallOutputType.TEXT, content="")

    async def exec(self, executor: "StepExecutor", input_data: dict[str, Any]) -> AsyncGenerator[CallOutputChunk, None]:
        """Call类实例的执行方法"""
        async for chunk in self._exec(input_data):
            yield chunk
