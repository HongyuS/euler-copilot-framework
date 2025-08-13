# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP宿主"""

import json
import logging
from typing import Any

from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment

from apps.llm.function import JsonGenerator
from apps.scheduler.mcp.prompt import MEMORY_TEMPLATE
from apps.scheduler.mcp_agent.base import McpBase
from apps.scheduler.mcp_agent.prompt import GEN_PARAMS, REPAIR_PARAMS
from apps.schemas.mcp import MCPTool
from apps.schemas.task import Task


def tojson_filter(value: Any) -> str:
    """将值转换为JSON字符串"""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


logger = logging.getLogger(__name__)
_env = SandboxedEnvironment(
    loader=BaseLoader,
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
    filters={"tojson": tojson_filter},
)


class MCPHost(McpBase):
    """MCP宿主服务"""

    @staticmethod
    async def assemble_memory(task: Task) -> str:
        """组装记忆"""
        return _env.from_string(MEMORY_TEMPLATE).render(
            context_list=task.context,
        )

    @staticmethod
    async def _get_first_input_params(mcp_tool: MCPTool, goal: str, current_goal: str, task: Task,
                                      resoning_llm: ReasoningLLM = ReasoningLLM()) -> dict[str, Any]:
        """填充工具参数"""
        # 更清晰的输入·指令，这样可以调用generate
        prompt = _env.from_string(GEN_PARAMS).render(
            tool_name=mcp_tool.name,
            tool_description=mcp_tool.description,
            goal=goal,
            current_goal=current_goal,
            input_schema=mcp_tool.input_schema,
            background_info=await MCPHost.assemble_memory(task),
        )
        logger.info("[MCPHost] 填充工具参数: %s", prompt)
        result = await MCPHost.get_resoning_result(
            prompt,
            resoning_llm
        )
        # 使用JsonGenerator解析结果
        result = await MCPHost._parse_result(
            result,
            mcp_tool.input_schema,
        )
        return result

    @staticmethod
    async def _fill_params(  # noqa: PLR0913
        goal: str, current_goal: str,
        mcp_tool: MCPTool, current_input: dict[str, Any],
        error_message: str = "", params: dict[str, Any] | None = None,
        params_description: str = "") -> dict[str, Any]:
        llm_query = "请生成修复之后的工具参数"
        prompt = _env.from_string(REPAIR_PARAMS).render(
            tool_name=mcp_tool.name,
            tool_description=mcp_tool.description,
            goal=goal,
            current_goal=current_goal,
            input_schema=mcp_tool.input_schema,
            current_input=current_input,
            error_message=error_message,
            params=params,
            params_description=params_description,
        )

        json_generator = JsonGenerator(
            llm_query,
            [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
            mcp_tool.input_schema,
        )
        return await json_generator.generate()
