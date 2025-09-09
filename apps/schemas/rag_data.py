# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""请求RAG相关接口时，使用的数据类型"""

from typing import Literal

from pydantic import BaseModel


class RAGFileParseReqItem(BaseModel):
    """请求RAG处理文件时的POST请求体中的文件项"""

    id: str
    name: str
    bucket_name: str
    type: str


class RAGFileParseReq(BaseModel):
    """请求RAG处理文件时的POST请求体"""

    document_list: list[RAGFileParseReqItem]


class RAGFileStatusRspItem(BaseModel):
    """RAG处理文件状态的GET请求返回体"""

    id: str
    status: Literal["pending", "running", "success", "failed"]
