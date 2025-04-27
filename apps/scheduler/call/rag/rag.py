"""
RAG工具：查询知识库

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

import logging
from collections.abc import AsyncGenerator
from typing import Any, Literal

import httpx
from fastapi import status
from pydantic import Field

from apps.common.config import Config
from apps.entities.enum_var import CallOutputType
from apps.entities.scheduler import (
    CallError,
    CallInfo,
    CallOutputChunk,
    CallVars,
)
from apps.llm.patterns.rewrite import QuestionRewrite
from apps.scheduler.call.core import CoreCall
from apps.scheduler.call.rag.schema import RAGInput, RAGOutput, RetrievalMode

logger = logging.getLogger(__name__)


class RAG(CoreCall, input_model=RAGInput, output_model=RAGOutput):
    """RAG工具：查询知识库"""

    knowledge_base: str | None = Field(description="知识库的id", alias="kb_sn", default=None)
    top_k: int = Field(description="返回的答案数量(经过整合以及上下文关联)", default=5)
    retrieval_mode: Literal["chunk", "full_text"] = Field(description="检索模式", default="chunk")


    @classmethod
    def info(cls) -> CallInfo:
        """返回Call的名称和描述"""
        return CallInfo(name="知识库", description="查询知识库，从文档中获取必要信息")


    async def _init(self, call_vars: CallVars) -> RAGInput:
        """初始化RAG工具"""
        return RAGInput(
            content=call_vars.question,
            kb_sn=self.knowledge_base,
            top_k=self.top_k,
            retrieval_mode=RetrievalMode(self.retrieval_mode),
        )


    async def _exec(self, input_data: dict[str, Any]) -> AsyncGenerator[CallOutputChunk, None]:
        """调用RAG工具"""
        data = RAGInput(**input_data)
        question_obj = QuestionRewrite()
        question = await question_obj.generate(question=data.content)
        data.content = question
        self.tokens.input_tokens += question_obj.input_tokens
        self.tokens.output_tokens += question_obj.output_tokens

        url = Config().get_config().rag.rag_service.rstrip("/") + "/chunk/get"
        headers = {
            "Content-Type": "application/json",
        }

        # 发送请求
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=input_data)

            # 检查响应状态码
            if response.status_code == status.HTTP_200_OK:
                result = response.json()
                chunk_list = result["data"]

                corpus = []
                for chunk in chunk_list:
                    clean_chunk = chunk.replace("\n", " ")
                    corpus.append(clean_chunk)

                yield CallOutputChunk(
                    type=CallOutputType.DATA,
                    content=RAGOutput(
                        question=data.content,
                        corpus=corpus,
                    ).model_dump(exclude_none=True, by_alias=True),
                )
                return

            text = response.text
            logger.error("[RAG] 调用失败：%s", text)

            raise CallError(
                message=f"rag调用失败：{text}",
                data={
                    "question": data.content,
                    "status": response.status_code,
                    "text": text,
                },
            )
