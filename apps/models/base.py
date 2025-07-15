"""SQLAlchemy模型基类"""

from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass


class Base(MappedAsDataclass, DeclarativeBase):
    """SQLAlchemy模型基类"""

