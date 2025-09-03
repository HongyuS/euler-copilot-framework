# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Scheduler模块"""

import asyncio
import logging
import uuid
from datetime import UTC, datetime

from apps.common.queue import MessageQueue
from apps.llm.embedding import Embedding
from apps.llm.function import FunctionLLM
from apps.llm.reasoning import ReasoningLLM
from apps.models.task import Task, TaskRuntime
from apps.models.user import User
from apps.scheduler.executor.agent import MCPAgentExecutor
from apps.scheduler.executor.flow import FlowExecutor
from apps.scheduler.pool.pool import Pool
from apps.scheduler.scheduler.flow import FlowChooser
from apps.schemas.enum_var import AppType, EventType, ExecutorStatus
from apps.schemas.message import (
    InitContent,
    InitContentFeature,
)
from apps.schemas.rag_data import RAGQueryReq
from apps.schemas.request_data import RequestData
from apps.schemas.scheduler import ExecutorBackground, LLMConfig
from apps.schemas.task import TaskData
from apps.services.activity import Activity
from apps.services.appcenter import AppCenterManager
from apps.services.knowledge import KnowledgeBaseManager
from apps.services.llm import LLMManager
from apps.services.task import TaskManager
from apps.services.user import UserManager

logger = logging.getLogger(__name__)


