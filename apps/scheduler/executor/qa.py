"""用于执行智能问答的Executor"""

import logging
import uuid
from datetime import UTC, datetime

from apps.models import ExecutorCheckpoint, ExecutorStatus, StepStatus
from apps.models.task import LanguageType
from apps.scheduler.call.rag.schema import DocItem, RAGOutput
from apps.schemas.document import DocumentInfo
from apps.schemas.enum_var import EventType, SpecialCallType
from apps.schemas.flow import Step
from apps.schemas.message import DocumentAddContent
from apps.schemas.task import StepQueueItem

from .base import BaseExecutor
from .step import StepExecutor

_logger = logging.getLogger(__name__)
_RAG_STEP_LIST = [
    {
        LanguageType.CHINESE: Step(
            name="RAG检索",
            description="从知识库中检索相关文档",
            node="RAG",
            type="RAG",
        ),
        LanguageType.ENGLISH: Step(
            name="RAG retrieval",
            description="Retrieve relevant documents from the knowledge base",
            node="RAG",
            type="RAG",
        ),
    },
    {
        LanguageType.CHINESE: Step(
            name="LLM问答",
            description="基于检索到的文档生成答案",
            node="LLM",
            type="LLM",
        ),
        LanguageType.ENGLISH: Step(
            name="LLM answer",
            description="Generate answer based on the retrieved documents",
            node="LLM",
            type="LLM",
        ),
    },
    {
        LanguageType.CHINESE: Step(
            name="问题推荐",
            description="根据对话答案，推荐相关问题",
            node="Suggestion",
            type="Suggestion",
        ),
        LanguageType.ENGLISH: Step(
            name="Question Suggestion",
            description="Display the suggested next question under the answer",
            node="Suggestion",
            type="Suggestion",
        ),
    },
    {
        LanguageType.CHINESE: Step(
            name="记忆存储",
            description="理解对话答案，并存储到记忆中",
            node=SpecialCallType.FACTS.value,
            type=SpecialCallType.FACTS.value,
        ),
        LanguageType.ENGLISH: Step(
            name="Memory storage",
            description="Understand the answer of the dialogue and store it in the memory",
            node=SpecialCallType.FACTS.value,
            type=SpecialCallType.FACTS.value,
        ),
    },
]


class QAExecutor(BaseExecutor):
    """用于执行智能问答的Executor"""

    async def init(self) -> None:
        """初始化QAExecutor"""
        await self._load_history()
        # 初始化新State
        self.task.state = ExecutorCheckpoint(
            taskId=self.task.metadata.id,
            executorId=str(self.task.metadata.conversationId),
            executorName="QAExecutor",
            executorStatus=ExecutorStatus.RUNNING,
            stepStatus=StepStatus.RUNNING,
            stepId=uuid.uuid4(),
            stepName="QAExecutor",
            appId=None,
        )

    async def _assemble_doc_info(
        self,
        doc_chunk_list: list[DocItem],
        max_tokens: int,
    ) -> list[DocumentInfo]:
        """组装文档信息"""
        doc_info_list = []
        doc_cnt = 0
        doc_id_map = {}
        # 预留tokens
        _ = round(max_tokens * 0.8)

        for doc_chunk in doc_chunk_list:
            if doc_chunk.docId not in doc_id_map:
                doc_cnt += 1
                # 创建DocumentInfo对象
                created_at_value = (
                    doc_chunk.docCreatedAt.timestamp()
                    if isinstance(doc_chunk.docCreatedAt, datetime)
                    else doc_chunk.docCreatedAt
                )
                doc_info = DocumentInfo(
                    id=doc_chunk.docId,
                    order=doc_cnt,
                    name=doc_chunk.docName,
                    author=doc_chunk.docAuthor,
                    extension=doc_chunk.docExtension,
                    abstract=doc_chunk.docAbstract,
                    size=doc_chunk.docSize,
                    created_at=created_at_value,
                )
                doc_info_list.append(doc_info)
                doc_id_map[doc_chunk.docId] = doc_cnt

        return doc_info_list

    async def run(self) -> None:
        """运行QA"""
        rag_exec = StepExecutor(
            msg_queue=self.msg_queue,
            task=self.task,
            step=StepQueueItem(
                step_id=uuid.uuid4(),
                step=_RAG_STEP_LIST[0][self.task.runtime.language],
                enable_filling=False,
                to_user=False,
            ),
            background=self.background,
            question=self.question,
            llm=self.llm,
        )
        await rag_exec.init()
        await rag_exec.run()



        # 解析并推送文档信息
        if first_chunk and isinstance(first_chunk.content, dict):
            rag_output = RAGOutput.model_validate(first_chunk.content)
            doc_chunk_list: list[DocItem] = [
                DocItem.model_validate(item) if not isinstance(item, DocItem) else item
                for item in rag_output.corpus
            ]
            doc_info_list = await self._assemble_doc_info(doc_chunk_list, 8192)
            for doc_info in doc_info_list:
                await self._push_rag_doc(doc_info)

        # 保存答案
        full_answer = ""
        self.task.runtime.fullAnswer = full_answer
        self.task.runtime.fullTime = round(datetime.now(UTC).timestamp(), 2) - self.task.runtime.time
