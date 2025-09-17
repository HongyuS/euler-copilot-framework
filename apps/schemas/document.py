# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""FastAPI 返回数据结构 - 文档相关"""

from pydantic import BaseModel, Field

from .enum_var import DocumentStatus


class ConversationDocumentItem(BaseModel):
    """GET /api/document/{conversation_id} Result内元素数据结构"""

    id: str = Field(alias="_id", default="")
    user_sub: None = None
    status: DocumentStatus
    conversation_id: None = None

    class Config:
        """配置"""

        populate_by_name = True


class ConversationDocumentMsg(BaseModel):
    """GET /api/document/{conversation_id} Result数据结构"""

    documents: list[ConversationDocumentItem] = []


class ConversationDocumentRsp(BaseModel):
    """GET /api/document/{conversation_id} 返回数据结构"""

    code: int
    message: str
    result: ConversationDocumentMsg


class UploadDocumentMsgItem(BaseModel):
    """POST /api/document/{conversation_id} 返回数据结构"""

    id: str = Field(alias="_id", default="")
    user_sub: None = None
    name: str = Field(default="", description="文档名称")
    type: str = Field(default="", description="文档类型")
    size: float = Field(default=0.0, description="文档大小")
    created_at: None = None
    conversation_id: None = None

    class Config:
        """配置"""

        populate_by_name = True


class UploadDocumentMsg(BaseModel):
    """POST /api/document/{conversation_id} 返回数据结构"""

    documents: list[UploadDocumentMsgItem]


class UploadDocumentRsp(BaseModel):
    """POST /api/document/{conversation_id} 返回数据结构"""

    code: int
    message: str
    result: UploadDocumentMsg
