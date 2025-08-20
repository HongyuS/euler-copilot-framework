# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP 用户目标拆解与规划"""

import logging
from collections.abc import AsyncGenerator
from typing import Any

from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment

from apps.llm.reasoning import ReasoningLLM
from apps.scheduler.mcp_agent.base import MCPBase
from apps.scheduler.mcp_agent.prompt import (
    CHANGE_ERROR_MESSAGE_TO_DESCRIPTION,
    FINAL_ANSWER,
    GEN_STEP,
    GENERATE_FLOW_NAME,
    GET_MISSING_PARAMS,
    IS_PARAM_ERROR,
    RISK_EVALUATE,
)
from apps.scheduler.slot.slot import Slot
from apps.schemas.enum_var import LanguageType
from apps.schemas.mcp import (
    FlowName,
    IsParamError,
    MCPTool,
    Step,
    ToolRisk,
)

_env = SandboxedEnvironment(
    loader=BaseLoader,
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
)
logger = logging.getLogger(__name__)


class MCPPlanner(MCPBase):
    """MCP 用户目标拆解与规划"""

    goal: str
    llm: ReasoningLLM

    def __init__(self, goal: str, llm: ReasoningLLM, language: LanguageType) -> None:
        """初始化MCPPlanner"""
        super().__init__()
        self.goal = goal
        self.llm = llm
        self.language = language

    async def get_flow_name(self) -> FlowName:
        """获取当前流程的名称"""
        template = _env.from_string(GENERATE_FLOW_NAME[self.language])
        prompt = template.render(goal=self.goal)
        result = await self.get_resoning_result(prompt)
        result = await self._parse_result(result, FlowName.model_json_schema())
        return FlowName.model_validate(result)

    async def create_next_step(self, history: str, tools: list[MCPTool]) -> Step:
        """创建下一步的执行步骤"""
        # 获取推理结果
        template = _env.from_string(GEN_STEP[self.language])
        prompt = template.render(goal=self.goal, history=history, tools=tools)
        result = await self.get_resoning_result(prompt)

        # 解析为结构化数据
        schema = Step.model_json_schema()
        if "enum" not in schema["properties"]["tool_id"]:
            schema["properties"]["tool_id"]["enum"] = []
        for tool in tools:
            schema["properties"]["tool_id"]["enum"].append(tool.id)
        step = await self._parse_result(result, schema)
        logger.info("[MCPPlanner] 创建下一步的执行步骤: %s", step)
        # 使用Step模型解析结果
        return Step.model_validate(step)

    async def get_tool_risk(
        self,
        tool: MCPTool,
        input_param: dict[str, Any],
        additional_info: str = "",
    ) -> ToolRisk:
        """获取MCP工具的风险评估结果"""
        # 获取推理结果
        template = _env.from_string(RISK_EVALUATE[self.language])
        prompt = template.render(
            tool_name=tool.name,
            tool_description=tool.description,
            input_param=input_param,
            additional_info=additional_info,
        )
        result = await self.get_resoning_result(prompt)

        schema = ToolRisk.model_json_schema()
        risk = await self._parse_result(result, schema)

        # 返回风险评估结果
        return ToolRisk.model_validate(risk)

    async def is_param_error(
        self,
        history: str,
        error_message: str,
        tool: MCPTool,
        step_description: str,
        input_params: dict[str, Any],
    ) -> IsParamError:
        """判断错误信息是否是参数错误"""
        tmplate = _env.from_string(IS_PARAM_ERROR[self.language])
        prompt = tmplate.render(
            goal=self.goal,
            history=history,
            step_id=tool.id,
            step_name=tool.name,
            step_description=step_description,
            input_params=input_params,
            error_message=error_message,
        )
        result = await self.get_resoning_result(prompt)
        # 解析为结构化数据
        schema = IsParamError.model_json_schema()
        is_param_error = await self._parse_result(result, schema)
        # 使用IsParamError模型解析结果
        return IsParamError.model_validate(is_param_error)

    async def change_err_message_to_description(
        self, error_message: str, tool: MCPTool, input_params: dict[str, Any],
    ) -> str:
        """将错误信息转换为工具描述"""
        template = _env.from_string(CHANGE_ERROR_MESSAGE_TO_DESCRIPTION[self.language])
        prompt = template.render(
            error_message=error_message,
            tool_name=tool.name,
            tool_description=tool.description,
            input_schema=tool.input_schema,
            input_params=input_params,
        )
        return await self.get_resoning_result(prompt)

    async def get_missing_param(self, tool: MCPTool, input_param: dict[str, Any], error_message: str) -> dict[str, Any]:
        """获取缺失的参数"""
        slot = Slot(schema=tool.input_schema)
        template = _env.from_string(GET_MISSING_PARAMS[self.language])
        schema_with_null = slot.add_null_to_basic_types()
        prompt = template.render(
            tool_name=tool.name,
            tool_description=tool.description,
            input_param=input_param,
            schema=schema_with_null,
            error_message=error_message,
        )
        result = await self.get_resoning_result(prompt)
        # 解析为结构化数据
        return await self._parse_result(result, schema_with_null)

    async def generate_answer(
        self, memory: str,
    ) -> AsyncGenerator[str, None]:
        """生成最终回答"""
        template = _env.from_string(FINAL_ANSWER[self.language])
        prompt = template.render(
            memory=memory,
            goal=self.goal,
        )
        async for chunk in self.llm.call(
            [{"role": "user", "content": prompt}],
            streaming=True,
            temperature=0.07,
        ):
            yield chunk
