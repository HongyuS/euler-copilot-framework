# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""获取和保存Task信息到数据库"""

import logging
import uuid

from sqlalchemy import delete, select

from apps.common.postgres import postgres
from apps.models.task import ExecutorCheckpoint, ExecutorHistory, Task
from apps.schemas.request_data import RequestData

from .record import RecordManager

logger = logging.getLogger(__name__)


class TaskManager:
    """从数据库中获取任务信息"""

    @staticmethod
    async def get_task_by_conversation_id(conversation_id: str) -> Task | None:
        """获取对话ID的最后一条问答组关联的任务"""
        # 查询对话ID的最后一条问答组
        last_group = await RecordManager.query_record_group_by_conversation_id(conversation_id, 1)
        if not last_group or len(last_group) == 0:
            logger.error("[TaskManager] 没有找到对话 %s 的问答组", conversation_id)
            # 空对话或无效对话，新建Task
            return None

        last_group = last_group[0]
        task_id = last_group.task_id

        # 查询最后一条问答组关联的任务
        task_collection = MongoDB().get_collection("task")
        task = await task_collection.find_one({"_id": task_id})
        if not task:
            # 任务不存在，新建Task
            logger.error("[TaskManager] 任务 %s 不存在", task_id)
            return None

        return Task.model_validate(task)


    @staticmethod
    async def get_task_by_task_id(task_id: uuid.UUID) -> Task | None:
        """根据task_id获取任务"""
        task_collection = MongoDB().get_collection("task")
        task = await task_collection.find_one({"_id": task_id})
        if not task:
            return None
        return Task.model_validate(task)


    @staticmethod
    async def get_context_by_task_id(task_id: str, length: int | None = None) -> list[FlowStepHistory]:
        """根据task_id获取flow信息"""
        async with postgres.session() as session:
            executor_history_collection = session.query(ExecutorHistory)

        flow_context = []
        try:
            async for history in flow_context_collection.find(
                {"task_id": task_id},
            ).sort(
                "created_at", -1,
            ).limit(length):
                for i in range(len(flow_context)):
                    flow_context.append(FlowStepHistory.model_validate(history))
        except Exception:
            logger.exception("[TaskManager] 获取task_id的flow信息失败")
            return []
        else:
            return flow_context


    @staticmethod
    async def init_new_task(
        user_sub: str,
        session_id: str | None = None,
        post_body: RequestData | None = None,
    ) -> Task:
        """获取任务块"""
        return Task(
            _id=str(uuid.uuid4()),
            ids=TaskIds(
                user_sub=user_sub if user_sub else "",
                session_id=session_id if session_id else "",
                conversation_id=post_body.conversation_id,
            ),
            question=post_body.question if post_body else "",
            tokens=TaskTokens(),
            runtime=TaskRuntime(),
        )

    @staticmethod
    async def save_flow_context(task_id: str, flow_context: list[FlowStepHistory]) -> None:
        """保存flow信息到flow_context"""
        flow_context_collection = MongoDB().get_collection("flow_context")
        try:
            for history in flow_context:
                # 查找是否存在
                current_context = await flow_context_collection.find_one({
                    "task_id": task_id,
                    "_id": history.id,
                })
                if current_context:
                    await flow_context_collection.update_one(
                        {"_id": current_context["_id"]},
                        {"$set": history.model_dump(exclude_none=True, by_alias=True)},
                    )
                else:
                    await flow_context_collection.insert_one(history.model_dump(exclude_none=True, by_alias=True))
        except Exception:
            logger.exception("[TaskManager] 保存flow执行记录失败")


    @staticmethod
    async def delete_task_by_task_id(task_id: str) -> None:
        """通过task_id删除Task信息"""
        async with postgres.session() as session:
            task = (await session.scalars(
                select(Task).where(Task.id == task_id),
            )).one_or_none()
            if task:
                await session.delete(task)


    @staticmethod
    async def delete_tasks_by_conversation_id(conversation_id: uuid.UUID) -> list[str]:
        """通过ConversationID删除Task信息"""
        async with postgres.session() as session:
            task_ids = []
            tasks = (await session.scalars(
                select(Task).where(Task.conversationId == conversation_id),
            )).all()
            for task in tasks:
                task_ids.append(str(task.id))
                await session.delete(task)
            await session.commit()
            return task_ids


    @staticmethod
    async def delete_task_history_checkpoint_by_conversation_id(conversation_id: uuid.UUID) -> None:
        """通过ConversationID删除Task信息"""
        # 删除Task
        task_ids = []
        async with postgres.session() as session:
            task = list((await session.scalars(
                select(Task).where(Task.conversationId == conversation_id),
            )).all())
            for item in task:
                task_ids.append(item.id)
                await session.delete(item)

            # 删除Task对应的State
            await session.execute(
                delete(ExecutorCheckpoint).where(ExecutorCheckpoint.taskId.in_(task_ids)),
            )
            await session.execute(
                delete(ExecutorHistory).where(ExecutorHistory.taskId.in_(task_ids)),
            )
            await session.commit()


    @classmethod
    async def save_task(cls, task_id: str, task: Task) -> None:
        """保存任务块"""
        task_collection = MongoDB().get_collection("task")

        # 更新已有的Task记录
        await task_collection.update_one(
            {"_id": task_id},
            {"$set": task.model_dump(by_alias=True, exclude_none=True)},
            upsert=True,
        )
