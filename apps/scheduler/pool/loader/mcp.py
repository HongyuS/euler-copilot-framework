"""
MCP 加载器

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

import json
import logging

from anyio import Path

from apps.common.config import Config
from apps.entities.mcp import MCPConfig

logger = logging.getLogger(__name__)
SERVICE_PATH = Path(Config().get_config().deploy.data_dir) / "semantics" / "service"
PROGRAM_PATH = Path(Config().get_config().deploy.data_dir) / "semantics" / "mcp"


class MCPLoader:
    """MCP 加载器"""

    @staticmethod
    async def load_mcp_config(config_path: Path) -> MCPConfig:
        """加载 MCP 配置"""
        f = await config_path.open("r", encoding="utf-8")
        f_content = json.loads(await f.read())
        await f.aclose()

        return MCPConfig(**f_content)


