# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""用户画像管理"""

import logging

from sqlalchemy import and_, select

from apps.common.postgres import postgres
from apps.models import Tag, UserTag
from apps.schemas.tag import UserTagInfo

logger = logging.getLogger(__name__)


class UserTagManager:
    """用户画像管理"""

    @staticmethod
    async def get_user_domain_by_user_sub_and_topk(user_sub: str, topk: int | None = None) -> list[UserTagInfo]:
        """根据用户ID，查询用户最常涉及的n个领域"""
        async with postgres.session() as session:
            query = select(UserTag).where(UserTag.userSub == user_sub).order_by(UserTag.count.desc())

            if topk is not None:
                query = query.limit(topk)

            user_domains = (await session.scalars(query)).all()

            result = []
            for user_domain in user_domains:
                tag = (await session.scalars(select(Tag).where(Tag.id == user_domain.tag))).one_or_none()
                if tag:
                    result.append(UserTagInfo(name=tag.name, count=user_domain.count))
            return result


    @staticmethod
    async def update_user_domain_by_user_sub_and_domain_name(user_sub: str, domain_name: str) -> None:
        """增加特定用户特定领域的频次"""
        async with postgres.session() as session:
            tag = (
                await session.scalars(
                    select(Tag).where(Tag.name == domain_name),
                )
            ).one_or_none()
            if not tag:
                err = f"[UserTagManager] Tag {domain_name} not found"
                logger.error(err)
                raise ValueError(err)

            user_domain = (
                await session.scalars(
                    select(UserTag).where(
                        and_(
                            UserTag.userSub == user_sub,
                            UserTag.tag == tag.id,
                        ),
                    ),
                )
            ).one_or_none()

            if not user_domain:
                user_domain = UserTag(userSub=user_sub, tag=tag.id, count=1)
                await session.merge(user_domain)
            else:
                user_domain.count += 1
            await session.commit()