class Scheduler:
    """
    “调度器”，是最顶层的、控制Executor执行顺序和状态的逻辑。

    Scheduler包含一个“SchedulerContext”，作用为多个Executor的“聊天会话”
    """

    task: TaskData
    llm: LLMConfig
    queue: MessageQueue
    post_body: RequestData
    user: User


    async def init(
            self,
            task_id: uuid.UUID,
            queue: MessageQueue,
            post_body: RequestData,
            user_sub: str,
    ) -> None:
        """初始化"""
        self.queue = queue
        self.post_body = post_body
        # 获取用户
        user = await UserManager.get_user(user_sub)
        if not user:
            err = f"[Scheduler] 用户 {user_sub} 不存在"
            logger.error(err)
            raise RuntimeError(err)
        self.user = user

        # 获取Task
        task = await TaskManager.get_task_data_by_task_id(task_id)
        if not task:
            logger.info("[Scheduler] 新建任务")
            task = TaskData(
                metadata=Task(
                    id=task_id,
                    userSub=user_sub,
                    conversationId=self.post_body.conversation_id,
                ),
                runtime=TaskRuntime(
                    taskId=task_id,
                ),
                state=None,
                context=[],
            )
        self.task = task


    async def push_init_message(
        self, context_num: int, *, is_flow: bool = False,
    ) -> None:
        """推送初始化消息"""
        # 组装feature
        if is_flow:
            feature = InitContentFeature(
                maxTokens=self.llm.reasoning.config.maxToken or 0,
                contextNum=context_num,
                enableFeedback=False,
                enableRegenerate=False,
            )
        else:
            feature = InitContentFeature(
                maxTokens=self.llm.reasoning.config.maxToken or 0,
                contextNum=context_num,
                enableFeedback=True,
                enableRegenerate=True,
            )

        # 保存必要信息到Task
        created_at = round(datetime.now(UTC).timestamp(), 3)
        self.task.runtime.time = created_at

        # 推送初始化消息
        await self.queue.push_output(
            task=self.task,
            event_type=EventType.INIT.value,
            data=InitContent(feature=feature, createdAt=created_at).model_dump(exclude_none=True, by_alias=True),
        )

    async def _monitor_activity(self, kill_event: asyncio.Event, user_sub: str) -> None:
        """监控用户活动状态，不活跃时终止工作流"""
        try:
            check_interval = 0.5  # 每0.5秒检查一次

            while not kill_event.is_set():
                # 检查用户活动状态
                is_active = await Activity.is_active(user_sub)

                if not is_active:
                    logger.warning("[Scheduler] 用户 %s 不活跃，终止工作流", user_sub)
                    kill_event.set()
                    break

                # 控制检查频率
                await asyncio.sleep(check_interval)
        except asyncio.CancelledError:
            logger.info("[Scheduler] 活动监控任务已取消")
        except Exception:
            logger.exception("[Scheduler] 活动监控过程中发生错误")
            kill_event.set()


    async def get_scheduler_llm(self, reasoning_llm_id: str) -> LLMConfig:
        """获取RAG大模型"""
        # 获取当前会话使用的大模型
        reasoning_llm = await LLMManager.get_llm(reasoning_llm_id)
        if not reasoning_llm:
            err = "[Scheduler] 获取问答用大模型ID失败"
            logger.error(err)
            raise ValueError(err)
        reasoning_llm = ReasoningLLM(reasoning_llm)

        # 获取功能性的大模型信息
        function_llm = None
        if not self.user.functionLLM:
            logger.error("[Scheduler] 用户 %s 没有设置函数调用大模型，相关功能将被禁用", self.user.userSub)
        else:
            function_llm = await LLMManager.get_llm(self.user.functionLLM)
            if not function_llm:
                logger.error(
                    "[Scheduler] 用户 %s 设置的函数调用大模型ID %s 不存在，相关功能将被禁用",
                    self.user.userSub, self.user.functionLLM,
                )
            else:
                function_llm = FunctionLLM(function_llm)

        embedding_llm = None
        if not self.user.embeddingLLM:
            logger.error("[Scheduler] 用户 %s 没有设置向量模型，相关功能将被禁用", self.user.userSub)
        else:
            embedding_llm = await LLMManager.get_llm(self.user.embeddingLLM)
            if not embedding_llm:
                logger.error(
                    "[Scheduler] 用户 %s 设置的向量模型ID %s 不存在，相关功能将被禁用",
                    self.user.userSub, self.user.embeddingLLM,
                )
            else:
                embedding_llm = Embedding(embedding_llm)

        return LLMConfig(
            reasoning=reasoning_llm,
            function=function_llm,
            embedding=embedding_llm,
        )


    async def run(self) -> None:
        """运行调度器"""
        # 如果是智能问答，直接执行
        logger.info("[Scheduler] 开始执行")
        # 创建用于通信的事件
        kill_event = asyncio.Event()
        monitor = asyncio.create_task(self._monitor_activity(kill_event, self.task.metadata.userSub))

        rag_method = True
        if self.post_body.app and self.post_body.app.app_id:
            rag_method = False

        if self.task.state.appId:
            rag_method = False
        if rag_method:
            llm = await self.get_scheduler_llm()
            kb_ids = await KnowledgeBaseManager.get_selected_kb(self.task.ids.user_sub)
            self.task = await push_init_message(self.task, self.queue, 3, is_flow=False)
            rag_data = RAGQueryReq(
                kbIds=kb_ids,
                query=self.post_body.question,
                tokensLimit=llm.max_tokens,
            )
            # 启动监控任务和主任务
            main_task = asyncio.create_task(push_rag_message(
                self.task, self.queue, self.task.ids.user_sub, llm, history, doc_ids, rag_data))
        else:
            # 查找对应的App元数据
            app_data = await AppCenterManager.fetch_app_data_by_id(self.post_body.app.app_id)
            if not app_data:
                logger.error("[Scheduler] App %s 不存在", self.post_body.app.app_id)
                await self.queue.close()
                return

            # 获取上下文
            context, facts = await get_context(self.task.ids.user_sub, self.post_body, app_data.history_len)
            if app_data.app_type == AppType.FLOW:
                # 需要执行Flow
                is_flow = True
            else:
                # Agent 应用
                is_flow = False
            # 需要执行Flow
            self.task = await push_init_message(self.task, self.queue, app_data.history_len, is_flow=is_flow)
            # 组装上下文
            executor_background = ExecutorBackground(
                conversation=context,
                facts=facts,
            )
            # 启动监控任务和主任务
            main_task = asyncio.create_task(self.run_executor(self.queue, self.post_body, executor_background))
        # 等待任一任务完成
        done, pending = await asyncio.wait(
            [main_task, monitor],
            return_when=asyncio.FIRST_COMPLETED,
        )

        # 如果是监控任务触发，终止主任务
        if kill_event.is_set():
            logger.warning("[Scheduler] 用户活动状态检测不活跃，正在终止工作流执行...")
            main_task.cancel()
            if self.task.state.executorStatus in [ExecutorStatus.RUNNING, ExecutorStatus.WAITING]:
                self.task.state.executorStatus = ExecutorStatus.CANCELLED
            try:
                await main_task
                logger.info("[Scheduler] 工作流执行已被终止")
            except Exception:
                logger.exception("[Scheduler] 终止工作流时发生错误")

        # 更新Task，发送结束消息
        logger.info("[Scheduler] 发送结束消息")
        await self.queue.push_output(self.task, event_type=EventType.DONE.value, data={})
        # 关闭Queue
        await self.queue.close()

        return

    async def run_executor(
            self, queue: MessageQueue, post_body: RequestData, background: ExecutorBackground,
    ) -> None:
        """构造Executor并执行"""
        # 获取agent信息
        app_collection = MongoDB().get_collection("app")
        app_metadata = AppPool.model_validate(await app_collection.find_one({"_id": app_info.app_id}))
        if not app_metadata:
            logger.error("[Scheduler] 未找到Agent应用")
            return

        if app_metadata.app_type == AppType.FLOW.value:
            logger.info("[Scheduler] 获取工作流元数据")
            flow_info = await Pool().get_flow_metadata(app_info.app_id)

            # 如果flow_info为空，则直接返回
            if not flow_info:
                logger.error("[Scheduler] 未找到工作流元数据")
                return

            # 如果用户选了特定的Flow
            if app_info.flow_id:
                logger.info("[Scheduler] 获取工作流定义")
                flow_id = app_info.flow_id
                flow_data = await Pool().get_flow(app_info.app_id, flow_id)
            else:
                # 如果用户没有选特定的Flow，则根据语义选择一个Flow
                logger.info("[Scheduler] 选择最合适的流")
                flow_chooser = FlowChooser(self.task, post_body.question, app_info)
                flow_id = await flow_chooser.get_top_flow()
                self.task = flow_chooser.task
                logger.info("[Scheduler] 获取工作流定义")
                flow_data = await Pool().get_flow(app_info.app_id, flow_id)

            # 如果flow_data为空，则直接返回
            if not flow_data:
                logger.error("[Scheduler] 未找到工作流定义")
                return

            # 初始化Executor
            logger.info("[Scheduler] 初始化Executor")

            flow_exec = FlowExecutor(
                flow_id=flow_id,
                flow=flow_data,
                task=self.task,
                msg_queue=queue,
                question=post_body.question,
                post_body_app=app_info,
                background=background,
            )

            # 开始运行
            logger.info("[Scheduler] 运行Executor")
            await flow_exec.init()
            await flow_exec.run()
            self.task = flow_exec.task
        elif app_metadata.app_type == AppType.AGENT.value:
            # 初始化Executor
            agent_exec = MCPAgentExecutor(
                task=self.task,
                msg_queue=queue,
                question=post_body.question,
                history_len=app_metadata.history_len,
                background=background,
                agent_id=app_info.app_id,
                params=post_body.params,
            )
            # 开始运行
            logger.info("[Scheduler] 运行Executor")
            await agent_exec.run()
            self.task = agent_exec.task
        else:
            logger.error("[Scheduler] 无效的应用类型")

        return
