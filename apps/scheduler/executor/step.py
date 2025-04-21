"""工作流中步骤相关函数"""

import logging
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from pydantic import ConfigDict

from apps.entities.enum_var import (
    EventType,
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

        self._history = FlowStepHistory(
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
        await TaskManager.save_task(self.task.id, self.task)

        # 获取并验证Call类
        node_id = self.step.step.node
        # 获取node详情并存储
        try:
            self.node = await NodeManager.get_node(node_id)
        except ValueError:
            logger.info("[StepExecutor] 获取Node失败，为内部Node或ID不存在")
            self.node = None

        if self.node:
            call_cls = await StepNode.get_call_cls(self.node.call_id)
            self._call_id = self.node.call_id
        else:
            # 可能是特殊的内置Node
            call_cls = await StepNode.get_call_cls(node_id)
            self._call_id = node_id

        # 初始化Call Class，用户参数会覆盖node的参数
        params: dict[str, Any] = (
            self.node.known_params if self.node and self.node.known_params else {}
        )
        if self.step.step.params:
            params.update(self.step.step.params)

        try:
            self.obj = await call_cls.instance(self, self.node, **params)
        except Exception:
            logger.exception("[StepExecutor] 初始化Call失败")
            raise


    async def _run_slot_filling(self) -> None:
        """运行自动参数填充；相当于特殊Step，但是不存库"""
        # 判断State是否为空
        self.validate_flow_state(self.task)

        # 判断是否需要进行自动参数填充
        if not self.obj.enable_filling:
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
            "data": self.obj.input,
            "current_schema": self.obj.input_model.model_json_schema(
                override=self.node.override_input if self.node and self.node.override_input else {},
            ),
        }

        # 初始化填参
        slot_obj = await Slot.instance(self, self.node, **params)
        # 推送填参消息
        await self.push_message(EventType.STEP_INPUT.value, slot_obj.input)
        # 运行填参
        iterator = slot_obj.exec(self, slot_obj.input)
        async for chunk in iterator:
            result: SlotOutput = SlotOutput.model_validate(chunk.content)

        # 如果没有填全
        if result.remaining_schema:
            # 状态设置为待填参
            self.task.state.status = StepStatus.PARAM # type: ignore[arg-type]
        else:
            # 推送填参结果
            self.task.state.status = StepStatus.SUCCESS # type: ignore[arg-type]
        await TaskManager.save_task(self.task.id, self.task)
        await self.push_message(EventType.STEP_OUTPUT.value, result.slot_data)

        # 没完整填参，则返回
        if self.task.state.status == StepStatus.PARAM: # type: ignore[arg-type]
            return

        # 更新输入
        self.obj.input.update(result.slot_data)

        # 恢复State
        self.task.state.step_id = current_step_id # type: ignore[arg-type]
        self.task.state.step_name = current_step_name # type: ignore[arg-type]
        self.task.state.status = current_step_status # type: ignore[arg-type]
        await TaskManager.save_task(self.task.id, self.task)


    async def _process_chunk(
        self,
        iterator: AsyncGenerator[CallOutputChunk, None],
        *,
        to_user: bool = False,
    ) -> str | dict[str, Any]:
        """处理Chunk"""
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

        return content


    async def run_step(self) -> None:
        """运行单个步骤"""
        self.validate_flow_state(self.task)
        logger.info("[StepExecutor] 运行步骤 %s", self.step.step.name)

        # 进行自动参数填充
        await self._run_slot_filling()

        # 更新history
        self._history.input_data = self.obj.input
        self._history.output_data = {}
        # 更新状态
        self.task.state.status = StepStatus.RUNNING # type: ignore[arg-type]
        self._history.status = self.task.state.status # type: ignore[arg-type]
        await TaskManager.save_task(self.task.id, self.task)
        # 推送输入
        await self.push_message(EventType.STEP_INPUT.value, self.obj.input)

        # 执行步骤
        iterator = self.obj.exec(self, self.obj.input)

        try:
            content = await self._process_chunk(iterator, to_user=self.obj.to_user)
        except Exception:
            logger.exception("[StepExecutor] 运行步骤失败")
            self.task.state.status = StepStatus.ERROR # type: ignore[arg-type]
            await self.push_message(EventType.STEP_OUTPUT.value, {})
            await TaskManager.save_task(self.task.id, self.task)
            return

        # 更新执行状态
        self.task.state.status = StepStatus.SUCCESS # type: ignore[arg-type]
        self._history.status = self.task.state.status # type: ignore[arg-type]

        # 更新history
        if isinstance(content, str):
            self._history.output_data = TextAddContent(text=content).model_dump(exclude_none=True, by_alias=True)
        else:
            self._history.output_data = content

        # 更新context
        self.task.context.append(self._history.model_dump(exclude_none=True, by_alias=True))
        await TaskManager.save_task(self.task.id, self.task)

        # 推送输出
        await self.push_message(EventType.STEP_OUTPUT.value, self._history.output_data)
