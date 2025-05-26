import asyncio
import json
import logging
from typing import Any, Optional

from pydantic import Field

from apps.entities.enum_var import AgentState
from apps.llm.function import JsonGenerator
from apps.llm.patterns import Select
from apps.scheduler.mcp_agent.agent.react import ReActAgent
from apps.scheduler.mcp_agent.schema import Function, Message, ToolCall
from apps.scheduler.mcp_agent.tool import Terminate, ToolCollection

logger = logging.getLogger(__name__)


class ToolCallAgent(ReActAgent):
    """用于处理工具/函数调用的基本Agent类"""

    name: str = "toolcall"
    description: str = "可以执行工具调用的智能体"

    available_tools: ToolCollection = ToolCollection(
        Terminate(),
    )
    tool_choices: str = "auto"
    special_tool_names: list[str] = Field(default_factory=lambda: [Terminate().name])

    tool_calls: list[ToolCall] = Field(default_factory=list)
    _current_base64_image: str | None = None

    max_observe: int | bool | None = None

    async def think(self) -> bool:
        """使用工具处理当前状态并决定下一步行动"""
        messages = []
        for message in self.messages:
            if isinstance(message, Message):
                message = message.to_dict()
            messages.append(message)
        try:
            # 通过工具获得响应
            select_obj = Select()
            choices = []
            for available_tool in self.available_tools.to_params():
                choices.append(available_tool.get("function"))

            tool = await select_obj.generate(question=self.question, choices=choices)
            if tool in self.available_tools.tool_map:
                schema = self.available_tools.tool_map[tool].parameters
                json_generator = JsonGenerator(
                    query="根据跟定的信息，获取工具参数",
                    conversation=messages,
                    schema=schema,
                )  # JsonGenerator
                parameters = await json_generator.generate()

            else:
                raise ValueError(f"尝试调用不存在的工具： {tool}")
        except Exception as e:
            raise
        self.tool_calls = tool_calls = [ToolCall(function=Function(name=tool, arguments=parameters))]
        content = f"选择的执行工具为：{tool}， 参数为{parameters}"

        logger.info(
            f"{self.name} 选择 {len(tool_calls) if tool_calls else 0}个工具执行"
        )
        if tool_calls:
            logger.info(
                f"准备使用的工具: {[call.function.name for call in tool_calls]}"
            )
            logger.info(f"工具参数: {tool_calls[0].function.arguments}")

        try:

            assistant_msg = (
                Message.from_tool_calls(content=content, tool_calls=self.tool_calls)
                if self.tool_calls
                else Message.assistant_message(content)
            )
            self.memory.add_message(assistant_msg)

            if not self.tool_calls:
                return bool(content)

            return bool(self.tool_calls)
        except Exception as e:
            logger.error(f"{self.name}的思考过程遇到了问题：: {e}")
            self.memory.add_message(
                Message.assistant_message(
                    f"处理时遇到错误: {str(e)}"
                )
            )
            return False

    async def act(self) -> str:
        """执行工具调用并处理其结果"""
        if not self.tool_calls:
            # 如果没有工具调用，则返回最后的消息内容
            return self.messages[-1].content or "没有要执行的内容或命令"

        results = []
        for command in self.tool_calls:
            await self.msg_queue.push_output(
                self.task,
                event_type="text.add",
                data={"text": f"正在执行工具{command.function.name}"}
            )

            self._current_base64_image = None

            result = await self.execute_tool(command)

            if self.max_observe:
                result = result[: self.max_observe]

            push_result = ""
            async for chunk in self.llm.call(
                    messages=[{"role": "system", "content": "You are a helpful asistant."},
                              {"role": "user", "content": self.user_prompt.format(
                                  step=self.current_step,
                                  result=result,
                              )}, ], streaming=False
            ):
                push_result += chunk
            self.task.tokens.input_tokens += self.llm.input_tokens
            self.task.tokens.output_tokens += self.llm.output_tokens
            await self.msg_queue.push_output(
                self.task,
                event_type="text.add",
                data={"text": push_result},  # type: ignore[arg-type]
            )

            await self.msg_queue.push_output(
                self.task,
                event_type="text.add",
                data={"text": f"工具{command.function.name}执行完成"},  # type: ignore[arg-type]
            )

            logger.info(
                f"工具'{command.function.name}'执行完成! 执行结果为: {result}"
            )

            # 将工具响应添加到内存
            tool_msg = Message.tool_message(
                content=result,
                tool_call_id=command.id,
                name=command.function.name,
            )
            self.memory.add_message(tool_msg)
            results.append(result)
            self.question += (
                f"\n已执行工具{command.function.name}， "
                f"作用是{self.available_tools.tool_map[command.function.name].description}，结果为{result}"
            )

        return "\n\n".join(results)

    async def execute_tool(self, command: ToolCall) -> str:
        """执行单个工具调用"""
        if not command or not command.function or not command.function.name:
            return "错误：无效的命令格式"

        name = command.function.name
        if name not in self.available_tools.tool_map:
            return f"错误：未知工具 '{name}'"

        try:
            # 解析参数
            args = command.function.arguments
            # 执行工具
            logger.info(f"激活工具：'{name}'...")
            result = await self.available_tools.execute(name=name, tool_input=args)

            # 执行特殊工具
            await self._handle_special_tool(name=name, result=result)

            # 格式化结果
            observation = (
                f"观察到执行的工具 `{name}`的输出：\n{str(result)}"
                if result
                else f"工具 `{name}` 已完成，无输出"
            )

            return observation
        except json.JSONDecodeError:
            error_msg = f"解析{name}的参数时出错：JSON格式无效"
            logger.error(
                f"{name}”的参数没有意义-无效的JSON，参数：{command.function.arguments}"
            )
            return f"错误: {error_msg}"
        except Exception as e:
            error_msg = f"工具 '{name}' 遇到问题: {str(e)}"
            logger.exception(error_msg)
            return f"错误: {error_msg}"

    async def _handle_special_tool(self, name: str, result: Any, **kwargs):
        """处理特殊工具的执行和状态变化"""
        if not self._is_special_tool(name):
            return

        if self._should_finish_execution(name=name, result=result, **kwargs):
            # 将智能体状态设为finished
            logger.info(f"特殊工具'{name}'已完成任务！")
            self.state = AgentState.FINISHED

    @staticmethod
    def _should_finish_execution(**kwargs) -> bool:
        """确定工具执行是否应完成"""
        return True

    def _is_special_tool(self, name: str) -> bool:
        """检查工具名称是否在特殊工具列表中"""
        return name.lower() in [n.lower() for n in self.special_tool_names]

    async def cleanup(self):
        """清理Agent工具使用的资源。"""
        logger.info(f"正在清理智能体的资源'{self.name}'...")
        for tool_name, tool_instance in self.available_tools.tool_map.items():
            if hasattr(tool_instance, "cleanup") and asyncio.iscoroutinefunction(
                    tool_instance.cleanup
            ):
                try:
                    logger.debug(f"清理工具: {tool_name}")
                    await tool_instance.cleanup()
                except Exception as e:
                    logger.error(
                        f"清理工具时发生错误'{tool_name}': {e}", exc_info=True
                    )
        logger.info(f"智能体清理完成'{self.name}'.")

    async def run(self, request: Optional[str] = None) -> str:
        """运行Agent"""
        try:
            return await super().run(request)
        finally:
            await self.cleanup()
