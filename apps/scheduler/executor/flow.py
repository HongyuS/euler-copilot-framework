"""
Flow执行Executor

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

import logging
import uuid
from collections import deque
from typing import Any

from pydantic import Field

from apps.entities.enum_var import EventType, SpecialCallType, StepStatus
from apps.entities.flow import Flow, Step
from apps.entities.request_data import RequestDataApp
from apps.entities.task import ExecutorState, StepQueueItem
from apps.manager.task import TaskManager
from apps.scheduler.call.llm.schema import LLM_ERROR_PROMPT
from apps.scheduler.call.output.output import Output
from apps.scheduler.executor.base import BaseExecutor
from apps.scheduler.executor.step import StepExecutor

logger = logging.getLogger(__name__)
FIXED_STEPS_BEFORE_START = [
    Step(
        name="理解上下文",
        description="使用大模型，理解对话上下文",
        node=SpecialCallType.SUMMARY.value,
        type=SpecialCallType.SUMMARY.value,
    ),
]
FIXED_STEPS_AFTER_END = [
    Step(
        name="记忆存储",
        description="理解对话答案，并存储到记忆中",
        node=SpecialCallType.FACTS.value,
        type=SpecialCallType.FACTS.value,
    ),
]
SLOT_FILLING_STEP = Step(
    name="自动参数填充",
    description="根据工作流上下文，自动填充参数",
    node=SpecialCallType.SLOT.value,
    type=SpecialCallType.SLOT.value,
)
ERROR_STEP = Step(
    name="错误处理",
    description="错误处理",
    node=SpecialCallType.LLM.value,
    type=SpecialCallType.LLM.value,
    params={
        "user_prompt": LLM_ERROR_PROMPT,
    },
)


# 单个流的执行工具
class FlowExecutor(BaseExecutor):
    """用于执行工作流的Executor"""

    flow: Flow
    flow_id: str = Field(description="Flow ID")
    question: str = Field(description="用户输入")
    post_body_app: RequestDataApp = Field(description="请求体中的app信息")

    """Pydantic配置"""

    async def load_state(self) -> None:
        """从数据库中加载FlowExecutor的状态"""
        logger.info("[FlowExecutor] 加载Executor状态")
        # 尝试恢复State
        if self.task.state:
            self.task.context = await TaskManager.get_flow_history_by_task_id(self.task.id)
        else:
            # 创建ExecutorState
            self.task.state = ExecutorState(
                flow_id=str(self.flow_id),
                description=str(self.flow.description),
                status=StepStatus.RUNNING,
                app_id=str(self.post_body_app.app_id),
                step_id="start",
                step_name="开始",
            )
        # 是否到达Flow结束终点（变量）
        self._reached_end: bool = False
        self.step_queue: deque[StepQueueItem] = deque()


    async def _invoke_runner(self, step_id: str, step: Step, *, enable_slot_filling: bool = True) -> dict[str, Any]:
        """单一Step执行"""
        if not self.task.state:
            err = "[FlowExecutor] 当前ExecutorState为空"
            logger.error(err)
            raise ValueError(err)

        # 创建步骤Runner
        step_runner = StepExecutor(
            msg_queue=self.msg_queue,
            task=self.task,
            step=step,
            step_id=step_id,
            background=self.background,
            question=self.question,
            history=self.history,
        )

        # 初始化步骤
        await step_runner.init()

        if step.type in [
            SpecialCallType.SUMMARY.value,
            SpecialCallType.FACTS.value,
            SpecialCallType.SLOT.value,
            SpecialCallType.OUTPUT.value,
            SpecialCallType.EMPTY.value,
            SpecialCallType.START.value,
            SpecialCallType.END.value,
        ]:
            enable_slot_filling = False

        # 运行参数填充Step
        if enable_slot_filling:
            slot_step = StepExecutor(
                msg_queue=self.msg_queue,
                task=self.task,
                step=SLOT_FILLING_STEP,
                step_id=str(uuid.uuid4()),
                background=self.background,
                question=self.question,
                history=self.history,
            )
            await slot_step.init()
            result = await slot_step.run_step()
            if result:
                self.task.runtime.filled.update(result)

            # 合并参数
            step_runner.input = self.task.runtime.filled

        # 运行Step，并判断是否需要输出
        if isinstance(step_runner.obj, Output):
            await step_runner.run_step(to_user=True)
        else:
            await step_runner.run_step()

        # 更新Task
        self.task = step_runner.task
        await TaskManager.save_task(self.task.id, self.task)

        # 返回迭代器
        return step_runner.content


    async def _step_process(self) -> None:
        """单一Step执行"""
        if not self.task.state:
            err = "[FlowExecutor] 当前ExecutorState为空"
            logger.error(err)
            raise ValueError(err)

        while True:
            try:
                queue_item = self.step_queue.pop()
            except IndexError:
                break

            # 更新Task
            self.task.state.step_id = queue_item.step_id
            self.task.state.step_name = queue_item.step.name
            if queue_item.step_id not in self.flow.steps:
                self.task.state.slot = {}
            else:
                self.task.state.slot = self.flow.steps[queue_item.step_id].params

            # 执行Step
            content = await self._invoke_runner(
                queue_item.step_id,
                queue_item.step,
                enable_slot_filling=queue_item.enable_filling,
            )


    async def _find_flow_next(self) -> list[StepQueueItem]:
        """在当前步骤执行前，尝试获取下一步"""
        if not self.task.state:
            err = "[StepExecutor] 当前ExecutorState为空"
            logger.error(err)
            raise ValueError(err)

        # 如果当前步骤为结束，则直接返回
        if self.task.state.step_id == "end" or not self.task.state.step_id:
            return []

        next_steps = []
        # 遍历Edges，查找下一个节点
        for edge in self.flow.edges:
            if edge.edge_from == self.task.state.step_id:
                next_steps += [edge.edge_to]

        # 如果step没有任何出边，直接跳到end
        if not next_steps:
            return [
                StepQueueItem(
                    step_id="end",
                    step=self.flow.steps["end"],
                ),
            ]

        logger.info("[FlowExecutor] 下一步：%s", next_steps)
        return [
            StepQueueItem(
                step_id=next_step,
                step=self.flow.steps[next_step],
            )
            for next_step in next_steps
        ]


    async def run(self) -> None:
        """
        运行流，返回各步骤结果，直到无法继续执行

        数据通过向Queue发送消息的方式传输
        """
        if not self.task.state:
            err = "[FlowExecutor] 当前ExecutorState为空"
            logger.error(err)
            raise ValueError(err)

        logger.info("[FlowExecutor] 运行工作流")
        # 推送Flow开始消息
        await self.push_message(EventType.FLOW_START)

        # 进行开始前的系统步骤
        for step in FIXED_STEPS_BEFORE_START:
            self.step_queue.append(StepQueueItem(
                step_id=str(uuid.uuid4()),
                step=step,
                enable_filling=False,
            ))

        # 如果允许继续运行Flow
        while not self._reached_end:
            # 如果当前步骤出错，执行错误处理步骤
            if self.task.state.status == StepStatus.ERROR:
                logger.warning("[FlowExecutor] Executor出错，执行错误处理步骤")
                self.step_queue.clear()
                self.step_queue.append(StepQueueItem(
                    step_id=str(uuid.uuid4()),
                    step=ERROR_STEP,
                    enable_filling=False,
                ))
                # 错误处理后结束
                self._reached_end = True
            else:
                try:
                    self.step_queue.append(StepQueueItem(
                        step_id=self.task.state.step_id,
                        step=self.flow.steps[self.task.state.step_id],
                    ))
                except KeyError:
                    logger.info("[FlowExecutor] 当前步骤 %s 不存在", self.task.state.step_id)
                    self.task.state.status = StepStatus.ERROR
                    continue

            # 执行正常步骤
            await self._step_process()

            # 步骤结束，更新全局的Task
            await TaskManager.save_task(self.task.id, self.task)

            # 查找下一个节点
            next_step = await self._find_flow_next()
            if not next_step:
                # 没有下一个节点，结束
                self._reached_end = True
            for step in next_step:
                self.step_queue.append(step)

        # 运行结束后的系统步骤
        for step in FIXED_STEPS_AFTER_END:
            self.step_queue.append(StepQueueItem(
                step_id=str(uuid.uuid4()),
                step=step,
            ))
        await self._step_process()

        # 推送Flow停止消息
        await self.push_message(EventType.FLOW_STOP)

        # 更新全局的Task
        await TaskManager.save_task(self.task.id, self.task)
