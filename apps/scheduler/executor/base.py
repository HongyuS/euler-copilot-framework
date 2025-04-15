"""Executor基类"""

import logging
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict

from apps.common.queue import MessageQueue
from apps.entities.enum_var import EventType
from apps.entities.message import FlowStartContent
from apps.entities.scheduler import ExecutorBackground
from apps.entities.task import FlowStepHistory, Task

logger = logging.getLogger(__name__)


class BaseExecutor(BaseModel):
    """Executor基类"""

    task: Task
    msg_queue: MessageQueue
    background: ExecutorBackground
    question: str
    history: FlowStepHistory | None = None

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="allow",
    )

    def validate_flow_state(self) -> None:
        """验证flow_state是否存在"""
        if not self.task.state:
            err = "[Executor] 当前ExecutorState为空"
            logger.error(err)
            raise ValueError(err)

    async def push_message(self, event_type: EventType, data: dict | None = None) -> None:
        """
        统一的消息推送接口

        :param event_type: 事件类型
        :param data: 消息数据，如果是FLOW_START事件且data为None，则自动构建FlowStartContent
        """
        self.validate_flow_state()

        if event_type == EventType.FLOW_START and data is None:
            content = FlowStartContent(
                question=self.question,
                params=self.task.runtime.filled,
            )
            data = content.model_dump(exclude_none=True, by_alias=True)
        elif event_type == EventType.FLOW_STOP and data is None:
            data = {}
        elif event_type == EventType.STEP_INPUT:
            # 更新step_history的输入数据
            if self.history is not None and data is not None:
                self.history.input_data = data
                if self.task.state is not None:
                    self.history.status = self.task.state.status
                # 步骤开始，重置时间
                self.task.tokens.time = round(datetime.now(UTC).timestamp(), 2)
        elif event_type == EventType.STEP_OUTPUT:
            # 更新step_history的输出数据
            if self.history is not None and data is not None:
                self.history.output_data = data
                if self.task.state is not None:
                    self.history.status = self.task.state.status
                    self.task.context[self.task.state.step_id] = self.history

        await self.msg_queue.push_output(
            self.task,
            event_type=event_type,
            data=data,  # type: ignore[arg-type]
        )
