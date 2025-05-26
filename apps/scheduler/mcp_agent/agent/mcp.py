"""MCP Agent"""
import logging

from pydantic import Field

from apps.scheduler.mcp.host import MCPHost
from apps.scheduler.mcp_agent.agent.toolcall import ToolCallAgent
from apps.scheduler.mcp_agent.tool import Terminate, ToolCollection
from apps.scheduler.pool.mcp.client import MCPClientTool

logger = logging.getLogger(__name__)


class MCPAgent(ToolCallAgent):
    """
    用于与MCP（模型上下文协议）服务器交互。

    使用SSE或stdio传输连接到MCP服务器
    并使服务器的工具
    """

    name: str = "MCPAgent"
    description: str = "一个多功能的智能体，能够使用多种工具（包括基于MCP的工具）解决各种任务"

    # Add general-purpose tools to the tool collection
    available_tools: ToolCollection = Field(
        default_factory=lambda: ToolCollection(
            Terminate(),
        )
    )

    special_tool_names: list[str] = Field(default_factory=lambda: [Terminate().name])

    _initialized: bool = False

    @classmethod
    async def create(cls, **kwargs) -> "MCPAgent":
        """创建并初始化MCP Agent实例"""
        instance = cls(**kwargs)
        await instance.initialize_mcp_servers()
        instance._initialized = True
        return instance

    async def initialize_mcp_servers(self) -> None:
        """初始化与已配置的MCP服务器的连接"""
        mcp_host = MCPHost(self.task.ids.user_sub, self.task.id, self.agent_id, self.agent_description)
        mcps = {}
        for mcp_id in self.servers_id:
            mcps[mcp_id] = await mcp_host.get_client(mcp_id)

        for mcp_id, mcp_client in mcps.items():
            new_tools = []
            for tool in mcp_client.tools:
                original_name = tool.name
                # Always prefix with server_id to ensure uniqueness
                tool_name = f"mcp_{mcp_id}_{original_name}"

                server_tool = MCPClientTool(
                    name=tool_name,
                    description=tool.description,
                    parameters=tool.inputSchema,
                    session=mcp_client.session,
                    server_id=mcp_id,
                    original_name=original_name,
                )
                new_tools.append(server_tool)
            self.available_tools.add_tools(*new_tools)

    async def think(self) -> bool:
        """使用适当的上下文处理当前状态并决定下一步操作"""
        if not self._initialized:
            await self.initialize_mcp_servers()
            self._initialized = True

        result = await super().think()

        # Restore original prompt

        return result
