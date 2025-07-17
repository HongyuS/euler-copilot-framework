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
    userSub: Mapped[str] = mapped_column(ForeignKey("framework_user.userSub"))  # noqa: N815
    """用户名"""
    conversationId: Mapped[uuid.UUID] = mapped_column(ForeignKey("framework_conversation.id"))  # noqa: N815
    """对话ID"""
    taskId: Mapped[uuid.UUID] = mapped_column(ForeignKey("framework_task.id"))  # noqa: N815
    """任务ID"""
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default_factory=lambda: uuid.uuid4(),
    )
    """问答对ID"""
    createdAt: Mapped[datetime] = mapped_column(  # noqa: N815
        DateTime(timezone=True), default_factory=lambda: datetime.now(tz=pytz.timezone("Asia/Shanghai")),
    )
    """问答对创建时间"""


class RecordDocument(Base):
    """问答对关联的文件"""

    __tablename__ = "framework_record_document"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, init=False)
    """主键ID"""
    recordId: Mapped[uuid.UUID] = mapped_column(ForeignKey("framework_record.id"))  # noqa: N815
    """问答对ID"""
    documentId: Mapped[uuid.UUID] = mapped_column(ForeignKey("framework_document.id"))  # noqa: N815
    """文件ID"""
