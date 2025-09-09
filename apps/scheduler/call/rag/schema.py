# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""RAG工具的输入和输出"""

import uuid
from enum import Enum

from pydantic import BaseModel, Field

from apps.scheduler.call.core import DataBase

CHUNK_ELEMENT_TOKENS = 5


class SearchMethod(str, Enum):
    """搜索方法"""

    KEYWORD = "keyword"
    VECTOR = "vector"
    KEYWORD_AND_VECTOR = "keyword_and_vector"
    DOC2CHUNK = "doc2chunk"
    DOC2CHUNK_BFS = "doc2chunk_bfs"
    ENHANCED_BY_LLM = "enhanced_by_llm"


class QuestionRewriteOutput(BaseModel):
    """问题重写工具的输出"""

    question: str = Field(description="用户输入")


class RAGOutput(DataBase):
    """RAG工具的输出"""

    question: str = Field(description="用户输入")
    corpus: list[str] = Field(description="知识库的语料列表")


class RAGInput(DataBase):
    """RAG工具的输入"""

    # 来自RAGInput的独有字段
    session_id: str = Field(description="会话id")
    is_compress: bool = Field(description="是否压缩", default=False, alias="isCompress")

    # 来自RAGQueryReq的字段（以RAGQueryReq为准）
    kb_ids: list[uuid.UUID] = Field(default=[], description="资产id", alias="kbIds")
    query: str = Field(default="", description="查询内容")
    top_k: int = Field(default=5, description="返回的结果数量", alias="topK")
    doc_ids: list[str] | None = Field(default=None, description="文档id", alias="docIds")
    search_method: str = Field(default="dynamic_weighted_keyword_and_vector",
                               description="检索方法", alias="searchMethod")
    is_related_surrounding: bool = Field(default=True, description="是否关联上下文", alias="isRelatedSurrounding")
    is_classify_by_doc: bool = Field(default=True, description="是否按文档分类", alias="isClassifyByDoc")
    is_rerank: bool = Field(default=False, description="是否重新排序", alias="isRerank")
    tokens_limit: int | None = Field(default=None, description="token限制", alias="tokensLimit")
