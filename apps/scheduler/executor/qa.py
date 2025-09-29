"""用于执行智能问答的Executor"""

import json
import logging
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from apps.llm import TokenCalculator
from apps.models import Document, ExecutorCheckpoint, ExecutorStatus, StepStatus
from apps.models.task import LanguageType
from apps.scheduler.call.rag.schema import DocItem, RAGInput
from apps.schemas.document import DocumentInfo
from apps.schemas.enum_var import EventType, SpecialCallType
from apps.schemas.flow import Step
from apps.schemas.message import DocumentAddContent, TextAddContent
from apps.schemas.record import RecordDocument
from apps.schemas.task import StepQueueItem
from apps.services import DocumentManager

from .base import BaseExecutor
from .prompt import GEN_RAG_ANSWER
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

    async def _construct_prompt(
        self,
        doc_ids: list[str],
        data: RAGInput,
    ) -> AsyncGenerator[str, None]:
        """获取RAG服务的结果"""
        # 获取文档信息
        doc_chunk_list = await self._fetch_doc_chunks(data)
        bac_info, doc_info_list = await self._assemble_doc_info(
            doc_chunk_list=doc_chunk_list, max_tokens=8192,
        )
        # 构建提示词
        prompt_template = GEN_RAG_ANSWER[self.task.runtime.language]
        prompt = prompt_template.format(bac_info=bac_info, user_question=data.query)
        # 计算token数
        input_tokens = TokenCalculator().calculate_token_length(messages=[{"role": "system", "content": prompt}])
        output_tokens = 0
        doc_cnt: int = 0
        for doc_info in doc_info_list:
            doc_cnt = max(doc_cnt, doc_info.order)
            yield (
                "data: "
                + json.dumps(
                    {
                        "event_type": EventType.DOCUMENT_ADD.value,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "content": doc_info.model_dump(),
                    },
                    ensure_ascii=False,
                )
                + "\n\n"
            )
        # 使用LLM的推理模型调用大模型
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": data.query},
        ]

    async def _assemble_doc_info(
        self,
        doc_chunk_list: list[DocItem],
        max_tokens: int,
    ) -> tuple[str, list[DocumentInfo]]:
        """组装文档信息"""
        bac_info = ""
        doc_info_list = []
        doc_cnt = 0
        doc_id_map = {}
        remaining_tokens = round(max_tokens * 0.8)

        for doc_chunk in doc_chunk_list:
            if doc_chunk.docId not in doc_id_map:
                doc_cnt += 1
                # 创建DocumentInfo对象
                doc_info = DocumentInfo(
                    id=doc_chunk.docId,
                    order=doc_cnt,
                    name=doc_chunk.docName,
                    author=doc_chunk.docAuthor,
                    extension=doc_chunk.docExtension,
                    abstract=doc_chunk.docAbstract,
                    size=doc_chunk.docSize,
                    created_at=doc_chunk.docCreatedAt.timestamp() if isinstance(doc_chunk.docCreatedAt, datetime) else doc_chunk.docCreatedAt,
                )
                doc_info_list.append(doc_info)
                doc_id_map[doc_chunk.docId] = doc_cnt
            doc_index = doc_id_map[doc_chunk.docId]

            if bac_info:
                bac_info += "\n\n"
            bac_info += f"""<document id="{doc_index}"  name="{doc_chunk.docName}">"""

            for chunk in doc_chunk.chunks:
                if remaining_tokens <= 0:
                    break
                chunk_text = chunk.text
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

    async def _push_rag_doc(self, doc: DocumentInfo, document_order: int = 1) -> None:
        """推送RAG使用的文档信息"""
        await self._push_message(
            event_type=EventType.DOCUMENT_ADD.value,
            data=DocumentAddContent(
                documentId=str(doc.id),
                documentOrder=doc.order,
                documentAuthor=doc.author,
                documentName=doc.name,
                documentAbstract=doc.abstract,
                documentType=doc.extension,
                documentSize=doc.size,
                createdAt=doc.created_at,
            ).model_dump(exclude_none=True, by_alias=True),
        )

    async def run(self) -> None:
        """运行QA"""
        # 运行RAG步骤
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



        # 保存答案
        self.task.runtime.fullAnswer = full_answer
        self.task.runtime.fullTime = round(datetime.now(UTC).timestamp(), 2) - self.task.runtime.time
