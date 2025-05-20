# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""文件上传至RAG，作为临时语料"""

import httpx
from fastapi import status

from apps.common.config import Config
from apps.entities.collection import Document
from apps.entities.rag_data import (
    RAGFileParseReq,
    RAGFileParseReqItem,
    RAGFileStatusRspItem,
)

rag_host = Config().get_config().rag.rag_service
_RAG_DOC_PARSE_URI = rag_host.rstrip("/") + "/doc/temporary/parser"
_RAG_DOC_STATUS_URI = rag_host.rstrip("/") + "/doc/temporary/status"
_RAG_DOC_DELETE_URI = rag_host.rstrip("/") + "/doc/temporary/delete"

class KnowledgeBaseService:
    """知识库服务"""

    @staticmethod
    async def send_file_to_rag(docs: list[Document]) -> list[str]:
        """上传文件给RAG，进行处理和向量化"""
        rag_docs = [RAGFileParseReqItem(
                id=doc.id,
                name=doc.name,
                bucket_name="document",
                type=doc.type,
            )
            for doc in docs
        ]
        post_data = RAGFileParseReq(document_list=rag_docs).model_dump(exclude_none=True, by_alias=True)

        async with httpx.AsyncClient() as client:
            resp = await client.post(_RAG_DOC_PARSE_URI, json=post_data)
            resp_data = resp.json()
            if resp.status_code != status.HTTP_200_OK:
                return []
            return resp_data["data"]

    @staticmethod
    async def delete_doc_from_rag(doc_ids: list[str]) -> list[str]:
        """删除文件"""
        post_data = {"ids": doc_ids}
        async with httpx.AsyncClient() as client:
            resp = await client.post(_RAG_DOC_DELETE_URI, json=post_data)
            resp_data = resp.json()
            if resp.status_code != status.HTTP_200_OK:
                return []
            return resp_data["data"]

    @staticmethod
    async def get_doc_status_from_rag(doc_ids: list[str]) -> list[RAGFileStatusRspItem]:
        """获取文件状态"""
        post_data = {"ids": doc_ids}
        async with httpx.AsyncClient() as client:
            resp = await client.post(_RAG_DOC_STATUS_URI, json=post_data)
            resp_data = resp.json()
            if resp.status_code != status.HTTP_200_OK:
                return []
            return [RAGFileStatusRspItem.model_validate(item) for item in resp_data["data"]]
