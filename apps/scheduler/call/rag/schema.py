# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""RAG工具的输入和输出"""

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from apps.scheduler.call.core import DataBase


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


class DocChunks(BaseModel):
    """文档语料"""

    chunkId: uuid.UUID = Field(description="语料id")  # noqa: N815
    chunkType: str = Field(description="语料类型")  # noqa: N815
    text: str = Field(description="语料文本")
    enabled: bool = Field(description="是否启用")


class DocItem(BaseModel):
    """文档信息"""

    docId: uuid.UUID = Field(description="文档id")  # noqa: N815
    docCreatedAt: datetime = Field(description="文档创建时间")  # noqa: N815
    docName: str = Field(description="文档名称")  # noqa: N815
    docAuthor: str = Field(description="文档作者")  # noqa: N815
    docExtension: str = Field(description="文档扩展名")  # noqa: N815
    docSize: int = Field(description="文档大小")  # noqa: N815
    docAbstract: str = Field(description="文档摘要")  # noqa: N815
    chunks: list[DocChunks] = Field(description="文档语料")


class RAGOutput(DataBase):
    """RAG工具的输出"""

    question: str = Field(description="用户输入")
    corpus: list[DocItem] = Field(description="知识库的语料列表")


class RAGInput(DataBase):
    """RAG API查询请求体"""

    kbIds: list[uuid.UUID] = Field(default=[], description="资产id")  # noqa: N815
    query: str = Field(default="", description="查询内容")
    topK: int = Field(default=5, description="返回的结果数量")  # noqa: N815
    docIds: list[str] | None = Field(default=None, description="文档id")  # noqa: N815
    searchMethod: str = Field(default="dynamic_weighted_keyword_and_vector", description="检索方法")  # noqa: N815
    isRelatedSurrounding: bool = Field(default=True, description="是否关联上下文")  # noqa: N815
    isClassifyByDoc: bool = Field(default=True, description="是否按文档分类")  # noqa: N815
    isRerank: bool = Field(default=False, description="是否重新排序")  # noqa: N815
    tokensLimit: int | None = Field(default=None, description="token限制")  # noqa: N815
    isCompress: bool = Field(description="是否压缩", default=False)  # noqa: N815
