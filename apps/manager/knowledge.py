"""
用户资产库管理

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

import logging
import httpx
from fastapi import status
from typing import Any
from apps.models.mongo import MongoDB
from apps.common.config import Config
from apps.entities.collection import KnowledgeBaseItem
from apps.entities.response_data import KnowledgeBaseItem as KnowledgeBaseItemResponse, TeamKnowledgeBaseItem
from apps.manager.session import SessionManager
logger = logging.getLogger(__name__)


class KnowledgeBaseManager:
    """用户资产库管理"""
    @staticmethod
    async def get_kb_ids_by_conversation_id(user_sub: str, conversation_id: str) -> list[str]:
        """
        通过对话ID获取知识库ID
        :param user_sub: 用户ID
        :param conversation_id: 对话ID
        :return: 知识库ID列表
        """
        try:
            conv_collection = MongoDB().get_collection("conversation")
            result = await conv_collection.find_one({"_id": conversation_id, "user_sub": user_sub})
            if not result:
                err_msg = "[KnowledgeBaseManager] 获取知识库ID失败，未找到对话"
                logger.error(err_msg)
                return []
            kb_config_list = result.get("kb_list", [])
            kb_ids_used = [kb_config["kb_id"] for kb_config in kb_config_list]
            return kb_ids_used
        except Exception:
            logger.exception("[KnowledgeBaseManager] 获取知识库ID失败")
            return []

    @staticmethod
    async def get_team_kb_list_from_rag(user_sub: str, kb_name: str) -> list[dict[str, Any]]:
        try:
            session_id = await SessionManager.get_session_by_user_sub(user_sub)
            url = Config().get_config().rag.rag_service.rstrip("/")+"/api/knowledge"
            headers = {
                "Authorization": f"Bearer {session_id}",
                "Content-Type": "application/json",
            }
            async with httpx.AsyncClient() as client:
                data = {
                    "name": kb_name
                }
                resp = await client.get(url, headers=headers, params=data)
                resp_data = resp.json()
                if resp.status_code != status.HTTP_200_OK:
                    return []
            return resp_data["result"]["teamKnowledgebases"]
        except Exception as e:
            logger.exception("[KnowledgeBaseManager] 获取知识库ID失败")
            return []

    @staticmethod
    async def list_team_kb(user_sub: str, conversation_id: str, kb_name: str) -> list[KnowledgeBaseItemResponse]:
        """
        获取当前用户的知识库ID
        :param user_sub: 用户sub
        :return: 知识库ID列表
        """
        try:
            conv_collection = MongoDB().get_collection("conversation")
            result = await conv_collection.find_one({"_id": conversation_id, "user_sub": user_sub})
            if not result:
                err_msg = "[KnowledgeBaseManager] 获取知识库ID失败，未找到对话"
                logger.error(err_msg)
                return []
            kb_config_list = result.get("kb_list", [])
            kb_ids_used = [kb_config["kb_id"] for kb_config in kb_config_list]
            kb_ids_used = set(kb_ids_used)
        except Exception:
            logger.exception("[KnowledgeBaseManager] 获取知识库ID失败")
            return []
        try:
            session_id = await SessionManager.get_session_by_user_sub(user_sub)
            url = Config().get_config().rag.rag_service.rstrip("/")+"/api/knowledge"
            headers = {
                "Authorization": f"Bearer {session_id}",
                "Content-Type": "application/json",
            }
            async with httpx.AsyncClient() as client:
                data = {
                    "name": kb_name
                }
                resp = await client.get(url, headers=headers, params=data)
                resp_data = resp.json()
                if resp.status_code != status.HTTP_200_OK:
                    return []
                team_kb_item_list = []
                team_kb_list = await KnowledgeBaseManager.get_team_kb_list_from_rag(user_sub, kb_name)
                for team_kb in team_kb_list:
                    team_kb_item = TeamKnowledgeBaseItem(
                        teamId=team_kb["teamId"],
                        teamName=team_kb["teamName"],
                    )
                    for kb in team_kb["kbList"]:
                        kb_item = KnowledgeBaseItemResponse(
                            kbId=kb["kbId"],
                            kbName=kb["kbName"],
                            description=kb["description"],
                            isUsed=kb["kbId"] in kb_ids_used
                        )
                        team_kb_item.kb_list.append(kb_item)
                    team_kb_item_list.append(team_kb_item)
            return team_kb_item_list
        except Exception as e:
            logger.exception("[KnowledgeBaseManager] 获取知识库ID失败")
            return []

    @staticmethod
    async def update_conv_kb(
        user_sub: str,
        conversation_id: str,
        kb_ids: list[str],
    ) -> bool:
        """
        更新对话的知识库列表
        :param user_sub: 用户sub
        :param conversation_id: 对话ID
        :param kb_list: 知识库列表
        :return: 是否更新成功
        """
        try:
            conv_collection = MongoDB().get_collection("conversation")
            conv_dict = await conv_collection.find_one({"_id": conversation_id, "user_sub": user_sub})
            if not conv_dict:
                err_msg = "[KnowledgeBaseManager] 更新知识库失败，未找到对话"
                logger.error(err_msg)
                return False
            session_id = await SessionManager.get_session_by_user_sub(user_sub)
            url = Config().get_config().rag.rag_service.rstrip("/")+"/api/knowledge"
            headers = {
                "Authorization": f"Bearer {session_id}",
                "Content-Type": "application/json",
            }
            kb_item_list = []
            team_kb_list = await KnowledgeBaseManager.get_team_kb_list_from_rag(user_sub, "")
            for team_kb in team_kb_list:
                for kb in team_kb["kbList"]:
                    if str(kb["kbId"]) in kb_ids:
                        kb_item = KnowledgeBaseItem(
                            kb_id=kb["kbId"],
                            kb_name=kb["kbName"],
                        )
                        kb_item_list.append(kb_item)
            await conv_collection.update_one(
                {"_id": conversation_id, "user_sub": user_sub},
                {"$set": {"kb_list": kb_item_list}},
            )
            return True
        except Exception:
            logger.exception("[KnowledgeBaseManager] 更新知识库失败")
            return False
