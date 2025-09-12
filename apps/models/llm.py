"""大模型信息 数据库表"""

from datetime import UTC, datetime
from enum import Enum as PyEnum
from typing import Any

from sqlalchemy import ARRAY, DateTime, Enum, Float, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class LLMType(str, PyEnum):
    """大模型类型"""

    FUNCTION = "function"
    """模型支持Function Call"""
    EMBEDDING = "embedding"
    """模型支持Embedding"""
    VISION = "vision"
    """模型支持图片理解"""
    THINKING = "thinking"
    """模型支持思考推理"""


class LLMProvider(str, PyEnum):
    """Function Call后端"""

    OLLAMA = "ollama"
    """Ollama"""
    VLLM = "vllm"
    """VLLM"""
    OPENAI = "openai"
    """OpenAI"""
    TEI = "tei"
    """TEI"""
    LM_STUDIO = "lm_studio"
    """LLM Studio"""


class LLMData(Base):
    """大模型信息"""

    __tablename__ = "framework_llm"
    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    """大模型ID"""
    baseUrl: Mapped[str] = mapped_column(String(300), nullable=False)  # noqa: N815
    """LLM URL地址"""
    apiKey: Mapped[str] = mapped_column(String(300), nullable=False)  # noqa: N815
    """LLM API Key"""
    modelName: Mapped[str] = mapped_column(String(300), nullable=False)  # noqa: N815
    """LLM模型名"""
    maxToken: Mapped[int] = mapped_column(Integer, default=8192, nullable=False)  # noqa: N815
    """LLM最大Token数量"""
    temperature: Mapped[float] = mapped_column(Float, default=0.7, nullable=False)
    """LLM温度"""
    llmType: Mapped[list[LLMType]] = mapped_column(ARRAY(Enum(LLMType)), default=[], nullable=False)  # noqa: N815
    """LLM类型"""
    provider: Mapped[LLMProvider] = mapped_column(
        Enum(LLMProvider), default=None, nullable=True,
    )
    extraConfig: Mapped[dict[str, Any]] = mapped_column(JSONB, default={}, nullable=False)  # noqa: N815
    """大模型API类型"""
    createdAt: Mapped[DateTime] = mapped_column(  # noqa: N815
        DateTime,
        default_factory=lambda: datetime.now(tz=UTC),
        init=False,
        nullable=False,
    )
    """添加LLM的时间"""
