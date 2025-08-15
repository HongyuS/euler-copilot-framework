"""Flow 数据库表"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Flow(Base):
    """Flow"""

    __tablename__ = "framework_flow"
    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    """Flow的ID"""
    appId: Mapped[uuid.UUID] = mapped_column(  # noqa: N815
        UUID(as_uuid=True),
        ForeignKey("framework_app.id"),
        nullable=False,
        index=True,
    )
    """所属App的ID"""
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    """Flow的名称"""
    description: Mapped[str] = mapped_column(Text, nullable=False)
    """Flow的描述"""
    path: Mapped[str] = mapped_column(String(255), nullable=False)
    """Flow的路径"""
    debug: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    """是否经过调试"""
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    """是否启用"""
    updatedAt: Mapped[datetime] = mapped_column(  # noqa: N815
        DateTime(timezone=True),
        default_factory=lambda: datetime.now(tz=UTC),
        onupdate=lambda: datetime.now(tz=UTC),
        nullable=False,
    )
    """Flow的更新时间"""
    __table_args__ = (
        Index("idx_app_id_id", "appId", "id"),
        Index("idx_app_id_name", "appId", "name"),
    )
