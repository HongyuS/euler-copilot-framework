"""向量表"""

import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class FlowPoolVector(Base):
    """Flow向量数据"""

    __tablename__ = "framework_flow_vector"
    appId: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("framework_app.id"), nullable=False)  # noqa: N815
    """所属App的ID"""
    embedding: Mapped[list[float]] = mapped_column(Vector(1024), nullable=False)
    """向量数据"""
    id: Mapped[str] = mapped_column(String(255), ForeignKey("framework_flow.id"), primary_key=True)
    """Flow的ID"""
    __table_args__ = (
        Index(
            "hnsw_index",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 200},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class ServicePoolVector(Base):
    """Service向量数据"""

    __tablename__ = "framework_service_vector"
    embedding: Mapped[list[float]] = mapped_column(Vector(1024), nullable=False)
    """向量数据"""
    id: Mapped[str] = mapped_column(String(255), ForeignKey("framework_service.id"), primary_key=True)
    """Service的ID"""
    __table_args__ = (
        Index(
            "hnsw_index",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 200},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class NodePoolVector(Base):
    """Node向量数据"""

    __tablename__ = "framework_node_vector"
    embedding: Mapped[list[float]] = mapped_column(Vector(1024), nullable=False)
    """向量数据"""
    serviceId: Mapped[str | None] = mapped_column(String(255), ForeignKey("framework_service.id"), nullable=True)  # noqa: N815
    """Service的ID"""
    id: Mapped[str] = mapped_column(String(255), ForeignKey("framework_node.id"), primary_key=True)
    """Node的ID"""
    __table_args__ = (
        Index(
            "hnsw_index",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 200},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class MCPVector(Base):
    """MCP向量数据"""

    __tablename__ = "framework_mcp_vector"
    embedding: Mapped[list[float]] = mapped_column(Vector(1024), nullable=False)
    """向量数据"""
    id: Mapped[str] = mapped_column(String(255), ForeignKey("framework_mcp.id"), primary_key=True)
    """MCP的ID"""
    __table_args__ = (
        Index(
            "hnsw_index",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 200},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class MCPToolVector(Base):
    """MCP工具向量数据"""

    __tablename__ = "framework_mcp_tool_vector"
    embedding: Mapped[list[float]] = mapped_column(Vector(1024), nullable=False)
    """向量数据"""
    mcpId: Mapped[str] = mapped_column(String(255), ForeignKey("framework_mcp.id"), nullable=False, index=True)  # noqa: N815
    """MCP的ID"""
    id: Mapped[str] = mapped_column(String(255), ForeignKey("framework_mcp_tool.id"), primary_key=True)
    """MCP工具的ID"""
    __table_args__ = (
        Index(
            "hnsw_index",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 200},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
