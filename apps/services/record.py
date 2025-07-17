# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""问答对Manager"""

import logging
from typing import Literal

from apps.schemas.record import Record

logger = logging.getLogger(__name__)


class RecordManager:
    """问答对相关操作"""

    @staticmethod
    async def create_record_group(group_id: str, user_sub: str, conversation_id: str, task_id: str) -> str | None:
        """创建问答组"""
        mongo = MongoDB()
        record_group_collection = mongo.get_collection("record_group")
        conversation_collection = mongo.get_collection("conversation")
        record_group = RecordGroup(
            _id=group_id,
            user_sub=user_sub,
            conversation_id=conversation_id,
            task_id=task_id,
        )

        try:
            async with mongo.get_session() as session, await session.start_transaction():
                # RecordGroup里面加一条记录
                await record_group_collection.insert_one(record_group.model_dump(by_alias=True), session=session)
                # Conversation里面加一个ID
                await conversation_collection.update_one(
                    {"_id": conversation_id}, {"$push": {"record_groups": group_id}}, session=session,
                )
        except Exception:
            logger.exception("[RecordManager] 创建问答组失败")
            return None

        return group_id

    @staticmethod
    async def insert_record_data_into_record_group(user_sub: str, group_id: str, record: Record) -> str | None:
        """加密问答对，并插入MongoDB中的特定问答组"""
        mongo = MongoDB()
        group_collection = mongo.get_collection("record_group")
        try:
            await group_collection.update_one(
                {"_id": group_id, "user_sub": user_sub},
                {"$push": {"records": record.model_dump(by_alias=True)}},
            )
        except Exception:
            logger.exception("[RecordManager] 插入加密问答对失败")
            return None
        else:
            return record.id

    @staticmethod
    async def query_record_by_conversation_id(
        user_sub: str,
        conversation_id: str,
        total_pairs: int | None = None,
        order: Literal["desc", "asc"] = "desc",
    ) -> list[Record]:
        """
        查询ConversationID的最后n条问答对

        每个record_group只取最后一条record
        """
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

    @staticmethod
    async def query_record_group_by_conversation_id(
        conversation_id: str, total_pairs: int | None = None,
    ) -> list[RecordGroup]:
        """
        查询对话ID的最后n条问答组

        包含全部record_group及其关联的record
        """
        record_group_collection = MongoDB().get_collection("record_group")
        try:
            pipeline = [
                {"$match": {"conversation_id": conversation_id}},
                {"$sort": {"created_at": -1}},
            ]
            if total_pairs is not None:
                pipeline.append({"$limit": total_pairs})

            records = await record_group_collection.aggregate(pipeline)
            return [RecordGroup.model_validate(record) async for record in records]
        except Exception:
            logger.exception("[RecordManager] 查询问答组失败")
            return []
