"""问答对 数据库表"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import VARCHAR, BigInteger, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
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
    content: Mapped[str] = mapped_column(VARCHAR)
    """问答对数据"""
    key: Mapped[dict[str, Any]] = mapped_column(JSONB)
    """问答对密钥"""
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default_factory=lambda: uuid.uuid4(),
    )
    """问答对ID"""
    createdAt: Mapped[datetime] = mapped_column(  # noqa: N815
        DateTime(timezone=True), default_factory=lambda: datetime.now(tz=UTC),
    )
    """问答对创建时间"""


class RecordMetadata(Base):
    """问答对元数据"""

    __tablename__ = "framework_record_metadata"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, init=False)
    """主键ID"""
    record_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("framework_record.id"), unique=True)
    """问答对ID"""
    timeCost: Mapped[float] = mapped_column(Float, default=0)  # noqa: N815
    """问答对耗时"""
    inputTokens: Mapped[int] = mapped_column(Integer, default=0)  # noqa: N815
    """问答对输入token数"""
    outputTokens: Mapped[int] = mapped_column(Integer, default=0)  # noqa: N815
    """问答对输出token数"""
    featureSwitch: Mapped[dict[str, Any]] = mapped_column(JSONB, default={})  # noqa: N815
    """问答对功能开关"""


class RecordFootNote(Base):
    """问答对脚注"""

    __tablename__ = "framework_record_foot_note"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, init=False)
    """主键ID"""
    record_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("framework_record.id"))
    """问答对ID"""
    releatedId: Mapped[str] = mapped_column(String, default="")  # noqa: N815
    """脚注数字"""
    insertPosition: Mapped[int] = mapped_column(Integer, default=0)  # noqa: N815
    """插入位置"""
    footSource: Mapped[str] = mapped_column(String, default="")  # noqa: N815
    """脚注来源"""
    footType: Mapped[str] = mapped_column(String, default="")  # noqa: N815
    """脚注类型"""
