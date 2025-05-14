"""
对话 Manager

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from apps.entities.collection import Conversation
from apps.manager.task import TaskManager
from apps.models.mongo import MongoDB

logger = logging.getLogger(__name__)


class ConversationManager:
    """对话管理器"""

    @staticmethod
    async def get_conversation_by_user_sub(user_sub: str) -> list[Conversation]:
        """根据用户ID获取对话列表，按时间由近到远排序"""
        try:
            conv_collection = MongoDB().get_collection("conversation")
            return [
                Conversation(**conv)
                async for conv in conv_collection.find({"user_sub": user_sub, "debug": False}).sort({"created_at": 1})
            ]
        except Exception:
            logger.exception("[ConversationManager] 通过用户ID获取对话失败")
        return []

    @staticmethod
    async def get_conversation_by_conversation_id(user_sub: str, conversation_id: str) -> Conversation | None:
        """通过ConversationID查询对话信息"""
        try:
            conv_collection = MongoDB().get_collection("conversation")
            result = await conv_collection.find_one({"_id": conversation_id, "user_sub": user_sub})
            if not result:
                return None
            return Conversation.model_validate(result)
        except Exception:
            logger.exception("[ConversationManager] 通过ConversationID获取对话失败")
            return None

    @staticmethod
    async def add_conversation_by_user_sub(user_sub: str, app_id: str, *, debug: bool) -> Conversation | None:
        """通过用户ID新建对话"""
        conversation_id = str(uuid.uuid4())
        conv = Conversation(
            _id=conversation_id,
            user_sub=user_sub,
            app_id=app_id,
            debug=debug if debug else False,
        )
        mongo = MongoDB()
        try:
            async with mongo.get_session() as session, await session.start_transaction():
                conv_collection = mongo.get_collection("conversation")
                await conv_collection.insert_one(conv.model_dump(by_alias=True), session=session)
                user_collection = mongo.get_collection("user")
                update_data: dict[str, dict[str, Any]] = {
                    "$push": {"conversations": conversation_id},
                }
                if app_id:
                    # 非调试模式下更新应用使用情况
                    if not debug:
                        update_data["$set"] = {
                            f"app_usage.{app_id}.last_used": round(datetime.now(UTC).timestamp(), 3),
                        }
                        update_data["$inc"] = {f"app_usage.{app_id}.count": 1}
                    await user_collection.update_one(
                        {"_id": user_sub},
                        update_data,
                        session=session,
                    )
                    await session.commit_transaction()
                return conv
        except Exception:
            logger.exception("[ConversationManager] 新建对话失败")
            return None

    @staticmethod
    async def update_conversation_by_conversation_id(user_sub: str, conversation_id: str, data: dict[str, Any]) -> bool:
        """通过ConversationID更新对话信息"""
        try:
            conv_collection = MongoDB().get_collection("conversation")
            result = await conv_collection.update_one(
                {"_id": conversation_id, "user_sub": user_sub},
                {"$set": data},
            )
        except Exception:
            logger.exception("[ConversationManager] 更新对话失败")
            return False
        else:
            return result.modified_count > 0

    @staticmethod
    async def delete_conversation_by_conversation_id(user_sub: str, conversation_id: str) -> bool:
        """通过ConversationID删除对话"""
        mongo = MongoDB()
        user_collection = mongo.get_collection("user")
        conv_collection = mongo.get_collection("conversation")
        record_group_collection = mongo.get_collection("record_group")
        try:
            async with mongo.get_session() as session, await session.start_transaction():
                conversation_data = await conv_collection.find_one_and_delete(
                    {"_id": conversation_id, "user_sub": user_sub}, session=session,
                )
                if not conversation_data:
                    return False

                await user_collection.update_one(
                    {"_id": user_sub}, {"$pull": {"conversations": conversation_id}}, session=session,
                )
                await record_group_collection.delete_many({"conversation_id": conversation_id}, session=session)
                await session.commit_transaction()
        except Exception:
            logger.exception("[ConversationManager] 删除对话失败")
            return False
        else:
            await TaskManager.delete_tasks_by_conversation_id(conversation_id)
            return True
