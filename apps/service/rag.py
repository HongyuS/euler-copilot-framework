# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""对接Euler Copilot RAG"""

import json
import logging
from collections.abc import AsyncGenerator

import httpx
from fastapi import status

from apps.common.config import Config
from apps.entities.collection import LLM
from apps.entities.config import LLMConfig
from apps.entities.enum_var import EventType
from apps.entities.rag_data import RAGQueryReq
from apps.llm.patterns.rewrite import QuestionRewrite
from apps.llm.reasoning import ReasoningLLM
from apps.llm.token import TokenCalculator
from apps.manager.session import SessionManager
from apps.service import Activity

logger = logging.getLogger(__name__)


class RAG:
    """调用RAG服务，获取知识库答案"""

    system_prompt: str = "You are a helpful assistant."
    """系统提示词"""
    user_prompt = """'
    <instructions>
            你是openEuler社区的智能助手。请结合给出的背景信息, 回答用户的提问。
            上下文背景信息将在<bac_info>中给出。
            用户的提问将在<user_question>中给出。
            注意：输出不要包含任何XML标签，不要编造任何信息。若你认为用户提问与背景信息无关，请忽略背景信息直接作答。
    </instructions>

    <bac_info>
            {bac_info}
    </bac_info>
    <user_question>
            {user_question}
    </user_question>
    """

    @staticmethod
    def get_k_tokens_words_from_content(content: str, k: int | None = None) -> str:
        """获取k个token的词"""
        if k is None:
            return content

        try:
            if TokenCalculator().calculate_token_length(messages=[
                {"role": "user", "content": content},
            ]) <= k:
                return content
            l = 0
            r = len(content)
            while l + 1 < r:
                mid = (l + r) // 2
                if TokenCalculator().calculate_token_length(messages=[
                    {"role": "user", "content": content[:mid]},
                ]) <= k:
                    l = mid
                else:
                    r = mid
            return content[:l]
        except Exception:
            logger.exception("[RAG] 获取k个token的词失败")
        return ""

    @staticmethod
    async def get_rag_result(
        user_sub: str, llm: LLM, history: list[dict[str, str]], doc_ids: list[str], data: RAGQueryReq,
    ) -> AsyncGenerator[str, None]:
        """获取RAG服务的结果"""
        session_id = await SessionManager.get_session_by_user_sub(user_sub)
        url = Config().get_config().rag.rag_service.rstrip("/") + "/chunk/search"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {session_id}",
        }
        data.tokens_limit = llm.max_tokens
        llm_config = LLMConfig(
            endpoint=llm.openai_base_url,
            key=llm.openai_api_key,
            model=llm.model_name,
            max_tokens=llm.max_tokens,
        )
        if history:
            try:
                question_obj = QuestionRewrite()
                data.query = await question_obj.generate(history=history, question=data.query)
            except Exception:
                logger.exception("[RAG] 问题重写失败")

        reasion_llm = ReasoningLLM(llm_config)
        corpus = []
        doc_id_name_list = []
        if doc_ids:
            tmp_data = RAGQueryReq(
                kb_ids=["00000000-0000-0000-0000-000000000000"],
                query=data.query,
                top_k=data.top_k,
                doc_ids=doc_ids,
                search_method=data.search_method,
                is_related_surrounding=data.is_related_surrounding,
                is_classify_by_doc=data.is_classify_by_doc,
                is_rerank=data.is_rerank,
                tokens_limit=data.tokens_limit
            )
            async with httpx.AsyncClient() as client:
                data_json = tmp_data.model_dump(exclude_none=True, by_alias=True)
                response = await client.post(url, headers=headers, json=data_json)
                if response.status_code == status.HTTP_200_OK:
                    result = response.json()
                    doc_chunk_list = result["result"]["docChunks"]
                    for doc_chunk in doc_chunk_list:
                        doc_id_name_list.append(
                            {
                                "id": doc_chunk["docId"],
                                "name": doc_chunk["docName"],
                            }
                        )
                        for chunk in doc_chunk["chunks"]:
                            corpus.append(chunk["text"].replace("\n", ""))
        if data.kb_ids:
            async with httpx.AsyncClient() as client:
                data_json = data.model_dump(exclude_none=True, by_alias=True)
                response = await client.post(url, headers=headers, json=data_json)
                # 检查响应状态码
                if response.status_code == status.HTTP_200_OK:
                    result = response.json()
                    doc_chunk_list = result["result"]["docChunks"]
                    for doc_chunk in doc_chunk_list:
                        doc_id_name_list.append(
                            {
                                "id": doc_chunk["docId"],
                                "name": doc_chunk["docName"],
                            }
                        )
                        for chunk in doc_chunk["chunks"]:
                            corpus.append(chunk["text"].replace("\n", ""))

        text = ""
        for i in range(len(corpus)):
            text += corpus[i] + "\n"
        text = RAG.get_k_tokens_words_from_content(text, llm.max_tokens)

        messages = [
            *history,
            {
                "role": "system",
                "content": RAG.system_prompt,
            },
            {
                "role": "user",
                "content": RAG.user_prompt.format(
                    bac_info=text,
                    user_question=data.query,
                ),
            },
        ]
        input_tokens = TokenCalculator().calculate_token_length(messages=messages)
        output_tokens = 0
        doc_id_name_set = set()
        for doc_id_name in doc_id_name_list:
            if json.dumps(doc_id_name) not in doc_id_name_set:
                doc_id_name_set.add(json.dumps(doc_id_name))
                yield (
                    "data: "
                    + json.dumps(
                        {
                            "event_type": EventType.DOCUMENT_ADD.value,
                            "input_tokens": input_tokens,
                            "output_tokens": output_tokens,
                            "content": doc_id_name,
                        },
                        ensure_ascii=False,
                    )
                    + "\n\n"
                )
        async for chunk in reasion_llm.call(
            messages,
            max_tokens=llm.max_tokens,
            streaming=True,
            temperature=0.7,
            result_only=False,
            model=llm.model_name,
        ):
            if not await Activity.is_active(user_sub):
                return
            output_tokens += TokenCalculator().calculate_token_length(
                messages=[
                    {"role": "assistant", "content": chunk},
                ],
            )
            yield (
                "data: "
                + json.dumps(
                    {
                        "event_type": EventType.TEXT_ADD.value,
                        "content": chunk,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                    },
                    ensure_ascii=False,
                )
                + "\n\n"
            )
