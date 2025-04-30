"""MCP Client"""

from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client

from apps.entities.mcp import MCPConfig, MCPType


class MCPClient:
    """MCP Agent Client"""

    async def _send_request(self, data: dict) -> dict:
        """发送消息给Server"""
        raise NotImplementedError


class MCPClientSSE(MCPClient):
    """MCP Client SSE"""

    def __init__(self, name: str, url: str, headers: dict[str, str]) -> None:
        """初始化 MCP SSE客户端"""
        self.name = name
        self.url = url
        self.headers = headers

    async def _send_request(self, data: dict[str, Any]) -> dict:
        """发送消息给Server"""
        raise NotImplementedError


class MCPClientStdio(MCPClient):
    """MCP Client Stdio"""

    def __init__(self, name: str, command: str, args: list[str], env: dict[str, str]) -> None:
        """初始化 MCP Stdio客户端"""
        self._name = name
        self._param = StdioServerParameters(
            command=command,
            args=args,
            env=env,
        )

    async def _send_request(self, data: dict[str, Any]) -> dict:
        """发送消息给Server"""
        raise NotImplementedError


    async def run(self):
        """运行 MCP Stdio客户端"""
        self._client = stdio_client(self._param)
