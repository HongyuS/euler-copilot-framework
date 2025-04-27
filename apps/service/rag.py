"""
对接Euler Copilot RAG

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

import json
import logging
from collections.abc import AsyncGenerator

import httpx
from fastapi import status

from apps.common.config import Config
from apps.entities.rag_data import RAGQueryReq
from apps.service import Activity

logger = logging.getLogger(__name__)

class RAG:
    """调用RAG服务，获取知识库答案"""

    @staticmethod
    async def get_rag_result(user_sub: str, data: RAGQueryReq) -> AsyncGenerator[str, None]:
        """获取RAG服务的结果"""
        url = Config().get_config().rag.rag_service.rstrip("/") + "/kb/get_stream_answer"
        headers = {
            "Content-Type": "application/json",
        }

        payload = json.dumps(data.model_dump(exclude_none=True, by_alias=True), ensure_ascii=False)


        # asyncio HTTP请求
        async with (
            httpx.AsyncClient(timeout=300, verify=False) as client,  # noqa: S501
            client.stream("POST", url, headers=headers, content=payload) as response,
        ):
            if response.status_code != status.HTTP_200_OK:
                logger.error("[RAG] RAG服务返回错误码: %s\n%s", response.status_code, await response.aread())
                return

            async for line in response.aiter_lines():
                if not await Activity.is_active(user_sub):
                    return

                if "data: [DONE]" in line:
                    return

                yield line
