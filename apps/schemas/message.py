# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""队列中的消息结构"""

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from apps.schemas.enum_var import EventType, ExecutorStatus, StepStatus

from .record import RecordMetadata


class FlowParams(BaseModel):
    """流执行过程中的参数补充"""

    content: dict[str, Any] = Field(default={}, description="流执行过程中的参数补充内容")
    description: str = Field(default="", description="流执行过程中的参数补充描述")


class HeartbeatData(BaseModel):
    """心跳事件的数据结构"""

    event: str = Field(
        default=EventType.HEARTBEAT.value, description="支持的事件类型",
    )


class MessageFlow(BaseModel):
    """消息中有关Flow信息的部分"""

    app_id: uuid.UUID = Field(description="插件ID", alias="appId")
    flow_id: str = Field(description="Flow ID", alias="flowId")
    flow_name: str = Field(description="Flow名称", alias="flowName")
    flow_status: ExecutorStatus = Field(description="Flow状态", alias="flowStatus", default=ExecutorStatus.UNKNOWN)
    step_id: uuid.UUID = Field(description="当前步骤ID", alias="stepId")
    step_name: str = Field(description="当前步骤名称", alias="stepName")
    sub_step_id: str | None = Field(description="当前子步骤ID", alias="subStepId", default=None)
    sub_step_name: str | None = Field(description="当前子步骤名称", alias="subStepName", default=None)
    step_status: StepStatus = Field(description="当前步骤状态", alias="stepStatus")
    step_description: str | None = Field(
        description="当前步骤描述",
        alias="stepDescription",
        default=None,
    )


class MessageMetadata(RecordMetadata):
    """消息的元数据"""

    feature: None = None


class InitContentFeature(BaseModel):
    """init消息的feature"""

    max_tokens: int = Field(description="最大生成token数", ge=0, alias="maxTokens")
    context_num: int = Field(description="上下文消息数量", le=10, ge=0, alias="contextNum")
    enable_feedback: bool = Field(description="是否启用反馈", alias="enableFeedback")
    enable_regenerate: bool = Field(description="是否启用重新生成", alias="enableRegenerate")


class InitContent(BaseModel):
    """init消息的content"""

    feature: InitContentFeature = Field(description="问答功能开关")
    created_at: float = Field(description="创建时间", alias="createdAt")


class TextAddContent(BaseModel):
    """text.add消息的content"""

    text: str = Field(min_length=1, description="流式生成的文本内容")


class DocumentAddContent(BaseModel):
    """document.add消息的content"""

    document_id: str = Field(description="文档UUID", alias="documentId")
    document_order: int = Field(description="文档在对话中的顺序，从1开始", alias="documentOrder")
    document_author: str = Field(description="文档作者", alias="documentAuthor", default="")
    document_name: str = Field(description="文档名称", alias="documentName")
    document_abstract: str = Field(description="文档摘要", alias="documentAbstract", default="")
    document_type: str = Field(description="文档MIME类型", alias="documentType", default="")
    document_size: float = Field(ge=0, description="文档大小，单位是KB，保留两位小数", alias="documentSize", default=0)
    created_at: float = Field(
        description="文档创建时间，单位是秒", alias="createdAt",
        default_factory=lambda: round(datetime.now(tz=UTC).timestamp(), 3),
    )


class FlowStartContent(BaseModel):
    """flow.start消息的content"""

    question: str = Field(description="用户问题")
    params: dict[str, Any] | None = Field(description="预先提供的参数", default=None)


class MessageBase(HeartbeatData):
    """基础消息事件结构"""

    id: str = Field(min_length=36, max_length=36)
    conversation_id: uuid.UUID = Field(min_length=36, max_length=36, alias="conversationId")
    task_id: uuid.UUID = Field(min_length=36, max_length=36, alias="taskId")
    flow: MessageFlow | None = None
    content: Any | None = Field(default=None, description="消息内容")
    metadata: MessageMetadata
