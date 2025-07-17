# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Record数据结构"""

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from .collection import (
    Document,
)
from .enum_var import CommentType, StepStatus


class RecordDocument(Document):
    """GET /api/record/{conversation_id} Result中的document数据结构"""

    id: str = Field(alias="_id", default="")
    abstract: str = Field(default="", description="文档摘要")
    user_sub: None = None
    associated: Literal["question", "answer"]

    class Config:
        """配置"""

        populate_by_name = True


class RecordFlowStep(BaseModel):
    """Record表子项：flow的单步数据结构"""

    step_id: str = Field(alias="stepId")
    step_status: StepStatus = Field(alias="stepStatus")
    input: dict[str, Any]
    output: dict[str, Any]


class RecordFlow(BaseModel):
    """Flow的执行信息"""

    id: str
    record_id: str = Field(alias="recordId")
    flow_id: str = Field(alias="flowId")
    step_num: int = Field(alias="stepNum")
    steps: list[RecordFlowStep]


class RecordContent(BaseModel):
    """Record表子项：Record加密前的数据结构"""

    question: str
    answer: str
    data: dict[str, Any] = {}
    facts: list[str] = Field(description="[运行后修改]与Record关联的事实信息", default=[])


class FootNoteMetaData(BaseModel):
    """Record表子项：Record的脚注元信息"""

    releated_id: str = Field(default="", description="相关ID", alias="releatedId")
    insert_position: int = Field(default=0, description="插入位置", alias="insertPosition")
    foot_source: str = Field(default="", description="脚注来源", alias="footSource")
    foot_type: str = Field(default="", description="脚注类型", alias="footType")


class RecordMetadata(BaseModel):
    """Record表子项：Record的元信息"""

    input_tokens: int = Field(default=0, alias="inputTokens")
    output_tokens: int = Field(default=0, alias="outputTokens")
    time_cost: float = Field(default=0, alias="timeCost")
    feature: dict[str, Any] = {}
    foot_note_metadata_list: list[FootNoteMetaData] = Field(
        default=[], alias="footNoteMetadataList", description="脚注元信息列表")


class RecordComment(BaseModel):
    """Record表子项：Record的评论信息"""

    comment: CommentType = Field(default=CommentType.NONE)
    feedback_type: list[str] = Field(default=[], alias="dislike_reason")
    feedback_link: str = Field(default="", alias="reason_link")
    feedback_content: str = Field(default="", alias="reason_description")
    feedback_time: float = Field(default_factory=lambda: round(datetime.now(tz=UTC).timestamp(), 3))


class RecordData(BaseModel):
    """GET /api/record/{conversation_id} Result内元素数据结构"""

    id: str
    group_id: str = Field(alias="groupId")
    conversation_id: str = Field(alias="conversationId")
    task_id: str = Field(alias="taskId")
    document: list[RecordDocument] = []
    flow: RecordFlow | None = None
    content: RecordContent
    metadata: RecordMetadata
    comment: CommentType = Field(default=CommentType.NONE)
    created_at: float = Field(alias="createdAt")


class RecordGroupDocument(BaseModel):
    """RecordGroup关联的文件"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="_id")
    name: str = Field(description="文档名称")
    abstract: str = Field(description="文档摘要", default="")
    extension: str = Field(description="文档扩展名", default="")
    size: int = Field(description="文档大小，单位是KB", default=0)
    associated: Literal["question", "answer"]


class Record(RecordData):
    """问答，用于保存在MongoDB中"""

    user_sub: str
    key: dict[str, Any] = {}
    content: str
    comment: RecordComment = Field(default=RecordComment())
    flow: list[str] = Field(default=[])
