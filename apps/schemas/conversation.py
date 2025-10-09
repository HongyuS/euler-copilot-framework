# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""对话相关数据结构"""

import uuid

from pydantic import BaseModel, Field

from .response_data import ResponseData


class ChangeConversationData(BaseModel):
    """修改会话信息"""

    title: str = Field(..., min_length=1, max_length=2000)


class DeleteConversationData(BaseModel):
    """删除会话"""

    conversation_list: list[uuid.UUID] = Field(alias="conversationList")


class ConversationListItem(BaseModel):
    """GET /api/conversation Result数据结构"""

    conversation_id: uuid.UUID = Field(alias="conversationId")
    title: str
    doc_count: int = Field(alias="docCount")
    created_time: str = Field(alias="createdTime")
    app_id: uuid.UUID | None = Field(alias="appId")
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
