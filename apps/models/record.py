"""问答对 数据库表"""

import uuid
from datetime import datetime

import pytz
from sqlalchemy import BigInteger, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Record(Base):
    """问答对"""

    __tablename__ = "framework_record"
    user_sub: Mapped[str] = mapped_column(ForeignKey("framework_user.user_sub"))
    """用户名"""
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("framework_conversation.id"))
    """对话ID"""
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("framework_task.id"))
    """任务ID"""
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default_factory=lambda: uuid.uuid4(),
    )
    """问答对ID"""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default_factory=lambda: datetime.now(tz=pytz.timezone("Asia/Shanghai")),
    )
    """问答对创建时间"""


class RecordDocument(Base):
    """问答对关联的文件"""

    __tablename__ = "framework_record_document"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, init=False)
    """主键ID"""
    record_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("framework_record.id"))
    """问答对ID"""
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("framework_document.id"))
    """文件ID"""
