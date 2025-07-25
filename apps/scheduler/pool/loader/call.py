# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Call 加载器"""

import asyncio
import importlib
import logging
import sys
from hashlib import shake_128
from pathlib import Path

import apps.scheduler.call as system_call
from apps.common.config import config
from apps.common.lance import LanceDB
from apps.common.mongo import MongoDB
from apps.common.singleton import SingletonMeta
from apps.llm.embedding import Embedding
from apps.models.node import NodeInfo

logger = logging.getLogger(__name__)
BASE_PATH = Path(config.deploy.data_dir) / "semantics" / "call"


class CallLoader(metaclass=SingletonMeta):
    """
    Call 加载器

    系统Call放在apps.scheduler.call下
    用户Call放在call下
    """

    async def _load_system_call(self) -> list[CallPool]:
        """加载系统Call"""
        call_metadata = []

        # 检查合法性
        for call_id in system_call.__all__:
            call_cls = getattr(system_call, call_id)
            call_info = call_cls.info()

            call_metadata.append(
                CallPool(
                    _id=call_id,
                    type=CallType.SYSTEM,
                    name=call_info.name,
                    description=call_info.description,
                    path=f"python::apps.scheduler.call::{call_id}",
                ),
            )

        return call_metadata


    async def _delete_from_db(self, call_name: str) -> None:
        """从数据库中删除单个Call"""
        # 从MongoDB中删除
        mongo = MongoDB()
        call_collection = mongo.get_collection("call")
        node_collection = mongo.get_collection("node")
        try:
            await call_collection.delete_one({"_id": call_name})
            await node_collection.delete_many({"call_id": call_name})
        except Exception as e:
            err = f"[CallLoader] 从MongoDB删除Call失败：{e}"
            logger.exception(err)
            raise RuntimeError(err) from e

        # 从LanceDB中删除
        while True:
            try:
                table = await LanceDB().get_table("call")
                await table.delete(f"id = '{call_name}'")
                break
            except RuntimeError as e:
                if "Commit conflict" in str(e):
                    logger.error("[CallLoader] LanceDB删除call冲突，重试中...")  # noqa: TRY400
                    await asyncio.sleep(0.01)
                else:
                    raise


    # 更新数据库
    async def _add_to_db(self, call_metadata: list[CallPool]) -> None:  # noqa: C901
        """更新数据库"""
        # 更新MongoDB
        mongo = MongoDB()
        call_collection = mongo.get_collection("call")
        node_collection = mongo.get_collection("node")
        call_descriptions = []
        try:
            for call in call_metadata:
                await call_collection.update_one(
                    {"_id": call.id}, {"$set": call.model_dump(exclude_none=True, by_alias=True)}, upsert=True,
                )
                await node_collection.insert_one(
                    NodePool(
                        _id=call.id,
                        name=call.name,
                        description=call.description,
                        service_id="",
                        call_id=call.id,
                    ).model_dump(exclude_none=True, by_alias=True),
                )
                call_descriptions += [call.description]
        except Exception as e:
            err = "[CallLoader] 更新MongoDB失败"
            logger.exception(err)
            raise RuntimeError(err) from e

        while True:
            try:
                table = await LanceDB().get_table("call")
                # 删除重复的ID
                for call in call_metadata:
                    await table.delete(f"id = '{call.id}'")
                break
            except RuntimeError as e:
                if "Commit conflict" in str(e):
                    logger.error("[CallLoader] LanceDB插入call冲突，重试中...")  # noqa: TRY400
                    await asyncio.sleep(0.01)
                else:
                    raise

        # 进行向量化，更新LanceDB
        call_vecs = await Embedding.get_embedding(call_descriptions)
        vector_data = []
        for i, vec in enumerate(call_vecs):
            vector_data.append(
                CallPoolVector(
                    id=call_metadata[i].id,
                    embedding=vec,
                ),
            )
        while True:
            try:
                table = await LanceDB().get_table("call")
                await table.merge_insert("id").when_matched_update_all().when_not_matched_insert_all().execute(
                    vector_data,
                )
                break
            except RuntimeError as e:
                if "Commit conflict" in str(e):
                    logger.error("[CallLoader] LanceDB插入call冲突，重试中...")  # noqa: TRY400
                    await asyncio.sleep(0.01)
                else:
                    raise

    async def load(self) -> None:
        """初始化Call信息"""
        # 清空collection
        mongo = MongoDB()
        call_collection = mongo.get_collection("call")
        node_collection = mongo.get_collection("node")
        try:
            await call_collection.delete_many({})
            await node_collection.delete_many({"service_id": ""})
        except Exception:
            logger.exception("[CallLoader] Call的collection清空失败")

        # 载入所有已知的Call信息
        try:
            sys_call_metadata = await self._load_system_call()
        except Exception as e:
            err = "[CallLoader] 载入系统Call信息失败"
            logger.exception(err)
            raise RuntimeError(err) from e

        try:
            user_call_metadata = await self._load_all_user_call()
        except Exception:
            err = "[CallLoader] 载入用户Call信息失败"
            logger.exception(err)
            user_call_metadata = []

        # 合并Call元数据
        call_metadata = sys_call_metadata + user_call_metadata

        # 更新数据库
        await self._add_to_db(call_metadata)

    async def load_one(self, call_name: str) -> None:
        """加载单个Call"""
        try:
            call_metadata = await self._load_single_call_dir(call_name)
        except Exception as e:
            err = f"[CallLoader] 载入Call信息失败：{e}。"
            logger.exception(err)
            raise RuntimeError(err) from e

        # 有数据时更新数据库
        if call_metadata:
            await self._add_to_db(call_metadata)
