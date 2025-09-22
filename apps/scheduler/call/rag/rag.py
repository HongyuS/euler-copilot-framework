# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""RAG工具：查询知识库"""

import logging
import uuid
from collections.abc import AsyncGenerator
from copy import deepcopy
from typing import Any

import httpx
from fastapi import status
from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment
from pydantic import Field

from apps.common.config import config
from apps.scheduler.call.core import CoreCall
from apps.schemas.enum_var import CallOutputType, LanguageType
from apps.schemas.scheduler import (
    CallError,
    CallInfo,
    CallOutputChunk,
    CallVars,
)

from .prompt import QUESTION_REWRITE
from .schema import (
    DocItem,
    QuestionRewriteOutput,
    RAGInput,
    RAGOutput,
    SearchMethod,
)

_logger = logging.getLogger(__name__)


class RAG(CoreCall, input_model=RAGInput, output_model=RAGOutput):
    """RAG工具：查询知识库"""

    kb_ids: list[uuid.UUID] = Field(description="知识库的id列表", default=[])
    top_k: int = Field(description="返回的分片数量", default=5)
    doc_ids: list[str] | None = Field(description="文档id列表", default=None)
    search_method: str = Field(description="检索方法", default=SearchMethod.KEYWORD_AND_VECTOR.value)
    is_related_surrounding: bool = Field(description="是否关联上下文", default=True)
    is_classify_by_doc: bool = Field(description="是否按文档分类", default=False)
    is_rerank: bool = Field(description="是否重新排序", default=False)
    is_compress: bool = Field(description="是否压缩", default=False)
    tokens_limit: int = Field(description="token限制", default=8192)
    history_len: int = Field(description="历史对话长度", default=3)


    @classmethod
    def info(cls, language: LanguageType = LanguageType.CHINESE) -> CallInfo:
        """返回Call的名称和描述"""
        i18n_info = {
            LanguageType.CHINESE: CallInfo(
                name="知识库", description="查询知识库，从文档中获取必要信息",
            ),
            LanguageType.ENGLISH: CallInfo(
                name="Knowledge Base",
                description="Query the knowledge base and obtain necessary information from documents.",
            ),
        }
        return i18n_info[language]


    async def _init(self, call_vars: CallVars) -> RAGInput:
        """初始化RAG工具"""
        if not call_vars.ids.session_id:
            err = "[RAG] 未设置Session ID"
            _logger.error(err)
            raise CallError(message=err, data={})

        return RAGInput(
            kbIds=self.kb_ids,
            topK=self.top_k,
            query=call_vars.question,
            docIds=self.doc_ids,
            searchMethod=self.search_method,
            isRelatedSurrounding=self.is_related_surrounding,
            isClassifyByDoc=self.is_classify_by_doc,
            isRerank=self.is_rerank,
            isCompress=self.is_compress,
            tokensLimit=self.tokens_limit,
        )


    async def _fetch_doc_chunks(self, data: RAGInput) -> list[DocItem]:
        """从知识库获取文档分片"""
        url = config.rag.rag_service.rstrip("/") + "/chunk/search"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._sys_vars.ids.session_id}",
        }

        doc_chunk_list = []
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                data_json = data.model_dump(exclude_none=True, by_alias=True)
                response = await client.post(url, headers=headers, json=data_json)
                # 检查响应状态码
                if response.status_code == status.HTTP_200_OK:
                    result = response.json()
                    # 对返回的docChunks进行校验
                    try:
                        validated_chunks = []
                        for chunk_data in result["result"]["docChunks"]:
                            validated_chunk = DocItem.model_validate(chunk_data)
                            validated_chunks.append(validated_chunk)
                        doc_chunk_list += validated_chunks
                    except Exception as e:
                        _logger.error(f"[RAG] chunk校验失败: {e}")
                        raise
        except Exception:
            _logger.exception("[RAG] 获取文档分片失败")

        return doc_chunk_list

    async def _get_doc_info(self, doc_ids: list[str], data: RAGInput) -> AsyncGenerator[CallOutputChunk, None]:
        """获取文档信息"""
        doc_chunk_list = []

        # 处理指定文档ID的情况
        if doc_ids:
            tmp_data = deepcopy(data)
            tmp_data.kbIds = [ uuid.UUID("00000000-0000-0000-0000-000000000000") ]
            doc_chunk_list.extend(await self._fetch_doc_chunks(tmp_data))

        # 处理知识库ID的情况
        if data.kbIds:
            doc_chunk_list.extend(await self._fetch_doc_chunks(data))

        # 将文档分片转换为文本片段并返回
        for doc_chunk in doc_chunk_list:
            for chunk in doc_chunk.chunks:
                text = chunk.text.replace("\n", "")
                yield CallOutputChunk(
                    type=CallOutputType.DATA,
                    content=text,
                )


    async def _exec(self, input_data: dict[str, Any]) -> AsyncGenerator[CallOutputChunk, None]:
        """调用RAG工具"""
        data = RAGInput(**input_data)
        # 使用Jinja2渲染问题重写模板，并用JsonGenerator解析结果
        try:
            env = SandboxedEnvironment(
                loader=BaseLoader(),
                autoescape=False,
                trim_blocks=True,
                lstrip_blocks=True,
            )
            tmpl = env.from_string(QUESTION_REWRITE[self._sys_vars.language])

            # 从背景对话中提取最近的问答对（user -> assistant）
            tail_messages = self._sys_vars.background.conversation[-self.history_len:]
            qa_pairs = []
            for message in tail_messages:
                qa_pairs += [{
                    "question": message["question"],
                    "answer": message["answer"],
                }]
            prompt = tmpl.render(history=qa_pairs, question=data.query)

            # 使用_json方法直接获取JSON结果
            json_result = await self._json([
                {"role": "user", "content": prompt},
            ], schema=QuestionRewriteOutput.model_json_schema())
            # 直接使用解析后的JSON结果
            data.query = QuestionRewriteOutput.model_validate(json_result).question
        except Exception:
            _logger.exception("[RAG] 问题重写失败，使用原始问题")

        url = config.rag.rag_service.rstrip("/") + "/chunk/search"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._sys_vars.ids.session_id}",
        }

        # 发送请求
        data_json = data.model_dump(exclude_none=True, by_alias=True)
        async with httpx.AsyncClient(timeout=300) as client:
            response = await client.post(url, headers=headers, json=data_json)

            # 检查响应状态码
            if response.status_code == status.HTTP_200_OK:
                result = response.json()
                doc_chunk_list = result["result"]["docChunks"]

                # 对返回的docChunks进行校验
                try:
                    validated_chunks = []
                    for chunk_data in doc_chunk_list:
                        validated_chunk = DocItem.model_validate(chunk_data)
                        validated_chunks.append(validated_chunk)
                    doc_chunk_list = validated_chunks
                except Exception as e:
                    err = f"[RAG] chunk校验失败: {e}"
                    _logger.error(err)  # noqa: TRY400
                    raise

                corpus = []
                for doc_chunk in doc_chunk_list:
                    for chunk in doc_chunk["chunks"]:
                        corpus.extend([chunk["text"].replace("\n", "")])

                yield CallOutputChunk(
                    type=CallOutputType.DATA,
                    content=RAGOutput(
                        question=data.query,
                        corpus=corpus,
                    ).model_dump(exclude_none=True, by_alias=True),
                )
                return

            text = response.text
            _logger.error("[RAG] 调用失败：%s", text)

            raise CallError(
                message=f"rag调用失败：{text}",
                data={
                    "question": data.query,
                    "status": response.status_code,
                    "text": text,
                },
            )
