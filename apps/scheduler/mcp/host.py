# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP宿主"""

import logging

from apps.models.mongo import MongoDB
from apps.scheduler.pool.loader.mcp import MCPLoader
from apps.scheduler.pool.mcp.client import (
    SSEMCPClient,
    StdioMCPClient,
)

logger = logging.getLogger(__name__)


class MCPHost:
    """MCP宿主服务"""

    @staticmethod
    async def get_clients(user_sub: str, mcp_id_list: list[str]) -> dict[str, SSEMCPClient | StdioMCPClient]:
        """获取MCP客户端"""
        mcp_loader = MCPLoader()
        mcp_collection = MongoDB.get_collection("mcp")
        result = {}

        # 遍历给定的list
        for mcp_id in mcp_id_list:
            # 检查用户是否启用了这个mcp
            mcp_db_result = await mcp_collection.find_one({"mcp_id": mcp_id, "activated": user_sub})
            if not mcp_db_result:
                logger.warning("用户 %s 未启用MCP %s", user_sub, mcp_id)
                continue

            # 获取MCP配置
            try:
                result[mcp_id] = mcp_loader.data[mcp_id][user_sub]
            except KeyError:
                logger.warning("用户 %s 的MCP %s 没有运行中的实例，请检查环境", user_sub, mcp_id)
                continue

        return result
