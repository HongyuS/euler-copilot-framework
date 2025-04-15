"""工作流中步骤相关函数"""

import logging
from typing import Any

from pydantic import ConfigDict, Field

from apps.common.queue import MessageQueue
from apps.entities.enum_var import EventType, StepStatus
from apps.entities.flow import Step
from apps.entities.scheduler import CallOutputChunk
from apps.entities.task import FlowStepHistory, Task
from apps.manager.node import NodeManager
from apps.manager.task import TaskManager
from apps.scheduler.executor.base import BaseExecutor
from apps.scheduler.executor.node import StepNode

logger = logging.getLogger(__name__)
SPECIAL_EVENT_TYPES = [
    EventType.GRAPH,
    EventType.SUGGEST,
    EventType.TEXT_ADD,
]


class StepExecutor(BaseExecutor):
    """工作流中步骤相关函数"""

    step: Step
    step_id: str = Field(description="步骤ID")


    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="allow",
    )

    def __init__(self, **kwargs: Any) -> None:
        """初始化"""
        super().__init__(**kwargs)
        if not self.task.state:
            err = "[StepExecutor] 当前ExecutorState为空"
            logger.error(err)
            raise ValueError(err)

        self.history = FlowStepHistory(
            task_id=self.task.id,
            flow_id=self.task.state.flow_id,
            step_id=self.task.state.step_id,
            status=self.task.state.status,
            input_data={},
            output_data={},
        )

    async def _push_call_output(
        self,
        task: Task,
        queue: MessageQueue,
        msg_type: EventType,
        data: dict[str, Any],
    ) -> None:
        """推送输出"""
        # 如果不是特殊类型
        if msg_type not in SPECIAL_EVENT_TYPES:
            err = f"[StepExecutor] 不支持的事件类型: {msg_type}"
            logger.error(err)
            raise ValueError(err)

        # 推送消息
        await queue.push_output(
            task,
            event_type=msg_type,
            data=data,
        )

    async def init(self) -> None:
        """初始化步骤"""
        if not self.task.state:
            err = "[StepExecutor] 当前ExecutorState为空"
            logger.error(err)
            raise ValueError(err)

        logger.info("[StepExecutor] 初始化步骤 %s", self.step.name)

        # State写入ID和运行状态
        self.task.state.step_id = self.step_id
        self.task.state.step_name = self.step.name
        self.task.state.status = StepStatus.RUNNING
        await TaskManager.save_task(self.task.id, self.task)

        # 获取并验证Call类
        node_id = self.step.node
        # 获取node详情并存储
        try:
            self._node_data = await NodeManager.get_node(node_id)
        except ValueError:
            logger.info("[StepExecutor] 获取Node失败，为内部Node或ID不存在")
            self._node_data = None

        if self._node_data:
            call_cls = await StepNode.get_call_cls(self._node_data.call_id)
            self._call_id = self._node_data.call_id
        else:
            # 可能是特殊的内置Node
            call_cls = await StepNode.get_call_cls(node_id)
            self._call_id = node_id

        # 初始化Call Class，用户参数会覆盖node的参数
        params: dict[str, Any] = (
            self._node_data.known_params if self._node_data and self._node_data.known_params else {}
        )
        if self.step.params:
            params.update(self.step.params)

        try:
            self.obj, self.input = await call_cls.init(self, **params)
        except Exception:
            logger.exception("[StepExecutor] 初始化Call失败")
            raise


    async def run_step(self, *, to_user: bool = False) -> None:
        """运行单个步骤"""
        if not self.task.state:
            err = "[StepExecutor] 当前ExecutorState为空"
            logger.error(err)
            raise ValueError(err)

        logger.info("[StepExecutor] 运行步骤 %s", self.step.name)

        # 合并已经填充的参数
        self.input.update(self.task.runtime.filled)
        await self.push_message(EventType.STEP_INPUT, self.input)

        # 执行步骤
        iterator = self.obj.exec(self, self.input)

        self.answer = ""
        self.content = {}
        if not to_user:
            async for chunk in iterator:
                if not isinstance(chunk, CallOutputChunk):
                    err = "[StepExecutor] 返回结果类型错误"
                    logger.error(err)
                    raise TypeError(err)

                if isinstance(chunk.content, str):
                    self.answer += chunk.content
                else:
                    self.content = chunk.content

        # 更新执行状态
        self.task.state.status = StepStatus.SUCCESS
        await self.push_message(EventType.STEP_OUTPUT, self.content)
