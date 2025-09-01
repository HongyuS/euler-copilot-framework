# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Call 加载器"""

import logging

from sqlalchemy import delete

import apps.scheduler.call as system_call
from apps.common.postgres import postgres
from apps.common.singleton import SingletonMeta
from apps.llm.embedding import Embedding, VectorBase
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


    # 更新数据库
    async def _add_to_db(self, call_metadata: dict[str, CallInfo]) -> None:
        """更新数据库"""
        # 清除旧数据
        async with postgres.session() as session:
            await session.execute(delete(NodeInfo).where(NodeInfo.serviceId == None))  # noqa: E711
            NodePoolVector = VectorBase.metadata.tables["framework_node_vector"]  # noqa: N806
            await session.execute(delete(NodePoolVector).where(NodePoolVector.serviceId == None))  # noqa: E711

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

            # 进行向量化
            call_vecs = await Embedding.get_embedding(call_descriptions)
            vector_data = []
            for call_id, vec in zip(call_metadata.keys(), call_vecs, strict=True):
                vector_data.append(
                    NodePoolVector(
                        id=call_id,
                        serviceId=None,
                        embedding=vec,
                    ),
                )
            session.add_all(vector_data)
            await session.commit()


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
        await self._add_to_db(sys_call_metadata)
