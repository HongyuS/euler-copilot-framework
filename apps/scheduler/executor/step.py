"""工作流中步骤相关函数"""

import logging
import uuid
from typing import Any

from pydantic import ConfigDict

from apps.entities.enum_var import (
    EventType,
    SpecialCallType,
    StepStatus,
)
from apps.entities.message import TextAddContent
from apps.entities.scheduler import CallOutputChunk
from apps.entities.task import FlowStepHistory, StepQueueItem
from apps.manager.node import NodeManager
from apps.manager.task import TaskManager
from apps.scheduler.call.slot.schema import SlotOutput
from apps.scheduler.call.slot.slot import Slot
from apps.scheduler.executor.base import BaseExecutor
from apps.scheduler.executor.node import StepNode

logger = logging.getLogger(__name__)


class StepExecutor(BaseExecutor):
    """工作流中步骤相关函数"""

    step: StepQueueItem


    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="allow",
    )

    def __init__(self, **kwargs: Any) -> None:
        """初始化"""
        super().__init__(**kwargs)
        self.validate_flow_state(self.task)

        self.history = FlowStepHistory(
            task_id=self.task.id,
            flow_id=self.task.state.flow_id, # type: ignore[arg-type]
            step_id=self.task.state.step_id, # type: ignore[arg-type]
            status=self.task.state.status, # type: ignore[arg-type]
            input_data={},
            output_data={},
        )

    async def init(self) -> None:
        """初始化步骤"""
        self.validate_flow_state(self.task)

        logger.info("[StepExecutor] 初始化步骤 %s", self.step.step.name)

        # State写入ID和运行状态
        self.task.state.step_id = self.step.step_id # type: ignore[arg-type]
        self.task.state.step_name = self.step.step.name # type: ignore[arg-type]
        self.task.state.status = StepStatus.RUNNING # type: ignore[arg-type]
        await TaskManager.save_task(self.task.id, self.task)

        # 获取并验证Call类
        node_id = self.step.step.node
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
        if self.step.step.params:
            params.update(self.step.step.params)

        try:
            self.obj, self.input = await call_cls.init(self, **params)
        except Exception:
            logger.exception("[StepExecutor] 初始化Call失败")
            raise


    async def _run_slot_filling(self) -> None:
        """运行自动参数填充"""
        # 判断State是否为空
        self.validate_flow_state(self.task)

        # 特殊步骤跳过填参
        if self.step.step.type in [
            SpecialCallType.SUMMARY.value,
            SpecialCallType.FACTS.value,
            SpecialCallType.SLOT.value,
            SpecialCallType.OUTPUT.value,
            SpecialCallType.EMPTY.value,
            SpecialCallType.START.value,
            SpecialCallType.END.value,
        ]:
            return

        # 暂存旧数据
        current_step_id = self.task.state.step_id # type: ignore[arg-type]
        current_step_name = self.task.state.step_name # type: ignore[arg-type]
        current_step_status = self.task.state.status # type: ignore[arg-type]

        # 更新State
        self.task.state.step_id = str(uuid.uuid4()) # type: ignore[arg-type]
        self.task.state.step_name = "自动参数填充" # type: ignore[arg-type]
        self.task.state.status = StepStatus.RUNNING # type: ignore[arg-type]
        await TaskManager.save_task(self.task.id, self.task)
        # 准备参数
        params = {
            "data": self.input,
            "current_schema": self.obj.input_type.model_json_schema(),
        }

        # 初始化填参
        slot_obj, slot_input = await Slot.init(self, **params)
        # 推送填参消息
        await self.push_message(EventType.STEP_INPUT.value, slot_input)
        # 运行填参
        iterator = slot_obj.exec(self, slot_input)
        async for chunk in iterator:
            result: SlotOutput = SlotOutput.model_validate(chunk.content)

        self.input.update(result.slot_data)

        # 恢复State
        self.task.state.step_id = current_step_id # type: ignore[arg-type]
        self.task.state.step_name = current_step_name # type: ignore[arg-type]
        self.task.state.status = current_step_status # type: ignore[arg-type]
        await TaskManager.save_task(self.task.id, self.task)


    async def run_step(self, *, to_user: bool = False) -> None:
        """运行单个步骤"""
        self.validate_flow_state(self.task)
        logger.info("[StepExecutor] 运行步骤 %s", self.step.step.name)

        # 推送输入
        await self.push_message(EventType.STEP_INPUT.value, self.input)

        # 执行步骤
        iterator = self.obj.exec(self, self.input)

        content: str | dict[str, Any] = ""
        async for chunk in iterator:
            if not isinstance(chunk, CallOutputChunk):
                err = "[StepExecutor] 返回结果类型错误"
                logger.error(err)
                raise TypeError(err)

            if isinstance(chunk.content, str):
                if not isinstance(content, str):
                    content = ""
                content += chunk.content
            else:
                if not isinstance(content, dict):
                    content = {}
                content = chunk.content

            if to_user:
                if isinstance(chunk.content, str):
                    await self.push_message(EventType.TEXT_ADD.value, chunk.content)
                    self.task.runtime.answer += chunk.content
                else:
                    await self.push_message(self.step.step.type, chunk.content)

        # 更新执行状态
        self.task.state.status = StepStatus.SUCCESS # type: ignore[arg-type]

        if isinstance(content, str):
            self.content = TextAddContent(text=content).model_dump(exclude_none=True, by_alias=True)
        else:
            self.content = content
        await self.push_message(EventType.STEP_OUTPUT.value, self.content)
