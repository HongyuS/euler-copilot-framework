# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""FastAPI 返回数据结构"""

import uuid
from typing import Any

from pydantic import BaseModel, Field

from .appcenter import AppCenterCardItem, AppData
from .flow_topology import (
    FlowItem,
)
from .parameters import (
    BoolOperate,
    DictOperate,
    ListOperate,
    NumberOperate,
    StringOperate,
    Type,
)
from .record import RecordData
from .user import UserInfo


class ResponseData(BaseModel):
    """基础返回数据结构"""

    code: int
    message: str
    result: Any


class AuthUserMsg(BaseModel):
    """GET /api/auth/user Result数据结构"""

    user_sub: str
    revision: bool
    is_admin: bool
    auto_execute: bool


class AuthUserRsp(ResponseData):
    """GET /api/auth/user 返回数据结构"""

    result: AuthUserMsg


class HealthCheckRsp(BaseModel):
    """GET /health_check 返回数据结构"""

    status: str


class ConversationListItem(BaseModel):
    """GET /api/conversation Result数据结构"""

    conversation_id: uuid.UUID = Field(alias="conversationId")
    title: str
    doc_count: int = Field(alias="docCount")
    created_time: str = Field(alias="createdTime")
    app_id: str = Field(alias="appId")
    debug: bool = Field(alias="debug")


class ConversationListMsg(BaseModel):
    """GET /api/conversation Result数据结构"""

    conversations: list[ConversationListItem]


class ConversationListRsp(ResponseData):
    """GET /api/conversation 返回数据结构"""

    result: ConversationListMsg


class DeleteConversationMsg(BaseModel):
    """DELETE /api/conversation Result数据结构"""

    conversation_id_list: list[str] = Field(alias="conversationIdList")


class DeleteConversationRsp(ResponseData):
    """DELETE /api/conversation 返回数据结构"""

    result: DeleteConversationMsg


class AddConversationMsg(BaseModel):
    """POST /api/conversation Result数据结构"""

    conversation_id: uuid.UUID = Field(alias="conversationId")


class AddConversationRsp(ResponseData):
    """POST /api/conversation 返回数据结构"""

    result: AddConversationMsg


class UpdateConversationRsp(ResponseData):
    """POST /api/conversation 返回数据结构"""

    result: ConversationListItem


class RecordListMsg(BaseModel):
    """GET /api/record/{conversation_id} Result数据结构"""

    records: list[RecordData]


class RecordListRsp(ResponseData):
    """GET /api/record/{conversation_id} 返回数据结构"""

    result: RecordListMsg



class OidcRedirectMsg(BaseModel):
    """GET /api/auth/redirect Result数据结构"""

    url: str


class OidcRedirectRsp(ResponseData):
    """GET /api/auth/redirect 返回数据结构"""

    result: OidcRedirectMsg


class ListTeamKnowledgeMsg(BaseModel):
    """GET /api/knowledge Result数据结构"""

    team_kb_list: list[uuid.UUID] = Field(default=[], alias="teamKbList", description="团队知识库列表")


class ListTeamKnowledgeRsp(ResponseData):
    """GET /api/knowledge 返回数据结构"""

    result: ListTeamKnowledgeMsg


class BaseAppOperationMsg(BaseModel):
    """基础应用操作Result数据结构"""

    app_id: uuid.UUID = Field(..., alias="appId", description="应用ID")


class BaseAppOperationRsp(ResponseData):
    """基础应用操作返回数据结构"""

    result: BaseAppOperationMsg


class GetAppPropertyMsg(AppData):
    """GET /api/app/{appId} Result数据结构"""

    app_id: str = Field(..., alias="appId", description="应用ID")
    published: bool = Field(..., description="是否已发布")
    mcp_service: list[AppMcpServiceInfo] = Field(default=[], alias="mcpService", description="MCP服务信息列表")


class GetAppPropertyRsp(ResponseData):
    """GET /api/app/{appId} 返回数据结构"""

    result: GetAppPropertyMsg


class ChangeFavouriteAppMsg(BaseModel):
    """PUT /api/app/{appId} Result数据结构"""

    app_id: str = Field(..., alias="appId", description="应用ID")
    favorited: bool = Field(..., description="是否已收藏")


class ChangeFavouriteAppRsp(ResponseData):
    """PUT /api/app/{appId} 返回数据结构"""

    result: ChangeFavouriteAppMsg


class GetAppListMsg(BaseModel):
    """GET /api/app Result数据结构"""

    page_number: int = Field(..., alias="currentPage", description="当前页码")
    app_count: int = Field(..., alias="totalApps", description="总应用数")
    applications: list[AppCenterCardItem] = Field(..., description="应用列表")


class GetAppListRsp(ResponseData):
    """GET /api/app 返回数据结构"""

    result: GetAppListMsg


