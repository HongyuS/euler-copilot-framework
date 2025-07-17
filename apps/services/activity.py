# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""用户限流"""

import uuid
from datetime import datetime, timedelta

import pytz
from sqlalchemy import delete

from apps.common.postgres import postgres
from apps.constants import SLIDE_WINDOW_QUESTION_COUNT, SLIDE_WINDOW_TIME
from apps.exceptions import ActivityError
from apps.models.session import SessionActivity


class Activity:
    """用户活动控制，限制单用户同一时间只能提问一个问题"""

    @staticmethod
    async def is_active(user_sub: str) -> bool:
        """
        判断当前用户是否正在提问（占用GPU资源）

        :param user_sub: 用户实体ID
        :return: 判断结果，正在提问则返回True
        """
        time = datetime.now(pytz.timezone("Asia/Shanghai"))

        # 检查窗口内总请求数
        count = await MongoDB().get_collection("activity").count_documents(
            {"timestamp": {"$gte": time - SLIDE_WINDOW_TIME, "$lte": time}},
        )
        if count >= SLIDE_WINDOW_QUESTION_COUNT:
            return True

        # 检查用户是否正在提问
        active = await MongoDB().get_collection("activity").find_one(
            {"user_sub": user_sub},
        )
        return bool(active)

    @staticmethod
    async def set_active(user_sub: str) -> None:
        """设置用户的活跃标识"""
        time = round(datetime.now(UTC).timestamp(), 3)
        # 设置用户活跃状态
        collection = MongoDB().get_collection("activity")
        active = await collection.find_one({"user_sub": user_sub})
        if active:
            err = "用户正在提问"
            raise ActivityError(err)
        await collection.insert_one(
            {
                "_id": str(uuid.uuid4()),
                "user_sub": user_sub,
                "timestamp": time,
            },
        )

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
