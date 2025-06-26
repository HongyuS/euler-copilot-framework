from abc import ABC, abstractmethod

from pydantic import Field

from apps.schemas.enum_var import AgentState
from apps.llm.reasoning import ReasoningLLM
from apps.scheduler.mcp_agent.agent.base import BaseAgent
from apps.scheduler.mcp_agent.schema import Memory


class ReActAgent(BaseAgent, ABC):
    name: str
    description: str | None = None

    system_prompt: str | None = None
    next_step_prompt: str | None = None

    llm: ReasoningLLM | None = Field(default_factory=ReasoningLLM)
    memory: Memory = Field(default_factory=Memory)
    state: AgentState = AgentState.IDLE

    @abstractmethod
    async def think(self) -> bool:
        """处理当前状态并决定下一步操作"""

    @abstractmethod
    async def act(self) -> str:
        """执行已决定的行动"""

    async def step(self) -> str:
        """执行一个步骤：思考和行动"""
        should_act = await self.think()
        if not should_act:
            return "思考完成-无需采取任何行动"
        return await self.act()
