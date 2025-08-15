"""大模型信息 数据库表"""

from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from apps.common.config import config
from apps.templates.generate_llm_operator_config import llm_provider_dict

from .base import Base


class LLMData(Base):
    """大模型信息"""

    __tablename__ = "framework_llm"
    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    """大模型ID"""
    icon: Mapped[str] = mapped_column(String(1000), default=llm_provider_dict["ollama"]["icon"], nullable=False)
    """LLM图标路径"""
    openaiBaseUrl: Mapped[str] = mapped_column(String(300), default=config.llm.endpoint, nullable=False)  # noqa: N815
    """LLM URL地址"""
    openaiAPIKey: Mapped[str] = mapped_column(String(300), default=config.llm.key, nullable=False)  # noqa: N815
    """LLM API Key"""
    modelName: Mapped[str] = mapped_column(String(300), default=config.llm.model, nullable=False)  # noqa: N815
    """LLM模型名"""
    maxToken: Mapped[int] = mapped_column(Integer, default=config.llm.max_tokens, nullable=False)  # noqa: N815
    """LLM最大Token数量"""
    createdAt: Mapped[DateTime] = mapped_column(  # noqa: N815
        DateTime,
        default_factory=lambda: datetime.now(tz=UTC),
        init=False,
        nullable=False,
    )
    """添加LLM的时间"""
