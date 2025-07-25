# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""用户 Manager"""

import logging
from datetime import datetime

import pytz
from sqlalchemy import select

from apps.common.postgres import postgres
from apps.models.user import User

from .conversation import ConversationManager

logger = logging.getLogger(__name__)


class UserManager:
    """用户相关操作"""

    @staticmethod
    async def list_user(n: int = 10, page: int = 1) -> list[User]:
        """
        获取所有用户

        :param n: 每页数量
        :param page: 页码
        :return: 所有用户列表
        """
        async with postgres.session() as session:
            users = (await session.scalars(select(User).offset((page - 1) * n).limit(n))).all()
            return list(users)


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
    async def update_user(user_sub: str) -> None:
        """
        根据用户sub更新用户信息

        :param user_sub: 用户sub
        """
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
                session.add(user)
                await session.commit()
                return

            user.lastLogin = datetime.now(tz=pytz.timezone("Asia/Shanghai"))
            await session.commit()

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
