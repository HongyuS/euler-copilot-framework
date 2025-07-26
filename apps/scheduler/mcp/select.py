# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""选择MCP Server及其工具"""

import logging

from apps.llm.embedding import Embedding
from apps.llm.function import FunctionLLM
from apps.llm.reasoning import ReasoningLLM
from apps.models.mcp import MCPTools
from apps.schemas.mcp import MCPSelectResult
from apps.services.mcp_service import MCPServiceManager

logger = logging.getLogger(__name__)


class MCPSelector:
    """MCP选择器"""

    def __init__(self) -> None:
        """初始化助手类"""
        self.input_tokens = 0
        self.output_tokens = 0

    @staticmethod
    def _assemble_sql(mcp_list: list[str]) -> str:
        """组装SQL"""
        sql = "("
        for mcp_id in mcp_list:
            sql += f"'{mcp_id}', "
        return sql.rstrip(", ") + ")"


    async def _call_reasoning(self, prompt: str) -> str:
        """调用大模型进行推理"""
        logger.info("[MCPHelper] 调用推理大模型")
        llm = ReasoningLLM()
        message = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ]
        result = ""
        async for chunk in llm.call(message):
            result += chunk
        self.input_tokens += llm.input_tokens
        self.output_tokens += llm.output_tokens
        return result


    async def _call_function_mcp(self, reasoning_result: str, mcp_ids: list[str]) -> MCPSelectResult:
        """调用结构化输出小模型提取JSON"""
        logger.info("[MCPHelper] 调用结构化输出小模型")
        llm = FunctionLLM()
        message = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": reasoning_result},
        ]
        schema = MCPSelectResult.model_json_schema()
        # schema中加入选项
        schema["properties"]["mcp_id"]["enum"] = mcp_ids
        result = await llm.call(messages=message, schema=schema)
        try:
            result = MCPSelectResult.model_validate(result)
        except Exception:
            logger.exception("[MCPHelper] 解析MCP Select Result失败")
            raise
        return result


    @staticmethod
    async def select_top_tool(query: str, mcp_list: list[str], top_n: int = 10) -> list[MCPTools]:
        """选择最合适的工具"""
        tool_vector = await LanceDB().get_table("mcp_tool")
        query_embedding = await Embedding.get_embedding([query])
        tool_vecs = await (await tool_vector.search(
            query=query_embedding,
            vector_column_name="embedding",
        )).where(f"mcp_id IN {MCPSelector._assemble_sql(mcp_list)}").limit(top_n).to_list()

        # 拿到工具
        llm_tool_list = []

        for tool_vec in tool_vecs:
            logger.info("[MCPHelper] 查询MCP Tool名称和描述: %s", tool_vec["mcp_id"])
            tool_data = await MCPServiceManager.get_service_tools(tool_vec["mcp_id"])
            llm_tool_list.extend(tool_data)

        return llm_tool_list
