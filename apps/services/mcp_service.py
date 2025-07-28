# Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
"""MCP服务（插件中心）管理器"""

import logging
import re
import uuid

import magic
from fastapi import UploadFile
from PIL import Image
from sqlalchemy import and_, or_, select

from apps.common.postgres import postgres
from apps.constants import (
    ALLOWED_ICON_MIME_TYPES,
    ICON_PATH,
    SERVICE_PAGE_SIZE,
)
from apps.models.mcp import (
    MCPActivated,
    MCPInfo,
    MCPInstallStatus,
    MCPTools,
    MCPType,
)
from apps.scheduler.pool.loader.mcp import MCPLoader
from apps.scheduler.pool.mcp.pool import MCPPool
from apps.schemas.enum_var import SearchType
from apps.schemas.mcp import (
    MCPServerConfig,
    MCPServerSSEConfig,
    MCPServerStdioConfig,
)
from apps.schemas.request_data import UpdateMCPServiceRequest
from apps.schemas.response_data import MCPServiceCardItem

logger = logging.getLogger(__name__)
MCP_ICON_PATH = ICON_PATH / "mcp"


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
        async with postgres.session() as session:
            mcp_info = (await session.scalars(select(MCPActivated).where(
                and_(
                    MCPActivated.mcpId == mcp_id,
                    MCPActivated.userSub == user_sub,
                ),
            ))).one_or_none()
            return bool(mcp_info)


    @staticmethod
    async def get_service_status(mcp_id: str) -> MCPInstallStatus:
        """
        获取MCP服务状态

        :param str mcp_id: MCP服务ID
        :return: MCP服务状态
        """
        async with postgres.session() as session:
            mcp_info = (await session.scalars(select(MCPInfo).where(MCPInfo.id == mcp_id))).one_or_none()
            if mcp_info:
                return mcp_info.status
            return MCPInstallStatus.FAILED


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
        mcpservice_pools = await MCPServiceManager._search_mcpservice(search_type, keyword, page)
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
    async def get_mcp_service(mcpservice_id: str) -> MCPInfo | None:
        """
        获取MCP服务详细信息

        :param mcpservice_id: str: MCP服务ID
        :return: MCP服务详细信息
        """
        async with postgres.session() as session:
            return (await session.scalars(select(MCPInfo).where(MCPInfo.id == mcpservice_id))).one_or_none()


    @staticmethod
    async def get_mcp_config(mcpservice_id: str) -> tuple[MCPServerConfig, str]:
        """
        获取MCP服务配置

        :param mcpservice_id: str: MCP服务ID
        :return: MCP服务配置
        """
        icon = await MCPLoader.get_icon(mcpservice_id)
        config = await MCPLoader.get_config(mcpservice_id)
        return config, icon


    @staticmethod
    async def get_service_tools(
            service_id: str,
    ) -> list[MCPTools]:
        """
        获取MCP可以用工具

        :param service_id: str: MCP服务ID
        :return: MCP工具详细信息列表
        """
        async with postgres.session() as session:
            return list((await session.scalars(select(MCPTools).where(MCPTools.mcpId == service_id))).all())


    @staticmethod
    async def _search_mcpservice(
            search_type: SearchType,
            keyword: str | None,
            page: int,
    ) -> list[MCPInfo]:
        """
        基于输入条件搜索MCP服务

        :param search_conditions: dict[str, Any]: 搜索条件
        :param page: int: 页码
        :return: MCP列表
        """
        # 分页查询
        skip = (page - 1) * SERVICE_PAGE_SIZE

        async with postgres.session() as session:
            if not keyword:
                result = list(
                    (await session.scalars(select(MCPInfo).offset(skip).limit(SERVICE_PAGE_SIZE))).all(),
                )
            elif search_type == SearchType.ALL:
                result = list(
                    (await session.scalars(select(MCPInfo).where(
                        or_(
                            MCPInfo.name.like(f"%{keyword}%"),
                            MCPInfo.description.like(f"%{keyword}%"),
                            MCPInfo.author.like(f"%{keyword}%"),
                        ),
                    ).offset(skip).limit(SERVICE_PAGE_SIZE))).all(),
                )
            elif search_type == SearchType.NAME:
                result = list(
                    (await session.scalars(
                        select(MCPInfo).where(MCPInfo.name.like(f"%{keyword}%")).offset(skip).limit(SERVICE_PAGE_SIZE),
                    )).all(),
                )
            elif search_type == SearchType.DESCRIPTION:
                result = list(
                    (await session.scalars(
                        select(MCPInfo).where(MCPInfo.description.like(f"%{keyword}%")).offset(skip).limit(SERVICE_PAGE_SIZE),
                    )).all(),
                )
            elif search_type == SearchType.AUTHOR:
                result = list(
                    (await session.scalars(
                        select(MCPInfo).where(MCPInfo.author.like(f"%{keyword}%")).offset(skip).limit(SERVICE_PAGE_SIZE),
                    )).all(),
                )

        # 如果未找到，返回空列表
        if not result:
            logger.warning("[MCPServiceManager] 没有找到符合条件的MCP服务: %s", search_type)
            return []
        # 将数据库中的MCP服务转换为对象
        return result


    @staticmethod
    async def create_mcpservice(data: UpdateMCPServiceRequest, user_sub: str) -> uuid.UUID:
        """
        创建MCP服务

        :param UpdateMCPServiceRequest data: MCP服务配置
        :return: MCP服务ID
        """
        # 检查config
        if data.mcp_type == MCPType.SSE:
            config = MCPServerSSEConfig.model_validate_json(data.config)
        else:
            config = MCPServerStdioConfig.model_validate_json(data.config)

        # 构造Server
        mcp_server = MCPServerConfig(
            name=await MCPServiceManager.clean_name(data.name),
            overview=data.overview,
            description=data.description,
            config=config,
            mcpType=data.mcp_type,
            author=user_sub,
        )

        # 检查是否存在相同服务
        async with postgres.session() as session:
            mcp_info = (await session.scalars(select(MCPInfo).where(MCPInfo.name == mcp_server.name))).one_or_none()
            if mcp_info:
                mcp_server.name = f"{mcp_server.name}-{uuid.uuid4().hex[:6]}"
                logger.warning("[MCPServiceManager] 已存在相同ID或名称的MCP服务")

        # 保存并载入配置
        logger.info("[MCPServiceManager] 创建mcp：%s", mcp_server.name)
        await MCPLoader.save_one(mcp_server.id, mcp_server)
        await MCPLoader.init_one_template(mcp_id=mcp_server.id, config=mcp_server)
        return mcp_server.id


    @staticmethod
    async def update_mcpservice(data: UpdateMCPServiceRequest, user_sub: str) -> str:
        """
        更新MCP服务

        :param UpdateMCPServiceRequest data: MCP服务配置
        :return: MCP服务ID
        """
        if not data.service_id:
            msg = "[MCPServiceManager] MCP服务ID为空"
            raise ValueError(msg)

        mcp_collection = MongoDB().get_collection("mcp")
        db_service = await mcp_collection.find_one({"_id": data.service_id, "author": user_sub})
        if not db_service:
            msg = "[MCPServiceManager] MCP服务未找到或无权限"
            raise ValueError(msg)

        db_service = MCPCollection.model_validate(db_service)
        for user_id in db_service.activated:
            await MCPServiceManager.deactive_mcpservice(user_sub=user_id, service_id=data.service_id)

        await MCPLoader.init_one_template(mcp_id=data.service_id, config=MCPServerConfig(
            name=data.name,
            overview=data.overview,
            description=data.description,
            config=MCPServerStdioConfig.model_validate_json(
                data.config,
            ) if data.mcp_type == MCPType.STDIO else MCPServerSSEConfig.model_validate_json(
                data.config,
            ),
            mcpType=data.mcp_type,
            author=user_sub,
        ))
        # 返回服务ID
        return data.service_id


    @staticmethod
    async def delete_mcpservice(service_id: str) -> None:
        """
        删除MCP服务

        :param service_id: str: MCP服务ID
        :return: 是否删除成功
        """
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
            service_id: uuid.UUID,
    ) -> None:
        """
        激活MCP服务

        :param user_sub: str: 用户ID
        :param service_id: str: MCP服务ID
        :return: 无
        """
        async with postgres.session() as session:
            mcp_info = (await session.scalars(select(MCPInfo).where(MCPInfo.id == service_id))).one_or_none()
            if not mcp_info:
                err = "[MCPServiceManager] MCP服务未找到"
                raise ValueError(err)
            if mcp_info.status != MCPInstallStatus.READY:
                err = "[MCPServiceManager] MCP服务未准备就绪"
                raise RuntimeError(err)
            await session.merge(MCPActivated(
                mcpId=mcp_info.id,
                userSub=user_sub,
            ))
            await session.commit()
            await MCPLoader.user_active_template(user_sub, service_id)

    @staticmethod
    async def deactive_mcpservice(
            user_sub: str,
            service_id: uuid.UUID,
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
        except KeyError:
            logger.warning("[MCPServiceManager] MCP服务无进程")
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

    @staticmethod
    async def save_mcp_icon(
            service_id: uuid.UUID,
            icon: UploadFile,
    ) -> str:
        """保存MCP服务图标"""
        # 检查MIME
        mime = magic.from_buffer(icon.file.read(), mime=True)
        icon.file.seek(0)

        if mime not in ALLOWED_ICON_MIME_TYPES:
            err = "[MCPServiceManager] 不支持的图标格式"
            raise ValueError(err)

        # 保存图标
        image = Image.open(icon.file)
        image = image.convert("RGB")
        image = image.resize((64, 64), resample=Image.Resampling.LANCZOS)
        # 检查文件夹
        if not await MCP_ICON_PATH.exists():
            await MCP_ICON_PATH.mkdir(parents=True, exist_ok=True)
        # 保存
        image.save(MCP_ICON_PATH / f"{service_id}.png", format="PNG", optimize=True, compress_level=9)

        return f"/static/mcp/{service_id}.png"


    @staticmethod
    async def is_user_actived(user_sub: str, mcp_id: str) -> bool:
        """
        判断用户是否激活MCP

        :param user_sub: str: 用户ID
        :param mcp_id: str: MCP服务ID
        :return: 是否激活
        """
        async with postgres.session() as session:
            mcp_info = (await session.scalars(select(MCPActivated).where(
                and_(
                    MCPActivated.mcpId == mcp_id,
                    MCPActivated.userSub == user_sub,
                ),
            ))).one_or_none()
            return bool(mcp_info)


    @staticmethod
    async def query_mcp_tools(mcp_id: str) -> list[MCPTools]:
        """
        查询MCP工具

        :param mcp_id: str: MCP服务ID
        :return: MCP工具列表
        """
        async with postgres.session() as session:
            return list((await session.scalars(select(MCPTools).where(MCPTools.mcpId == mcp_id))).all())


    @staticmethod
    async def add_mcp_template(mcp_id: str, config: MCPServerConfig, tools: list[MCPTools]) -> None:
        # 插入MCP表
        async with postgres.session() as session:
            await session.merge(MCPInfo(
                id=mcp_id,
                name=config.name,
                description=config.description,
                config=config,
                overview=config.overview,
                mcpType=config.mcpType,
                author=config.author,
                status=MCPInstallStatus.INSTALLING,
            ))
