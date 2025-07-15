"""文件 数据库表"""

import uuid
from datetime import datetime

import pytz
from sqlalchemy import DateTime, Float, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Document(Base):
    """文件"""

    __tablename__ = "framework_document"
    user_sub: Mapped[str] = mapped_column(ForeignKey("framework_user.user_sub"))
    """用户ID"""
    name: Mapped[str] = mapped_column(String(255))
    """文件名称"""
    type: Mapped[str] = mapped_column(String(100))
    """文件类型"""
    size: Mapped[float] = mapped_column(Float)
    """文件大小"""
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("framework_conversation.id"))
    """所属对话的ID"""
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default_factory=uuid.uuid4,
    )
    """文件的ID"""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default_factory=lambda: datetime.now(tz=pytz.timezone("Asia/Shanghai")),
    )
    """文件的创建时间"""
    __table_args__ = (
        Index("idx_user_sub_conversation_id", "user_sub", "conversation_id"),
    )
