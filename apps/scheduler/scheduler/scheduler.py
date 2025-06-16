# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Scheduler模块"""

import asyncio
import logging
from datetime import UTC, datetime

from apps.common.config import Config
from apps.common.queue import MessageQueue
from apps.entities.collection import LLM
from apps.entities.enum_var import AppType, EventType
from apps.entities.pool import AppPool
from apps.entities.rag_data import RAGQueryReq
from apps.entities.request_data import RequestData
from apps.entities.scheduler import ExecutorBackground
from apps.entities.task import Task
from apps.manager.appcenter import AppCenterManager
from apps.manager.knowledge import KnowledgeBaseManager
from apps.manager.llm import LLMManager
from apps.models.mongo import MongoDB
from apps.scheduler.executor.agent import MCPAgentExecutor
from apps.scheduler.executor.flow import FlowExecutor
from apps.scheduler.pool.pool import Pool
from apps.scheduler.scheduler.context import get_context, get_docs
from apps.scheduler.scheduler.flow import FlowChooser
from apps.scheduler.scheduler.message import (
    push_init_message,
    push_rag_message,
)

logger = logging.getLogger(__name__)


class Scheduler:
    """
    “调度器”，是最顶层的、控制Executor执行顺序和状态的逻辑。

    Scheduler包含一个“SchedulerContext”，作用为多个Executor的“聊天会话”
    """

    def __init__(self, task: Task, queue: MessageQueue, post_body: RequestData) -> None:
        """初始化"""
        self.used_docs = []
        self.task = task

        self.queue = queue
        self.post_body = post_body

    async def run(self) -> None:  # noqa: PLR0911
        """运行调度器"""
        try:
            # 获取当前会话使用的大模型
            llm_id = await LLMManager.get_llm_id_by_conversation_id(
                self.task.ids.user_sub, self.task.ids.conversation_id,
            )
            if not llm_id:
                logger.error("[Scheduler] 获取大模型ID失败")
                await self.queue.close()
                return
            if llm_id == "empty":
                llm = LLM(
                    _id="empty",
                    user_sub=self.task.ids.user_sub,
                    openai_base_url=Config().get_config().llm.endpoint,
                    openai_api_key=Config().get_config().llm.key,
                    model_name=Config().get_config().llm.model,
                    max_tokens=Config().get_config().llm.max_tokens,
                )
            else:
                llm = await LLMManager.get_llm_by_id(self.task.ids.user_sub, llm_id)
                if not llm:
                    logger.error("[Scheduler] 获取大模型失败")
                    await self.queue.close()
                    return
        except Exception:
            logger.exception("[Scheduler] 获取大模型失败")
            await self.queue.close()
            return
        try:
            # 获取当前会话使用的知识库
            kb_ids = await KnowledgeBaseManager.get_kb_ids_by_conversation_id(
                self.task.ids.user_sub, self.task.ids.conversation_id)
        except Exception:
            logger.exception("[Scheduler] 获取知识库ID失败")
            await self.queue.close()
            return
        try:
            # 获取当前问答可供关联的文档
            docs, doc_ids = await get_docs(self.task.ids.user_sub, self.post_body)
        except Exception:
            logger.exception("[Scheduler] 获取文档失败")
            await self.queue.close()
            return
        history, _ = await get_context(self.task.ids.user_sub, self.post_body, 3)
        # 已使用文档
        self.used_docs = []

        # 如果是智能问答，直接执行
        logger.info("[Scheduler] 开始执行")
        if not self.post_body.app or self.post_body.app.app_id == "":
            self.task = await push_init_message(self.task, self.queue, 3, is_flow=False)
            rag_data = RAGQueryReq(
                kbIds=kb_ids,
                query=self.post_body.question,
                tokensLimit=llm.max_tokens,
            )
            self.task = await push_rag_message(self.task, self.queue, self.task.ids.user_sub, llm, history, doc_ids, rag_data)
            self.task.tokens.full_time = round(datetime.now(UTC).timestamp(), 2) - self.task.tokens.time
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
            await self.run_executor(self.queue, self.post_body, executor_background)

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
            await flow_exec.load_state()
            await flow_exec.run()
            self.task = flow_exec.task
        elif app_metadata.app_type == AppType.AGENT.value:
            # 获取agent中对应的MCP server信息
            servers_id = app_metadata.mcp_service
            # 初始化Executor
            agent_exec = MCPAgentExecutor(
                task=self.task,
                msg_queue=queue,
                question=post_body.question,
                max_steps=app_metadata.history_len,
                servers_id=servers_id,
                background=background,
                agent_id=app_info.app_id,
            )
            # 开始运行
            logger.info("[Scheduler] 运行Executor")
            await agent_exec.run()
            self.task = agent_exec.task
        else:
            logger.error("[Scheduler] 无效的应用类型")

        return
