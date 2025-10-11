# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""选择MCP Server及其工具"""

import logging

from sqlalchemy import select

from apps.common.postgres import postgres
from apps.llm import JsonGenerator
from apps.models import MCPTools
from apps.schemas.mcp import MCPSelectResult
from apps.schemas.scheduler import LLMConfig
from apps.services.mcp_service import MCPServiceManager

logger = logging.getLogger(__name__)


class MCPSelector:
    """MCP选择器"""

    def __init__(self, llm: LLMConfig) -> None:
        """初始化MCP选择器"""
        self._llm = llm

    async def _call_reasoning(self, prompt: str) -> str:
        """调用大模型进行推理"""
        logger.info("[MCPSelector] 调用推理大模型")
        message = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ]
        result = ""
        async for chunk in self._llm.reasoning.call(message):
            result += chunk.content or ""
        return result


    async def _call_function_mcp(self, reasoning_result: str, mcp_ids: list[str]) -> MCPSelectResult:
        """调用结构化输出小模型提取JSON"""
        if not self._llm.function:
            err = "[MCPSelector] 未设置Function模型"
            logger.error(err)
            raise RuntimeError(err)

        logger.info("[MCPSelector] 调用结构化输出小模型")
        schema = MCPSelectResult.model_json_schema()
        # schema中加入选项
        schema["properties"]["mcp_id"]["enum"] = mcp_ids

        # 使用JsonGenerator生成JSON
        conversation = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": reasoning_result},
        ]
        generator = JsonGenerator(
            llm=self._llm.function,
            query=reasoning_result,
            conversation=conversation,
            schema=schema,
        )
        result = await generator.generate()

        try:
            result = MCPSelectResult.model_validate(result)
        except Exception:
            logger.exception("[MCPSelector] 解析MCP Select Result失败")
            raise
        return result


    async def select_top_tool(self, query: str, mcp_list: list[str], top_n: int = 10) -> list[MCPTools]:
        """选择最合适的工具"""
        if not self._llm.embedding:
            err = "[MCPSelector] 未设置Embedding模型"
            logger.error(err)
            raise RuntimeError(err)

        query_embedding = await self._llm.embedding.get_embedding([query])
        async with postgres.session() as session:
            tool_vecs = await session.scalars(
                select(self._llm.embedding.MCPToolVector).where(self._llm.embedding.MCPToolVector.mcpId.in_(mcp_list))
                .order_by(self._llm.embedding.MCPToolVector.embedding.cosine_distance(query_embedding)).limit(top_n),
            )

        # 拿到工具
        llm_tool_list = []

        for tool_vec in tool_vecs:
            logger.info("[MCPHelper] 查询MCP Tool名称和描述: %s", tool_vec.mcpId)
            tool_data = await MCPServiceManager.get_mcp_tools(tool_vec.mcpId)
            llm_tool_list.extend(tool_data)

        return llm_tool_list
