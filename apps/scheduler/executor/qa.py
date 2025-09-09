"""用于执行智能问答的Executor"""

import logging
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

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
        messages = [
            *history,
            {
                "role": "system",
                "content": "You are a helpful assistant.",
            },
            {
                "role": "user",
                "content": RAG.user_prompt[self.task.runtime.language].format(
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
                createdAt=round(doc.created_at, 3),
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
