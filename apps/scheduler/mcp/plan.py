# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP 用户目标拆解与规划"""

import logging

from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment

from apps.llm.function import JsonGenerator
from apps.models.mcp import MCPTools
from apps.schemas.enum_var import LanguageType
from apps.schemas.mcp import MCPPlan
from apps.schemas.scheduler import LLMConfig

from .prompt import CREATE_PLAN, FINAL_ANSWER

_logger = logging.getLogger(__name__)

class MCPPlanner:
    """MCP 用户目标拆解与规划"""

    def __init__(self, user_goal: str, language: LanguageType, llm: LLMConfig) -> None:
        """初始化MCP规划器"""
        self._user_goal = user_goal
        self._env = SandboxedEnvironment(
            loader=BaseLoader,
            autoescape=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self._language = language
        self._llm = llm


    async def create_plan(self, tool_list: list[MCPTools], max_steps: int = 6) -> MCPPlan:
        """规划下一步的执行流程，并输出"""
        # 获取推理结果
        result = await self._get_reasoning_plan(tool_list, max_steps)

        # 解析为结构化数据
        return await self._parse_plan_result(result, max_steps)


    async def _get_reasoning_plan(self, tool_list: list[MCPTools], max_steps: int) -> str:
        """获取推理大模型的结果"""
        # 格式化Prompt
        template = self._env.from_string(CREATE_PLAN[self._language])
        prompt = template.render(
            goal=self._user_goal,
            tools=tool_list,
            max_num=max_steps,
        )

        # 调用推理大模型
        message = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ]
        result = ""
        async for chunk in self._llm.reasoning.call(
            message,
            streaming=False,
        ):
            result += chunk.content or ""
        return result


    async def _parse_plan_result(self, result: str, max_steps: int) -> MCPPlan:
        """将推理结果解析为结构化数据"""
        if not self._llm.function:
            err = "[MCPPlanner] 未设置Function模型"
            _logger.error(err)
            raise RuntimeError(err)

        # 格式化Prompt
        schema = MCPPlan.model_json_schema()
        schema["properties"]["plans"]["maxItems"] = max_steps

        # 使用Function模型解析结果
        json_generator = JsonGenerator(
            self._llm.function,
            result,
            [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": result},
            ],
            schema,
        )
        plan = await json_generator.generate()
        return MCPPlan.model_validate(plan)


    async def generate_answer(self, plan: MCPPlan, memory: str) -> str:
        """生成最终回答"""
        template = self._env.from_string(FINAL_ANSWER[self._language])
        prompt = template.render(
            plan=plan,
            memory=memory,
            goal=self._user_goal,
        )

        result = ""
        async for chunk in self._llm.reasoning.call(
            [{"role": "user", "content": prompt}],
            streaming=False,
        ):
            result += chunk.content or ""

        return result
