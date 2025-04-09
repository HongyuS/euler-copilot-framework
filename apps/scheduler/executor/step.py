"""工作流中步骤相关函数"""

import logging
from typing import Any

from pydantic import ConfigDict

from apps.common.queue import MessageQueue
from apps.entities.enum_var import EventType, StepStatus
from apps.entities.scheduler import CallOutputChunk, CallVars
from apps.entities.task import FlowStepHistory, Task
from apps.manager.node import NodeManager
from apps.manager.task import TaskManager
from apps.scheduler.call.core import CoreCall
from apps.scheduler.call.slot.schema import SlotInput, SlotOutput
from apps.scheduler.call.slot.slot import Slot
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

    sys_vars: CallVars

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

        self.step_history = FlowStepHistory(
            task_id=self.sys_vars.task_id,
            flow_id=self.sys_vars.flow_id,
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

    async def init_step(self, step_id: str) -> tuple[str, Any]:
        """初始化步骤"""
        if not self.task.state:
            err = "[StepExecutor] 当前ExecutorState为空"
            logger.error(err)
            raise ValueError(err)

        logger.info("[FlowExecutor] 运行步骤 %s", self.flow.steps[step_id].name)

        # State写入ID和运行状态
        self.task.state.step_id = step_id
        self.task.state.step_name = self.flow.steps[step_id].name
        self.task.state.status = StepStatus.RUNNING
        await TaskManager.save_task(self.task.id, self.task)

        # 获取并验证Call类
        node_id = self.flow.steps[step_id].node
        # 获取node详情并存储
        try:
            self._node_data = await NodeManager.get_node(node_id)
        except Exception:
            logger.exception("[StepExecutor] 获取Node失败，为内部Node或ID不存在")
            self._node_data = None

        if self._node_data:
            call_cls = await StepNode.get_call_cls(self._node_data.call_id)
            call_id = self._node_data.call_id
        else:
            # 可能是特殊的内置Node
            call_cls = await StepNode.get_call_cls(node_id)
            call_id = node_id

        # 初始化Call Class，用户参数会覆盖node的参数
        params: dict[str, Any] = (
            self._node_data.known_params if self._node_data and self._node_data.known_params else {}
        )  # type: ignore[union-attr]
        if self.flow.steps[step_id].params:
            params.update(self.flow.steps[step_id].params)

        # 检查初始化Call Class是否需要特殊处理
        try:
            call_obj, input_data = await call_cls.init(self.sys_vars, **params)
        except Exception:
            logger.exception("[StepExecutor] 初始化Call失败")
            raise
        else:
            return call_id, call_obj

    async def fill_slots(self, call_obj: Any) -> dict[str, Any]:
        """执行Call并处理结果"""
        if not self.task.state:
            err = "[StepExecutor] 当前ExecutorState为空"
            logger.error(err)
            raise ValueError(err)

        # 尝试初始化call_obj
        try:
            input_data = await call_obj.init(self.sys_vars)
        except Exception:
            logger.exception("[StepExecutor] 初始化Call失败")
            raise

        # 合并已经填充的参数
        input_data.update(self.task.runtime.filled)

        # 检查输入参数
        input_schema = (
            call_obj.input_type.model_json_schema(override=self._node_data.override_input) if self._node_data else {}
        )

        # 检查输入参数是否需要填充
        slot_obj = Slot(
            data=input_data,
            current_schema=input_schema,
            summary=self.task.runtime.summary,
            facts=self.task.runtime.facts,
        )
        slot_input = SlotInput(**await slot_obj.init(self.sys_vars))

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
        return input_data

    # TODO: 需要评估如何进行流式输出
    async def run_step(self, call_id: str, call_obj: CoreCall, input_data: dict[str, Any]) -> dict[str, Any]:
        """运行单个步骤"""
        iterator = call_obj.exec(self, input_data)
        await self.push_message(EventType.STEP_INPUT, input_data)

        result: CallOutputChunk | None = None
        async for chunk in iterator:
            result = chunk

        if result is None:
            content = {}
        else:
            content = result.content if isinstance(result.content, dict) else {"message": result.content}

        # 更新执行状态
        self.task.state.status = StepStatus.SUCCESS
        await self.push_message(EventType.STEP_OUTPUT, content)

        return content
