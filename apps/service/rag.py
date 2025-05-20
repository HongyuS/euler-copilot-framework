"""
对接Euler Copilot RAG

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
import tiktoken
import httpx
from fastapi import status

from apps.llm.patterns.rewrite import QuestionRewrite
from apps.manager.session import SessionManager
from apps.common.config import Config
from apps.llm.reasoning import ReasoningLLM
from apps.entities.collection import LLM
from apps.entities.rag_data import RAGQueryReq
from apps.entities.config import LLMConfig
from apps.service import Activity

logger = logging.getLogger(__name__)


class RAG:
    """调用RAG服务，获取知识库答案"""
    system_prompt: str = "You are a helpful assistant."
    """系统提示词"""
    user_prompt = ''''
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
    '''

    @staticmethod
    def get_tokens(content: str) -> int:
        try:
            enc = tiktoken.encoding_for_model("gpt-4")
            return len(enc.encode(str(content)))
        except Exception as e:
            err = f"[TokenTool] 获取token失败 {e}"
            logging.exception("[TokenTool] %s", err)
        return 0

    @staticmethod
    def get_k_tokens_words_from_content(content: str, k: int = 16) -> list:
        try:
            if (RAG.get_tokens(content) <= k):
                return content
            l = 0
            r = len(content)
            while l+1 < r:
                mid = (l+r)//2
                if (RAG.get_tokens(content[:mid]) <= k):
                    l = mid
                else:
                    r = mid
            return content[:l]
        except Exception as e:
            err = f"[RAG] 获取k个token的词失败 {e}"
            logging.exception("[RAG] %s", err)
        return ""

    @staticmethod
    async def get_rag_result(user_sub: str, llm: LLM, history: list[dict[str, str]],
                             data: RAGQueryReq) -> AsyncGenerator[str, None]:
        """获取RAG服务的结果"""
        session_id = await SessionManager.get_session_by_user_sub(user_sub)
        url = Config().get_config().rag.rag_service.rstrip("/") + "/chunk/search"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {session_id}"
        }
        print(session_id)
        data.tokens_limit = llm.max_tokens
        llm_config = LLMConfig(
            endpoint=llm.openai_base_url,
            key=llm.openai_api_key,
            model=llm.model_name,
            max_tokens=llm.max_tokens,
        )
        if history:
            try:
                question_obj = QuestionRewrite(llm_config)
                data.query = await question_obj.generate(history=history, question=data.query)
            except Exception as e:
                logger.error("[RAG] 问题重写失败: %s", e)
        reasion_llm = ReasoningLLM(llm_config)
        corpus = []
        async with httpx.AsyncClient() as client:
            data_json = data.model_dump(exclude_none=True, by_alias=True)
            print(data_json)
            response = await client.post(url, headers=headers, json=data_json)
            print(response.text)
            # 检查响应状态码
            if response.status_code == status.HTTP_200_OK:
                result = response.json()
                doc_chunk_list = result["result"]["docChunks"]
                for doc_chunk in doc_chunk_list:
                    for chunk in doc_chunk["chunks"]:
                        corpus.append(chunk["text"].replace("\n", ""))
        text = ''
        for i in range(len(corpus)):
            text += corpus[i]+'\n'
        text = RAG.get_k_tokens_words_from_content(text, llm.max_tokens)

        messages = history+[
            {"role": "system", "content": RAG.system_prompt},
            {"role": "user", "content": RAG.user_prompt.format(
                bac_info=text,
                user_question=data.query,
            )},
        ]
        input_tokens = RAG.get_tokens(text)
        async for chunk in reasion_llm.call(messages, max_tokens=llm.max_tokens, streaming=True, temperature=0.7, result_only=False):
            yield "data: " + json.dumps(
                {'content': chunk,
                 'input_tokens': input_tokens,
                 'output_tokens': RAG.get_tokens(chunk),
                 }, ensure_ascii=False
            ) + '\n\n'
