# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""RAG工具：查询知识库"""

import logging
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
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
    CHUNK_ELEMENT_TOKENS,
    QuestionRewriteOutput,
    RAGInput,
    RAGOutput,
    SearchMethod,
)

_logger = logging.getLogger(__name__)


class RAG(CoreCall, input_model=RAGInput, output_model=RAGOutput):
    """RAG工具：查询知识库"""

    knowledge_base_ids: list[str] = Field(description="知识库的id列表", default=[])
    top_k: int = Field(description="返回的分片数量", default=5)
    document_ids: list[str] | None = Field(description="文档id列表", default=None)
    search_method: str = Field(description="检索方法", default=SearchMethod.KEYWORD_AND_VECTOR.value)
    is_related_surrounding: bool = Field(description="是否关联上下文", default=True)
    is_classify_by_doc: bool = Field(description="是否按文档分类", default=False)
    is_rerank: bool = Field(description="是否重新排序", default=False)
    is_compress: bool = Field(description="是否压缩", default=False)
    tokens_limit: int = Field(description="token限制", default=8192)

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
            session_id=call_vars.ids.session_id,
            kbIds=self.knowledge_base_ids,
            topK=self.top_k,
            query=call_vars.question,
            docIds=self.document_ids,
            searchMethod=self.search_method,
            isRelatedSurrounding=self.is_related_surrounding,
            isClassifyByDoc=self.is_classify_by_doc,
            isRerank=self.is_rerank,
            isCompress=self.is_compress,
            tokensLimit=self.tokens_limit,
        )

    async def _assemble_doc_info(
        self,
        doc_chunk_list: list[dict[str, Any]],
        max_tokens: int,
    ) -> tuple[str, list[dict[str, Any]]]:
        """组装文档信息"""
        bac_info = ""
        doc_info_list = []
        doc_cnt = 0
        doc_id_map = {}
        remaining_tokens = max_tokens * 0.8

        for doc_chunk in doc_chunk_list:
            if doc_chunk["docId"] not in doc_id_map:
                doc_cnt += 1
                t = doc_chunk.get("docCreatedAt", None)
                if isinstance(t, str):
                    t = datetime.strptime(t, "%Y-%m-%d %H:%M").replace(
                        tzinfo=UTC,
                    )
                    t = round(t.replace(tzinfo=UTC).timestamp(), 3)
                else:
                    t = round(datetime.now(UTC).timestamp(), 3)
                doc_info_list.append({
                    "id": doc_chunk["docId"],
                    "order": doc_cnt,
                    "name": doc_chunk.get("docName", ""),
                    "author": doc_chunk.get("docAuthor", ""),
                    "extension": doc_chunk.get("docExtension", ""),
                    "abstract": doc_chunk.get("docAbstract", ""),
                    "size": doc_chunk.get("docSize", 0),
                    "created_at": t,
                })
                doc_id_map[doc_chunk["docId"]] = doc_cnt
            doc_index = doc_id_map[doc_chunk["docId"]]

            if bac_info:
                bac_info += "\n\n"
            bac_info += f"""<document id="{doc_index}"  name="{doc_chunk["docName"]}">"""

            for chunk in doc_chunk["chunks"]:
                if remaining_tokens <= CHUNK_ELEMENT_TOKENS:
                    break
                chunk_text = chunk["text"]
                chunk_text = TokenCalculator().get_k_tokens_words_from_content(
                    content=chunk_text, k=remaining_tokens)
                remaining_tokens -= TokenCalculator().calculate_token_length(messages=[
                    {"role": "user", "content": "<chunk>"},
                    {"role": "user", "content": chunk_text},
                    {"role": "user", "content": "</chunk>"},
                ], pure_text=True)
                bac_info += f"""
                    <chunk>
                        {chunk_text}
                    </chunk>
                """
            bac_info += "</document>"
        return bac_info, doc_info_list

    async def _get_doc_info(self, doc_ids: list[str], data: RAGInput) -> AsyncGenerator[CallOutputChunk, None]:
        """获取文档信息"""
        url = config.rag.rag_service.rstrip("/") + "/chunk/search"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._sys_vars.ids.session_id}",
        }
        doc_chunk_list = []
        if doc_ids:
            default_kb_id = "00000000-0000-0000-0000-000000000000"
            tmp_data = RAGQueryReq(
                kbIds=[default_kb_id],
                query=data.query,
                topK=data.top_k,
                docIds=doc_ids,
                searchMethod=data.search_method,
                isRelatedSurrounding=data.is_related_surrounding,
                isClassifyByDoc=data.is_classify_by_doc,
                isRerank=data.is_rerank,
                tokensLimit=max_tokens,
            )
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    data_json = tmp_data.model_dump(exclude_none=True, by_alias=True)
                    response = await client.post(url, headers=headers, json=data_json)
                    if response.status_code == status.HTTP_200_OK:
                        result = response.json()
                        doc_chunk_list += result["result"]["docChunks"]
            except Exception:
                _logger.exception("[RAG] 获取文档分片失败")
        if data.kb_ids:
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    data_json = data.model_dump(exclude_none=True, by_alias=True)
                    response = await client.post(url, headers=headers, json=data_json)
                    # 检查响应状态码
                    if response.status_code == status.HTTP_200_OK:
                        result = response.json()
                        doc_chunk_list += result["result"]["docChunks"]
            except Exception:
                _logger.exception("[RAG] 获取文档分片失败")
        return doc_chunk_list

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
            prompt = tmpl.render(history="", question=data.question)

            # 使用_json方法直接获取JSON结果
            json_result = await self._json([
                {"role": "user", "content": prompt},
            ], schema=QuestionRewriteOutput.model_json_schema())
            # 直接使用解析后的JSON结果
            data.question = QuestionRewriteOutput.model_validate(json_result).question
        except Exception:
            _logger.exception("[RAG] 问题重写失败，使用原始问题")

        url = config.rag.rag_service.rstrip("/") + "/chunk/search"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {data.session_id}",
        }

        # 发送请求
        data_json = data.model_dump(exclude_none=True, by_alias=True)
        del data_json["session_id"]
        async with httpx.AsyncClient(timeout=300) as client:
            response = await client.post(url, headers=headers, json=data_json)

            # 检查响应状态码
            if response.status_code == status.HTTP_200_OK:
                result = response.json()
                doc_chunk_list = result["result"]["docChunks"]

                corpus = []
                for doc_chunk in doc_chunk_list:
                    for chunk in doc_chunk["chunks"]:
                        corpus.extend([chunk["text"].replace("\n", "")])

                yield CallOutputChunk(
                    type=CallOutputType.DATA,
                    content=RAGOutput(
                        question=data.question,
                        corpus=corpus,
                    ).model_dump(exclude_none=True, by_alias=True),
                )
                return

            text = response.text
            _logger.error("[RAG] 调用失败：%s", text)

            raise CallError(
                message=f"rag调用失败：{text}",
                data={
                    "question": data.question,
                    "status": response.status_code,
                    "text": text,
                },
            )
