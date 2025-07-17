"""对话 数据库表"""

import uuid
from datetime import datetime

import pytz
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.constants import NEW_CHAT

from .base import Base


class Conversation(Base):
    """对话"""

    __tablename__ = "framework_conversation"
    userSub: Mapped[str] = mapped_column(ForeignKey("framework_user.userSub"))  # noqa: N815
    """用户名"""
    appId: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("framework_app.id"), nullable=True)  # noqa: N815
    """对话使用的App的ID"""
    title: Mapped[str] = mapped_column(String(255), default=NEW_CHAT)
    """对话标题"""
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default_factory=lambda: uuid.uuid4(),
    )
    """对话ID"""
    createdAt: Mapped[datetime] = mapped_column(  # noqa: N815
        DateTime(timezone=True), default_factory=lambda: datetime.now(tz=pytz.timezone("Asia/Shanghai")),
    )
    """对话创建时间"""
    isTemporary: Mapped[bool] = mapped_column(Boolean, default=False)  # noqa: N815
    """是否为临时对话"""


class ConversationDocument(Base):
    """对话所用的临时文件"""

    __tablename__ = "framework_conversation_document"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, init=False)
    """主键ID"""
    conversationId: Mapped[uuid.UUID] = mapped_column(ForeignKey("framework_conversation.id"))  # noqa: N815
    """对话ID"""
    documentId: Mapped[uuid.UUID] = mapped_column(ForeignKey("framework_document.id"))  # noqa: N815
    """文件ID"""
    isUnused: Mapped[bool] = mapped_column(Boolean, default=True)  # noqa: N815
    """是否未使用"""
