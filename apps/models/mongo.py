# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MongoDB 连接器"""

from __future__ import annotations

import logging
import urllib.parse
from typing import TYPE_CHECKING

from pymongo import AsyncMongoClient

from apps.common.config import Config

logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from pymongo.asynchronous.client_session import AsyncClientSession
    from pymongo.asynchronous.collection import AsyncCollection


class MongoDB:
    """MongoDB连接器"""

    _client: AsyncMongoClient = AsyncMongoClient(
        f"mongodb://{urllib.parse.quote_plus(Config().get_config().mongodb.user)}:{urllib.parse.quote_plus(Config().get_config().mongodb.password)}@{Config().get_config().mongodb.host}:{Config().get_config().mongodb.port}/?directConnection=true&replicaSet=rs0",
    )
    """异步的MongoDB Client"""

    @classmethod
    def get_collection(cls, collection_name: str) -> AsyncCollection:
        """
        获取MongoDB集合

        :param str collection_name: 集合名称
        :return: 集合对象
        :rtype: AsyncCollection
        """
        try:
            return cls._client[Config().get_config().mongodb.database][collection_name]
        except Exception as e:
            logger.exception("[MongoDB] 获取集合 %s 失败", collection_name)
            raise RuntimeError(str(e)) from e

    @classmethod
    async def clear_collection(cls, collection_name: str) -> None:
        """
        清空MongoDB集合

        :param str collection_name: 集合名称
        :return: 无
        """
        try:
            await cls._client[Config().get_config().mongodb.database][collection_name].delete_many({})
        except Exception:
            logger.exception("[MongoDB] 清空集合 %s 失败", collection_name)

    @classmethod
    def get_session(cls) -> AsyncClientSession:
        """
        获取MongoDB会话

        一个Client可以创建多个会话，一个会话一般用于一个事务。

        :return: 会话对象
        :rtype: AsyncClientSession
        """
        return cls._client.start_session()
