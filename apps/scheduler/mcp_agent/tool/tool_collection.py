"""用于管理多个工具的集合类"""
import logging
from typing import Any

from apps.scheduler.mcp_agent.tool.base import BaseTool, ToolFailure, ToolResult

logger = logging.getLogger(__name__)


class ToolCollection:
    """定义工具的集合"""

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, *tools: BaseTool):
        self.tools = tools
        self.tool_map = {tool.name: tool for tool in tools}

    def __iter__(self):
        return iter(self.tools)

    def to_params(self) -> list[dict[str, Any]]:
        return [tool.to_param() for tool in self.tools]

    async def execute(
            self, *, name: str, tool_input: dict[str, Any] = None
    ) -> ToolResult:
        tool = self.tool_map.get(name)
        if not tool:
            return ToolFailure(error=f"Tool {name} is invalid")
        try:
            result = await tool(**tool_input)
            return result
        except Exception as e:
            return ToolFailure(error=f"Failed to execute tool {name}: {e}")

    def add_tool(self, tool: BaseTool):
        """
        将单个工具添加到集合中。

        如果已存在同名工具，则将跳过该工具并记录警告。
        """
        if tool.name in self.tool_map:
            logger.warning(f"Tool {tool.name} already exists in collection, skipping")
            return self

        self.tools += (tool,)
        self.tool_map[tool.name] = tool
        return self

    def add_tools(self, *tools: BaseTool):
        for tool in tools:
            self.add_tool(tool)
        return self
