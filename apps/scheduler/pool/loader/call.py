# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Call 加载器"""

import logging

from sqlalchemy import delete

import apps.scheduler.call as system_call
from apps.common.postgres import postgres
from apps.common.singleton import SingletonMeta
from apps.llm.embedding import Embedding
from apps.models.node import NodeInfo
from apps.schemas.scheduler import CallInfo

_logger = logging.getLogger(__name__)


class CallLoader(metaclass=SingletonMeta):
    """Call 加载器"""

    async def _load_system_call(self) -> dict[str, CallInfo]:
        """加载系统Call"""
        call_metadata = {}

        # 检查合法性
        for call_id in system_call.__all__:
            call_cls = getattr(system_call, call_id)
            call_info = call_cls.info()
            call_metadata[call_id] = call_info

        return call_metadata


    # 将数据插入数据库
    async def _add_data_to_db(self, call_metadata: dict[str, CallInfo]) -> None:
        """将数据插入数据库"""
        # 清除旧数据
        async with postgres.session() as session:
            await session.execute(delete(NodeInfo).where(NodeInfo.serviceId == None))  # noqa: E711

            # 更新数据库
            call_descriptions = []
            for call_id, call in call_metadata.items():
                await session.merge(NodeInfo(
                    id=call_id,
                    name=call.name,
                    description=call.description,
                    serviceId=None,
                    callId=call_id,
                    knownParams={},
                    overrideInput={},
                    overrideOutput={},
                ))
                call_descriptions.append(call.description)

            await session.commit()


    async def _add_vector_to_db(
        self, call_metadata: dict[str, CallInfo], embedding_model: Embedding,
    ) -> None:
        """将向量化数据存入数据库"""
        async with postgres.session() as session:
            # 删除旧数据
            await session.execute(
                delete(embedding_model.NodePoolVector).where(embedding_model.NodePoolVector.serviceId == None),  # noqa: E711
            )

            call_vecs = await embedding_model.get_embedding([call.description for call in call_metadata.values()])
            for call_id, vec in zip(call_metadata.keys(), call_vecs, strict=True):
                session.add(embedding_model.NodePoolVector(
                    id=call_id,
                    embedding=vec,
                ))
            await session.commit()


    async def set_vector(self, embedding_model: Embedding) -> None:
        """将向量化数据存入数据库"""
        call_metadata = await self._load_system_call()
        await self._add_vector_to_db(call_metadata, embedding_model)


    async def load(self) -> None:
        """初始化Call信息"""
        # 载入所有已知的Call信息
        try:
            sys_call_metadata = await self._load_system_call()
        except Exception as e:
            err = "[CallLoader] 载入系统Call信息失败"
            _logger.exception(err)
            raise RuntimeError(err) from e

        # 更新数据库
        await self._add_data_to_db(sys_call_metadata)
