"""工作流中步骤相关函数"""

import logging
from typing import TYPE_CHECKING, Any

from pydantic import ConfigDict, Field

from apps.common.queue import MessageQueue
from apps.entities.enum_var import EventType, StepStatus
from apps.entities.flow import Step
from apps.entities.task import FlowStepHistory, Task
from apps.manager.node import NodeManager
from apps.manager.task import TaskManager
from apps.scheduler.call.slot.schema import SlotInput, SlotOutput
from apps.scheduler.call.slot.slot import Slot
from apps.scheduler.executor.base import BaseExecutor
from apps.scheduler.executor.node import StepNode

if TYPE_CHECKING:
    from apps.entities.scheduler import CallOutputChunk

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

        logger.info("[FlowExecutor] 运行步骤 %s", self.step.name)

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
        except Exception:
            logger.exception("[StepExecutor] 获取Node失败，为内部Node或ID不存在", stack_info=False)
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

        # 检查初始化Call Class是否需要特殊处理
        try:
            self._obj, self._input = await call_cls.init(self, **params)
        except Exception:
            logger.exception("[StepExecutor] 初始化Call失败")
            raise


    async def fill_slots(self) -> dict[str, Any]:
        """执行Call并处理结果"""
        if not self.task.state:
            err = "[StepExecutor] 当前ExecutorState为空"
            logger.error(err)
            raise ValueError(err)

        # 合并已经填充的参数
        self._input.update(self.task.runtime.filled)

        # 检查输入参数是否需要填充
        input_schema = (
            self._obj.input_type.model_json_schema(override=self._node_data.override_input) if self._node_data else {}
        )
        slot_obj = Slot(
            data=self._input,
            current_schema=input_schema,
            summary=self.task.runtime.summary,
            facts=self.task.runtime.facts,
        )
        slot_input = SlotInput(**await slot_obj.init(self))

        # 若需要填参，额外执行一步
        if slot_input.remaining_schema:
            output = SlotOutput(**await self.run_step("Slot", slot_obj, slot_input.remaining_schema))
            self.task.runtime.filled = output.slot_data

            # 如果还有剩余参数，则中断
            if output.remaining_schema:
                # 更新状态
                self.task.state.status = StepStatus.PARAM
                self.task.state.slot = output.remaining_schema
                err = "[StepExecutor] 需要填参"
                logger.error(err)
                raise ValueError(err)

            return output.slot_data
        return self._input


    # TODO: 需要评估如何进行流式输出
    async def run_step(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """运行单个步骤"""
        iterator = self._obj.exec(self, input_data)
        await self.push_message(EventType.STEP_INPUT, input_data)

        result: CallOutputChunk | None = None
        async for chunk in iterator:
            result = chunk

        if result is None:
            content = {}
        else:
            content = result.content if isinstance(result.content, dict) else {"message": result.content}

        # 更新执行状态
        if not self.task.state:
            err = "[StepExecutor] 当前ExecutorState为空"
            logger.error(err)
            raise ValueError(err)

        self.task.state.status = StepStatus.SUCCESS
        await self.push_message(EventType.STEP_OUTPUT, content)

        return content
