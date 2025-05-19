"""
语义接口中心 Manager

Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
"""

import json
import logging
import uuid
from hashlib import sha256
from typing import Any

from fastapi.encoders import jsonable_encoder

from apps.entities.enum_var import MCPSearchType
from apps.entities.mcp import MCPConfig, MCPServiceMetadata, MCPType
from apps.entities.response_data import MCPServiceCardItem
from apps.exceptions import InstancePermissionError
from apps.models.mongo import MongoDB
from apps.scheduler.pool.loader.mcp import MCPLoader

logger = logging.getLogger(__name__)


class MCPServiceManager:
    """MCP服务管理器"""

    @staticmethod
    async def is_active(user_sub: str, mcp_id: str) -> bool:
        """
        判断用户MCP是否激活

        :param str user_sub: 用户ID
        :param str mcp_id: MCP模板ID
        :return: bool
        """
        mongo = MongoDB()
        mcp_collection = mongo.get_collection("mcp")
        mcp_list = await mcp_collection.find({"_id": mcp_id}, {"activated": True}).to_list(None)
        return any(user_sub in db_item["activated"] for db_item in mcp_list)

    @staticmethod
    async def delete(service_id: str) -> None:
        """删除MCPService，并更新数据库"""
        mongo = MongoDB()
        service_collection = mongo.get_collection("mcp_service")
        try:
            await service_collection.delete_one({"id": service_id})
        except Exception as exp:
            err = f"[MCPServiceLoader] 删除MCPService失败: {exp}"
            logger.exception(err)
            raise RuntimeError(err) from exp

    @staticmethod
    async def _update_db(metadata: MCPServiceMetadata) -> None:
        """更新数据库"""
        if not metadata.hashes:
            err = f"[MCPServiceLoader] MCP服务 {metadata.id} 的哈希值为空"
            logger.error(err)
            raise ValueError(err)
        # 更新MongoDB
        mongo = MongoDB()
        service_collection = mongo.get_collection("mcp_service")
        try:
            # 插入或更新 Service
            await service_collection.update_one(
                {"id": metadata.id},
                {"$set": jsonable_encoder(metadata, by_alias=True)},
                upsert=True,
            )
        except Exception as e:
            err = f"[MCPServiceLoader] 更新 MongoDB 失败：{e}"
            logger.exception(err)
            raise RuntimeError(err) from e

    @staticmethod
    async def load_mcp_config(description: str, config_str: str, mcp_type: MCPType = MCPType.STDIO) -> MCPConfig:
        """字符串转换为MCPConfig"""
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
        """获取所有MCP服务列表"""
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
        return mcpservices, total_count

    @staticmethod
    async def get_mcpservice_data(
            user_sub: str,
            mcpservice_id: str,
    ) -> MCPServiceMetadata:
        """获取服务数据"""
        # 验证用户权限
        mcpservice_collection = MongoDB().get_collection("mcp_service")
        match_conditions = {
            {"author": user_sub}
        }
        query = {"$and": [{"service_id": mcpservice_id}, match_conditions]}
        db_service = await mcpservice_collection.find_one(query, {"_id": False})
        if not db_service:
            msg = "MCPService not found"
            raise Exception(msg)
        mcpservice_pool_store = MCPServiceMetadata.model_validate(db_service)
        if mcpservice_pool_store.author != user_sub:
            msg = "Permission denied"
            raise InstancePermissionError(msg)

        return mcpservice_pool_store

    @staticmethod
    async def get_service_details(
            service_id: str,
    ) -> MCPServiceMetadata:
        """获取服务API列表"""
        # 获取服务名称
        service_collection = MongoDB().get_collection("mcp_service")
        db_service = await service_collection.find_one({"id": service_id}, {"_id": False})
        if not db_service:
            msg = "MCPService not found"
            raise Exception(msg)
        mcpservice_pool_store = MCPServiceMetadata.model_validate(db_service)

        return mcpservice_pool_store

    @staticmethod
    async def _search_mcpservice(
            search_conditions: dict,
            page: int,
            page_size: int,
    ) -> tuple[list[MCPServiceMetadata], int]:
        """基于输入条件获取MCP服务数据"""
        mcpservice_collection = MongoDB().get_collection("mcp_service")
        # 获取服务总数
        total = await mcpservice_collection.count_documents(search_conditions)
        # 分页查询
        skip = (page - 1) * page_size
        db_mcpservices = await mcpservice_collection.find(search_conditions, {"_id": False}).skip(skip).limit(page_size).to_list()
        if not db_mcpservices:
            logger.warning("[MCPServiceManager] 没有找到符合条件的MCP服务: %s", search_conditions)
            return [], -1
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

    async def save(self, metadata: MCPServiceMetadata) -> None:
        """保存mcp到数据库"""
        metadata.hashes = sha256(metadata.config_str.encode(encoding='utf-8')).hexdigest()
        await self._update_db(metadata)

    async def create_mcpservice(
            self,
            user_sub: str,
            name: str,
            icon: str,
            description: str,
            config: MCPConfig,
            config_str: str,
            mcp_type: MCPType
    ) -> str:
        """创建MCP服务"""
        if len(config.mcp_servers) != 1:
            msg = "[MCPServiceManager] MCP服务配置不唯一"
            raise Exception(msg)
        mcpservice_id = str(uuid.uuid4())
        # 检查是否存在相同服务
        service_collection = MongoDB().get_collection("mcp_service")
        db_service = await service_collection.find_one(
            {
                "name": name,
                "description": description
            },
            {"_id": False}
        )
        if db_service:
            msg = "[MCPServiceManager] 已存在相同名称和描述的MCP服务"
            raise Exception(msg)

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
            mcpType=mcp_type
        )
        await self.save(service_metadata)
        mcp_loader = MCPLoader()
        await mcp_loader.save_one(user_sub='', mcp_id=mcpservice_id, config=config)
        await mcp_loader.save_one(user_sub=user_sub, mcp_id=mcpservice_id, config=config)
        return mcpservice_id

    async def update_mcpservice(
            self,
            user_sub: str,
            mcpservice_id: str,
            name: str,
            icon: str,
            description: str,
            config: MCPConfig,
            config_str: str
    ) -> str:
        """更新服务"""
        if len(config.mcp_servers) != 1:
            msg = "[MCPServiceManager] MCP服务配置不唯一"
            raise Exception(msg)
        mcpservice_collection = MongoDB().get_collection("mcp_service")
        db_service = await mcpservice_collection.find_one({"id": mcpservice_id}, {"_id": False})
        if not db_service:
            msg = "MCPService not found"
            raise Exception(msg)
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
            mcpType=service_pool_store.mcp_type
        )
        await self.save(mcpservice_metadata)
        mcp_loader = MCPLoader()
        await mcp_loader.save_one(user_sub="", mcp_id=mcpservice_id, config=config)
        await mcp_loader.save_one(user_sub=user_sub, mcp_id=mcpservice_id, config=config)
        # 返回服务ID
        return mcpservice_id

    async def delete_mcpservice(
            self,
            user_sub: str,
            service_id: str,
    ) -> bool:
        """删除服务"""
        service_collection = MongoDB().get_collection("mcp_service")
        db_service = await service_collection.find_one({"id": service_id}, {"_id": False})
        if not db_service:
            msg = "[MCPServiceCenterManager] Service未找到"
            raise ValueError(msg)
        # 验证用户权限
        service_pool_store = MCPServiceMetadata.model_validate(db_service)
        if service_pool_store.author != user_sub:
            msg = "Permission denied"
            raise InstancePermissionError(msg)
        # 删除服务
        await self.delete(service_id)
        await MCPLoader().user_deactive_template(user_sub, service_id)
        return True
