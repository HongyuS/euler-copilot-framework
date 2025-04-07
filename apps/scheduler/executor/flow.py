"""
Flow执行Executor

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

import logging

from pydantic import ConfigDict, Field

from apps.entities.enum_var import EventType, StepStatus
from apps.entities.flow import Step
from apps.entities.request_data import RequestDataApp
from apps.entities.scheduler import CallVars
from apps.entities.task import ExecutorState
from apps.manager.task import TaskManager
from apps.scheduler.call.llm.schema import LLM_ERROR_PROMPT
from apps.scheduler.executor.base import BaseExecutor
from apps.scheduler.executor.step import StepExecutor

logger = logging.getLogger(__name__)
FIXED_STEPS_BEFORE_START = {
    "_summary": Step(
        name="理解上下文",
        description="使用大模型，理解对话上下文",
        node="Summary",
        type="Summary",
        params={},
    ),
}
FIXED_STEPS_AFTER_END = {
    "_facts": Step(
        name="记忆存储",
        description="理解对话答案，并存储到记忆中",
        node="Facts",
        type="Facts",
        params={},
    ),
}
SLOT_FILLING_STEP = Step(
    name="填充参数",
    description="根据步骤历史，填充参数",
    node="Slot",
    type="Slot",
    params={},
)
ERROR_STEP = Step(
    name="错误处理",
    description="错误处理",
    node="LLM",
    type="LLM",
    params={
        "user_prompt": LLM_ERROR_PROMPT,
    },
)


# 单个流的执行工具
class FlowExecutor(BaseExecutor):
    """用于执行工作流的Executor"""

    flow_id: str = Field(description="Flow ID")
    question: str = Field(description="用户输入")
    post_body_app: RequestDataApp = Field(description="请求体中的app信息")

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="allow",
    )
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

    async def _invoke_runner(self, step_id: str) -> None:
        """调用Runner"""
        if not self.task.state:
            err = "[FlowExecutor] 当前ExecutorState为空"
            logger.error(err)
            raise ValueError(err)

        step = self.flow.steps[step_id]

        # 准备系统变量
        sys_vars = CallVars(
            question=self.question,
            task_id=self.task.id,
            flow_id=self.post_body_app.flow_id,
            session_id=self.task.ids.session_id,
            history=self.task.context,
            summary=self.task.runtime.summary,
            user_sub=self.task.ids.user_sub,
            service_id=step.params.get("service_id", ""),
        )
        step_runner = StepExecutor(
            queue=self.queue,
            task=self.task,
            flow=self.flow,
            sys_vars=sys_vars,
            executor_background=self.executor_background,
            question=self.question,
        )

        # 运行Step
        call_id, call_obj = await step_runner.init_step(step_id)
        # 尝试填参
        input_data = await step_runner.fill_slots(call_obj)
        # 运行
        await step_runner.run_step(call_id, call_obj, input_data)

        # 更新Task
        self.task = step_runner.task
        await TaskManager.save_task(self.task.id, self.task)

    async def _find_flow_next(self) -> str:
        """在当前步骤执行前，尝试获取下一步"""
        if not self.task.state:
            err = "[StepExecutor] 当前ExecutorState为空"
            logger.error(err)
            raise ValueError(err)

        # 如果当前步骤为结束，则直接返回
        if self.task.state.step_id == "end" or not self.task.state.step_id:
            # 如果是最后一步，设置停止标志
            self._reached_end = True
            return ""

        next_steps = []
        # 遍历Edges，查找下一个节点
        for edge in self.flow.edges:
            if edge.edge_from == self.task.state.step_id:
                next_steps += [edge.edge_to]

        # 如果step没有任何出边，直接跳到end
        if not next_steps:
            return "end"

        # TODO: 目前只使用第一个出边
        logger.info("[FlowExecutor] 下一步 %s", next_steps[0])
        return next_steps[0]

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
        for step_id, step in FIXED_STEPS_BEFORE_START.items():
            self.flow.steps[step_id] = step
            await self._invoke_runner(step_id)

        self.task.state.step_id = "start"
        self.task.state.step_name = "开始"
        # 如果允许继续运行Flow
        while not self._reached_end:
            # Flow定义中找不到step
            if not self.task.state.step_id or (self.task.state.step_id not in self.flow.steps):
                logger.error("[FlowExecutor] 当前步骤 %s 不存在", self.task.state.step_id)
                self.task.state.status = StepStatus.ERROR

            if self.task.state.status == StepStatus.ERROR:
                # 执行错误处理步骤
                logger.warning("[FlowExecutor] Executor出错，执行错误处理步骤")
                self.flow.steps["_error"] = ERROR_STEP
                await self._invoke_runner("_error")
            else:
                # 执行正常步骤
                step = self.flow.steps[self.task.state.step_id]
                await self._invoke_runner(self.task.state.step_id)

            # 步骤结束，更新全局的Task
            await TaskManager.save_task(self.task.id, self.task)

            # 查找下一个节点
            next_step_id = await self._find_flow_next()
            if next_step_id:
                self.task.state.step_id = next_step_id
                self.task.state.step_name = self.flow.steps[next_step_id].name
            else:
                # 如果没有下一个节点，设置结束标志
                self._reached_end = True

        # 运行结束后的系统步骤
        for step_id, step in FIXED_STEPS_AFTER_END.items():
            self.flow.steps[step_id] = step
            await self._invoke_runner(step_id)

        # 推送Flow停止消息
        await self.push_message(EventType.FLOW_STOP)

        # 更新全局的Task
        await TaskManager.save_task(self.task.id, self.task)
