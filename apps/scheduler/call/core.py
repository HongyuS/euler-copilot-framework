# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""
Core Call类是定义了所有Call都应具有的方法和参数的PyDantic类。

所有Call类必须继承此类，并根据需求重载方法。
"""

import logging
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any, ClassVar, Self

from pydantic import BaseModel, ConfigDict, Field
from pydantic.json_schema import SkipJsonSchema

from apps.llm.function import FunctionLLM
from apps.llm.reasoning import ReasoningLLM
from apps.models.node import NodeInfo
from apps.schemas.enum_var import CallOutputType
from apps.schemas.scheduler import (
    CallError,
    CallIds,
    CallInfo,
    CallOutputChunk,
    CallTokens,
    CallVars,
)
from apps.schemas.task import FlowStepHistory

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
    """所有Call的父类，包含通用的逻辑"""

    name: SkipJsonSchema[str] = Field(description="Step的名称", exclude=True)
    description: SkipJsonSchema[str] = Field(description="Step的描述", exclude=True)
    node: SkipJsonSchema[NodeInfo | None] = Field(description="节点信息", exclude=True)
    enable_filling: SkipJsonSchema[bool] = Field(description="是否需要进行自动参数填充", default=False, exclude=True)
    tokens: SkipJsonSchema[CallTokens] = Field(
        description="Call的输入输出Tokens信息",
        default=CallTokens(),
        exclude=True,
    )
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

        history = {}
        history_order = []
        for item in executor.task.context:
            item_obj = FlowStepHistory.model_validate(item)
            history[item_obj.step_id] = item_obj
            history_order.append(item_obj.step_id)

        return CallVars(
            ids=CallIds(
                task_id=executor.task.id,
                flow_id=executor.task.state.flow_id,
                session_id=executor.task.ids.session_id,
                user_sub=executor.task.ids.user_sub,
                app_id=executor.task.state.app_id,
            ),
            question=executor.question,
            history=history,
            history_order=history_order,
            summary=executor.task.runtime.summary,
        )


    @staticmethod
    def _extract_history_variables(path: str, history: dict[str, FlowStepHistory]) -> Any:
        """
        提取History中的变量

        :param path: 路径，格式为：step_id/key/to/variable
        :param history: Step历史，即call_vars.history
        :return: 变量
        """
        split_path = path.split("/")
        if len(split_path) < 1:
            err = f"[CoreCall] 路径格式错误: {path}"
            logger.error(err)
            return None
        if split_path[0] not in history:
            err = f"[CoreCall] 步骤{split_path[0]}不存在"
            logger.error(err)
            return None

        data = history[split_path[0]].output_data
        for key in split_path[1:]:
            if key not in data:
                err = f"[CoreCall] 输出Key {key} 不存在"
                logger.error(err)
                raise CallError(
                    message=err,
                    data={
                        "step_id": split_path[0],
                        "key": key,
                    },
                )
            data = data[key]
        return data


    @classmethod
    async def instance(cls, executor: "StepExecutor", node: NodeInfo | None, **kwargs: Any) -> Self:
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


    async def _llm(self, messages: list[dict[str, Any]]) -> str:
        """Call可直接使用的LLM非流式调用"""
        result = ""
        llm = ReasoningLLM()
        async for chunk in llm.call(messages, streaming=False):
            result += chunk
        self.input_tokens = llm.input_tokens
        self.output_tokens = llm.output_tokens
        return result


    async def _json(self, messages: list[dict[str, Any]], schema: type[BaseModel]) -> BaseModel:
        """Call可直接使用的JSON生成"""
        json = FunctionLLM()
        result = await json.call(messages=messages, schema=schema.model_json_schema())
        return schema.model_validate(result)
