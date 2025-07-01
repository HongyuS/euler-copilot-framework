"""向量表"""

from pgvector.sqlalchemy import Vector
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class FlowPoolVector(Base):
    """Flow向量数据"""

    __tablename__ = "flow_vector"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    flow_id: Mapped[str] = mapped_column(String(32), index=True, unique=True)
    app_id: Mapped[str] = mapped_column(String(32))
    embedding: Mapped[Vector] = mapped_column(Vector(1024))


class ServicePoolVector(Base):
    """Service向量数据"""

    __tablename__ = "service_vector"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    service_id: Mapped[str] = mapped_column(String(32), index=True, unique=True)
    embedding: Mapped[Vector] = mapped_column(Vector(1024))


class CallPoolVector(Base):
    """Call向量数据"""

    __tablename__ = "call_vector"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    call_id: Mapped[str] = mapped_column(String(32), index=True, unique=True)
    embedding: Mapped[Vector] = mapped_column(Vector(1024))


class NodePoolVector(Base):
    """Node向量数据"""

    __tablename__ = "node_vector"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    service_id: Mapped[str] = mapped_column(String(32))
    embedding: Mapped[Vector] = mapped_column(Vector(1024))
