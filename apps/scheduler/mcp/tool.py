# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""选择MCP Server及其工具"""

import logging

from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment

from apps.entities.mcp import (
    MCPCollection,
    MCPSelectResult,
)
from apps.llm.embedding import Embedding
from apps.llm.function import FunctionLLM
from apps.llm.reasoning import ReasoningLLM
from apps.models.lance import LanceDB
from apps.models.mongo import MongoDB
from apps.scheduler.mcp.prompt import (
    MCP_SELECT_REASON,
)

logger = logging.getLogger(__name__)


class MCPToolHelper:
    """MCP工具助手"""

    def __init__(self) -> None:
        """初始化助手类"""
        self.input_tokens = 0
        self.output_tokens = 0


    async def select_top_mcp(
        self,
        query: str,
        mcp_list: list[str],
    ) -> MCPSelectResult:
        """
        选择最合适的MCP Server

        先通过Embedding选择Top5，然后通过LLM选择Top 1
        """
        logger.info("[MCPHelper] 查询MCP Server向量: %s, %s", query, mcp_list)
        mcp_table = await LanceDB().get_table("mcp")
        query_embedding = await Embedding.get_embedding([query])
        mcp_vecs = await (await mcp_table.search(
            query=query_embedding,
            vector_column_name="embedding",
        )).where(f"id IN ({', '.join(mcp_list)})").limit(5).to_list()

        # 拿到名称和description
        logger.info("[MCPHelper] 查询MCP Server名称和描述: %s", mcp_vecs)
        mcp_collection = MongoDB().get_collection("mcp")
        llm_mcp_list: list[dict[str, str]] = []
        for mcp_vec in mcp_vecs:
            mcp_id = mcp_vec["id"]
            mcp_data = await mcp_collection.find_one({"_id": mcp_id})
            if not mcp_data:
                logger.warning("[MCPHelper] 查询MCP Server名称和描述失败: %s", mcp_id)
                continue
            mcp_data = MCPCollection.model_validate(mcp_data)
            llm_mcp_list.extend([{
                "id": mcp_id,
                "name": mcp_data.name,
                "description": mcp_data.description,
            }])

        # 初始化jinja2环境
        env = SandboxedEnvironment(
            loader=BaseLoader,
            autoescape=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        template = env.from_string(MCP_SELECT_REASON)
        # 渲染模板
        mcp_prompt = template.render(
            mcp_list=llm_mcp_list,
            goal=query,
        )

        # 调用大模型
        logger.info("[MCPHelper] 分析最合适的MCP Server")
        llm = ReasoningLLM()
        message = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": mcp_prompt},
        ]
        result = ""
        async for chunk in llm.call(message):
            result += chunk
        self.input_tokens += llm.input_tokens
        self.output_tokens += llm.output_tokens

        # 使用小模型提取JSON
        llm = FunctionLLM()
        message = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": result},
        ]
        result = await llm.call(messages=message, schema=MCPSelectResult.model_json_schema())
        try:
            result = MCPSelectResult.model_validate(result)
        except Exception:
            logger.exception("[MCPHelper] 解析MCP Select Result失败")
            raise
        return result


    @staticmethod
    async def select_top_tool(mcp_list: list[str], top_n: int) -> list[str]:
        """选择最合适的工具"""
        pass
