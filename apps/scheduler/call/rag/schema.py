"""RAG工具的输入和输出"""

from enum import Enum

from pydantic import Field

from apps.scheduler.call.core import DataBase


class RetrievalMode(str, Enum):
    """检索模式"""

    CHUNK = "chunk"
    FULL_TEXT = "full_text"


class RAGOutput(DataBase):
    """RAG工具的输出"""

    question: str = Field(description="用户输入")
    corpus: list[str] = Field(description="知识库的语料列表")


class RAGInput(DataBase):
    """RAG工具的输入"""

    content: str = Field(description="用户输入")
    knowledge_base: str | None = Field(description="知识库的id", alias="kb_sn", default=None)
    top_k: int = Field(description="返回的答案数量(经过整合以及上下文关联)", default=5)
    retrieval_mode: RetrievalMode = Field(description="检索模式", default=RetrievalMode.CHUNK)
