"""
MCP 加载器

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

import json
import logging

import sqids
from anyio import Path
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client

from apps.common.config import Config
from apps.entities.mcp import (
    MCPConfig,
    MCPServerSSEConfig,
    MCPServerStdioConfig,
)

logger = logging.getLogger(__name__)
SERVICE_PATH = Path(Config().get_config().deploy.data_dir) / "semantics" / "service"
PROGRAM_PATH = Path(Config().get_config().deploy.data_dir) / "semantics" / "mcp"


class MCPLoader:
    """MCP 加载器"""

    @staticmethod
    async def _load_config(config_path: Path) -> MCPConfig:
        """加载 MCP 配置"""
        f = await config_path.open("r", encoding="utf-8")
        f_content = json.loads(await f.read())
        await f.aclose()

        return MCPConfig(**f_content)


    async def _install_stdio(self, mcp_id: str, config: MCPServerStdioConfig) -> None:
        """安装 Stdio的MCP 服务"""
        args = config.args

        if "uv" in config.command:
            args += []
        if "npx" in config.command:
            args += []


    async def _load(self, config: MCPConfig) -> None:
        """加载 MCP 配置"""
        pass


    async def get(self, mcp_name: str) -> None:
        """获取 MCP 配置"""
        pass

