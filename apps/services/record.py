# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""问答对Manager"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import and_, select

from apps.common.postgres import postgres
from apps.models.conversation import Conversation
from apps.models.record import Record as PgRecord
from apps.schemas.record import Record

logger = logging.getLogger(__name__)


class RecordManager:
    """问答对相关操作"""

    @staticmethod
    async def verify_record_in_conversation(record_id: uuid.UUID, user_sub: str, conversation_id: uuid.UUID) -> bool:
        """
        校验指定record_id是否属于指定用户和会话（PostgreSQL实现）

        :param record_id: 记录ID
        :param user_sub: 用户sub
        :param conversation_id: 会话ID
        :return: 是否存在
        """
        async with postgres.session() as session:
            result = (await session.scalars(
                select(PgRecord).where(
                    and_(
                        PgRecord.id == record_id,
                        PgRecord.userSub == user_sub,
                        PgRecord.conversationId == conversation_id,
                    ),
            ))).one_or_none()
            return result is not None


    @staticmethod
    async def insert_record_data(user_sub: str, conversation_id: uuid.UUID, record: Record) -> uuid.UUID | None:
        """Record插入PostgreSQL"""
        async with postgres.session() as session:
            conv = (await session.scalars(
                select(Conversation).where(
                    and_(
                        Conversation.id == conversation_id,
                        Conversation.userSub == user_sub,
                    ),
                ),
            )).one_or_none()
            if not conv:
                logger.error("[RecordManager] 对话不存在: %s", conversation_id)
                return None

            session.add(PgRecord(
                id=record.id,
                conversationId=conversation_id,
                taskId=record.task_id,
                userSub=user_sub,
                content=record.content,
                key=record.key,
                createdAt=datetime.fromtimestamp(record.created_at, tz=UTC),
            ))
            await session.commit()

        return record.id


    @staticmethod
    async def query_record_by_conversation_id(
        user_sub: str,
        conversation_id: uuid.UUID,
        total_pairs: int | None = None,
        order: Literal["desc", "asc"] = "desc",
    ) -> list[Record]:
        """查询ConversationID的最后n条问答对"""
        sort_order = -1 if order == "desc" else 1

        mongo = MongoDB()
        record_group_collection = mongo.get_collection("record_group")
        try:
            # 得到conversation的全部record_group id
            record_groups = await record_group_collection.aggregate(
                [
                    {"$match": {"conversation_id": conversation_id, "user_sub": user_sub}},
                    {"$sort": {"created_at": sort_order}},
                    {"$project": {"_id": 1}},
                    {"$limit": total_pairs} if total_pairs is not None else {},
                ],
            )

            records = []
            async for record_group_id in record_groups:
                record = await record_group_collection.aggregate(
                    [
                        {"$match": {"_id": record_group_id["_id"]}},
                        {"$project": {"records": 1}},
                        {"$unwind": "$records"},
                        {"$sort": {"records.created_at": -1}},
                        {"$limit": 1},
                    ],
                )
                record = await record.to_list(length=1)
                if not record:
                    logger.info("[RecordManager] 问答组 %s 没有问答对", record_group_id)
                    continue

                records.append(Record.model_validate(record[0]["records"]))
        except Exception:
            logger.exception("[RecordManager] 查询加密问答对失败")
            return []
        else:
            return records
