# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP宿主"""

import json
import logging
from typing import Any

from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment

from apps.llm.function import JsonGenerator
from apps.llm.reasoning import ReasoningLLM
from apps.models.task import TaskRuntime
from apps.scheduler.mcp.prompt import MEMORY_TEMPLATE
from apps.scheduler.mcp_agent.base import MCPBase
from apps.scheduler.mcp_agent.prompt import GEN_PARAMS, REPAIR_PARAMS
from apps.schemas.enum_var import LanguageType
from apps.schemas.mcp import MCPTool

logger = logging.getLogger(__name__)
_env = SandboxedEnvironment(
    loader=BaseLoader,
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
)


def tojson_filter(value: dict[str, Any]) -> str:
    """将字典转换为紧凑JSON字符串"""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


_env.filters["tojson"] = tojson_filter
LLM_QUERY_FIX = {
    LanguageType.CHINESE: "请生成修复之后的工具参数",
    LanguageType.ENGLISH: "Please generate the tool parameters after repair",
}


class MCPHost(MCPBase):
    """MCP宿主服务"""

    def __init__(self, goal: str, llm: ReasoningLLM) -> None:
        """初始化MCP宿主服务"""
        super().__init__()
        self.goal = goal
        self.llm = llm

    @staticmethod
    async def assemble_memory(runtime: TaskRuntime) -> str:
        """组装记忆"""
        return _env.from_string(MEMORY_TEMPLATE[runtime.language]).render(
            context_list=runtime.context,
        )

    async def get_first_input_params(
        self, mcp_tool: MCPTool, current_goal: str, runtime: TaskRuntime,
    ) -> dict[str, Any]:
        """填充工具参数"""
        # 更清晰的输入·指令，这样可以调用generate
        prompt = _env.from_string(GEN_PARAMS[runtime.language]).render(
            tool_name=mcp_tool.name,
            tool_description=mcp_tool.description,
            goal=self.goal,
            current_goal=current_goal,
            input_schema=mcp_tool.input_schema,
            background_info=await MCPHost.assemble_memory(runtime),
        )
        logger.info("[MCPHost] 填充工具参数: %s", prompt)
        result = await self.get_resoning_result(prompt)
        # 使用JsonGenerator解析结果
        return await MCPHost._parse_result(
            result,
            mcp_tool.input_schema,
        )

    async def fill_params(  # noqa: D102, PLR0913
        self,
        mcp_tool: MCPTool,
        current_goal: str,
        current_input: dict[str, Any],
        language: LanguageType,
        error_message: str = "",
        params: dict[str, Any] | None = None,
        params_description: str = "",
    ) -> dict[str, Any]:
        llm_query = LLM_QUERY_FIX[language]
        prompt = _env.from_string(REPAIR_PARAMS[language]).render(
            tool_name=mcp_tool.name,
            goal=self.goal,
            current_goal=current_goal,
            tool_description=mcp_tool.description,
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
