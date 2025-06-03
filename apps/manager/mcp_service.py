# Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
"""MCP服务管理器"""

import logging
import random
import re
from typing import Any

from sqids.sqids import Sqids

from apps.constants import SERVICE_PAGE_SIZE
from apps.entities.enum_var import SearchType
from apps.entities.mcp import (
    MCPCollection,
    MCPServerConfig,
    MCPServerSSEConfig,
    MCPServerStdioConfig,
    MCPStatus,
    MCPTool,
    MCPType,
)
from apps.entities.request_data import UpdateMCPServiceRequest
from apps.entities.response_data import MCPServiceCardItem
from apps.exceptions import InstancePermissionError
from apps.models.mongo import MongoDB
from apps.scheduler.pool.loader.mcp import MCPLoader
from apps.scheduler.pool.mcp.pool import MCPPool

logger = logging.getLogger(__name__)
sqids = Sqids(min_length=6)


class MCPServiceManager:
    """MCP服务管理器"""

    @staticmethod
    async def is_active(user_sub: str, mcp_id: str) -> bool:
        """
        判断用户是否激活MCP

        :param str user_sub: 用户ID
        :param str mcp_id: MCP服务ID
        :return: 是否激活
        """
        mongo = MongoDB()
        mcp_collection = mongo.get_collection("mcp")
        mcp_list = await mcp_collection.find({"_id": mcp_id}, {"activated": True}).to_list(None)
        return any(user_sub in db_item.get("activated", []) for db_item in mcp_list)

    @staticmethod
    async def get_service_status(mcp_id: str) -> MCPStatus:
        """
        获取MCP服务状态

        :param str mcp_id: MCP服务ID
        :return: MCP服务状态
        """
        mongo = MongoDB()
        mcp_collection = mongo.get_collection("mcp")
        mcp_list = await mcp_collection.find({"_id": mcp_id}, {"status": True}).to_list(None)
        for db_item in mcp_list:
            status = db_item.get("status")
            if MCPStatus.READY.value == status:
                return MCPStatus.READY
            if MCPStatus.INSTALLING.value == status:
                return MCPStatus.INSTALLING
        return MCPStatus.FAILED

    @staticmethod
    async def fetch_mcp_services(
            search_type: SearchType,
            user_sub: str,
            keyword: str | None,
            page: int,
    ) -> list[MCPServiceCardItem]:
        """
        获取所有MCP服务列表

        :param search_type: SearchType: str: MCP搜索类型
        :param user_sub: str: 用户ID
        :param keyword: str: MCP搜索关键字
        :param page: int: 页码
        :return: MCP服务列表
        """
        filters = MCPServiceManager._build_filters(search_type, keyword)
        mcpservice_pools = await MCPServiceManager._search_mcpservice(filters, page)
        return [
            MCPServiceCardItem(
                mcpserviceId=item.id,
                icon=await MCPLoader.get_icon(item.id),
                name=item.name,
                description=item.description,
                author=item.author,
                isActive=await MCPServiceManager.is_active(user_sub, item.id),
                status=await MCPServiceManager.get_service_status(item.id),
            )
            for item in mcpservice_pools
        ]

    @staticmethod
    async def get_mcp_service(mcpservice_id: str) -> MCPCollection:
        """
        获取MCP服务详细信息

        :param mcpservice_id: str: MCP服务ID
        :return: MCP服务详细信息
        """
        # 验证用户权限
        mcpservice_collection = MongoDB().get_collection("mcp")
        db_service = await mcpservice_collection.find_one({"_id": mcpservice_id})
        if not db_service:
            msg = "[MCPServiceManager] MCP服务未找到或用户无权限"
            raise RuntimeError(msg)
        return MCPCollection.model_validate(db_service)


    @staticmethod
    async def get_mcp_config(mcpservice_id: str) -> tuple[MCPServerConfig, str]:
        """
        获取MCP服务配置

        :param mcpservice_id: str: MCP服务ID
        :return: MCP服务配置
        """
        icon = MCPLoader.get_icon(mcpservice_id)
        config = MCPLoader.get_config(mcpservice_id)


    @staticmethod
    async def get_service_tools(
            service_id: str,
    ) -> list[MCPTool]:
        """
        获取MCP可以用工具

        :param service_id: str: MCP服务ID
        :return: MCP工具详细信息列表
        """
        # 获取服务名称
        service_collection = MongoDB().get_collection("mcp")
        data = await service_collection.find({"_id": service_id}, {"tools": True}).to_list(None)
        result = []
        for item in data:
            for tool in item.get("tools", {}):
                tool_data = MCPTool.model_validate(tool)
                result.append(tool_data)
        return result

    @staticmethod
    async def _search_mcpservice(
            search_conditions: dict[str, Any],
            page: int,
    ) -> list[MCPCollection]:
        """
        基于输入条件搜索MCP服务

        :param search_conditions: dict[str, Any]: 搜索条件
        :param page: int: 页码
        :return: MCP列表
        """
        mcpservice_collection = MongoDB().get_collection("mcp")
        # 分页查询
        skip = (page - 1) * SERVICE_PAGE_SIZE
        db_mcpservices = await mcpservice_collection.find(search_conditions).skip(skip).limit(
            SERVICE_PAGE_SIZE,
        ).to_list()
        # 如果未找到，返回空列表
        if not db_mcpservices:
            logger.warning("[MCPServiceManager] 没有找到符合条件的MCP服务: %s", search_conditions)
            return []
        # 将数据库中的MCP服务转换为对象
        return [MCPCollection.model_validate(db_mcpservice) for db_mcpservice in db_mcpservices]

    @staticmethod
    def _build_filters(
            search_type: SearchType,
            keyword: str | None,
    ) -> dict[str, Any]:
        if not keyword:
            return {}

        if search_type == SearchType.ALL:
            base_filters = {"$or": [
                {"name": {"$regex": keyword, "$options": "i"}},
                {"description": {"$regex": keyword, "$options": "i"}},
                {"author": {"$regex": keyword, "$options": "i"}},
            ]}
        elif search_type == SearchType.NAME:
            base_filters = {"name": {"$regex": keyword, "$options": "i"}}
        elif search_type == SearchType.DESCRIPTION:
            base_filters = {"description": {"$regex": keyword, "$options": "i"}}
        elif search_type == SearchType.AUTHOR:
            base_filters = {"author": {"$regex": keyword, "$options": "i"}}
        return base_filters


    @staticmethod
    async def create_mcpservice(data: UpdateMCPServiceRequest) -> str:
        """
        创建MCP服务

        :param UpdateMCPServiceRequest data: MCP服务配置
        :return: MCP服务ID
        """
        # 检查config
        if data.mcp_type == MCPType.SSE:
            config = MCPServerSSEConfig.model_validate(data.config)
        else:
            config = MCPServerStdioConfig.model_validate(data.config)

        # 构造Server
        mcp_server = MCPServerConfig(
            name=await MCPServiceManager.clean_name(data.name),
            description=data.description,
            config=config,
            type=data.mcp_type,
        )

        # 检查是否存在相同服务
        mcp_collection = MongoDB().get_collection("mcp")
        db_service = await mcp_collection.find_one({"name": mcp_server.name})
        mcp_id = sqids.encode([random.randint(0, 1000000) for _ in range(5)])[:6]  # noqa: S311
        if db_service:
            mcp_server.name = f"{mcp_server.name}-{mcp_id}"
            logger.warning("[MCPServiceManager] 已存在相同名称和描述的MCP服务")

        # 保存并载入配置
        logger.info("[MCPServiceManager] 创建mcp：%s", mcp_server.name)
        await MCPLoader.save_one(mcp_id, data.icon, mcp_server)
        await MCPLoader.init_one_template(mcp_id=mcp_id, config=mcp_server)
        return mcp_id

    @staticmethod
    async def update_mcpservice(data: UpdateMCPServiceRequest) -> str:
        """
        更新MCP服务

        :param UpdateMCPServiceRequest data: MCP服务配置
        :return: MCP服务ID
        """
        for user_sub in doc.activated:
            await MCPServiceManager.deactive_mcpservice(user_sub=user_sub, service_id=mcpservice_id)
        for server in config.mcp_servers.values():
            logger.info("[MCPServiceManager] 初始化mcp")
            await mcp_loader.init_one_template(mcp_id=mcpservice_id, config=server)
        # 返回服务ID
        return mcpservice_id

    @staticmethod
    async def delete_mcpservice(
            user_sub: str,
            service_id: str,
    ) -> None:
        """
        删除MCP服务

        :param user_sub: str: 用户ID
        :param service_id: str: MCP服务ID
        :return: 是否删除成功
        """
        service_collection = MongoDB().get_collection("mcp")
        db_service = await service_collection.find_one(
            {"id": service_id, "author": user_sub},
            {"_id": False},
        )
        if not db_service:
            msg = "[MCPServiceManager] MCP服务未找到或无权限"
            raise ValueError(msg)
        # 删除对应的mcp
        await MCPLoader.delete_mcp(service_id)

        # 遍历所有应用，将其中的MCP依赖删除
        app_collection = MongoDB().get_collection("application")
        await app_collection.update_many(
            {"mcp_service": service_id},
            {"$pull": {"mcp_service": service_id}},
        )

    @staticmethod
    async def active_mcpservice(
            user_sub: str,
            service_id: str,
    ) -> None:
        """
        激活MCP服务

        :param user_sub: str: 用户ID
        :param service_id: str: MCP服务ID
        :return: 无
        """
        mcp_collection = MongoDB().get_collection("mcp")
        status = await mcp_collection.find({"_id": service_id}, {"status": 1}).to_list()
        for item in status:
            mcp_status = item.get("status", MCPStatus.INSTALLING)
            if mcp_status == MCPStatus.READY:
                await MCPLoader.user_active_template(user_sub, service_id)
            else:
                err = "[MCPServiceManager] MCP服务未准备就绪"
                raise RuntimeError(err)

    @staticmethod
    async def deactive_mcpservice(
            user_sub: str,
            service_id: str,
    ) -> None:
        """
        取消激活MCP服务

        :param user_sub: str: 用户ID
        :param service_id: str: MCP服务ID
        :return: 无
        """
        mcp_pool = MCPPool()
        try:
            await mcp_pool.stop(mcp_id=service_id, user_sub=user_sub)
        except KeyError as e:
            logger.warning("[MCPServiceManager] MCP服务未找到: %s", str(e))
        await MCPLoader.user_deactive_template(user_sub, service_id)

    @staticmethod
    async def clean_name(name: str) -> str:
        """
        移除MCP服务名称中的特殊字符

        :param name: str: MCP服务名称
        :return: 清理后的MCP服务名称
        """
        invalid_chars = r'[\\\/:*?"<>|]'
        return re.sub(invalid_chars, "_", name)
