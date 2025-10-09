"""Embedding模型"""

import logging
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base

from apps.common.postgres import postgres
from apps.models import LLMData, LLMProvider

from .providers import BaseProvider, OpenAIProvider, TEIProvider

_logger = logging.getLogger(__name__)
_flow_pool_vector_table = {
    "__tablename__": "framework_flow_vector",
    "appId": Column(UUID(as_uuid=True), ForeignKey("framework_app.id"), nullable=False),
    "id": Column(String(255), ForeignKey("framework_flow.id"), primary_key=True),
    "__table_args__": (
        Index(
            "hnsw_index",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 200},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    ),
}
_service_pool_vector_table = {
    "__tablename__": "framework_service_vector",
    "id": Column(UUID(as_uuid=True), ForeignKey("framework_service.id"), primary_key=True),
    "__table_args__": (
        Index(
            "hnsw_index",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 200},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    ),
}
_node_pool_vector_table = {
    "__tablename__": "framework_node_vector",
    "id": Column(String(255), ForeignKey("framework_node.id"), primary_key=True),
    "serviceId": Column(UUID(as_uuid=True), ForeignKey("framework_service.id"), nullable=True),
    "__table_args__": (
        Index(
            "hnsw_index",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 200},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    ),
}
_mcp_vector_table = {
    "__tablename__": "framework_mcp_vector",
    "id": Column(String(255), ForeignKey("framework_mcp.id"), primary_key=True),
    "__table_args__": (
        Index(
            "hnsw_index",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 200},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    ),
}
_mcp_tool_vector_table = {
    "__tablename__": "framework_mcp_tool_vector",
    "id": Column(String(255), ForeignKey("framework_mcp_tool.id"), primary_key=True),
    "mcpId": Column(String(255), ForeignKey("framework_mcp.id"), nullable=False),
    "__table_args__": (
        Index(
            "hnsw_index",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 200},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    ),
}
_CLASS_DICT: dict[LLMProvider, type[BaseProvider]] = {
    LLMProvider.OPENAI: OpenAIProvider,
    LLMProvider.TEI: TEIProvider,
}


class Embedding:
    """Embedding模型"""

    VectorBase: Any
    NodePoolVector: Any
    FlowPoolVector: Any
    ServicePoolVector: Any
    MCPVector: Any
    MCPToolVector: Any

    async def _get_embedding_dimension(self) -> int:
        """获取Embedding的维度"""
        embedding = await self.get_embedding(["测试文本"])
        return len(embedding[0])

    async def delete_vector(self) -> None:
        """删除所有Vector表"""
        async with postgres.session() as session:
            await session.execute(text("DROP TABLE IF EXISTS framework_flow_vector"))
            await session.execute(text("DROP TABLE IF EXISTS framework_service_vector"))
            await session.execute(text("DROP TABLE IF EXISTS framework_node_vector"))
            await session.execute(text("DROP TABLE IF EXISTS framework_mcp_vector"))
            await session.execute(text("DROP TABLE IF EXISTS framework_mcp_tool_vector"))
            await session.commit()

    async def _create_vector_table(self, dim: int) -> None:
        """根据检测出的维度创建Vector表"""
        if dim <= 0:
            err = "[Embedding] 检测到的Embedding维度为0，无法创建Vector表"
            _logger.error(err)
            raise RuntimeError(err)
        # 给所有的Dict加入embedding字段
        for table in [
            _flow_pool_vector_table,
            _service_pool_vector_table,
            _node_pool_vector_table,
            _mcp_vector_table,
            _mcp_tool_vector_table,
        ]:
            table["embedding"] = Column(Vector(dim), nullable=False)

        # 创建表
        self.VectorBase = declarative_base()
        self.NodePoolVector = type("NodePoolVector", (self.VectorBase,), _node_pool_vector_table)
        self.FlowPoolVector = type("FlowPoolVector", (self.VectorBase,), _flow_pool_vector_table)
        self.ServicePoolVector = type("ServicePoolVector", (self.VectorBase,), _service_pool_vector_table)
        self.MCPVector = type("MCPVector", (self.VectorBase,), _mcp_vector_table)
        self.MCPToolVector = type("MCPToolVector", (self.VectorBase,), _mcp_tool_vector_table)
        self.VectorBase.metadata.create_all(postgres.engine)

    def __init__(self, llm_config: LLMData | None = None) -> None:
        """初始化Embedding对象"""
        if not llm_config:
            err = "[Embedding] 未设置LLM配置"
            _logger.error(err)
            raise RuntimeError(err)
        self._provider = _CLASS_DICT[llm_config.provider](llm_config)

    async def init(self) -> None:
        """在使用Embedding前初始化数据库表等资源"""
        # 检测维度
        dim = await self._get_embedding_dimension()
        await self._create_vector_table(dim)

    async def get_embedding(self, text: list[str]) -> list[list[float]]:
        """
        访问OpenAI兼容的Embedding API，获得向量化数据

        :param text: 待向量化文本（多条文本组成List）
        :return: 文本对应的向量（顺序与text一致，也为List）
        """
        return await self._provider.embedding(text)
