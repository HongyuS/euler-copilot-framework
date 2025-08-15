# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Scheduler模块"""

import asyncio
import logging
import uuid

from apps.common.config import config
from apps.common.queue import MessageQueue
from apps.llm.patterns.rewrite import QuestionRewrite
from apps.llm.reasoning import ReasoningLLM
from apps.models.llm import LLMData
from apps.models.task import Task
from apps.scheduler.executor.agent import MCPAgentExecutor
from apps.scheduler.executor.flow import FlowExecutor
from apps.scheduler.pool.pool import Pool
from apps.scheduler.scheduler.context import get_context, get_docs
from apps.scheduler.scheduler.flow import FlowChooser
from apps.scheduler.scheduler.message import (
    push_init_message,
    push_rag_message,
)
from apps.schemas.config import LLMConfig
from apps.schemas.enum_var import AppType, EventType, ExecutorStatus
from apps.schemas.rag_data import RAGQueryReq
from apps.schemas.request_data import RequestData
from apps.schemas.scheduler import ExecutorBackground
from apps.services.activity import Activity
from apps.services.appcenter import AppCenterManager
from apps.services.knowledge import KnowledgeBaseManager
from apps.services.llm import LLMManager
from apps.services.task import TaskManager

logger = logging.getLogger(__name__)


class Scheduler:
    """
    “调度器”，是最顶层的、控制Executor执行顺序和状态的逻辑。

    Scheduler包含一个“SchedulerContext”，作用为多个Executor的“聊天会话”
    """

    async def init(self, task_id: uuid.UUID, queue: MessageQueue, post_body: RequestData) -> None:
        """初始化"""
        self.used_docs = []
        self.task_id = task_id
        self.queue = queue
        self.post_body = post_body


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


    async def get_chat_llm(self, llm_id: uuid.UUID) -> LLMData:
        """获取RAG大模型"""
        # 获取当前会话使用的大模型
        llm = await LLMManager.get_llm(llm_id)
        if not llm:
            err = "[Scheduler] 获取大模型ID失败"
            logger.error(err)
            raise ValueError(err)
        return llm


    async def run(self) -> None:
        """运行调度器"""
        task = await TaskManager.get_task_by_conversation_id(self.task_id)
        if not task:
            task = Task(
                id=self.task_id,
                ids=TaskIds(
                    user_sub=self.post_body.user_sub,
                    conversation_id=self.task_id,
                ),
            )
        try:
            # 获取当前问答可供关联的文档
            docs, doc_ids = await get_docs(self.post_body)
        except Exception:
            logger.exception("[Scheduler] 获取文档失败")
            await self.queue.close()
            return
        history, _ = await get_context(self.task.ids.user_sub, self.post_body, 3)

        # 如果是智能问答，直接执行
        logger.info("[Scheduler] 开始执行")
        # 创建用于通信的事件
        kill_event = asyncio.Event()
        monitor = asyncio.create_task(self._monitor_activity(kill_event, self.task.ids.user_sub))
        rag_method = True
        if self.post_body.app and self.post_body.app.app_id:
            rag_method = False
        if self.task.state.app_id:
            rag_method = False
        if rag_method:
            llm = await self.get_chat_llm()
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
            need_change_cancel_flow_state = [ExecutorStatus.RUNNING, ExecutorStatus.WAITING]
            if self.task.state.flow_status in need_change_cancel_flow_state:
                self.task.state.flow_status = ExecutorStatus.CANCELLED
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
        # 读取App信息
        app_info = post_body.app
        if not app_info:
            logger.error("[Scheduler] 未使用应用中心功能！")
            return
        # 获取agent信息
        app_collection = MongoDB().get_collection("app")
        app_metadata = AppPool.model_validate(await app_collection.find_one({"_id": app_info.app_id}))
        if not app_metadata:
            logger.error("[Scheduler] 未找到Agent应用")
            return
        llm = await LLMManager.get_llm(app_metadata.llm_id)
        if not llm:
            logger.error("[Scheduler] 获取大模型失败")
            await self.queue.close()
            return
        reasion_llm = ReasoningLLM(
            LLMConfig(
                endpoint=llm.openai_base_url,
                key=llm.openai_api_key,
                model=llm.model_name,
                max_tokens=llm.max_tokens,
            ),
        )
        if background.conversation and self.task.state.flow_status == ExecutorStatus.INIT:
            try:
                question_obj = QuestionRewrite()
                post_body.question = await question_obj.generate(
                    history=background.conversation, question=post_body.question, llm=reasion_llm,
                )
            except Exception:
                logger.exception("[Scheduler] 问题重写失败")
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
