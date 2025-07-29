"""任务 数据库表"""

import uuid

from sqlalchemy import Column, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.models.base import Base


class Task(Base):
    """任务"""

    __tablename__ = "framework_task"
    userSub: Mapped[str] = mapped_column(String(255), ForeignKey("framework_user.sub"))  # noqa: N815
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default_factory=uuid.uuid4)




class ExecutorCheckpoint(Base):
    """执行器检查点"""

    __tablename__ = "framework_executor_checkpoint"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("framework_task.id"))
    flow_id: Mapped[str] = mapped_column(String(36), ForeignKey("framework_flow.id"))
    flow_name: Mapped[str] = mapped_column(String(255))
    step_id: Mapped[str] = mapped_column(String(36))