# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""用户资产库管理"""

import logging
import uuid
from typing import Any

import httpx
from fastapi import status
from sqlalchemy import select

from apps.common.config import config
from apps.common.postgres import postgres
from apps.models.user import User

from .session import SessionManager

logger = logging.getLogger(__name__)


class KnowledgeBaseManager:
    """用户资产库管理"""

    @staticmethod
    async def get_kb_list_from_rag(
        user_sub: str,
        kb_id: str | None = None,
        kb_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        从RAG获取知识库列表

        :param user_sub: 用户sub
        :param kb_id: 知识库ID
        :param kb_name: 知识库名称
        :return: 知识库列表
        """
        session_id = await SessionManager.get_session_by_user_sub(user_sub)
        url = config.rag.rag_service.rstrip("/")+"/kb"
        headers = {
            "Authorization": f"Bearer {session_id}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient() as client:
            data = {
                "kbName": kb_name,
            }
            if kb_id:
                data["kbId"] = kb_id
            resp = await client.get(url, headers=headers, params=data, timeout=30.0)
            resp_data = resp.json()
            if resp.status_code != status.HTTP_200_OK:
                return []
        return resp_data["result"]["teamKnowledgebases"]


    @staticmethod
    async def get_selected_kb(user_sub: str) -> list[uuid.UUID]:
        """
        获取当前用户的知识库ID

        :param user_sub: 用户sub
        :return: 知识库ID列表
        """
        async with postgres.session() as session:
            selected_kbs = (await session.scalars(
                select(User.selectedKB).where(User.userSub == user_sub),
            )).one_or_none()

            if not selected_kbs:
                logger.error("[KnowledgeBaseManager] 用户 %s 未选择知识库", user_sub)
                return []

            # 所有KB的列表在前端获取
            return selected_kbs


    @staticmethod
    async def save_selected_kb(user_sub: str, kb_ids: list[uuid.UUID]) -> None:
        """
        更新用户当前选择的知识库

        :param user_sub: 用户sub
        :param kb_list: 知识库列表
        :return: 是否更新成功
        """
        async with postgres.session() as session:
            user = (await session.scalars(
                select(User).where(User.userSub == user_sub),
            )).one_or_none()

            if not user:
                logger.error("[KnowledgeBaseManager]")
                return

            user.selectedKB = kb_ids
            await session.commit()
