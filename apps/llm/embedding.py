"""Embedding模型"""

import logging
from typing import Any

import httpx
from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base

from apps.common.postgres import postgres
from apps.models.llm import EmbeddingBackend, LLMData

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

    async def _delete_vector(self) -> None:
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
        if not llm_config or not llm_config.embeddingBackend:
            err = "[Embedding] 未设置Embedding模型"
            _logger.error(err)
            raise RuntimeError(err)
        self._config: LLMData = llm_config

    async def init(self) -> None:
        """在使用Embedding前初始化数据库表等资源"""
        await self._delete_vector()
        # 检测维度
        dim = await self._get_embedding_dimension()
        await self._create_vector_table(dim)

    async def _get_openai_embedding(self, text: list[str]) -> list[list[float]]:
        """访问OpenAI兼容的Embedding API，获得向量化数据"""
        api = self._config.openaiBaseUrl + "/embeddings"
        data = {
            "input": text,
            "model": self._config.modelName,
            "encoding_format": "float",
        }

        headers = {
            "Content-Type": "application/json",
        }
        if self._config.openaiAPIKey:
            headers["Authorization"] = f"Bearer {self._config.openaiAPIKey}"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                api,
                json=data,
                headers=headers,
                timeout=60.0,
            )
            json = response.json()
            return [item["embedding"] for item in json["data"]]

    async def _get_tei_embedding(self, text: list[str]) -> list[list[float]]:
        """访问TEI兼容的Embedding API，获得向量化数据"""
        api = self._config.openaiBaseUrl + "/embed"
        headers = {
            "Content-Type": "application/json",
        }
        if self._config.openaiAPIKey:
            headers["Authorization"] = f"Bearer {self._config.openaiAPIKey}"

        async with httpx.AsyncClient() as client:
            result = []
            for single_text in text:
                data = {
                    "inputs": single_text,
                    "normalize": True,
                }
                response = await client.post(
                    api, json=data, headers=headers, timeout=60.0,
                )
                json = response.json()
                result.append(json[0])

            return result

    async def get_embedding(self, text: list[str]) -> list[list[float]]:
        """
        访问OpenAI兼容的Embedding API，获得向量化数据

        :param text: 待向量化文本（多条文本组成List）
        :return: 文本对应的向量（顺序与text一致，也为List）
        """
        if self._config.embeddingBackend == EmbeddingBackend.OPENAI:
            return await self._get_openai_embedding(text)
        if self._config.embeddingBackend == EmbeddingBackend.TEI:
            return await self._get_tei_embedding(text)

        err = f"[Embedding] 不支持的Embedding API类型: {self._config.modelName}"
        _logger.error(err)
        raise RuntimeError(err)
