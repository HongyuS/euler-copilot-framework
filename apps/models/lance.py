"""
向postgresql中存储向量化数据

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

import lancedb
from lancedb.index import HnswSq

from apps.common.config import Config
from apps.common.singleton import SingletonMeta
from apps.entities.vector import (
    CallPoolVector,
    FlowPoolVector,
    NodePoolVector,
    ServicePoolVector,
)


class LanceDB(metaclass=SingletonMeta):
    """LanceDB向量化存储"""

    async def init(self) -> None:
        """初始化PostgreSQL"""
        self._engine = await lancedb.connect_async(
            Config().get_config().deploy.data_dir.rstrip("/") + "/vectors",
        )

        # 创建表
        await self._engine.create_table(
            "flow",
            schema=FlowPoolVector,
            exist_ok=True,
        )
        await self._engine.create_table(
            "service",
            schema=ServicePoolVector,
            exist_ok=True,
        )
        await self._engine.create_table(
            "call",
            schema=CallPoolVector,
            exist_ok=True,
        )
        await self._engine.create_table(
            "node",
            schema=NodePoolVector,
            exist_ok=True,
        )

    async def get_table(self, table_name: str) -> lancedb.AsyncTable:
        """获取表"""
        return await self._engine.open_table(table_name)

    async def create_index(self, table_name: str) -> None:
        """创建索引"""
        table = await self.get_table(table_name)
        await table.create_index(
            "embedding",
            config=HnswSq(),
        )
