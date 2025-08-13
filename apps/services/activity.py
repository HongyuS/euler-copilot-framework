# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""用户限流"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select

from apps.common.postgres import postgres
from apps.constants import SLIDE_WINDOW_QUESTION_COUNT, SLIDE_WINDOW_TIME
from apps.exceptions import ActivityError
from apps.models.session import SessionActivity


class Activity:
    """用户活动控制，限制单用户同一时间只能提问一个问题"""

    # TODO：改为同一时间整个系统最多有n个task在执行，与用户无关
    @staticmethod
    async def is_active(user_sub: str) -> bool:
        """
        判断当前用户是否正在提问（占用GPU资源）

        :param user_sub: 用户实体ID
        :return: 判断结果，正在提问则返回True
        """
        time = datetime.now(tz=UTC)

        async with postgres.session() as session:
            # 检查窗口内总请求数
            count = (await session.scalars(select(func.count(SessionActivity.id)).where(
                SessionActivity.timestamp >= time - timedelta(seconds=SLIDE_WINDOW_TIME),
                SessionActivity.timestamp <= time,
            ))).one()
            if count >= SLIDE_WINDOW_QUESTION_COUNT:
                return True

            # 检查用户是否正在提问
            active = (await session.scalars(select(SessionActivity).where(
                SessionActivity.userSub == user_sub,
            ))).one_or_none()
            return bool(active)

    @staticmethod
    async def set_active(user_sub: str) -> None:
        """设置用户的活跃标识"""
        time = datetime.now(UTC)
        # 设置用户活跃状态
        async with postgres.session() as session:
            active = (
                await session.scalars(select(SessionActivity).where(SessionActivity.userSub == user_sub))
            ).one_or_none()
            if active:
                err = "用户正在提问"
                raise ActivityError(err)
            await session.merge(SessionActivity(userSub=user_sub, timestamp=time))
            await session.commit()


    @staticmethod
    async def remove_active(user_sub: str) -> None:
        """
        清除用户的活跃标识，释放GPU资源

        :param user_sub: 用户实体ID
        """
        # 清除用户当前活动标识
        async with postgres.session() as session:
            await session.execute(
                delete(SessionActivity).where(SessionActivity.userSub == user_sub),
            )
            await session.commit()
