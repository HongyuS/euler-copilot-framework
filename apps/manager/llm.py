"""
用户资产库管理

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

import logging
import httpx
from fastapi import status
import yaml
from apps.entities.request_data import (
    UpdateLLMReq,
)
from apps.templates.generate_llm_operator_config import llm_provider_dict
from apps.common.config import Config
from apps.entities.collection import LLM, LLMItem
from apps.models.mongo import MongoDB
from apps.common.config import Config
from apps.entities.response_data import LLMProvider, LLM as LLMResponse
from apps.manager.session import SessionManager
logger = logging.getLogger(__name__)


class LLMManager:
    """大模型管理"""
    @staticmethod
    async def list_llm_provider() -> list[LLMProvider]:
        """
        获取大模型提供商列表
        :return: 大模型提供商列表
        """
        try:
            llm_provider_item_list = []
            for llm_provider in llm_provider_dict.values():
                llm_provider_item = LLMProvider(
                    provider=llm_provider["provider"],
                    url=llm_provider["url"],
                    description=llm_provider["description"],
                    icon=llm_provider["icon"],
                )
                llm_provider_item_list.append(llm_provider_item)
            return llm_provider_item_list
        except Exception as e:
            logger.exception("[LLMManager] 获取大模型提供商失败")
            return []

    @staticmethod
    async def get_llm_id_by_conversation_id(user_sub: str, conversation_id: str) -> str:
        """
        通过对话ID获取大模型ID
        :param user_sub: 用户ID
        :param conversation_id: 对话ID
        :return: 大模型ID
        """
        try:
            conv_collection = MongoDB().get_collection("conversation")
            result = await conv_collection.find_one({"_id": conversation_id, "user_sub": user_sub})
            if not result:
                return None
            llm_id = result.get("llm", {}).get("llm_id", None)
            return llm_id
        except Exception as e:
            logger.exception("[LLMManager] 获取大模型ID失败")
            return None

    @staticmethod
    async def get_llm_by_id(user_sub: str, llm_id: str) -> LLM:
        """
        通过ID获取大模型
        :param user_sub: 用户ID
        :param llm_id: 大模型ID
        :return: 大模型对象
        """
        try:
            llm_collection = MongoDB().get_collection("llm")
            result = await llm_collection.find_one({"_id": llm_id, "user_sub": user_sub})
            if not result:
                return None
            return LLM.model_validate(result)
        except Exception as e:
            logger.exception("[LLMManager] 获取大模型失败")
            return None

    @staticmethod
    async def list_llm(user_sub: str, llm_id: str) -> list[LLMResponse]:
        """
        获取大模型列表
        :param user_sub: 用户ID
        :return: 大模型列表
        """
        try:
            llm_collection = MongoDB().get_collection("llm")
            filter = {"user_sub": user_sub}
            if llm_id:
                filter["llm_id"] = llm_id
            result = await llm_collection.find(filter).sort({"created_at": 1}).to_list(length=None)
            if not result:
                return []
            llm_item = LLMResponse(
                llmId="empty",
                openaiBaseUrl=Config().get_config().llm.endpoint,
                openaiApiKey=Config().get_config().llm.key,
                modelName=Config().get_config().llm.model,
                maxTokens=Config().get_config().llm.max_tokens,
            )
            llm_item_list = [llm_item]
            for llm in result:
                llm_item = LLMResponse(
                    llmId=llm["_id"],
                    icon=llm["icon"],
                    openaiBaseUrl=llm["openai_base_url"],
                    openaiApiKey=llm["openai_api_key"],
                    modelName=llm["model_name"],
                    maxTokens=llm["max_tokens"],
                )
                llm_item_list.append(llm_item)
            return llm_item_list
        except Exception as e:
            logger.exception("[LLMManager] 获取大模型失败")
            return []

    @staticmethod
    async def update_llm(user_sub: str, llm_id: str, req: UpdateLLMReq) -> LLM:
        """
        创建大模型
        :param user_sub: 用户ID
        :param req: 创建大模型请求体
        :return: 大模型对象
        """
        try:
            llm_collection = MongoDB().get_collection("llm")
            if llm_id:
                llm_dict = await llm_collection.find_one({"_id": llm_id, "user_sub": user_sub})
                if not llm_dict:
                    err = f"[LLMManager] LLM {llm_id} 不存在"
                    logger.error(err)
                    raise Exception(err)
                llm = LLM(
                    _id=llm_id,
                    user_sub=user_sub,
                    icon=llm_dict["icon"],
                    openai_base_url=req.openai_base_url,
                    openai_api_key=req.openai_api_key,
                    model_name=req.model_name,
                    max_tokens=req.max_tokens,
                )
                await llm_collection.update_one({"_id": llm_id}, {"$set": llm.model_dump(by_alias=True)})
            else:
                llm = LLM(
                    user_sub=user_sub,
                    icon=req.icon,
                    openai_base_url=req.openai_base_url,
                    openai_api_key=req.openai_api_key,
                    model_name=req.model_name,
                    max_tokens=req.max_tokens,
                )
                await llm_collection.insert_one(llm.model_dump(by_alias=True))
            return llm.id
        except Exception as e:
            logger.exception("[LLMManager] 创建大模型失败")
            return None

    @staticmethod
    async def delete_llm(user_sub: str, llm_id: str) -> str:
        """
        删除大模型
        :param user_sub: 用户ID
        :param llm_id: 大模型ID
        :return: 大模型ID
        """
        try:
            if llm_id == "empty":
                err = "[LLMManager] 不能删除默认大模型"
                logger.error(err)
                raise Exception(err)
            llm_collection = MongoDB().get_collection("llm")
            llm_config = await llm_collection.find_one({"_id": llm_id, "user_sub": user_sub})
            if not llm_config:
                err = f"[LLMManager] LLM {llm_id} 不存在"
                logger.error(err)
                raise Exception(err)
            await llm_collection.delete_one({"_id": llm_id, "user_sub": user_sub})
            return llm_id
        except Exception as e:
            logger.exception("[LLMManager] 删除大模型失败")
            raise e

    @staticmethod
    async def update_conversation_llm(
        user_sub: str,
        conversation_id: str,
        llm_id: str,
    ) -> str:
        """更新对话的LLM"""
        try:
            conv_collection = MongoDB().get_collection("conversation")
            llm_collection = MongoDB().get_collection("llm")
            if llm_id != "empty":
                llm_dict = await llm_collection.find_one({"_id": llm_id, "user_sub": user_sub})
                if not llm_dict:
                    err = f"[LLMManager] LLM {llm_id} 不存在"
                    logger.error(err)
                    return False
            else:
                llm_dict = {
                    "model_name": Config().get_config().llm.model,
                    "icon": llm_provider_dict['ollama']['icon'],
                }
            conv_dict = await conv_collection.find_one({"_id": conversation_id, "user_sub": user_sub})
            if not conv_dict:
                err_msg = "[LLMManager] 更新对话的LLM失败，未找到对话"
                logger.error(err_msg)
                return False
            llm_item = LLMItem(
                llm_id=llm_id,
                model_name=llm_dict["model_name"],
                icon=llm_dict["icon"],
            )
            await conv_collection.update_one(
                {"_id": conversation_id, "user_sub": user_sub},
                {"$set": {"llm": llm_item.model_dump(by_alias=True)}},
            )
            return conversation_id
        except Exception as e:
            logger.exception("[LLMManager] 更新对话的LLM失败")
            raise e
