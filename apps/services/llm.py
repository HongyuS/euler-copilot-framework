# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""大模型管理"""

import logging

from sqlalchemy import and_, select

from apps.common.config import config
from apps.common.postgres import postgres
from apps.models.llm import LLMData
from apps.models.user import User
from apps.schemas.request_data import (
    UpdateLLMReq,
)
from apps.schemas.response_data import LLMProvider, LLMProviderInfo
from apps.templates.generate_llm_operator_config import llm_provider_dict

logger = logging.getLogger(__name__)


class LLMManager:
    """大模型管理"""

    @staticmethod
    async def list_llm_provider() -> list[LLMProvider]:
        """
        获取大模型提供商列表

        :return: 大模型提供商列表
        """
        provider_list = []
        for provider in llm_provider_dict.values():
            item = LLMProvider(
                provider=provider["provider"],
                url=provider["url"],
                description=provider["description"],
                icon=provider["icon"],
            )
            provider_list.append(item)
        return provider_list


    @staticmethod
    async def get_llm_id_by_user_id(user_sub: str) -> int | None:
        """
        通过用户ID获取大模型ID

        :param user_sub: 用户ID
        :return: 大模型ID
        """
        async with postgres.session() as session:
            user = (await session.scalars(
                select(User).where(User.userSub == user_sub),
            )).one_or_none()
            if not user:
                logger.error("[LLMManager] 用户 %s 不存在", user_sub)
                return None

            return user.selectedLLM


    @staticmethod
    async def get_llm_by_id(user_sub: str, llm_id: int) -> LLMData | None:
        """
        通过ID获取大模型

        :param user_sub: 用户ID
        :param llm_id: 大模型ID
        :return: 大模型对象
        """
        async with postgres.session() as session:
            llm = (await session.scalars(
                select(LLMData).where(
                    and_(
                        LLMData.id == llm_id,
                        LLMData.userSub == user_sub,
                    ),
                ),
            )).one_or_none()
            if not llm:
                logger.error("[LLMManager] LLM %s 不存在", llm_id)
                return None
            return llm


    @staticmethod
    async def list_llm(user_sub: str, llm_id: int | None) -> list[LLMProviderInfo]:
        """
        获取大模型列表

        :param user_sub: 用户ID
        :param llm_id: 大模型ID
        :return: 大模型列表
        """
        async with postgres.session() as session:
            if llm_id:
                llm_list = (await session.scalars(
                    select(LLMData).where(
                        and_(
                            LLMData.id == llm_id,
                            LLMData.userSub == user_sub,
                        ),
                    ),
                )).all()
            else:
                llm_list = (await session.scalars(
                    select(LLMData).where(LLMData.userSub == user_sub),
                )).all()
            if not llm_list:
                logger.error("[LLMManager] 无法找到用户 %s 的大模型", user_sub)
                return []

        # 默认大模型
        llm_item = LLMProviderInfo(llmId="empty")
        llm_list = [llm_item]
        for llm in result:
            llm_item = LLMProviderInfo(
                llmId=llm["_id"],
                icon=llm["icon"],
                openaiBaseUrl=llm["openai_base_url"],
                openaiApiKey=llm["openai_api_key"],
                modelName=llm["model_name"],
                maxTokens=llm["max_tokens"],
            )
            llm_list.append(llm_item)
        return llm_list

    @staticmethod
    async def update_llm(user_sub: str, llm_id: str | None, req: UpdateLLMReq) -> str:
        """
        创建大模型

        :param user_sub: 用户ID
        :param req: 创建大模型请求体
        :return: 大模型对象
        """
        mongo = MongoDB()
        llm_collection = mongo.get_collection("llm")

        if llm_id:
            llm_dict = await llm_collection.find_one({"_id": llm_id, "user_sub": user_sub})
            if not llm_dict:
                err = f"[LLMManager] LLM {llm_id} 不存在"
                logger.error(err)
                raise ValueError(err)
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


    @staticmethod
    async def delete_llm(user_sub: str, llm_id: int | None) -> None:
        """
        删除大模型

        :param user_sub: 用户ID
        :param llm_id: 大模型ID
        """
        if llm_id is None:
            err = "[LLMManager] 不能删除默认大模型"
            raise ValueError(err)

        async with postgres.session() as session:
            llm = (await session.scalars(
                select(LLMData).where(
                    and_(
                        LLMData.id == llm_id,
                        LLMData.userSub == user_sub,
                    ),
                ),
            )).one_or_none()
            if not llm:
                err = f"[LLMManager] LLM {llm_id} 不存在"
            else:
                await session.delete(llm)
                await session.commit()

        async with postgres.session() as session:
            user = (await session.scalars(
                select(User).where(User.userSub == user_sub),
            )).one_or_none()
            if not user:
                err = f"[LLMManager] 用户 {user_sub} 不存在"
                raise ValueError(err)
            user.selectedLLM = None
            await session.commit()


    @staticmethod
    async def update_user_llm(
        user_sub: str,
        conversation_id: str,
        llm_id: str,
    ) -> str:
        """更新对话的LLM"""
        mongo = MongoDB()
        conv_collection = mongo.get_collection("conversation")
        llm_collection = mongo.get_collection("llm")

        if llm_id != "empty":
            llm_dict = await llm_collection.find_one({"_id": llm_id, "user_sub": user_sub})
            if not llm_dict:
                err = f"[LLMManager] LLM {llm_id} 不存在"
                logger.error(err)
                raise ValueError(err)
            llm_dict = {
                "llm_id": llm_dict["_id"],
                "model_name": llm_dict["model_name"],
                "icon": llm_dict["icon"],
            }
        else:
            llm_dict = {
                "llm_id": "empty",
                "model_name": config.llm.model,
                "icon": llm_provider_dict["ollama"]["icon"],
            }
        conv_dict = await conv_collection.find_one({"_id": conversation_id, "user_sub": user_sub})
        if not conv_dict:
            err_msg = "[LLMManager] 更新对话的LLM失败，未找到对话"
            logger.error(err_msg)
            raise ValueError(err_msg)

        llm_item = LLMData(
            userSub=user_sub,
            icon=llm_dict["icon"],
            openaiBaseUrl=llm_dict["openai_base_url"],
            openaiAPIKey=llm_dict["openai_api_key"],
            modelName=llm_dict["model_name"],
            maxToken=llm_dict["max_tokens"],
        )

        await conv_collection.update_one(
            {"_id": conversation_id, "user_sub": user_sub},
            {"$set": {"llm": llm_item.model_dump(by_alias=True)}},
        )
        return conversation_id
