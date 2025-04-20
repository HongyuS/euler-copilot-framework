"""
Scheduler模块

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

import asyncio
import logging

from apps.common.queue import MessageQueue
from apps.entities.enum_var import EventType, StepStatus
from apps.entities.rag_data import RAGQueryReq
from apps.entities.request_data import RequestData
from apps.entities.scheduler import ExecutorBackground
from apps.entities.task import Task
from apps.manager.appcenter import AppCenterManager
from apps.manager.flow import FlowManager
from apps.manager.task import TaskManager
from apps.manager.user import UserManager
from apps.scheduler.executor.flow import FlowExecutor
from apps.scheduler.pool.pool import Pool
from apps.scheduler.scheduler.context import get_context, get_docs
from apps.scheduler.scheduler.flow import FlowChooser
from apps.scheduler.scheduler.message import (
    push_document_message,
    push_init_message,
    push_rag_message,
)

logger = logging.getLogger(__name__)


class Scheduler:
    """
    “调度器”，是最顶层的、控制Executor执行顺序和状态的逻辑。

    Scheduler包含一个“SchedulerContext”，作用为多个Executor的“聊天会话”
    """

    def __init__(self, task_id: str, queue: MessageQueue, post_body: RequestData) -> None:
        """初始化"""
        self.used_docs = []
        self.task_id = task_id

        self.queue = queue
        self.post_body = post_body


    async def run(self) -> None:
        """运行调度器"""
        task = await TaskManager.get_task(self.task_id)
        try:
            # 获取当前问答可供关联的文档
            docs, doc_ids = await get_docs(task.ids.user_sub, self.post_body)
        except Exception:
            logger.exception("[Scheduler] 获取文档失败")
            await self.queue.close()
            return

        # 获取用户配置的kb_sn
        user_info = await UserManager.get_userinfo_by_user_sub(task.ids.user_sub)
        if not user_info:
            logger.error("[Scheduler] 未找到用户")
            await self.queue.close()
            return

        # 已使用文档
        self.used_docs = []

        # 如果是智能问答，直接执行
        logger.info("[Scheduler] 开始执行")
        if not self.post_body.app or self.post_body.app.app_id == "":
            task = await push_init_message(task, self.queue, 3, is_flow=False)
            await asyncio.sleep(0.1)
            for doc in docs:
                # 保存使用的文件ID
                self.used_docs.append(doc.id)
                task = await push_document_message(task, self.queue, doc)
                await asyncio.sleep(0.1)

            # 调用RAG
            logger.info("[Scheduler] 获取上下文")
            history, _ = await get_context(task.ids.user_sub, self.post_body, 3)
            logger.info("[Scheduler] 调用RAG")
            rag_data = RAGQueryReq(
                question=self.post_body.question,
                language=self.post_body.language,
                document_ids=doc_ids,
                kb_sn=None if not user_info.kb_id else user_info.kb_id,
                top_k=5,
                history=history,
            )
            task = await push_rag_message(task, self.queue, task.ids.user_sub, rag_data)
        else:
            # 查找对应的App元数据
            app_data = await AppCenterManager.fetch_app_data_by_id(self.post_body.app.app_id)
            if not app_data:
                logger.error("[Scheduler] App %s 不存在", self.post_body.app.app_id)
                await self.queue.close()
                return

            # 获取上下文
            context, facts = await get_context(task.ids.user_sub, self.post_body, app_data.history_len)

            # 需要执行Flow
            task = await push_init_message(task, self.queue, app_data.history_len, is_flow=True)
            # 组装上下文
            executor_background = ExecutorBackground(
                conversation=context,
                facts=facts,
            )
            await self.run_executor(task, self.queue, self.post_body, executor_background)

        # 更新Task，发送结束消息
        logger.info("[Scheduler] 发送结束消息")
        await TaskManager.save_task(task.id, task)
        await self.queue.push_output(task, event_type=EventType.DONE.value, data={})
        # 关闭Queue
        await self.queue.close()

        return

    async def run_executor(
        self, task: Task, queue: MessageQueue, post_body: RequestData, background: ExecutorBackground,
    ) -> None:
        """构造FlowExecutor，并执行所选择的流"""
        # 读取App中所有Flow的信息
        app_info = post_body.app
        if not app_info:
            logger.error("[Scheduler] 未使用工作流功能！")
            return
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
            flow_chooser = FlowChooser(task.id, post_body.question, app_info)
            flow_id = await flow_chooser.get_top_flow()
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
            task=task,
            msg_queue=queue,
            question=post_body.question,
            post_body_app=app_info,
            background=background,
        )

        # 开始运行
        logger.info("[Scheduler] 运行Executor")
        await flow_exec.load_state()
        await flow_exec.run()

        # 更新Task
        task = await TaskManager.get_task(task.id)
        # 如果状态正常，则更新Flow的debug状态
        return
