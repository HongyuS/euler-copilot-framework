# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""FastAPI 返回数据结构"""

import uuid
from typing import Any

from pydantic import BaseModel, Field

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
