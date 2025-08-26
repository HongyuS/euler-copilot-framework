"""节点 数据库表"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class NodeInfo(Base):
    """节点"""

    __tablename__ = "framework_node"
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    """节点名称"""
    description: Mapped[str] = mapped_column(String(2000), nullable=False)
    """节点描述"""
    serviceId: Mapped[uuid.UUID | None] = mapped_column(  # noqa: N815
        UUID(as_uuid=True), ForeignKey("framework_service.id"), nullable=True,
    )
    """所属服务ID"""
    callId: Mapped[str] = mapped_column(String(50), nullable=False)  # noqa: N815
    """所属CallID"""
    knownParams: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)  # noqa: N815
    """已知的用于Call部分的参数，独立于输入和输出之外"""
    overrideInput: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)  # noqa: N815
    """Node的输入Schema；用于描述Call的参数中特定的字段"""
    overrideOutput: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)  # noqa: N815
    """Node的输出Schema；用于描述Call的输出中特定的字段"""
    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    """节点ID"""
    updatedAt: Mapped[datetime] = mapped_column(  # noqa: N815
        DateTime(timezone=True),
        default_factory=lambda: datetime.now(tz=UTC),
        onupdate=lambda: datetime.now(tz=UTC),
        nullable=False,
    )
    """节点更新时间"""
