# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP基类"""

import logging
from typing import Any

from apps.llm.function import JsonGenerator
from apps.models.llm import LLMData

logger = logging.getLogger(__name__)


class MCPBase:
    """MCP基类"""

    user_sub: str

    def __init__(self, user_sub: str) -> None:
        """初始化MCP基类"""
        self.user_sub = user_sub

    async def init(self) -> None:
        pass

    async def get_resoning_result(self, prompt: str) -> str:
        """获取推理结果"""
        # 调用推理大模型
        message = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "Please provide a JSON response based on the above information and schema."},
        ]
        result = ""
        async for chunk in self.llm.call(
            message,
            streaming=False,
            temperature=0.07,
            result_only=False,
        ):
            result += chunk

        return result

    @staticmethod
    async def _parse_result(result: str, schema: dict[str, Any]) -> dict[str, Any]:
        """解析推理结果"""
        json_result = await JsonGenerator.parse_result_by_stack(result, schema)
        if json_result is not None:
            return json_result
        json_generator = JsonGenerator(
            "Please provide a JSON response based on the above information and schema.\n\n",
            [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": result},
            ],
            schema,
        )
        return await json_generator.generate()
