# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""获取和保存Task信息到数据库"""

import logging
import uuid

from sqlalchemy import and_, delete, select, update

from apps.common.postgres import postgres
from apps.models.conversation import Conversation
from apps.models.task import ExecutorCheckpoint, ExecutorHistory, Task, TaskRuntime
from apps.schemas.request_data import RequestData

logger = logging.getLogger(__name__)


class TaskManager:
    """从数据库中获取任务信息"""

    @staticmethod
    async def get_task_by_conversation_id(conversation_id: uuid.UUID, user_sub: str) -> Task:
        """获取对话ID的最后一个任务"""
        async with postgres.session() as session:
            # 检查user_sub是否匹配Conversation
            conversation = (await session.scalars(
                select(Conversation.id).where(
                    and_(
                        Conversation.id == conversation_id,
                        Conversation.userSub == user_sub,
                    ),
                ),
            )).one_or_none()
            if not conversation:
                err = f"对话不存在或无权访问: {conversation_id}"
                raise RuntimeError(err)

            task = (await session.scalars(
                select(Task).where(Task.conversationId == conversation_id).order_by(Task.updatedAt.desc()).limit(1),
            )).one_or_none()
            if not task:
                # 任务不存在，新建Task
                return Task(
                    conversationId=conversation_id,
                    userSub=user_sub,
                )
            logger.info("[TaskManager] 新建任务 %s", task.id)
            return task


    @staticmethod
    async def get_task_by_task_id(task_id: uuid.UUID) -> Task | None:
        """根据task_id获取任务"""
        async with postgres.session() as session:
            return (await session.scalars(
                select(Task).where(Task.id == task_id),
            )).one_or_none()


    @staticmethod
    async def get_task_runtime_by_task_id(task_id: uuid.UUID) -> TaskRuntime | None:
        """根据task_id获取任务运行时"""
        async with postgres.session() as session:
            return (await session.scalars(
                select(TaskRuntime).where(TaskRuntime.taskId == task_id),
            )).one_or_none()


    @staticmethod
    async def get_task_state_by_task_id(task_id: uuid.UUID) -> ExecutorCheckpoint | None:
        """根据task_id获取任务状态"""
        async with postgres.session() as session:
            return (await session.scalars(
                select(ExecutorCheckpoint).where(ExecutorCheckpoint.taskId == task_id),
            )).one_or_none()


    @staticmethod
    async def get_context_by_task_id(task_id: uuid.UUID, length: int | None = None) -> list[ExecutorHistory]:
        """根据task_id获取flow信息"""
        async with postgres.session() as session:
            return list((await session.scalars(
                select(ExecutorHistory).where(
                    ExecutorHistory.taskId == task_id,
                ).order_by(ExecutorHistory.updatedAt.desc()).limit(length),
            )).all())


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
    async def save_flow_context(task_id: str, flow_context: list[ExecutorHistory]) -> None:
        """保存flow信息到flow_context"""
        if not flow_context:
            return

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
    async def delete_task_by_task_id(task_id: uuid.UUID) -> None:
        """通过task_id删除Task信息"""
        async with postgres.session() as session:
            task = (await session.scalars(
                select(Task).where(Task.id == task_id),
            )).one_or_none()
            if task:
                await session.delete(task)


    @staticmethod
    async def delete_tasks_by_conversation_id(conversation_id: uuid.UUID) -> list[uuid.UUID]:
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
    async def save_task(cls, task_id: uuid.UUID, task: Task) -> None:
        """保存任务块"""
        task_collection = MongoDB().get_collection("task")

        # 更新已有的Task记录
        await task_collection.update_one(
            {"_id": task_id},
            {"$set": task.model_dump(by_alias=True, exclude_none=True)},
            upsert=True,
        )


    @classmethod
    async def update_task_token(
        cls,
        task_id: uuid.UUID,
        input_token: int,
        output_token: int,
        *,
        override: bool = False,
    ) -> tuple[int, int]:
        """更新任务的Token"""
        async with postgres.session() as session:
            sql = select(TaskRuntime.inputToken, TaskRuntime.outputToken).where(TaskRuntime.taskId == task_id)
            row = (await session.execute(sql)).one()

            if override:
                new_input_token = input_token
                new_output_token = output_token
            else:
                new_input_token = row.inputToken + input_token
                new_output_token = row.outputToken + output_token

            sql = update(TaskRuntime).where(TaskRuntime.taskId == task_id).values(
                inputToken=new_input_token, outputToken=new_output_token,
            )
            await session.execute(sql)
            await session.commit()
            return new_input_token, new_output_token
