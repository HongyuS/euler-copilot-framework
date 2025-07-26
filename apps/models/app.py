"""应用 数据库表"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.schemas.enum_var import AppType, PermissionType

from .base import Base


class App(Base):
    """应用"""

    __tablename__ = "framework_app"
    name: Mapped[str] = mapped_column(String(255))
    """应用名称"""
    description: Mapped[str] = mapped_column(String(2000))
    """应用描述"""
    author: Mapped[str] = mapped_column(ForeignKey("framework_user.userSub"))
    """应用作者"""
    type: Mapped[AppType] = mapped_column(Enum(AppType))
    """应用类型"""
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default_factory=uuid.uuid4)
    """应用ID"""
    updatedAt: Mapped[datetime] = mapped_column(  # noqa: N815
        DateTime(timezone=True),
        default_factory=lambda: datetime.now(tz=UTC),
        onupdate=lambda: datetime.now(tz=UTC),
        index=True,
    )
    """应用更新时间"""
    iconPath: Mapped[str] = mapped_column(String(255), default="")  # noqa: N815
    """应用图标路径"""
    isPublished: Mapped[bool] = mapped_column(Boolean, default=False)  # noqa: N815
    """是否发布"""
    permission: Mapped[PermissionType] = mapped_column(Enum(PermissionType), default=PermissionType.PUBLIC)
    """权限类型"""
    __table_args__ = (
        Index("idx_published_updated_at", "isPublished", "updatedAt"),
        Index("idx_author_id_name", "author", "id", "name"),
    )


class AppACL(Base):
    """应用权限"""

    __tablename__ = "framework_app_acl"
    appId: Mapped[uuid.UUID] = mapped_column(ForeignKey("framework_app.id"))  # noqa: N815
    """关联的应用ID"""
    userSub: Mapped[str] = mapped_column(ForeignKey("framework_user.userSub"))  # noqa: N815
    """用户名"""
    action: Mapped[str] = mapped_column(String(255), default="")
    """操作类型（读/写）"""


class AppHashes(Base):
    """应用哈希"""

    __tablename__ = "framework_app_hashes"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, init=False)
    """主键ID"""
    appId: Mapped[uuid.UUID] = mapped_column(ForeignKey("framework_app.id"))  # noqa: N815
    """关联的应用ID"""
    filePath: Mapped[str] = mapped_column(String(255))  # noqa: N815
    """文件路径"""
    hash: Mapped[str] = mapped_column(String(255))
    """哈希值"""
