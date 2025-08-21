# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Flow执行Executor"""

import logging
import uuid
from collections import deque
from datetime import UTC, datetime

from pydantic import Field

from apps.models.task import ExecutorCheckpoint
from apps.scheduler.call.llm.prompt import LLM_ERROR_PROMPT
from apps.schemas.enum_var import EventType, ExecutorStatus, LanguageType, SpecialCallType, StepStatus
from apps.schemas.flow import Flow, Step
from apps.schemas.request_data import RequestDataApp
from apps.schemas.task import StepQueueItem
from apps.services.task import TaskManager

from .base import BaseExecutor
from .step import StepExecutor

logger = logging.getLogger(__name__)
# 开始前的固定步骤
FIXED_STEPS_BEFORE_START = [
    {
        LanguageType.CHINESE: Step(
            name="理解上下文",
            description="使用大模型，理解对话上下文",
            node=SpecialCallType.SUMMARY.value,
            type=SpecialCallType.SUMMARY.value,
        ),
        LanguageType.ENGLISH: Step(
            name="Understand context",
            description="Use large model to understand the context of the dialogue",
            node=SpecialCallType.SUMMARY.value,
            type=SpecialCallType.SUMMARY.value,
        ),
    },
]
# 结束后的固定步骤
FIXED_STEPS_AFTER_END = [
    {
        LanguageType.CHINESE: Step(
            name="记忆存储",
            description="理解对话答案，并存储到记忆中",
            node=SpecialCallType.FACTS.value,
            type=SpecialCallType.FACTS.value,
        ),
        LanguageType.ENGLISH: Step(
            name="Memory storage",
            description="Understand the answer of the dialogue and store it in the memory",
            node=SpecialCallType.FACTS.value,
            type=SpecialCallType.FACTS.value,
        ),
    },
]


