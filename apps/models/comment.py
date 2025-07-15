"""评论 数据库表"""

import uuid
from datetime import datetime

import pytz
from sqlalchemy import ARRAY, BigInteger, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from apps.schemas.enum_var import CommentType

from .base import Base


class Comment(Base):
    """评论"""

    __tablename__ = "framework_comment"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, init=False)
    """主键ID"""
    record_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("framework_record.id"))
    """问答对ID"""
    user_sub: Mapped[str] = mapped_column(ForeignKey("framework_user.user_sub"))
    """用户名"""
    comment_type: Mapped[CommentType] = mapped_column(Enum(CommentType))
    """点赞点踩"""
    feedback_type: Mapped[list[str]] = mapped_column(ARRAY(String(100)))
    """投诉类别"""
    feedback_link: Mapped[str] = mapped_column(String(1000))
    """投诉链接"""
    feedback_content: Mapped[str] = mapped_column(String(1000))
    """投诉内容"""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default_factory=lambda: datetime.now(tz=pytz.timezone("Asia/Shanghai")),
    )
    """评论创建时间"""
