"""Flow 数据库表"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Flow(Base):
    """Flow"""

    __tablename__ = "framework_flow"
    appId: Mapped[uuid.UUID] = mapped_column(ForeignKey("framework_app.id"))  # noqa: N815
    """所属App的ID"""
    name: Mapped[str] = mapped_column(String(255))
    """Flow的名称"""
    description: Mapped[str] = mapped_column(String(2000))
    """Flow的描述"""
    path: Mapped[str] = mapped_column(String(255))
    """Flow的路径"""
    debug: Mapped[bool] = mapped_column(Boolean, default=False)
    """是否经过调试"""
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    """是否启用"""
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default_factory=uuid.uuid4,
    )
    """Flow的ID"""
    updatedAt: Mapped[datetime] = mapped_column(  # noqa: N815
        DateTime(timezone=True),
        default_factory=lambda: datetime.now(tz=UTC),
        onupdate=lambda: datetime.now(tz=UTC),
    )
    """Flow的更新时间"""
    __table_args__ = (
        Index("idx_app_id_id", "appId", "id"),
        Index("idx_app_id_name", "appId", "name"),
    )


class FlowContext(Base):
    """Flow上下文"""

    __tablename__ = "framework_flow_context"
    flowId: Mapped[uuid.UUID] = mapped_column(ForeignKey("framework_flow.id"), index=True)  # noqa: N815
    """所属Flow的ID"""
    context: Mapped[str] = mapped_column(String(2000))
    """上下文"""
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default_factory=uuid.uuid4,
    )
    """Flow上下文的ID"""
