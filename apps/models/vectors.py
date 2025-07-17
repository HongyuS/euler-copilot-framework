"""向量表"""

import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class FlowPoolVector(Base):
    """Flow向量数据"""

    __tablename__ = "framework_flow_vector"
    appId: Mapped[uuid.UUID] = mapped_column(ForeignKey("framework_app.id"))  # noqa: N815
    """所属App的ID"""
    embedding: Mapped[Vector] = mapped_column(Vector(1024))
    """向量数据"""
    id: Mapped[uuid.UUID] = mapped_column(ForeignKey("framework_flow.id"), primary_key=True)
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
    embedding: Mapped[Vector] = mapped_column(Vector(1024))
    """向量数据"""
    id: Mapped[uuid.UUID] = mapped_column(ForeignKey("framework_service.id"), primary_key=True)
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
    embedding: Mapped[Vector] = mapped_column(Vector(1024))
    """向量数据"""
    serviceId: Mapped[uuid.UUID] = mapped_column(ForeignKey("framework_service.id"))  # noqa: N815
    """Service的ID"""
    id: Mapped[uuid.UUID] = mapped_column(ForeignKey("framework_node.id"), primary_key=True)
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
