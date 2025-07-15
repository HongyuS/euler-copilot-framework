"""插件 数据库表"""

import uuid
from datetime import datetime

import pytz
from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.schemas.enum_var import PermissionType

from .base import Base


class Service(Base):
    """插件"""

    __tablename__ = "framework_service"
    name: Mapped[str] = mapped_column(String(255))
    """插件名称"""
    description: Mapped[str] = mapped_column(String(2000))
    """插件描述"""
    author: Mapped[str] = mapped_column(ForeignKey("framework_user.user_sub"))
    """插件作者"""
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default_factory=lambda: datetime.now(tz=pytz.timezone("Asia/Shanghai")),
        onupdate=lambda: datetime.now(tz=pytz.timezone("Asia/Shanghai")),
    )
    """插件更新时间"""
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default_factory=uuid.uuid4)
    """插件ID"""
    icon_path: Mapped[str] = mapped_column(String(255), default="")
    """插件图标路径"""
    permission: Mapped[PermissionType] = mapped_column(Enum(PermissionType), default=PermissionType.PUBLIC)
    """权限类型"""


class ServiceACL(Base):
    """插件权限"""

    __tablename__ = "framework_service_acl"
    service_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("framework_service.id"))
    """关联的插件ID"""
    user_sub: Mapped[str] = mapped_column(ForeignKey("framework_user.user_sub"))
    """用户名"""
    action: Mapped[str] = mapped_column(String(255), default="")
    """操作类型（读/写）"""


class ServiceHashes(Base):
    """插件哈希"""

    __tablename__ = "framework_service_hashes"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, init=False)
    """主键ID"""
    service_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("framework_service.id"))
    """关联的插件ID"""
    file_path: Mapped[str] = mapped_column(String(255))
    """文件路径"""
    hash: Mapped[str] = mapped_column(String(255))
    """哈希值"""
