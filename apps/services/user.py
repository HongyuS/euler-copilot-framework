# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""用户 Manager"""

import logging
from datetime import UTC, datetime

from sqlalchemy import func, select

from apps.common.postgres import postgres
from apps.models.user import User
from apps.schemas.request_data import UserUpdateRequest

from .conversation import ConversationManager

logger = logging.getLogger(__name__)


class UserManager:
    """用户相关操作"""

    @staticmethod
    async def list_user(n: int = 10, page: int = 1) -> tuple[list[User], int]:
        """
        获取所有用户

        :param n: 每页数量
        :param page: 页码
        :return: 所有用户列表
        """
        async with postgres.session() as session:
            count = await session.scalar(select(func.count(User.id)))
            users = (await session.scalars(select(User).offset((page - 1) * n).limit(n))).all()
            return list(users), count or 0


    @staticmethod
    async def get_user(user_sub: str) -> User | None:
        """
        根据用户sub获取用户信息

        :param user_sub: 用户sub
        :return: 用户信息
        """
        async with postgres.session() as session:
            return (
                await session.scalars(select(User).where(User.userSub == user_sub))
            ).one_or_none()


    @staticmethod
    async def update_user(user_sub: str, data: UserUpdateRequest) -> None:
        """
        根据用户sub更新用户信息

        :param user_sub: 用户sub
        :param data: 更新数据
        """
        # 将 Pydantic 模型转换为字典
        update_data = data.model_dump(exclude_unset=True, exclude_none=True)

        async with postgres.session() as session:
            user = (
                await session.scalars(select(User).where(User.userSub == user_sub))
            ).one_or_none()
            if not user:
                user = User(
                    userSub=user_sub,
                    isActive=True,
                    isWhitelisted=False,
                    credit=0,
                )
                await session.merge(user)
                await session.commit()
                return

            # 更新指定字段
            for key, value in update_data.items():
                if hasattr(user, key) and value is not None:
                    setattr(user, key, value)

            user.lastLogin = datetime.now(tz=UTC)
            await session.commit()

    @staticmethod
    async def update_userinfo_by_user_sub(user_sub: str, data: UserUpdateRequest) -> None:
        """
        根据用户sub更新用户信息（兼容旧接口）

        :param user_sub: 用户sub
        :param data: 更新数据
        """
        await UserManager.update_user(user_sub, data)

    @staticmethod
    async def delete_user(user_sub: str) -> None:
        """
        根据用户sub删除用户信息

        :param user_sub: 用户sub
        """
        async with postgres.session() as session:
            user = (
                await session.scalars(select(User).where(User.userSub == user_sub))
            ).one_or_none()
            if not user:
                return

            await session.delete(user)
            await session.commit()

            await ConversationManager.delete_conversation_by_user_sub(user_sub)
