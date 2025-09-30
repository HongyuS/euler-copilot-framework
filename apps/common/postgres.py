"""Postgres连接器"""

import logging
import urllib.parse
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from apps.models import Base

from .config import config

logger = logging.getLogger(__name__)


class Postgres:
    """Postgres连接器"""

    engine: AsyncEngine

    async def init(self) -> None:
        """初始化Postgres连接器"""
        logger.info("[Postgres] 初始化Postgres连接器")
        self.engine = create_async_engine(
            f"postgresql+asyncpg://{urllib.parse.quote_plus(config.postgres.user)}:"
            f"{urllib.parse.quote_plus(config.postgres.password)}@{config.postgres.host}:"
            f"{config.postgres.port}/{config.postgres.database}",
        )
        self._session = async_sessionmaker(self.engine, expire_on_commit=False)

        logger.info("[Postgres] 创建表")
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """获取会话"""
        async with self._session() as session:
            try:
                yield session
            except Exception:
                logger.exception("[Postgres] 会话错误")
                await session.rollback()
                raise
            finally:
                await session.close()

postgres = Postgres()
