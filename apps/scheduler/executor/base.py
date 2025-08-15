# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Executor基类"""

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict

from apps.schemas.enum_var import EventType
from apps.schemas.message import TextAddContent

if TYPE_CHECKING:
    from apps.common.queue import MessageQueue
    from apps.models.task import ExecutorCheckpoint, Task, TaskRuntime
    from apps.schemas.scheduler import ExecutorBackground

logger = logging.getLogger(__name__)


class BaseExecutor(BaseModel, ABC):
    """Executor基类"""

    task: "Task"
    runtime: "TaskRuntime"
    state: "ExecutorCheckpoint"
    msg_queue: "MessageQueue"
    background: "ExecutorBackground"
    question: str

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="allow",
    )

    async def push_message(self, event_type: str, data: dict[str, Any] | str | None = None) -> None:
        """
        统一的消息推送接口

        :param event_type: 事件类型
        :param data: 消息数据，如果是FLOW_START事件且data为None，则自动构建FlowStartContent
        """
        if event_type == EventType.TEXT_ADD.value and isinstance(data, str):
            data = TextAddContent(text=data).model_dump(exclude_none=True, by_alias=True)

        if data is None:
            data = {}
        elif isinstance(data, str):
            data = TextAddContent(text=data).model_dump(exclude_none=True, by_alias=True)

        await self.msg_queue.push_output(
            self.task,
            event_type=event_type,
            data=data,
        )

    @abstractmethod
    async def run(self) -> None:
        """运行Executor"""
        raise NotImplementedError
