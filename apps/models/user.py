"""用户表"""

import enum
import uuid
from datetime import datetime
from hashlib import sha256

import pytz
from sqlalchemy import BigInteger, Boolean, DateTime, Enum, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class User(Base):
    """用户表"""

    __tablename__ = "framework_user"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, init=False)
    """用户ID"""
    user_sub: Mapped[str] = mapped_column(String(50), index=True, unique=True)
    """用户名"""
    last_login: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default_factory=lambda: datetime.now(tz=pytz.timezone("Asia/Shanghai")),
    )
    """用户最后一次登录时间"""
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    """用户是否活跃"""
    is_whitelisted: Mapped[bool] = mapped_column(Boolean, default=False)
    """用户是否白名单"""
    credit: Mapped[int] = mapped_column(Integer, default=100)
    """用户风控分"""
    personal_token: Mapped[str] = mapped_column(
        String(100), default_factory=lambda: sha256(str(uuid.uuid4()).encode()).hexdigest()[:16],
    )
    """用户个人令牌"""
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    """用户是否管理员"""


class UserFavoriteType(str, enum.Enum):
    """用户收藏类型"""

    app = "app"
    service = "service"


class UserFavorite(Base):
    """用户收藏"""

    __tablename__ = "framework_user_favorite"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, init=False)
    """用户收藏ID"""
    user_sub: Mapped[str] = mapped_column(String(50), index=True, foreign_key="framework_user.user_sub")
    """用户名"""
    type: Mapped[UserFavoriteType] = mapped_column(Enum(UserFavoriteType))
    """收藏类型"""
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    """收藏项目ID（App/Service ID）"""


class UserAppUsage(Base):
    """用户应用使用情况"""

    __tablename__ = "framework_user_app_usage"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, init=False)
    """用户应用使用情况ID"""
    user_sub: Mapped[str] = mapped_column(String(50), index=True, foreign_key="framework_user.user_sub")
    """用户名"""
    app_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    """应用ID"""
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    """应用使用次数"""
    last_used: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default_factory=lambda: datetime.now(tz=pytz.timezone("Asia/Shanghai")),
    )
    """用户最后一次使用时间"""


class UserTag(Base):
    """用户标签"""

    __tablename__ = "framework_user_tag"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, init=False)
    """用户标签ID"""
    user_sub: Mapped[str] = mapped_column(String(50), index=True, foreign_key="framework_user.user_sub")
    """用户名"""
    tag: Mapped[int] = mapped_column(BigInteger, index=True, foreign_key="framework_tag.id")
    """标签ID"""
    count: Mapped[int] = mapped_column(Integer, default=0)
    """标签归类次数"""
