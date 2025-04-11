"""
用于问题推荐的工具

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Annotated, Any, ClassVar, Self

from pydantic import Field

from apps.entities.scheduler import CallOutputChunk, CallVars
from apps.llm.patterns.recommend import Recommend
from apps.manager.task import TaskManager
from apps.manager.user_domain import UserDomainManager
from apps.scheduler.call.core import CoreCall
from apps.scheduler.call.suggest.schema import (
    SingleFlowSuggestionConfig,
    SuggestionInput,
    SuggestionOutput,
)

if TYPE_CHECKING:
    from apps.scheduler.executor.step import StepExecutor


class Suggestion(CoreCall, input_type=SuggestionInput, output_type=SuggestionOutput):
    """问题推荐"""

    name: ClassVar[Annotated[str, Field(description="工具名称", exclude=True, frozen=True)]] = "问题推荐"
    description: ClassVar[Annotated[str, Field(description="工具描述", exclude=True, frozen=True)]] = (
        "在答案下方显示推荐的下一个问题"
    )

    configs: list[SingleFlowSuggestionConfig] = Field(description="问题推荐配置", min_length=1)
    num: int = Field(default=3, ge=1, le=6, description="推荐问题的总数量（必须大于等于configs中涉及的Flow的数量）")

    context: list[dict[str, str]] = Field(description="Executor的上下文")


    async def init(self, executor: "StepExecutor", **kwargs: Any) -> tuple[Self, dict[str, Any]]:
        """初始化"""
        self.context = [
            {
                "role": "user",
                "content": executor.task.runtime.question,
            },
            {
                "role": "assistant",
                "content": executor.task.runtime.answer,
            },
        ]

        return await super().init(executor, **kwargs)


    async def _init(self, call_vars: CallVars) -> dict[str, Any]:
        """初始化"""
        return SuggestionInput(
            question=call_vars.question,
            task_id=call_vars.task_id,
            user_sub=call_vars.user_sub,
        ).model_dump(by_alias=True, exclude_none=True)


    async def _exec(self, input_data: dict[str, Any]) -> AsyncGenerator[CallOutputChunk, None]:
        """运行问题推荐"""
        data = SuggestionInput(**input_data)
        # 获取当前任务
        task = await TaskManager.get_task(task_id=data.task_id)

        # 获取当前用户的画像
        user_domain = await UserDomainManager.get_user_domain_by_user_sub_and_topk(data.user_sub, 5)

        recommended_questions = await Recommend().generate(
            data.task_id,
            conversation=self.context,
            user_preference=user_domain,
            history_questions=task.runtime.history,
        )

        yield CallOutputChunk(content="")
