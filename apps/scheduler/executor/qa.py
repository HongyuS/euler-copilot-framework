"""用于执行智能问答的Executor"""

import json
import logging
import re
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

from apps.llm.token import TokenCalculator
from apps.models.document import Document
from apps.scheduler.call import LLM, RAG
from apps.schemas.enum_var import EventType, ExecutorStatus
from apps.schemas.message import DocumentAddContent, TextAddContent
from apps.schemas.record import RecordDocument
from apps.services.document import DocumentManager

from .base import BaseExecutor

_logger = logging.getLogger(__name__)


class QAExecutor(BaseExecutor):
    """用于执行智能问答的Executor"""

    async def _get_docs(self, conversation_id: uuid.UUID) -> tuple[list[RecordDocument] | list[Document], list[str]]:
        """获取当前问答可供关联的文档"""
        doc_ids = []
        # 从Conversation中获取刚上传的文档
        docs = await DocumentManager.get_unused_docs(conversation_id)
        # 从最近10条Record中获取文档
        docs += await DocumentManager.get_used_docs(conversation_id, 10, "question")
        doc_ids += [doc.id for doc in docs]
        return docs, doc_ids


    async def _push_rag_text(self, content: str) -> None:
        """推送RAG单个消息块"""
        # 如果是换行
        if not content or not content.rstrip().rstrip("\n"):
            return
        await self._push_message(
            event_type=EventType.TEXT_ADD.value,
            data=TextAddContent(text=content).model_dump(exclude_none=True, by_alias=True),
        )


    async def chat_with_llm_base_on_rag(
        self,
        doc_ids: list[str],
        data: RAGInput,
    ) -> AsyncGenerator[str, None]:
        """获取RAG服务的结果"""
        bac_info, doc_info_list = await self._assemble_doc_info(
            doc_chunk_list=doc_chunk_list, max_tokens=llm_config.maxToken,
        )
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

        full_result = ""
        async for chunk in self._llm(
            messages,
            streaming=True,
        ):
            full_result += chunk
            yield chunk

        # 匹配脚注
        footnotes = re.findall(r"\[\[\d+\]\]", tmp_chunk)
        # 去除编号大于doc_cnt的脚注
        footnotes = [fn for fn in footnotes if int(fn[2:-2]) > doc_cnt]
        footnotes = list(set(footnotes))  # 去重


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
        remaining_tokens = round(max_tokens * 0.8)

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
                if remaining_tokens <= 0:
                    break
                chunk_text = chunk["text"]
                chunk_text = TokenCalculator().get_k_tokens_words_from_content(
                    content=chunk_text, k=remaining_tokens,
                )
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


    async def _push_rag_doc(self, doc: Document) -> None:
        """推送RAG单个消息块"""
        # 如果是换行
        await self._push_message(
            event_type=EventType.DOCUMENT_ADD.value,
            data=DocumentAddContent(
                documentId=doc.id,
                documentOrder=doc.order,
                documentAuthor=doc.author,
                documentName=doc.name,
                documentAbstract=doc.abstract,
                documentType=doc.extension,
                documentSize=doc.size,
                createdAt=round(doc.createdAt, 3),
            ).model_dump(exclude_none=True, by_alias=True),
        )

    async def run(self) -> None:
        """运行QA"""
        full_answer = ""

        try:
            async for chunk in RAG.chat_with_llm_base_on_rag(
                user_sub, llm, history, doc_ids, rag_data
            ):
                task, content_obj = await self._push_rag_chunk(task, queue, chunk)
                if not content_obj:
                    continue
                if content_obj.event_type == EventType.TEXT_ADD.value:
                    # 如果是文本消息，直接拼接到答案中
                    full_answer += content_obj.content
                elif content_obj.event_type == EventType.DOCUMENT_ADD.value:
                    task.runtime.documents.append(content_obj.content)
            task.state.flow_status = ExecutorStatus.SUCCESS
        except Exception:
            _logger.exception("[Scheduler] RAG服务发生错误 ")
            task.state.flow_status = ExecutorStatus.ERROR
        # 保存答案
        self.task.runtime.fullAnswer = full_answer
        self.task.runtime.fullTime = round(datetime.now(UTC).timestamp(), 2) - self.task.runtime.time
