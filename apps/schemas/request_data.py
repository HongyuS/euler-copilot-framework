# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""FastAPI 请求体"""

import uuid
from typing import Any

from pydantic import BaseModel, Field

from .appcenter import AppData
from .enum_var import CommentType
from .flow_topology import FlowItem
from .mcp import MCPType
from .message import param


class RequestDataApp(BaseModel):
    """模型对话中包含的app信息"""

    app_id: uuid.UUID = Field(description="应用ID", alias="appId")
    flow_id: str | None = Field(default=None, description="Flow ID", alias="flowId")
    params: param | None = Field(default=None, description="流执行过程中的参数补充", alias="params")


class RequestData(BaseModel):
    """POST /api/chat 请求的总的数据结构"""

    question: str = Field(max_length=2000, description="用户输入")
    conversation_id: uuid.UUID = Field(
        default=uuid.UUID("00000000-0000-0000-0000-000000000000"), alias="conversationId", description="聊天ID",
    )
    language: str = Field(default="zh", description="语言")
    files: list[str] = Field(default=[], description="文件列表")
    app: RequestDataApp | None = Field(default=None, description="应用")
    debug: bool = Field(default=False, description="是否调试")
    task_id: str | None = Field(default=None, alias="taskId", description="任务ID")


class QuestionBlacklistRequest(BaseModel):
    """POST /api/blacklist/question 请求数据结构"""

    id: str
    question: str
    answer: str
    is_deletion: int


class UserBlacklistRequest(BaseModel):
    """POST /api/blacklist/user 请求数据结构"""

    user_sub: str
    is_ban: int


class AbuseRequest(BaseModel):
    """POST /api/blacklist/complaint 请求数据结构"""

    record_id: uuid.UUID
    reason: str
    reason_type: str


class AbuseProcessRequest(BaseModel):
    """POST /api/blacklist/abuse 请求数据结构"""

    id: uuid.UUID
    is_deletion: int


class CreateAppRequest(AppData):
    """POST /api/app 请求数据结构"""

    app_id: str | None = Field(None, alias="appId", description="应用ID")


class ChangeFavouriteAppRequest(BaseModel):
    """PUT /api/app/{appId} 请求数据结构"""

    favorited: bool = Field(..., description="是否收藏")


class UpdateMCPServiceRequest(BaseModel):
    """POST /api/mcpservice 请求数据结构"""

    service_id: str | None = Field(None, alias="serviceId", description="服务ID（更新时传递）")
    name: str = Field(..., description="MCP服务名称")
    description: str = Field(..., description="MCP服务描述")
    overview: str = Field(..., description="MCP服务概述")
    config: str = Field(..., description="MCP服务配置")
    mcp_type: MCPType = Field(description="MCP传输协议(Stdio/SSE/Streamable)", default=MCPType.STDIO, alias="mcpType")


class ActiveMCPServiceRequest(BaseModel):
    """POST /api/mcp/{serviceId} 请求数据结构"""

    active: bool = Field(description="是否激活mcp服务")
    mcp_env: dict[str, Any] = Field(default={}, description="MCP服务环境变量", alias="mcpEnv")


class UpdateServiceRequest(BaseModel):
    """POST /api/service 请求数据结构"""

    service_id: uuid.UUID | None = Field(None, alias="serviceId", description="服务ID（更新时传递）")
    data: dict[str, Any] = Field(..., description="对应 YAML 内容的数据对象")


class ChangeFavouriteServiceRequest(BaseModel):
    """PUT /api/service/{serviceId} 请求数据结构"""

    favorited: bool = Field(..., description="是否收藏")


class ChangeConversationData(BaseModel):
    """修改会话信息"""

    title: str = Field(..., min_length=1, max_length=2000)


class DeleteConversationData(BaseModel):
    """删除会话"""

    conversation_list: list[uuid.UUID] = Field(alias="conversationList")


class AddCommentData(BaseModel):
    """添加评论"""

    record_id: str
    comment: CommentType
    dislike_reason: str = Field(default="", max_length=200)
    reason_link: str = Field(default="", max_length=200)
    reason_description: str = Field(default="", max_length=500)


class PostTagData(BaseModel):
    """添加领域"""

    tag: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., max_length=2000)


class PutFlowReq(BaseModel):
    """创建/修改流拓扑结构"""

    flow: FlowItem


class UpdateLLMReq(BaseModel):
    """更新大模型请求体"""

    icon: str = Field(description="图标", default="")
    openai_base_url: str = Field(default="", description="OpenAI API Base URL", alias="openaiBaseUrl")
    openai_api_key: str = Field(default="", description="OpenAI API Key", alias="openaiApiKey")
    model_name: str = Field(default="", description="模型名称", alias="modelName")
    max_tokens: int = Field(default=8192, description="最大token数", alias="maxTokens")


class DeleteLLMReq(BaseModel):
    """删除大模型请求体"""

    llm_id: str = Field(description="大模型ID", alias="llmId")


class UpdateUserKnowledgebaseReq(BaseModel):
    """更新知识库请求体"""

    kb_ids: list[uuid.UUID] = Field(description="知识库ID列表", alias="kbIds", default=[])


class UserUpdateRequest(BaseModel):
    """更新用户信息请求体"""

    auto_execute: bool = Field(default=False, description="是否自动执行", alias="autoExecute")