# 单个流的执行工具
class FlowExecutor(BaseExecutor):
    """用于执行工作流的Executor"""

    flow: Flow
    flow_id: str = Field(description="Flow ID")
    question: str = Field(description="用户输入")
    post_body_app: RequestDataApp = Field(description="请求体中的app信息")
    current_step: StepQueueItem | None = Field(
        description="当前执行的步骤",
        exclude=True,
        default=None,
    )


    async def init(self) -> None:
        """初始化FlowExecutor"""
        logger.info("[FlowExecutor] 加载Executor状态")
        # 尝试恢复State
        if (
            self.state
            and self.state.executorStatus not in [ExecutorStatus.INIT, ExecutorStatus.UNKNOWN]
        ):
            self.context = await TaskManager.get_context_by_task_id(self.task.id)
        else:
            # 创建ExecutorState
            self.state = ExecutorCheckpoint(
                taskId=self.task.id,
                appId=self.post_body_app.app_id,
                executorId=str(self.flow_id),
                executorName=self.flow.name,
                executorStatus=ExecutorStatus.RUNNING,
                stepStatus=StepStatus.RUNNING,
                stepId="start",
                stepName="开始" if self.runtime.language == LanguageType.CHINESE else "Start",
            )
        # 是否到达Flow结束终点（变量）
        self._reached_end: bool = False
        self.step_queue: deque[StepQueueItem] = deque()


    async def _invoke_runner(self) -> None:
        """单一Step执行"""
        # 创建步骤Runner
        step_runner = StepExecutor(
            msg_queue=self.msg_queue,
            task=self.task,
            step=self.current_step,
            background=self.background,
            question=self.question,
            runtime=self.runtime,
            state=self.state,
            context=self.context,
        )

        # 初始化步骤
        await step_runner.init()
        # 运行Step
        await step_runner.run()

        # 更新Task（已存过库）
        self.task = step_runner.task


    async def _step_process(self) -> None:
        """执行当前queue里面的所有步骤（在用户看来是单一Step）"""
        while True:
            try:
                self.current_step = self.step_queue.pop()
            except IndexError:
                break

            # 执行Step
            await self._invoke_runner()


    async def _find_next_id(self, step_id: uuid.UUID) -> list[uuid.UUID]:
        """查找下一个节点"""
        next_ids = []
        for edge in self.flow.edges:
            if edge.edge_from == step_id:
                next_ids += [edge.edge_to]
        return next_ids


    async def _find_flow_next(self) -> list[StepQueueItem]:
        """在当前步骤执行前，尝试获取下一步"""
        # 如果当前步骤为结束，则直接返回
        if self.state.stepId == "end" or not self.state.stepId:
            return []
        if self.current_step.step.type == SpecialCallType.CHOICE.value:
            # 如果是choice节点，获取分支ID
            branch_id = self.context[-1].outputData["branch_id"]
            if branch_id:
                next_steps = await self._find_next_id(str(self.state.stepId) + "." + branch_id)
                logger.info("[FlowExecutor] 分支ID：%s", branch_id)
            else:
                logger.warning("[FlowExecutor] 没有找到分支ID，返回空列表")
                return []
        else:
            next_steps = await self._find_next_id(self.state.stepId)
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
        logger.info("[FlowExecutor] 运行工作流")
        # 推送Flow开始消息
        await self.push_message(EventType.FLOW_START.value)

        # 获取首个步骤
        first_step = StepQueueItem(
            step_id=self.state.stepId,
            step=self.flow.steps[self.state.stepId],
        )

        # 头插开始前的系统步骤，并执行
        for step in FIXED_STEPS_BEFORE_START:
            self.step_queue.append(
                StepQueueItem(
                    step_id=uuid.uuid4(),
                    step=step.get(self.runtime.language, step[LanguageType.CHINESE]),
                    enable_filling=False,
                    to_user=False,
                ),
            )
        await self._step_process()

        # 插入首个步骤
        self.step_queue.append(first_step)
        self.state.executorStatus = ExecutorStatus.RUNNING

        # 运行Flow（未达终点）
        is_error = False
        while not self._reached_end:
            # 如果当前步骤出错，执行错误处理步骤
            if self.state.stepStatus == StepStatus.ERROR:
                logger.warning("[FlowExecutor] Executor出错，执行错误处理步骤")
                self.step_queue.clear()
                self.step_queue.appendleft(
                    StepQueueItem(
                        step_id=uuid.uuid4(),
                        step=Step(
                            name=(
                                "错误处理" if self.runtime.language == LanguageType.CHINESE else "Error Handling"
                            ),
                            description=(
                                "错误处理" if self.runtime.language == LanguageType.CHINESE else "Error Handling"
                            ),
                            node=SpecialCallType.LLM.value,
                            type=SpecialCallType.LLM.value,
                            params={
                                "user_prompt": LLM_ERROR_PROMPT[self.runtime.language].replace(
                                    "{{ error_info }}",
                                    self.state.errorMessage["err_msg"],
                                ),
                            },
                        ),
                        enable_filling=False,
                        to_user=False,
                    ),
                )
                is_error = True
                # 错误处理后结束
                self._reached_end = True

            # 执行步骤
            await self._step_process()

            # 查找下一个节点
            next_step = await self._find_flow_next()
            if not next_step:
                # 没有下一个节点，结束
                self._reached_end = True
            for step in next_step:
                self.step_queue.append(step)

        # 更新Task状态
        if is_error:
            self.state.executorStatus = ExecutorStatus.ERROR
        else:
            self.state.executorStatus = ExecutorStatus.SUCCESS

        # 尾插运行结束后的系统步骤
        for step in FIXED_STEPS_AFTER_END:
            self.step_queue.append(
                StepQueueItem(
                    step_id=uuid.uuid4(),
                    step=step.get(self.runtime.language, step[LanguageType.CHINESE]),
                ),
            )
        await self._step_process()

        # FlowStop需要返回总时间，需要倒推最初的开始时间（当前时间减去当前已用总时间）
        self.runtime.time = round(datetime.now(UTC).timestamp(), 2) - self.runtime.fullTime
        # 推送Flow停止消息
        if is_error:
            await self.push_message(EventType.FLOW_FAILED.value)
        else:
            await self.push_message(EventType.FLOW_SUCCESS.value)
