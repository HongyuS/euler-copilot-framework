"""MCP 相关 数据库表"""

import uuid
from datetime import UTC, datetime
from enum import Enum as PyEnum
from hashlib import shake_128
from typing import Any

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class MCPInstallStatus(str, PyEnum):
    """MCP 服务状态"""

    INSTALLING = "installing"
    READY = "ready"
    FAILED = "failed"


class MCPType(str, PyEnum):
    """MCP 类型"""

    SSE = "sse"
    STDIO = "stdio"
    STREAMABLE = "stream"


class MCPInfo(Base):
    """MCP"""

    __tablename__ = "framework_mcp"
    name: Mapped[str] = mapped_column(String(255))
    """MCP 名称"""
    overview: Mapped[str] = mapped_column(String(2000))
    """MCP 概述"""
    description: Mapped[str] = mapped_column(String(65535))
    """MCP 描述"""
    author: Mapped[str] = mapped_column(ForeignKey("framework_user.userSub"))
    """MCP 创建者"""
    config: Mapped[dict[str, Any]] = mapped_column(JSONB)
    """MCP 配置"""
    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    """MCP ID"""
    updatedAt: Mapped[datetime] = mapped_column(  # noqa: N815
        DateTime(timezone=True),
        default_factory=lambda: datetime.now(tz=UTC),
        onupdate=lambda: datetime.now(tz=UTC),
    )
    """MCP 更新时间"""
    status: Mapped[MCPInstallStatus] = mapped_column(Enum(MCPInstallStatus), default=MCPInstallStatus.INSTALLING)
    """MCP 状态"""
    mcpType: Mapped[MCPType] = mapped_column(Enum(MCPType), default=MCPType.STDIO)  # noqa: N815
    """MCP 类型"""


class MCPActivated(Base):
    """MCP 激活用户"""

    __tablename__ = "framework_mcp_activated"
    mcpId: Mapped[str] = mapped_column(ForeignKey("framework_mcp.id"), index=True, unique=True)  # noqa: N815
    """MCP ID"""
    userSub: Mapped[str] = mapped_column(ForeignKey("framework_user.userSub"))  # noqa: N815
    """用户ID"""
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, init=False)
    """主键ID"""


class MCPTools(Base):
    """MCP 工具"""

    __tablename__ = "framework_mcp_tools"
    mcpId: Mapped[str] = mapped_column(ForeignKey("framework_mcp.id"), index=True)  # noqa: N815
    """MCP ID"""
    toolName: Mapped[str] = mapped_column(String(255))  # noqa: N815
    """MCP 工具名称"""
    description: Mapped[str] = mapped_column(String(65535))
    """MCP 工具描述"""
    inputSchema: Mapped[dict[str, Any]] = mapped_column(JSONB)  # noqa: N815
    """MCP 工具输入参数"""
    outputSchema: Mapped[dict[str, Any]] = mapped_column(JSONB)  # noqa: N815
    """MCP 工具输出参数"""
    id: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
        default_factory=lambda: shake_128(uuid.uuid4().bytes).hexdigest(8),
    )
    """主键ID"""
