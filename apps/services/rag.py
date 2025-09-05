# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""对接Euler Copilot RAG"""

import json
import logging
import re
from collections.abc import AsyncGenerator

from apps.llm.token import TokenCalculator
from apps.schemas.enum_var import EventType, LanguageType
from apps.schemas.rag_data import RAGQueryReq

logger = logging.getLogger(__name__)


class RAG:
    """调用RAG服务，获取知识库答案"""

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
        if history:
            pass
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
