"""会话相关 数据库表"""

import secrets
from datetime import UTC, datetime, timedelta
from enum import Enum as PyEnum

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class SessionType(PyEnum):
    """会话类型"""

    ACCESS_TOKEN = "access_token"  # noqa: S105
    REFRESH_TOKEN = "refresh_token"  # noqa: S105
    PLUGIN_TOKEN = "plugin_token"  # noqa: S105
    CODE = "code"


class Session(Base):
    """会话"""

    __tablename__ = "framework_session"
    userSub: Mapped[str] = mapped_column(ForeignKey("framework_user.userSub"))  # noqa: N815
    """用户名"""
    validUntil: Mapped[datetime] = mapped_column(  # noqa: N815
        DateTime(timezone=True),
        default_factory=lambda: datetime.now(tz=UTC) + timedelta(days=30),
    )
    """有效期"""
    id: Mapped[str] = mapped_column(String(255), primary_key=True, default_factory=lambda: secrets.token_hex(16))
    """会话ID"""
    sessionType: Mapped[SessionType] = mapped_column(Enum(SessionType), default=SessionType.ACCESS_TOKEN)  # noqa: N815
    """会话类型"""
    ip: Mapped[str] = mapped_column(String(255), default="")
    """IP地址"""
    nonce: Mapped[str] = mapped_column(String(255), default="")
    """随机值"""
    pluginId: Mapped[str] = mapped_column(String(255), default="")  # noqa: N815
    """(AccessToken) 插件ID"""
    token: Mapped[str] = mapped_column(String(2000), default="")
    """(AccessToken) Token信息"""


class SessionActivity(Base):
    """会话活动"""

    __tablename__ = "framework_session_activity"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    """主键ID"""
    userSub: Mapped[str] = mapped_column(ForeignKey("framework_user.userSub"))  # noqa: N815
    """用户名"""
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    """时间戳"""
