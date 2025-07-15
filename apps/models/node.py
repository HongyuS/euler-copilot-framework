"""节点 数据库表"""

import uuid
from datetime import datetime
from typing import Any

import pytz
from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Node(Base):
    """节点"""

    __tablename__ = "framework_node"
    name: Mapped[str] = mapped_column(String(255))
    """节点名称"""
    description: Mapped[str] = mapped_column(String(2000))
    """节点描述"""
    service_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("framework_service.id"))
    """所属服务ID"""
    call_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("framework_call.id"))
    """所属CallID"""
    known_params: Mapped[dict[str, Any]] = mapped_column(JSONB)
    """已知的用于Call部分的参数，独立于输入和输出之外"""
    override_input: Mapped[dict[str, Any]] = mapped_column(JSONB)
    """Node的输入Schema；用于描述Call的参数中特定的字段"""
    override_output: Mapped[dict[str, Any]] = mapped_column(JSONB)
    """Node的输出Schema；用于描述Call的输出中特定的字段"""
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default_factory=uuid.uuid4)
    """节点ID"""
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default_factory=lambda: datetime.now(tz=pytz.timezone("Asia/Shanghai")),
        onupdate=lambda: datetime.now(tz=pytz.timezone("Asia/Shanghai")),
    )
    """节点更新时间"""
