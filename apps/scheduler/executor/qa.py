"""用于执行智能问答的Executor"""
import logging
import uuid
from datetime import UTC, datetime
from textwrap import dedent

from apps.models.document import Document
from apps.schemas.enum_var import EventType
from apps.schemas.message import DocumentAddContent, TextAddContent
from apps.schemas.rag_data import RAGEventData
from apps.schemas.record import RecordDocument
from apps.services.document import DocumentManager
from apps.services.rag import RAG

from .base import BaseExecutor

_logger = logging.getLogger(__name__)


class QAExecutor(BaseExecutor):
    """用于执行智能问答的Executor"""

    async def get_docs(self, conversation_id: uuid.UUID) -> tuple[list[RecordDocument] | list[Document], list[str]]:
        """获取当前问答可供关联的文档"""
        doc_ids = []
        # 从Conversation中获取刚上传的文档
        docs = await DocumentManager.get_unused_docs(conversation_id)
        # 从最近10条Record中获取文档
        docs += await DocumentManager.get_used_docs(conversation_id, 10, "question")
        doc_ids += [doc.id for doc in docs]
        return docs, doc_ids


    async def _push_rag_chunk(self, content: str) -> RAGEventData | None:
        """推送RAG单个消息块"""
        # 如果是换行
        if not content or not content.rstrip().rstrip("\n"):
            return None

        try:
            content_obj = RAGEventData.model_validate_json(dedent(content[6:]).rstrip("\n"))
            # 如果是空消息
            if not content_obj.content:
                return None

            # 推送消息
            if content_obj.event_type == EventType.TEXT_ADD.value:
                await self.msg_queue.push_output(
                    task=self.task,
                    event_type=content_obj.event_type,
                    data=TextAddContent(text=content_obj.content).model_dump(exclude_none=True, by_alias=True),
                )
            elif content_obj.event_type == EventType.DOCUMENT_ADD.value:
                await self.msg_queue.push_output(
                    task=self.task,
                    event_type=content_obj.event_type,
                    data=DocumentAddContent(
                        documentId=content_obj.content.get("id", ""),
                        documentOrder=content_obj.content.get("order", 0),
                        documentAuthor=content_obj.content.get("author", ""),
                        documentName=content_obj.content.get("name", ""),
                        documentAbstract=content_obj.content.get("abstract", ""),
                        documentType=content_obj.content.get("extension", ""),
                        documentSize=content_obj.content.get("size", 0),
                        createdAt=round(content_obj.content.get("created_at", datetime.now(tz=UTC).timestamp()), 3),
                    ).model_dump(exclude_none=True, by_alias=True),
                )
        except Exception:
            _logger.exception("[Scheduler] RAG服务返回错误数据")
            return None
        else:
            return content_obj

    async def run(self) -> None:
        """运行QA"""
        full_answer = ""

        try:
            async for chunk in RAG.chat_with_llm_base_on_rag(user_sub, llm, history, doc_ids, rag_data):
                task, content_obj = await self._push_rag_chunk(task, queue, chunk)
                if not content_obj:
                    continue
                if content_obj.event_type == EventType.TEXT_ADD.value:
                    # 如果是文本消息，直接拼接到答案中
                    full_answer += content_obj.content
                elif content_obj.event_type == EventType.DOCUMENT_ADD.value:
                    task.runtime.documents.append(content_obj.content)
            task.state.flow_status = ExecutorStatus.SUCCESS
        except Exception as e:
            logger.error(f"[Scheduler] RAG服务发生错误: {e}")
            task.state.flow_status = ExecutorStatus.ERROR
        # 保存答案
        task.runtime.answer = full_answer
        task.tokens.full_time = round(datetime.now(UTC).timestamp(), 2) - task.tokens.time
        await TaskManager.save_task(task.id, task)
