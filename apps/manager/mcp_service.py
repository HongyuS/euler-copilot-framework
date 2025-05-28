# Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
"""MCP服务管理器"""

import logging
import uuid
from hashlib import sha256
from typing import Any

from apps.constants import SERVICE_PAGE_SIZE
from apps.entities.enum_var import SearchType
from apps.entities.mcp import (
    MCPCollection,
    MCPConfig,
    MCPServerConfig,
    MCPStatus,
    MCPTool,
    MCPType,
)
from apps.entities.response_data import MCPServiceCardItem
from apps.exceptions import InstancePermissionError
from apps.models.mongo import MongoDB
from apps.scheduler.pool.loader.mcp import MCPLoader
from apps.scheduler.pool.mcp.pool import MCPPool

logger = logging.getLogger(__name__)


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

        :param search_type: SearchType: str: MCP描述
        :param user_sub: str: 用户ID
        :param keyword: str: 搜索关键字
        :param page: int: 页码
        :return: MCP服务列表
        """
        filters = MCPServiceManager._build_filters(search_type, keyword)
        mcpservice_pools = await MCPServiceManager._search_mcpservice(filters, page)
        return [
            MCPServiceCardItem(
                mcpserviceId=mcpservice_pool.id,
                icon=mcpservice_pool.icon,
                name=mcpservice_pool.name,
                description=mcpservice_pool.description,
                author=mcpservice_pool.author,
                isActive=await MCPServiceManager.is_active(user_sub, mcpservice_pool.id),
                status=await MCPServiceManager.get_service_status(mcpservice_pool.id),
            )
            for mcpservice_pool in mcpservice_pools
        ]

    @staticmethod
    async def get_mcp_service_detail(
            user_sub: str,
            mcpservice_id: str,
    ) -> MCPServiceMetadata:
        """
        验证用户权限，获取MCP服务详细信息

        :param user_sub: str: 用户ID
        :param mcpservice_id: str: MCP服务ID
        :return: MCP服务详细信息
        """
        # 验证用户权限
        mcpservice_collection = MongoDB().get_collection("mcp")
        query = {"$and": [{"service_id": mcpservice_id}, {"author": user_sub}]}
        db_service = await mcpservice_collection.find_one(query, {"_id": False})
        if not db_service:
            msg = "[MCPServiceManager] MCP服务未找到"
            raise RuntimeError(msg)
        mcpservice_pool_store = MCPServiceMetadata.model_validate(db_service)
        if mcpservice_pool_store.author != user_sub:
            msg = "[MCPServiceManager] 权限不足"
            raise InstancePermissionError(msg)

        return mcpservice_pool_store

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
    ) -> list[MCPServiceMetadata]:
        """
        基于输入条件搜索MCP服务

        :param search_conditions: dict[str, Any]: 搜索条件
        :param page: int: 页码
        :return: MCP列表
        """
        mcpservice_collection = MongoDB().get_collection("mcp")
        # 获取服务总数
        total = await mcpservice_collection.count_documents(search_conditions)
        # 分页查询
        skip = (page - 1) * SERVICE_PAGE_SIZE
        db_mcpservices = await mcpservice_collection.find(
            search_conditions, {"_id": False},
        ).skip(skip).limit(SERVICE_PAGE_SIZE).to_list()
        if not db_mcpservices:
            logger.warning("[MCPServiceManager] 没有找到符合条件的MCP服务: %s", search_conditions)
            return []
        mcpservice_pools = [MCPServiceMetadata.model_validate(db_mcpservice) for db_mcpservice in db_mcpservices]
        return mcpservice_pools

    @staticmethod
    def _build_filters(
            search_type: SearchType,
            keyword: str | None,
    ) -> dict[str, Any]:
        if not keyword:
            return {}

        base_filters = {}
        search_filters = [
            {"name": {"$regex": keyword, "$options": "i"}},
            {"description": {"$regex": keyword, "$options": "i"}},
            {"author": {"$regex": keyword, "$options": "i"}},
        ]

        if search_type == SearchType.ALL:
            base_filters["$or"] = search_filters
        elif search_type == SearchType.NAME:
            base_filters["name"] = {"$regex": keyword, "$options": "i"}
        elif search_type == SearchType.DESCRIPTION:
            base_filters["description"] = {"$regex": keyword, "$options": "i"}
        elif search_type == SearchType.AUTHOR:
            base_filters["author"] = {"$regex": keyword, "$options": "i"}
        return base_filters

    @staticmethod
    async def create_mcpservice(  # noqa: PLR0913
            user_sub: str,
            name: str,
            icon: str,
            description: str,
            config: MCPConfig,
            mcp_type: MCPType,
    ) -> str:
        """
        创建MCP服务

        :param user_sub: str: 用户ID
        :param name: str: MCP服务名
        :param icon: str: MCP服务图标，base64格式字符串
        :param description: str: MCP服务描述
        :param config: MCPConfig: MCP服务配置
        :param mcp_type: MCPType: MCP服务类型
        :return: MCP服务ID
        """
        if len(config.mcp_servers) != 1:
            msg = "[MCPServiceManager] MCP服务配置不唯一"
            raise RuntimeError(msg)
        mcpservice_id = str(uuid.uuid4())
        # 检查是否存在相同服务
        service_collection = MongoDB().get_collection("mcp")
        db_service = await service_collection.find_one(
            {
                "name": name,
                "description": description,
            },
            {"_id": False},
        )
        if db_service:
            msg = "[MCPServiceManager] 已存在相同名称和描述的MCP服务"
            raise RuntimeError(msg)

        tools = []

        # 存入数据库
        service_metadata = MCPServiceMetadata(
            id=mcpservice_id,
            name=name,
            icon=icon,
            description=description,
            author=user_sub,
            config=config,
            tools=tools,
            mcpType=mcp_type,
        )
        await MCPServiceManager.save(service_metadata)
        mcp_loader = MCPLoader()
        for server in config.mcp_servers.values():
            logger.info("[MCPServiceManager] 初始化mcp")
            await mcp_loader.init_one_template(mcp_id=mcpservice_id, config=server)
        return mcpservice_id

    @staticmethod
    async def update_mcpservice(  # noqa: PLR0913
            user_sub: str,
            mcpservice_id: str,
            name: str,
            icon: str,
            description: str,
            config: MCPConfig,
            mcp_type: MCPType,
    ) -> str:
        """
        更新MCP服务

        :param user_sub: str: 用户ID
        :param mcpservice_id: MCP服务ID,
        :param name: str: 要修改的MCP服务名
        :param icon: str: MCP服务图标，base64格式字符串
        :param description: str: MCP服务描述
        :param config: MCPConfig: MCP服务配置
        :param mcp_type: MCPType: MCP服务类型
        :return: MCP服务ID
        """
        if len(config.mcp_servers) != 1:
            msg = "[MCPServiceManager] MCP服务配置不唯一"
            raise RuntimeError(msg)
        mcpservice_collection = MongoDB().get_collection("mcp_service")
        db_service = await mcpservice_collection.find_one({"id": mcpservice_id}, {"_id": False})
        if not db_service:
            msg = "[MCPServiceManager] MCP服务未找到"
            raise RuntimeError(msg)
        service_pool_store = MCPServiceMetadata.model_validate(db_service)

        # 存入数据库
        mcpservice_metadata = MCPServiceMetadata(
            id=mcpservice_id,
            name=name,
            icon=icon,
            description=description,
            author=user_sub,
            config=config,
            tools=service_pool_store.tools,
            hashes=service_pool_store.hashes,
            mcpType=mcp_type,
        )
        await MCPServiceManager.save(mcpservice_metadata)
        mcp_loader = MCPLoader()
        doc = MCPCollection.model_validate(db_service)
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
    ) -> bool:
        """
        删除MCP服务

        :param user_sub: str: 用户ID
        :param service_id: str: MCP服务ID
        :return: 是否删除成功
        """
        service_collection = MongoDB().get_collection("mcp")
        db_service = await service_collection.find_one({"id": service_id}, {"_id": False})
        if not db_service:
            msg = "[MCPServiceManager] MCP服务未找到"
            raise ValueError(msg)
        # 验证用户权限
        service_pool_store = MCPServiceMetadata.model_validate(db_service)
        if service_pool_store.author != user_sub:
            msg = "[MCPServiceManager] 权限不足"
            raise InstancePermissionError(msg)
        await MCPServiceManager.delete(service_id)
        await MCPLoader.delete_mcp(service_id)
        return True

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
        status = await mcp_collection.find({"_id": service_id}, {"status": 1, "_id": False}).to_list(None)
        loader = MCPLoader()
        for item in status:
            mcp_status = item.get("status", MCPStatus.INSTALLING)
            if mcp_status == MCPStatus.READY:
                loader = MCPLoader()
                await loader.user_active_template(user_sub, service_id)
            else:
                err = "[MCPServiceManager] MCP服务未准备就绪"
                logger.error(err)
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
            logger.warning(e)
        await MCPLoader.user_deactive_template(user_sub, service_id)
