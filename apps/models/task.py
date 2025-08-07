"""任务 数据库表"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.schemas.enum_var import FlowStatus, StepStatus

from .base import Base


class Task(Base):
    """任务"""

    __tablename__ = "framework_task"
    userSub: Mapped[str] = mapped_column(String(255), ForeignKey("framework_user.sub"))  # noqa: N815
    """用户ID"""
    conversationId: Mapped[uuid.UUID] = mapped_column(  # noqa: N815
        UUID(as_uuid=True), ForeignKey("framework_conversation.id"), nullable=False,
    )
    """对话ID"""
    checkpointId: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("framework_executor_checkpoint.id"))  # noqa: N815
    """检查点ID"""
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default_factory=uuid.uuid4)
    """任务ID"""
    updatedAt: Mapped[datetime] = mapped_column(  # noqa: N815
        DateTime(timezone=True), nullable=False, default_factory=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class TaskRuntime(Base):
    """任务运行时数据"""

    __tablename__ = "framework_task_runtime"

    taskId: Mapped[uuid.UUID] = mapped_column(  # noqa: N815
        UUID(as_uuid=True), ForeignKey("framework_task.id"), nullable=False,
        primary_key=True,
    )
    """任务ID"""
    inputToken: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # noqa: N815
    """输入Token"""
    outputToken: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # noqa: N815
    """输出Token"""
    time: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    """时间"""
    fullTime: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)  # noqa: N815
    """完整时间成本"""
    userInput: Mapped[str] = mapped_column(Text, nullable=False, default="")  # noqa: N815
    """用户输入"""
    fullAnswer: Mapped[str] = mapped_column(Text, nullable=False, default="")  # noqa: N815
    """完整输出"""
    fact: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=[])
    """记忆"""
    reasoning: Mapped[str] = mapped_column(Text, nullable=False, default="")
    """中间推理"""
    filledSlot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default={})  # noqa: N815
    """计划"""
    document: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default={})
    """关联文档"""


class ExecutorCheckpoint(Base):
    """执行器检查点"""

    __tablename__ = "framework_executor_checkpoint"

    # 执行器级数据
    taskId: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("framework_task.id"), nullable=False)  # noqa: N815
    """任务ID"""
    appId: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)  # noqa: N815
    """应用ID"""
    executorId: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)  # noqa: N815
    """执行器ID（例如工作流ID）"""
    executorName: Mapped[str] = mapped_column(String(255), nullable=False)  # noqa: N815
    """执行器名称（例如工作流名称）"""
    executorStatus: Mapped[FlowStatus] = mapped_column(Enum(FlowStatus), nullable=False)  # noqa: N815
    """执行器状态"""
    # 步骤级数据
    stepId: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)  # noqa: N815
    """步骤ID"""
    stepName: Mapped[str] = mapped_column(String(255), nullable=False)  # noqa: N815
    """步骤名称"""
    stepStatus: Mapped[StepStatus] = mapped_column(Enum(StepStatus), nullable=False)  # noqa: N815
    """步骤状态"""
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default_factory=uuid.uuid4)
    """检查点ID"""
    executorDescription: Mapped[str] = mapped_column(Text, nullable=False, default="")  # noqa: N815
    """执行器描述"""
    stepDescription: Mapped[str] = mapped_column(Text, nullable=False, default="")  # noqa: N815
    """步骤描述"""
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default={})
    """步骤额外数据"""


class ExecutorHistory(Base):
    """执行器历史"""

    __tablename__ = "framework_executor_history"

    taskId: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("framework_task.id"), nullable=False)  # noqa: N815
    """任务ID"""
    executorId: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)  # noqa: N815
    """执行器ID（例如工作流ID）"""
    executorName: Mapped[str] = mapped_column(String(255))  # noqa: N815
    """执行器名称（例如工作流名称）"""
    executorStatus: Mapped[FlowStatus] = mapped_column(Enum(FlowStatus), nullable=False)  # noqa: N815
    """执行器状态"""
    stepId: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)  # noqa: N815
    """步骤ID"""
    stepName: Mapped[str] = mapped_column(String(255), nullable=False)  # noqa: N815
    """步骤名称"""
    stepStatus: Mapped[StepStatus] = mapped_column(Enum(StepStatus), nullable=False)  # noqa: N815
    """步骤状态"""
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default_factory=uuid.uuid4)
    """执行器历史ID"""
    stepDescription: Mapped[str] = mapped_column(Text, nullable=False, default="")  # noqa: N815
    """步骤描述"""
    inputData: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default={})  # noqa: N815
    """步骤输入数据"""
    outputData: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default={})  # noqa: N815
    """步骤输出数据"""
    extraData: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default={})  # noqa: N815
    """步骤额外数据"""
    updatedAt: Mapped[datetime] = mapped_column(  # noqa: N815
        DateTime(timezone=True), nullable=False, default_factory=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    """更新时间"""
