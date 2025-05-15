# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP Agent执行器"""

import logging

from pydantic import Field

from apps.scheduler.executor.base import BaseExecutor
from apps.scheduler.mcp_agent.agent.mcp import MCPAgent

logger = logging.getLogger(__name__)


class MCPAgentExecutor(BaseExecutor):
    """MCP Agent执行器"""

    question: str = Field(description="用户输入")
    max_steps: int = Field(default=10, description="最大步数")
    servers_id: list[str] = Field(description="MCP server id")
    agent_id: str = Field(default="", description="Agent ID")
    agent_description: str = Field(default="", description="Agent描述")

    async def run(self):
        agent = await MCPAgent.create(
            servers_id=self.servers_id,
            max_steps=self.max_steps,
            task=self.task,
            msg_queue=self.msg_queue,
            question=self.question,
            agent_id=self.agent_id,
            description=self.agent_description,
        )

        try:
            answer = await agent.run(self.question)
            self.task = agent.task
            self.task.runtime.answer = answer
        except Exception as e:
            logger.error(f"Error: {str(e)}")
