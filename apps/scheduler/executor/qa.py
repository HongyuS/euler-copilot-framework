"""用于执行智能问答的Executor"""
import uuid

from apps.models.document import Document
from apps.schemas.record import RecordDocument
from apps.services.document import DocumentManager

from .base import BaseExecutor


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

    async def run(self) -> None:
        """运行QA"""
        pass
