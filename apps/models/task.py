"""任务 数据库表"""

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.models.base import Base


class Task(Base):
    """任务"""

    __tablename__ = "framework_task"
    userSub: Mapped[str] = mapped_column(String(255), ForeignKey("framework_user.sub"))  # noqa: N815
    """用户ID"""
    conversationId: Mapped[uuid.UUID] = mapped_column(  # noqa: N815
        UUID(as_uuid=True), ForeignKey("framework_conversation.id"), nullable=False,
    )
    checkpointId: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("framework_executor_checkpoint.id"))  # noqa: N815
    """对话ID"""
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default_factory=uuid.uuid4)
    """任务ID"""


class ExecutorCheckpoint(Base):
    """执行器检查点"""

    __tablename__ = "framework_executor_checkpoint"

    taskId: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("framework_task.id"), nullable=False)  # noqa: N815
    """任务ID"""
    executorId: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)  # noqa: N815
    """执行器ID（例如工作流ID）"""
    executorName: Mapped[str] = mapped_column(String(255), nullable=False)  # noqa: N815
    """执行器名称（例如工作流名称）"""
    stepId: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)  # noqa: N815
    """步骤ID"""
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default_factory=uuid.uuid4)
    """检查点ID"""



class ExecutorHistory(Base):
    """执行器历史"""

    __tablename__ = "framework_executor_history"

    taskId: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("framework_task.id"), nullable=False)  # noqa: N815
    """任务ID"""
    executorId: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)  # noqa: N815
    """执行器ID（例如工作流ID）"""
    executorName: Mapped[str] = mapped_column(String(255))  # noqa: N815
    """执行器名称（例如工作流名称）"""
    stepId: Mapped[str] = mapped_column(String(36))  # noqa: N815
    """步骤ID"""
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default_factory=uuid.uuid4)
    """执行器历史ID"""
