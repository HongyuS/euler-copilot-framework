# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Executor基类"""

import logging
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ConfigDict

from apps.common.queue import MessageQueue
from apps.entities.enum_var import EventType
from apps.entities.message import FlowStartContent, TextAddContent
from apps.entities.scheduler import ExecutorBackground
from apps.entities.task import Task

logger = logging.getLogger(__name__)


class BaseExecutor(BaseModel, ABC):
    """Executor基类"""

    task: Task
    msg_queue: MessageQueue
    background: ExecutorBackground
    question: str

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="allow",
    )

    @staticmethod
    def validate_flow_state(task: Task) -> None:
        """验证flow_state是否存在"""
        if not task.state:
            err = "[Executor] 当前ExecutorState为空"
            logger.error(err)
            raise ValueError(err)

    async def push_message(self, event_type: str, data: dict[str, Any] | str | None = None) -> None:
        """
        统一的消息推送接口

        :param event_type: 事件类型
        :param data: 消息数据，如果是FLOW_START事件且data为None，则自动构建FlowStartContent
        """
        if event_type == EventType.FLOW_START.value and isinstance(data, dict):
            data = FlowStartContent(
                question=self.question,
                params=self.task.runtime.filled,
            ).model_dump(exclude_none=True, by_alias=True)
        elif event_type == EventType.FLOW_STOP.value:
            data = {}
        elif event_type == EventType.TEXT_ADD.value and isinstance(data, str):
            data=TextAddContent(text=data).model_dump(exclude_none=True, by_alias=True)

        if data is None:
            data = {}
        elif isinstance(data, str):
            data = TextAddContent(text=data).model_dump(exclude_none=True, by_alias=True)

        await self.msg_queue.push_output(
            self.task,
            event_type=event_type,
            data=data, # type: ignore[arg-type]
        )

    @abstractmethod
    async def run(self) -> None:
        """运行Executor"""
        raise NotImplementedError
