"""MCP Agent基类"""
import logging
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager

from pydantic import BaseModel, Field, model_validator

from apps.common.queue import MessageQueue
from apps.entities.enum_var import AgentState
from apps.entities.task import Task
from apps.llm.reasoning import ReasoningLLM
from apps.scheduler.mcp_agent.schema import Memory, Message, Role
from apps.service.activity import Activity

logger = logging.getLogger(__name__)


class BaseAgent(BaseModel, ABC):
    """
    用于管理代理状态和执行的抽象基类。

    为状态转换、内存管理、
    以及分步执行循环。子类必须实现`step`方法。
    """

    msg_queue: MessageQueue
    task: Task
    name: str = Field(..., description="Agent名称")
    agent_id: str = Field(default="", description="Agent ID")
    description: str = Field(default="", description="Agent描述")
    question: str
    # Prompts
    next_step_prompt: str | None = Field(
        None, description="判断下一步动作的提示"
    )

    # Dependencies
    llm: ReasoningLLM = Field(default_factory=ReasoningLLM, description="大模型实例")
    memory: Memory = Field(default_factory=Memory, description="Agent记忆库")
    state: AgentState = Field(
        default=AgentState.IDLE, description="Agent状态"
    )
    servers_id: list[str] = Field(default_factory=list, description="MCP server id")

    # Execution control
    max_steps: int = Field(default=10, description="终止前的最大步长")
    current_step: int = Field(default=0, description="执行中的当前步骤")

    duplicate_threshold: int = 2

    user_prompt: str = r"""
        当前步骤：{step} 工具输出结果：{result}
        请总结当前正在执行的步骤和对应的工具输出结果，内容包括当前步骤是多少，执行的工具是什么，输出是什么。
        最终以报告的形式展示。
        如果工具输出结果中执行的工具为terminate，请按照状态输出本次交互过程最终结果并完成对整个报告的总结，不需要输出你的分析过程。
    """
    """用户提示词"""

    class Config:
        arbitrary_types_allowed = True
        extra = "allow"  # Allow extra fields for flexibility in subclasses

    @model_validator(mode="after")
    def initialize_agent(self) -> "BaseAgent":
        """初始化Agent"""
        if self.llm is None or not isinstance(self.llm, ReasoningLLM):
            self.llm = ReasoningLLM()
        if not isinstance(self.memory, Memory):
            self.memory = Memory()
        return self

    @asynccontextmanager
    async def state_context(self, new_state: AgentState):
        """
        Agent状态转换上下文管理器

        Args:
            new_state: 要转变的状态

        :return: None
        :raise ValueError: 如果new_state无效
        """
        if not isinstance(new_state, AgentState):
            raise ValueError(f"无效状态: {new_state}")

        previous_state = self.state
        self.state = new_state
        try:
            yield
        except Exception as e:
            self.state = AgentState.ERROR  # Transition to ERROR on failure
            raise e
        finally:
            self.state = previous_state  # Revert to previous state

    def update_memory(
            self,
            role: Role,
            content: str,
            **kwargs,
    ) -> None:
        """添加信息到Agent的memory中"""
        message_map = {
            "user": Message.user_message,
            "system": Message.system_message,
            "assistant": Message.assistant_message,
            "tool": lambda content, **kw: Message.tool_message(content, **kw),
        }

        if role not in message_map:
            raise ValueError(f"不支持的消息角色: {role}")

        # Create message with appropriate parameters based on role
        kwargs = {**(kwargs if role == "tool" else {})}
        self.memory.add_message(message_map[role](content, **kwargs))

    async def run(self, request: str | None = None) -> str:
        """异步执行Agent的主循环"""
        self.task.runtime.question = request
        if self.state != AgentState.IDLE:
            raise RuntimeError(f"无法从以下状态运行智能体： {self.state}")

        if request:
            self.update_memory("user", request)

        results: list[str] = []
        async with self.state_context(AgentState.RUNNING):
            while (
                    self.current_step < self.max_steps and self.state != AgentState.FINISHED
            ):
                if not Activity.is_active(self.task.ids.user_sub):
                    logger.info("用户终止会话,任务停止！")
                    return ""
                self.current_step += 1
                logger.info(f"执行步骤{self.current_step}/{self.max_steps}")
                step_result = await self.step()

                # Check for stuck state
                if self.is_stuck():
                    self.handle_stuck_state()
                result = f"Step {self.current_step}: {step_result}"
                results.append(result)

            if self.current_step >= self.max_steps:
                self.current_step = 0
                self.state = AgentState.IDLE
                result = f"任务终止: 已达到最大步数 ({self.max_steps})"
                await self.msg_queue.push_output(
                    self.task,
                    event_type="text.add",
                    data={"text": result},  # type: ignore[arg-type]
                )
                results.append(result)
        return "\n".join(results) if results else "未执行任何步骤"

    @abstractmethod
    async def step(self) -> str:
        """
        执行代理工作流程中的单个步骤。

        必须由子类实现，以定义具体的行为。
        """

    def handle_stuck_state(self):
        """通过添加更改策略的提示来处理卡住状态"""
        stuck_prompt = "\
        观察到重复响应。考虑新策略，避免重复已经尝试过的无效路径"
        self.next_step_prompt = f"{stuck_prompt}\n{self.next_step_prompt}"
        logger.warning(f"检测到智能体处于卡住状态。新增提示：{stuck_prompt}")

    def is_stuck(self) -> bool:
        """通过检测重复内容来检查代理是否卡在循环中"""
        if len(self.memory.messages) < 2:
            return False

        last_message = self.memory.messages[-1]
        if not last_message.content:
            return False

        duplicate_count = sum(
            1
            for msg in reversed(self.memory.messages[:-1])
            if msg.role == "assistant" and msg.content == last_message.content
        )

        return duplicate_count >= self.duplicate_threshold

    @property
    def messages(self) -> list[Message]:
        """从Agent memory中检索消息列表"""
        return self.memory.messages

    @messages.setter
    def messages(self, value: list[Message]) -> None:
        """设置Agent memory的消息列表"""
        self.memory.messages = value
