"""MCP 相关 数据库表"""

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class MCP(Base):
    """MCP"""

    __tablename__ = "framework_mcp"
    