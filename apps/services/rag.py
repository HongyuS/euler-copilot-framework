# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""对接Euler Copilot RAG"""

import json
import logging
import re
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import status

from apps.common.config import config
from apps.llm.patterns.rewrite import QuestionRewrite
from apps.llm.reasoning import ReasoningLLM
from apps.llm.token import TokenCalculator
from apps.schemas.enum_var import EventType, LanguageType
from apps.schemas.rag_data import RAGQueryReq
from apps.services.llm import LLMManager
from apps.services.session import SessionManager

logger = logging.getLogger(__name__)
CHUNK_ELEMENT_TOKENS = 5


class RAG:
    """调用RAG服务，获取知识库答案"""

    @staticmethod
    async def get_doc_info_from_rag(
        user_sub: str, max_tokens: int | None, doc_ids: list[str], data: RAGQueryReq,
    ) -> list[dict[str, Any]]:
        """获取RAG服务的文档信息"""
        session_id = await SessionManager.get_session_by_user_sub(user_sub)
        url = config.rag.rag_service.rstrip("/") + "/chunk/search"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {session_id}",
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
                logger.exception("[RAG] 获取文档分片失败")
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
                logger.exception("[RAG] 获取文档分片失败")
        return doc_chunk_list

    @staticmethod
    async def assemble_doc_info(
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

    @staticmethod
    async def chat_with_llm_base_on_rag(  # noqa: C901, PLR0913
        user_sub: str,
        llm_id: str,
        history: list[dict[str, str]],
        doc_ids: list[str],
        data: RAGQueryReq,
        language: LanguageType = LanguageType.CHINESE,
    ) -> AsyncGenerator[str, None]:
        """获取RAG服务的结果"""
        llm_config = await LLMManager.get_llm(llm_id)
        if not llm_config:
            err = "[RAG] 未设置问答所用LLM"
            logger.error(err)
            raise RuntimeError(err)
        reasion_llm = ReasoningLLM(llm_config)

        if history:
            try:
                question_obj = QuestionRewrite()
                data.query = await question_obj.generate(
                    history=history, question=data.query, llm=reasion_llm, language=language,
                )
            except Exception:
                logger.exception("[RAG] 问题重写失败")
        doc_chunk_list = await RAG.get_doc_info_from_rag(
            user_sub=user_sub, max_tokens=llm_config.maxToken, doc_ids=doc_ids, data=data,
        )
        bac_info, doc_info_list = await RAG.assemble_doc_info(
            doc_chunk_list=doc_chunk_list, max_tokens=llm_config.maxToken,
        )
        messages = [
            *history,
            {
                "role": "system",
                "content": RAG.system_prompt,
            },
            {
                "role": "user",
                "content": RAG.user_prompt[language].format(
                    bac_info=bac_info,
                    user_question=data.query,
                ),
            },
        ]
        input_tokens = TokenCalculator().calculate_token_length(messages=messages)
        output_tokens = 0
        doc_cnt: int = 0
        for doc_info in doc_info_list:
            doc_cnt = max(doc_cnt, doc_info["order"])
            yield (
                "data: "
                + json.dumps(
                    {
                        "event_type": EventType.DOCUMENT_ADD.value,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "content": doc_info,
                    },
                    ensure_ascii=False,
                )
                + "\n\n"
            )
        max_footnote_length = 4
        tmp_doc_cnt = doc_cnt
        while tmp_doc_cnt > 0:
            tmp_doc_cnt //= 10
            max_footnote_length += 1
        buffer = ""
        async for chunk in reasion_llm.call(
            messages,
            max_tokens=llm_config.maxToken,
            streaming=True,
            temperature=0.7,
            result_only=False,
            model=llm_config.modelName,
        ):
            tmp_chunk = buffer + chunk
            # 防止脚注被截断
            if len(tmp_chunk) >= 2 and tmp_chunk[-2:] != "]]":
                index = len(tmp_chunk) - 1
                while index >= max(0, len(tmp_chunk) - max_footnote_length) and tmp_chunk[index] != "]":
                    index -= 1
                if index >= 0:
                    buffer = tmp_chunk[index + 1:]
                    tmp_chunk = tmp_chunk[:index + 1]
            else:
                buffer = ""
            # 匹配脚注
            footnotes = re.findall(r"\[\[\d+\]\]", tmp_chunk)
            # 去除编号大于doc_cnt的脚注
            footnotes = [fn for fn in footnotes if int(fn[2:-2]) > doc_cnt]
            footnotes = list(set(footnotes))  # 去重
            if footnotes:
                for fn in footnotes:
                    tmp_chunk = tmp_chunk.replace(fn, "")
            output_tokens += TokenCalculator().calculate_token_length(
                messages=[
                    {"role": "assistant", "content": tmp_chunk},
                ],
                pure_text=True,
            )
            yield (
                "data: "
                + json.dumps(
                    {
                        "event_type": EventType.TEXT_ADD.value,
                        "content": tmp_chunk,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                    },
                    ensure_ascii=False,
                )
                + "\n\n"
            )
        if buffer:
            output_tokens += TokenCalculator().calculate_token_length(
                messages=[
                    {"role": "assistant", "content": buffer},
                ],
                pure_text=True,
            )
            yield (
                "data: "
                + json.dumps(
                    {
                        "event_type": EventType.TEXT_ADD.value,
                        "content": buffer,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                    },
                    ensure_ascii=False,
                )
                + "\n\n"
            )
