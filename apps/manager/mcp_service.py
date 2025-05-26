# Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
"""MCP服务管理器"""

import json
import logging
import uuid
from hashlib import sha256
from typing import Any

from fastapi.encoders import jsonable_encoder

from apps.entities.enum_var import MCPSearchType
from apps.entities.mcp import MCPConfig, MCPServiceMetadata, MCPStatus, MCPTool, MCPType
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
    async def delete(service_id: str) -> None:
        """
        删除MCPService，并更新数据库

        :param str service_id: MCP服务ID
        :return: 无
        """
        mongo = MongoDB()
        service_collection = mongo.get_collection("mcp_service")
        await service_collection.delete_one({"id": service_id})

    @staticmethod
    async def _update_db(metadata: MCPServiceMetadata) -> None:
        """
        更新数据库

        :param metadata: MCPServiceMetadata: MCP数据
        :return: 无
        """
        if not metadata.hashes:
            err = f"[MCPServiceLoader] MCP服务 {metadata.id} 的哈希值为空"
            logger.error(err)
            raise ValueError(err)
        # 更新MongoDB
        mongo = MongoDB()
        service_collection = mongo.get_collection("mcp_service")

        # 插入或更新 Service
        await service_collection.update_one(
            {"id": metadata.id},
            {"$set": jsonable_encoder(metadata, by_alias=True)},
            upsert=True,
        )

    @staticmethod
    async def load_mcp_config(description: str, config_str: str, mcp_type: MCPType = MCPType.STDIO) -> MCPConfig:
        """
        字符串转换为MCPConfig

        :param description: str: MCP描述
        :param config_str: str: MCP配置字符串
        :param mcp_type: MCPType: MCP输出类型
        :return: MCPConfig
        """
        mcp_servers = json.loads(config_str)
        result = MCPConfig.model_validate(mcp_servers)
        for server_name, config in result.mcp_servers.items():
            config.name = server_name
            config.description = description
            config.type = mcp_type
        return result

    @staticmethod
    async def fetch_all_mcpservices(
            search_type: MCPSearchType,
            user_sub: str,
            keyword: str | None,
            page: int,
            page_size: int,
    ) -> tuple[list[MCPServiceCardItem], int]:
        """
        获取所有MCP服务列表

        :param search_type: MCPSearchType: str: MCP描述
        :param user_sub: str: 用户ID
        :param keyword: str: 搜索关键字
        :param page: int: 页码
        :param page_size: int: 每页显示数量
        :return: MCP服务列表，MCP总数
        """
        filters = MCPServiceManager._build_filters({}, search_type, keyword) if keyword else {}
        mcpservice_pools, total_count = await MCPServiceManager._search_mcpservice(filters, page, page_size)
        mcpservices = [
            MCPServiceCardItem(
                mcpserviceId=mcpservice_pool.id,
                icon=mcpservice_pool.icon,
                name=mcpservice_pool.name,
                description=mcpservice_pool.description,
                author=mcpservice_pool.author,
            )
            for mcpservice_pool in mcpservice_pools
        ]
        for mcp in mcpservices:
            mcp.is_active = await MCPServiceManager.is_active(user_sub, mcp.mcpservice_id)
            mcp.status = await MCPServiceManager.get_service_status(mcp.mcpservice_id)
        return mcpservices, total_count

    @staticmethod
    async def get_mcpservice_data(
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
        mcpservice_collection = MongoDB().get_collection("mcp_service")
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
    async def get_service_details(
            service_id: str,
    ) -> MCPServiceMetadata:
        """
        获取MCP服务信息，不验证用户权限

        :param service_id: str: MCP服务ID
        :return: MCP服务详细信息
        """
        # 获取服务名称
        service_collection = MongoDB().get_collection("mcp_service")
        db_service = await service_collection.find_one({"id": service_id}, {"_id": False})
        if not db_service:
            msg = "[MCPServiceManager] MCP服务未找到"
            raise RuntimeError(msg)
        mcpservice_pool_store = MCPServiceMetadata.model_validate(db_service)
        mcpservice_pool_store.tools = await MCPServiceManager.get_service_tools(service_id)
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
            page_size: int,
    ) -> tuple[list[MCPServiceMetadata], int]:
        """
        基于输入条件搜索MCP服务

        :param search_conditions: dict[str, Any]: 搜索条件
        :param page: int: 页码
        :param page_size: int: 每页显示数量
        :return: MCP列表，MCP总数
        """
        mcpservice_collection = MongoDB().get_collection("mcp_service")
        # 获取服务总数
        total = await mcpservice_collection.count_documents(search_conditions)
        # 分页查询
        skip = (page - 1) * page_size
        db_mcpservices = await mcpservice_collection.find(
            search_conditions, {"_id": False},
        ).skip(skip).limit(page_size).to_list()
        if not db_mcpservices:
            logger.warning("[MCPServiceManager] 没有找到符合条件的MCP服务: %s", search_conditions)
            return [], 0
        mcpservice_pools = [MCPServiceMetadata.model_validate(db_mcpservice) for db_mcpservice in db_mcpservices]
        return mcpservice_pools, total

    @staticmethod
    def _build_filters(
            base_filters: dict[str, Any],
            search_type: MCPSearchType,
            keyword: str,
    ) -> dict[str, Any]:
        search_filters = [
            {"name": {"$regex": keyword, "$options": "i"}},
            {"description": {"$regex": keyword, "$options": "i"}},
            {"author": {"$regex": keyword, "$options": "i"}},
        ]
        if search_type == MCPSearchType.ALL:
            base_filters["$or"] = search_filters
        elif search_type == MCPSearchType.NAME:
            base_filters["name"] = {"$regex": keyword, "$options": "i"}
        elif search_type == MCPSearchType.AUTHOR:
            base_filters["author"] = {"$regex": keyword, "$options": "i"}
        return base_filters

    @staticmethod
    async def save(metadata: MCPServiceMetadata) -> None:
        """
        保存MCP

        :param metadata: MCPServiceMetadata: MCP服务数据
        :return: 无
        """
        metadata.hashes["config"] = sha256(metadata.config_str.encode(encoding="utf-8")).hexdigest()
        await MCPServiceManager._update_db(metadata)

    @staticmethod
    async def create_mcpservice(  # noqa: PLR0913
            user_sub: str,
            name: str,
            icon: str,
            description: str,
            config: MCPConfig,
            config_str: str,
            mcp_type: MCPType,
    ) -> str:
        """
        创建MCP服务

        :param user_sub: str: 用户ID
        :param name: str: MCP服务名
        :param icon: str: MCP服务图标，base64格式字符串
        :param description: str: MCP服务描述
        :param config: MCPConfig: MCP服务配置
        :param config_str: str: MCP服务配置字符串格式
        :param mcp_type: MCPType: MCP服务类型
        :return: MCP服务ID
        """
        if len(config.mcp_servers) != 1:
            msg = "[MCPServiceManager] MCP服务配置不唯一"
            raise RuntimeError(msg)
        mcpservice_id = str(uuid.uuid4())
        # 检查是否存在相同服务
        service_collection = MongoDB().get_collection("mcp_service")
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
            configStr=config_str,
            mcpType=mcp_type,
        )
        await MCPServiceManager.save(service_metadata)
        mcp_loader = MCPLoader()
        for server in config.mcp_servers.values():
            await mcp_loader.init_one_template(mcp_id=mcpservice_id, config=server)
        try:
            await MCPServiceManager.active_mcpservice(user_sub=user_sub, service_id=mcpservice_id)
        except Exception:
            logger.exception("[MCPServiceLoader] 管理员激活mcp失败")
        return mcpservice_id

    @staticmethod
    async def update_mcpservice(  # noqa: PLR0913
            user_sub: str,
            mcpservice_id: str,
            name: str,
            icon: str,
            description: str,
            config: MCPConfig,
            config_str: str,
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
        :param config_str: str: MCP服务配置字符串
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
            configStr=config_str,
            mcpType=mcp_type,
        )
        await MCPServiceManager.save(mcpservice_metadata)
        mcp_loader = MCPLoader()
        await MCPServiceManager.deactive_mcpservice(user_sub=user_sub, service_id=mcpservice_id)
        for server in config.mcp_servers.values():
            await mcp_loader.init_one_template(mcp_id=mcpservice_id, config=server)
        await mcp_loader.update_template_status(mcp_id=mcpservice_id, status=MCPStatus.FAILED)
        try:
            await MCPServiceManager.active_mcpservice(user_sub=user_sub, service_id=mcpservice_id)
        except Exception as e:
            err = f"[MCPServiceLoader] 管理员激活mcp失败：{e}"
            logger.exception(err)
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
        service_collection = MongoDB().get_collection("mcp_service")
        db_service = await service_collection.find_one({"id": service_id}, {"_id": False})
        if not db_service:
            msg = "[MCPServiceManager] MCP服务未找到"
            raise ValueError(msg)
        # 验证用户权限
        service_pool_store = MCPServiceMetadata.model_validate(db_service)
        if service_pool_store.author != user_sub:
            msg = "[MCPServiceManager] 权限不足"
            raise InstancePermissionError(msg)
        # 删除服务
        await MCPServiceManager.delete(service_id)
        await MCPLoader().user_deactive_template(user_sub, service_id)
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
            mcp_status = item.get("status", MCPStatus.FAILED)
            if mcp_status == MCPStatus.READY:
                loader = MCPLoader()
                await loader.user_active_template(user_sub, service_id)
            else:
                await loader.process_install_mcp(service_id, [user_sub])
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
        loader = MCPLoader()
        await loader.user_deactive_template(user_sub, service_id)
