"""节点 数据库表"""

import uuid
from datetime import datetime
from typing import Any

import pytz
from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class NodeInfo(Base):
    """节点"""

    __tablename__ = "framework_node"
    name: Mapped[str] = mapped_column(String(255))
    """节点名称"""
    description: Mapped[str] = mapped_column(String(2000))
    """节点描述"""
    serviceId: Mapped[uuid.UUID] = mapped_column(ForeignKey("framework_service.id"))  # noqa: N815
    """所属服务ID"""
    callId: Mapped[str] = mapped_column(ForeignKey("framework_call.id"))  # noqa: N815
    """所属CallID"""
    knownParams: Mapped[dict[str, Any]] = mapped_column(JSONB)  # noqa: N815
    """已知的用于Call部分的参数，独立于输入和输出之外"""
    overrideInput: Mapped[dict[str, Any]] = mapped_column(JSONB)  # noqa: N815
    """Node的输入Schema；用于描述Call的参数中特定的字段"""
    overrideOutput: Mapped[dict[str, Any]] = mapped_column(JSONB)  # noqa: N815
    """Node的输出Schema；用于描述Call的输出中特定的字段"""
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default_factory=uuid.uuid4)
    """节点ID"""
    updatedAt: Mapped[datetime] = mapped_column(  # noqa: N815
        DateTime(timezone=True),
        default_factory=lambda: datetime.now(tz=pytz.timezone("Asia/Shanghai")),
        onupdate=lambda: datetime.now(tz=pytz.timezone("Asia/Shanghai")),
    )
    """节点更新时间"""


class CallInfo(Base):
    """工具信息"""

    __tablename__ = "framework_call"

