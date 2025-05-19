"""MCP Client"""

import logging
from abc import ABCMeta, abstractmethod

from anyio import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult

from apps.common.config import Config
from apps.entities.mcp import MCPServerSSEConfig, MCPServerStdioConfig

logger = logging.getLogger(__name__)
MCP_PATH = Path(Config().get_config().deploy.data_dir) / "semantics" / "mcp"

class MCPClient(metaclass=ABCMeta):
    """MCP客户端基类"""

    @abstractmethod
    async def _create_client(
        self, user_sub: str | None, mcp_id: str, config: MCPServerSSEConfig | MCPServerStdioConfig,
    ) -> ClientSession:
        """
        创建MCP Client

        抽象函数；作用为在初始化的时候使用MCP SDK创建Client
        由于目前MCP的实现中Client和Session是1:1的关系，所以直接创建了 :class:`~mcp.ClientSession`

        :param str user_sub: 用户ID
        :param str mcp_id: MCP ID
        :param MCPServerSSEConfig | MCPServerStdioConfig config: MCP配置
        :return: MCP ClientSession
        :rtype: ClientSession
        """
        ...

    async def init(self, user_sub: str | None, mcp_id: str, config: MCPServerSSEConfig | MCPServerStdioConfig) -> None:
        """
        初始化 MCP Client类

        初始化MCP Client，并创建MCP Server进程和ClientSession

        :param str user_sub: 用户ID
        :param str mcp_id: MCP ID
        :param MCPServerSSEConfig | MCPServerStdioConfig config: MCP配置
        :return: None
        """
        # 初始化变量
        self._config = config
        self._session = await self._create_client(user_sub, mcp_id, config)

        # 初始化逻辑
        await self._session.initialize()
        self.tools = (await self._session.list_tools()).tools

    async def call_tool(self, tool_name: str, params: dict) -> CallToolResult:
        """调用MCP Server的工具"""
        return await self._session.call_tool(tool_name, params)

    async def stop(self) -> None:
        """停止MCP Client"""
        if self._session_context: # type: ignore[attr-defined]
            await self._session_context.__aexit__(None, None, None) # type: ignore[attr-defined]
        if self._streams_context: # type: ignore[attr-defined]
            await self._streams_context.__aexit__(None, None, None) # type: ignore[attr-defined]


class SSEMCPClient(MCPClient):
    """SSE协议的MCP Client"""

    async def _create_client(self, user_sub: str | None, mcp_id: str, config: MCPServerSSEConfig) -> ClientSession:
        """
        初始化 SSE协议的MCP Client

        :param str user_sub: 用户ID
        :param str mcp_id: MCP ID
        :param MCPServerSSEConfig config: MCP配置
        :return: SSE协议的MCP Client
        :rtype: ClientSession
        """
        self._streams_context = sse_client(
            url=config.url,
            headers=config.env,
        )
        streams = await self._streams_context.__aenter__()

        self._session_context = ClientSession(*streams)
        return await self._session_context.__aenter__()


class StdioMCPClient(MCPClient):
    """Stdio协议的MCP Client"""

    async def _create_client(self, user_sub: str | None, mcp_id: str, config: MCPServerStdioConfig) -> ClientSession:
        """
        初始化 Stdio协议的MCP Client

        :param str user_sub: 用户ID
        :param str mcp_id: MCP ID
        :param MCPServerStdioConfig config: MCP配置
        :return: Stdio协议的MCP Client
        :rtype: ClientSession
        """
        if user_sub:
            cwd = MCP_PATH / "users" / user_sub / mcp_id / "project"
        else:
            cwd = MCP_PATH / "template" / mcp_id / "project"
        await cwd.mkdir(parents=True, exist_ok=True)
        server_params = StdioServerParameters(
            command=config.command,
            args=config.args,
            env=config.env,
            cwd=cwd.as_posix(),
        )

        self._streams_context = stdio_client(server=server_params)
        streams = await self._streams_context.__aenter__()
        self._session_context = ClientSession(*streams)
        return await self._session_context.__aenter__()
