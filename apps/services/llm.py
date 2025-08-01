# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""大模型管理"""

import logging
import uuid

from sqlalchemy import and_, select

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
    async def get_user_default_llm(user_sub: str) -> uuid.UUID | None:
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

            return user.defaultLLM


    @staticmethod
    async def get_llm(llm_id: uuid.UUID) -> LLMData | None:
        """
        通过ID获取大模型

        :param user_sub: 用户ID
        :param llm_id: 大模型ID
        :return: 大模型对象
        """
        async with postgres.session() as session:
            llm = (await session.scalars(
                select(LLMData).where(
                    LLMData.id == llm_id,
                ),
            )).one_or_none()
            if not llm:
                logger.error("[LLMManager] LLM %s 不存在", llm_id)
                return None
            return llm


    @staticmethod
    async def list_llm(llm_id: uuid.UUID | None) -> list[LLMProviderInfo]:
        """
        获取大模型列表

        :param llm_id: 大模型ID
        :return: 大模型列表
        """
        async with postgres.session() as session:
            if llm_id:
                llm_list = (await session.scalars(
                    select(LLMData).where(
                        LLMData.id == llm_id,
                    ),
                )).all()
            else:
                llm_list = (await session.scalars(
                    select(LLMData),
                )).all()
            if not llm_list:
                logger.error("[LLMManager] 无法找到大模型 %s", llm_id)
                return []

        # 默认大模型
        provider_list = []
        for llm in llm_list:
            llm_item = LLMProviderInfo(
                llmId=llm.id,
                icon=llm.icon,
                openaiBaseUrl=llm.openaiBaseUrl,
                openaiApiKey=llm.openaiAPIKey,
                modelName=llm.modelName,
                maxTokens=llm.maxToken,
            )
            provider_list.append(llm_item)
        return provider_list


    @staticmethod
    async def update_llm(llm_id: uuid.UUID | None, req: UpdateLLMReq) -> None:
        """
        创建大模型

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


    @staticmethod
    async def delete_llm(user_sub: str, llm_id: uuid.UUID | None) -> None:
        """
        删除大模型

        :param llm_id: 大模型ID
        """
        if llm_id is None:
            err = "[LLMManager] 不能删除默认大模型"
            raise ValueError(err)

        async with postgres.session() as session:
            llm = (await session.scalars(
                select(LLMData).where(
                    LLMData.id == llm_id,
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
            user.defaultLLM = None
            await session.commit()


    @staticmethod
    async def update_user_default_llm(
        user_sub: str,
        llm_id: uuid.UUID,
    ) -> None:
        """更新用户的默认LLM"""
        async with postgres.session() as session:
            user = (await session.scalars(
                select(User).where(User.userSub == user_sub),
            )).one_or_none()
            if not user:
                err = f"[LLMManager] 用户 {user_sub} 不存在"
                raise ValueError(err)
            user.defaultLLM = llm_id
            await session.commit()
