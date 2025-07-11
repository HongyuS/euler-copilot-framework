# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""用户 Manager"""

import logging
from datetime import UTC, datetime

from apps.entities.collection import User
from apps.manager.conversation import ConversationManager
from apps.models.mongo import MongoDB

logger = logging.getLogger(__name__)


class UserManager:
    """用户相关操作"""

    @staticmethod
    async def add_userinfo(user_sub: str) -> None:
        """
        向数据库中添加用户信息

        :param user_sub: 用户sub
        """
        mongo = MongoDB()
        user_collection = mongo.get_collection("user")
        await user_collection.insert_one(User(
            _id=user_sub,
        ).model_dump(by_alias=True))

    @staticmethod
    async def get_all_user_sub() -> list[str]:
        """
        获取所有用户的sub

        :return: 所有用户的sub列表
        """
        mongo = MongoDB()
        user_collection = mongo.get_collection("user")
        return [user["_id"] async for user in user_collection.find({}, {"_id": 1})]

    @staticmethod
    async def get_userinfo_by_user_sub(user_sub: str) -> User | None:
        """
        根据用户sub获取用户信息

        :param user_sub: 用户sub
        :return: 用户信息
        """
        mongo = MongoDB()
        user_collection = mongo.get_collection("user")
        user_data = await user_collection.find_one({"_id": user_sub})
        return User(**user_data) if user_data else None

    @staticmethod
    async def update_userinfo_by_user_sub(user_sub: str, *, refresh_revision: bool = False) -> bool:
        """
        根据用户sub更新用户信息

        :param user_sub: 用户sub
        :param refresh_revision: 是否刷新revision
        :return: 更新后的用户信息
        """
        mongo = MongoDB()
        user_data = await UserManager.get_userinfo_by_user_sub(user_sub)
        if not user_data:
            await UserManager.add_userinfo(user_sub)
            return True

        update_dict = {
            "$set": {"login_time": round(datetime.now(UTC).timestamp(), 3)},
        }

        if refresh_revision:
            update_dict["$set"]["status"] = "init"  # type: ignore[assignment]
        user_collection = mongo.get_collection("user")
        result = await user_collection.update_one({"_id": user_sub}, update_dict)
        return result.modified_count > 0

    @staticmethod
    async def query_userinfo_by_login_time(login_time: float) -> list[str]:
        """
        根据登录时间获取用户sub

        :param login_time: 登录时间
        :return: 用户sub列表
        """
        mongo = MongoDB()
        user_collection = mongo.get_collection("user")
        return [user["_id"] async for user in user_collection.find({"login_time": {"$lt": login_time}}, {"_id": 1})]

    @staticmethod
    async def delete_userinfo_by_user_sub(user_sub: str) -> None:
        """
        根据用户sub删除用户信息

        :param user_sub: 用户sub
        """
        mongo = MongoDB()
        user_collection = mongo.get_collection("user")
        result = await user_collection.find_one_and_delete({"_id": user_sub})
        if not result:
            return
        result = User.model_validate(result)

        for conv_id in result.conversations:
            await ConversationManager.delete_conversation_by_conversation_id(user_sub, conv_id)
