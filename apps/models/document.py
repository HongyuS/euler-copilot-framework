"""文件 数据库表"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Document(Base):
    """文件"""

    __tablename__ = "framework_document"
    userSub: Mapped[str] = mapped_column(String(50), ForeignKey("framework_user.userSub"), nullable=False)  # noqa: N815
    """用户ID"""
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    """文件名称"""
    extension: Mapped[str] = mapped_column(String(100), nullable=False)
    """文件类型"""
    size: Mapped[float] = mapped_column(Float, nullable=False)
    """文件大小"""
    conversationId: Mapped[uuid.UUID] = mapped_column(  # noqa: N815
        UUID(as_uuid=True), ForeignKey("framework_conversation.id"), nullable=False,
    )
    """所属对话的ID"""
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default_factory=uuid.uuid4,
    )
    """文件的ID"""
    createdAt: Mapped[datetime] = mapped_column(  # noqa: N815
        DateTime(timezone=True),
        default_factory=lambda: datetime.now(tz=UTC),
        nullable=False,
    )
    """文件的创建时间"""
    __table_args__ = (
        Index("idx_user_sub_conversation_id", "userSub", "conversationId"),
    )
