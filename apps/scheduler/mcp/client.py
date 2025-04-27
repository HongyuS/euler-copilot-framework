"""MCP Client"""

from mcp import ClientSession
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

    def __init__(self, url: str) -> None:
        """初始化 MCP SSE客户端"""
        self.url = url

    async def _send_request(self, data: dict) -> dict:
        """发送消息给Server"""
        raise NotImplementedError


class MCPClientStdio(MCPClient):
    """MCP Client Stdio"""

    async def _send_request(self, data: dict) -> dict:
        """发送消息给Server"""
        raise NotImplementedError
