# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""RAG工具的输入和输出"""

import uuid
from enum import Enum

from pydantic import Field

from apps.scheduler.call.core import DataBase


class SearchMethod(str, Enum):
    """搜索方法"""

    KEYWORD = "keyword"
    VECTOR = "vector"
    KEYWORD_AND_VECTOR = "keyword_and_vector"
    DOC2CHUNK = "doc2chunk"
    DOC2CHUNK_BFS = "doc2chunk_bfs"
    ENHANCED_BY_LLM = "enhanced_by_llm"


class RAGOutput(DataBase):
    """RAG工具的输出"""

    question: str = Field(description="用户输入")
    corpus: list[str] = Field(description="知识库的语料列表")


class RAGInput(DataBase):
    """RAG工具的输入"""

    session_id: str = Field(description="会话id")
    knowledge_base_ids: list[uuid.UUID] = Field(description="知识库的id列表", default=[], alias="kbIds")
    top_k: int = Field(description="返回的分片数量", default=5, alias="topK")
    question: str = Field(description="用户输入", default="", alias="query")
    document_ids: list[uuid.UUID] = Field(description="文档id列表", default=[], alias="docIds")
    search_method: str = Field(
        description="检索方法",
        default=SearchMethod.KEYWORD_AND_VECTOR.value,
        alias="searchMethod",
    )
    is_related_surrounding: bool = Field(
        description="是否关联上下文", default=True, alias="isRelatedSurrounding",
    )
    is_classify_by_doc: bool = Field(description="是否按文档分类", default=False, alias="isClassifyByDoc")
    is_rerank: bool = Field(description="是否重新排序", default=False, alias="isRerank")
    is_compress: bool = Field(description="是否压缩", default=False, alias="isCompress")
    tokens_limit: int = Field(description="token限制", default=8192, alias="tokensLimit")
