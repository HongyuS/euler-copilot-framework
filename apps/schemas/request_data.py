# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""FastAPI 请求体"""

import uuid

from pydantic import BaseModel, Field

from .enum_var import LanguageType
from .flow_topology import FlowItem
from .message import FlowParams


class RequestDataApp(BaseModel):
    """模型对话中包含的app信息"""

    app_id: uuid.UUID = Field(description="应用ID", alias="appId")
    flow_id: str | None = Field(default=None, description="Flow ID", alias="flowId")
    params: FlowParams | None = Field(default=None, description="流执行过程中的参数补充", alias="params")


class RequestData(BaseModel):
    """POST /api/chat 请求的总的数据结构"""

    question: str = Field(max_length=2000, description="用户输入")
    conversation_id: uuid.UUID = Field(
        default=uuid.UUID("00000000-0000-0000-0000-000000000000"), alias="conversationId", description="聊天ID",
    )
    language: LanguageType = Field(default=LanguageType.CHINESE, description="语言")
    files: list[str] = Field(default=[], description="文件列表")
    app: RequestDataApp | None = Field(default=None, description="应用")
    debug: bool = Field(default=False, description="是否调试")
    task_id: str | None = Field(default=None, alias="taskId", description="任务ID")
    llm_id: str = Field(alias="llmId", description="大模型ID")


class PostTagData(BaseModel):
    """添加领域"""

    tag: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., max_length=2000)


class PutFlowReq(BaseModel):
    """创建/修改流拓扑结构"""

    flow: FlowItem


class UpdateLLMReq(BaseModel):
    """更新大模型请求体"""

    llm_id: str | None = Field(default=None, description="大模型ID", alias="id")
    icon: str = Field(description="图标", default="")
    openai_base_url: str = Field(default="", description="OpenAI API Base URL", alias="openaiBaseUrl")
    openai_api_key: str = Field(default="", description="OpenAI API Key", alias="openaiApiKey")
    model_name: str = Field(default="", description="模型名称", alias="modelName")
    max_tokens: int = Field(default=8192, description="最大token数", alias="maxTokens")


class UpdateUserSelectedLLMReq(BaseModel):
    """更新用户特殊LLM请求体"""

    functionLLM: str = Field(description="Function Call LLM ID")  # noqa: N815
    embeddingLLM: str = Field(description="Embedding LLM ID")  # noqa: N815


class DeleteLLMReq(BaseModel):
    """删除大模型请求体"""

    llm_id: str = Field(description="大模型ID", alias="llmId")


class UpdateUserKnowledgebaseReq(BaseModel):
    """更新知识库请求体"""

    kb_ids: list[uuid.UUID] = Field(description="知识库ID列表", alias="kbIds", default=[])


class UserUpdateRequest(BaseModel):
    """更新用户信息请求体"""

    auto_execute: bool = Field(default=False, description="是否自动执行", alias="autoExecute")
