"""黑名单 数据库表结构"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Blacklist(Base):
    """黑名单"""

    __tablename__ = "framework_blacklist"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, init=False)
    """主键ID"""
    recordId: Mapped[uuid.UUID] = mapped_column(  # noqa: N815
        UUID(as_uuid=True), ForeignKey("framework_record.id"), nullable=False, index=True,
    )
    """关联的问答对ID"""
    question: Mapped[str] = mapped_column(Text, nullable=False)
    """黑名单问题"""
    answer: Mapped[str | None] = mapped_column(Text, default=None, nullable=False)
    """应做出的固定回答"""
    isAudited: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # noqa: N815
    """黑名单是否生效"""
    reasonType: Mapped[str] = mapped_column(String(255), default="", nullable=False)  # noqa: N815
    """举报类型"""
    reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    """举报原因"""
    updatedAt: Mapped[DateTime] = mapped_column(  # noqa: N815
        DateTime,
        default_factory=lambda: datetime.now(tz=UTC),
        init=False,
        nullable=False,
    )
    """更新时间"""
