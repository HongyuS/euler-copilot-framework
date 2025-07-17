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
    recordId: Mapped[uuid.UUID] = mapped_column(ForeignKey("framework_record.id"))  # noqa: N815
    """问答对ID"""
    userSub: Mapped[str] = mapped_column(ForeignKey("framework_user.userSub"))  # noqa: N815
    """用户名"""
    commentType: Mapped[CommentType] = mapped_column(Enum(CommentType))  # noqa: N815
    """点赞点踩"""
    feedbackType: Mapped[list[str]] = mapped_column(ARRAY(String(100)))  # noqa: N815
    """投诉类别"""
    feedbackLink: Mapped[str] = mapped_column(String(1000))  # noqa: N815
    """投诉链接"""
    feedbackContent: Mapped[str] = mapped_column(String(1000))  # noqa: N815
    """投诉内容"""
    createdAt: Mapped[datetime] = mapped_column(  # noqa: N815
        DateTime(timezone=True), default_factory=lambda: datetime.now(tz=pytz.timezone("Asia/Shanghai")),
    )
    """评论创建时间"""
