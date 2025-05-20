# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP池"""

import logging

from anyio import Path

from apps.common.config import Config
from apps.common.singleton import SingletonMeta
from apps.entities.mcp import MCPConfig, MCPType
from apps.models.mongo import MongoDB
from apps.scheduler.pool.mcp.client import SSEMCPClient, StdioMCPClient

logger = logging.getLogger(__name__)
MCP_USER_PATH = MCP_PATH = Path(Config().get_config().deploy.data_dir) / "semantics" / "mcp" / "users"


class MCPPool(metaclass=SingletonMeta):
    """MCP池"""

    def __init__(self) -> None:
        """初始化MCP池"""
        self.pool = {}


    async def _init_mcp(self, mcp_id: str, user_sub: str) -> SSEMCPClient | StdioMCPClient | None:
        """初始化MCP池"""
        mcp_math = MCP_USER_PATH / user_sub / mcp_id / "project"
        config_path = MCP_USER_PATH / user_sub / mcp_id / "config.json"

        if not await mcp_math.exists() or not await mcp_math.is_dir():
            logger.warning("[MCPPool] 用户 %s 的MCP %s 未激活", user_sub, mcp_id)
            return None

        config = MCPConfig.model_validate_json(await config_path.read_text())
        server_config = next(iter(config.mcp_servers.values()))

        if server_config.type == MCPType.SSE:
            client = SSEMCPClient()
        elif server_config.type == MCPType.STDIO:
            client = StdioMCPClient()
        else:
            logger.warning("[MCPPool] 用户 %s 的MCP %s 类型错误", user_sub, mcp_id)
            return None

        await client.init(user_sub, mcp_id, server_config)
        return client


    async def _get_from_dict(self, mcp_id: str, user_sub: str) -> SSEMCPClient | StdioMCPClient | None:
        """从字典中获取MCP客户端"""
        if user_sub not in self.pool:
            return None

        if mcp_id not in self.pool[user_sub]:
            return None

        return self.pool[user_sub][mcp_id]


    async def _validate_user(self, mcp_id: str, user_sub: str) -> bool:
        """验证用户是否已激活"""
        mongo = MongoDB()
        mcp_collection = mongo.get_collection("mcp")
        mcp_db_result = await mcp_collection.find_one({"_id": mcp_id, "activated": user_sub})
        return mcp_db_result is not None


    async def get(self, mcp_id: str, user_sub: str) -> SSEMCPClient | StdioMCPClient | None:
        """获取MCP客户端"""
        item = await self._get_from_dict(mcp_id, user_sub)
        if item is None:
            # 检查用户是否已激活
            if not await self._validate_user(mcp_id, user_sub):
                logger.warning("用户 %s 未激活MCP %s", user_sub, mcp_id)
                return None

            # 初始化进程
            item = await self._init_mcp(mcp_id, user_sub)
            if item is None:
                return None

            if user_sub not in self.pool:
                self.pool[user_sub] = {}

            self.pool[user_sub][mcp_id] = item

        return item


    async def stop(self, mcp_id: str, user_sub: str) -> None:
        """停止MCP客户端"""
        await self.pool[mcp_id][user_sub].stop()