class RecentAppListItem(BaseModel):
    """GET /api/app/recent 列表项数据结构"""

    app_id: uuid.UUID = Field(..., alias="appId", description="应用ID")
    name: str = Field(..., description="应用名称")


class RecentAppList(BaseModel):
    """GET /api/app/recent Result数据结构"""

    applications: list[RecentAppListItem] = Field(..., description="最近使用的应用列表")


class GetRecentAppListRsp(ResponseData):
    """GET /api/app/recent 返回数据结构"""

    result: RecentAppList


class FlowStructureGetMsg(BaseModel):
    """GET /api/flow result"""

    flow: FlowItem = Field(default=FlowItem())


class FlowStructureGetRsp(ResponseData):
    """GET /api/flow 返回数据结构"""

    result: FlowStructureGetMsg


class FlowStructurePutMsg(BaseModel):
    """PUT /api/flow result"""

    flow: FlowItem = Field(default=FlowItem())


class FlowStructurePutRsp(ResponseData):
    """PUT /api/flow 返回数据结构"""

    result: FlowStructurePutMsg


class FlowStructureDeleteMsg(BaseModel):
    """DELETE /api/flow/ result"""

    flow_id: str = Field(alias="flowId", default="")


class FlowStructureDeleteRsp(ResponseData):
    """DELETE /api/flow/ 返回数据结构"""

    result: FlowStructureDeleteMsg


class UserGetMsp(BaseModel):
    """GET /api/user result"""

    total: int = Field(default=0)
    user_info_list: list[UserInfo] = Field(alias="userInfoList", default=[])


class UserGetRsp(ResponseData):
    """GET /api/user 返回数据结构"""

    result: UserGetMsp


class LLMProvider(BaseModel):
    """LLM提供商数据结构"""

    provider: str = Field(description="LLM提供商")
    description: str = Field(description="LLM提供商描述")
    url: str | None = Field(default=None, description="LLM提供商URL")
    icon: str = Field(description="LLM提供商图标")


class ListLLMProviderRsp(ResponseData):
    """GET /api/llm/provider 返回数据结构"""

    result: list[LLMProvider] = Field(default=[], title="Result")


class LLMProviderInfo(BaseModel):
    """LLM数据结构"""

    llm_id: str = Field(alias="llmId", description="LLM ID")
    openai_base_url: str = Field(
        default="https://api.openai.com/v1",
        description="OpenAI API Base URL",
        alias="openaiBaseUrl",
    )
    openai_api_key: str = Field(
        description="OpenAI API Key",
        alias="openaiApiKey",
        default="",
    )
    model_name: str = Field(description="模型名称", alias="modelName")
    max_tokens: int | None = Field(default=None, description="最大token数", alias="maxTokens")
    is_editable: bool = Field(default=True, description="是否可编辑", alias="isEditable")


class ListLLMRsp(ResponseData):
    """GET /api/llm 返回数据结构"""

    result: list[LLMProviderInfo] = Field(default=[], title="Result")


class ParamsNode(BaseModel):
    """参数数据结构"""

    param_name: str = Field(..., description="参数名称", alias="paramName")
    param_path: str = Field(..., description="参数路径", alias="paramPath")
    param_type: Type = Field(..., description="参数类型", alias="paramType")
    sub_params: list["ParamsNode"] | None = Field(
        default=None, description="子参数列表", alias="subParams",
    )


class StepParams(BaseModel):
    """参数数据结构"""

    step_id: uuid.UUID = Field(..., description="步骤ID", alias="stepId")
    name: str = Field(..., description="Step名称")
    params_node: ParamsNode | None = Field(
        default=None, description="参数节点", alias="paramsNode")


class GetParamsRsp(ResponseData):
    """GET /api/params 返回数据结构"""

    result: list[StepParams] = Field(
        default=[], description="参数列表", alias="result",
    )


class OperateAndBindType(BaseModel):
    """操作和绑定类型数据结构"""

    operate: NumberOperate | StringOperate | ListOperate | BoolOperate | DictOperate = Field(description="操作类型")
    bind_type: Type | None = Field(description="绑定类型")


class GetOperaRsp(ResponseData):
    """GET /api/operate 返回数据结构"""

    result: list[OperateAndBindType] = Field(..., title="Result")


class UserSelectedLLMData(BaseModel):
    """用户选择的LLM数据结构"""

    functionLLM: str | None = Field(default=None, description="函数模型ID")  # noqa: N815
    embeddingLLM: str | None = Field(default=None, description="向量模型ID")  # noqa: N815


class UserSelectedLLMRsp(ResponseData):
    """GET /api/user/llm 返回数据结构"""

    result: UserSelectedLLMData = Field(..., title="Result")
