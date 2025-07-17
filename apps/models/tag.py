"""用户标签 数据库表"""

from datetime import datetime

import pytz
from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Tag(Base):
    """用户标签"""

    __tablename__ = "framework_tag"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, init=False)
    """标签ID"""
    name: Mapped[str] = mapped_column(String(255), index=True, unique=True)
    """标签名称"""
    definition: Mapped[str] = mapped_column(String(2000))
    """标签定义"""
    updatedAt: Mapped[datetime] = mapped_column(  # noqa: N815
        DateTime(timezone=True),
        default_factory=lambda: datetime.now(tz=pytz.timezone("Asia/Shanghai")),
        onupdate=lambda: datetime.now(tz=pytz.timezone("Asia/Shanghai")),
    )
    """标签的更新时间"""
