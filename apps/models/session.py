"""会话相关 数据库表"""

import uuid
from datetime import datetime, timedelta

import pytz
from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Session(Base):
    """会话"""

    __tablename__ = "framework_session"
    userSub: Mapped[str] = mapped_column(ForeignKey("framework_user.userSub"))  # noqa: N815
    """用户名"""
    validUntil: Mapped[datetime] = mapped_column(  # noqa: N815
        DateTime(timezone=True),
        default_factory=lambda: datetime.now(tz=pytz.timezone("Asia/Shanghai")) + timedelta(days=30),
    )
    """有效期"""
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default_factory=lambda: str(uuid.uuid4().hex))
    """会话ID"""


class SessionActivity(Base):
    """会话活动"""

    __tablename__ = "framework_session_activity"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    """主键ID"""
    userSub: Mapped[str] = mapped_column(ForeignKey("framework_user.userSub"))  # noqa: N815
    """用户名"""
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    """时间戳"""
