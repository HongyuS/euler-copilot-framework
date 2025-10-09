"""SQLAlchemy模型基类"""

from typing import Any, ClassVar

from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass


class Base(MappedAsDataclass, DeclarativeBase):
    """SQLAlchemy模型基类"""

    # 生成文档时需要启动这个参数，否则会触发重复导入告警
    __table_args__: ClassVar[dict[str, Any]] = {"extend_existing": True}

