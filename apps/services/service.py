# Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
"""语义接口中心 Manager"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

import yaml
from anyio import Path
from sqlalchemy import Select, and_, delete, func, or_, select

from apps.common.config import config
from apps.common.postgres import postgres
from apps.models import (
    NodeInfo,
    PermissionType,
    Service,
    ServiceACL,
    User,
    UserFavorite,
    UserFavoriteType,
)
from apps.scheduler.openapi import ReducedOpenAPISpec
from apps.scheduler.pool.loader.openapi import OpenAPILoader
from apps.scheduler.pool.loader.service import ServiceLoader
from apps.schemas.enum_var import SearchType
from apps.schemas.flow import (
    Permission,
    ServiceApiConfig,
    ServiceMetadata,
)
from apps.schemas.service import ServiceApiData, ServiceCardItem

logger = logging.getLogger(__name__)


class ServiceCenterManager:
    """语义接口中心管理器"""

    @staticmethod
    async def _build_service_query(
        search_type: SearchType,
        keyword: str | None,
        page: int,
        page_size: int,
    ) -> Select[tuple[Service, ...]]:
        """
        构建服务查询语句

        :param search_type: 搜索类型
        :param keyword: 搜索关键字
        :param page: 页码
        :param page_size: 页面大小
        :return: 查询语句和偏移量
        """
        # 构建基础查询
        query = select(Service)

        # 根据搜索类型和关键字添加WHERE条件
        if keyword:
            if search_type == SearchType.ALL:
                query = query.where(
                    or_(
                        Service.name.like(f"%{keyword}%"),
                        Service.description.like(f"%{keyword}%"),
                        Service.author.like(f"%{keyword}%"),
                    ),
                )
            elif search_type == SearchType.NAME:
                query = query.where(
                    Service.name.like(f"%{keyword}%"),
                )
            elif search_type == SearchType.DESCRIPTION:
                query = query.where(
                    Service.description.like(f"%{keyword}%"),
                )
            elif search_type == SearchType.AUTHOR:
                query = query.where(
                    Service.author.like(f"%{keyword}%"),
                )

        # 添加排序和分页
        return query.order_by(Service.updatedAt.desc()).offset((page - 1) * page_size).limit(page_size)


    @staticmethod
    async def fetch_all_services(
        user_sub: str,
        search_type: SearchType,
        keyword: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[ServiceCardItem], int]:
        """获取所有服务列表"""
        async with postgres.session() as session:
            # 使用通用查询构建方法
            query = await ServiceCenterManager._build_service_query(search_type, keyword, page, page_size)
            service_pools = list((await session.scalars(query)).all())

            # 获取总数（由于我们使用了分页查询，这里直接使用结果数量）
            total_count = len(service_pools)

        fav_service_ids = await ServiceCenterManager._get_favorite_service_ids_by_user(user_sub)
        services = [
            ServiceCardItem(
                serviceId=service_pool.id,
                icon="",
                name=service_pool.name,
                description=service_pool.description,
                author=service_pool.author,
                favorited=(service_pool.id in fav_service_ids),
            )
            for service_pool in service_pools
        ]
        return services, total_count


    @staticmethod
    async def _build_user_service_query(
        user_sub: str,
        search_type: SearchType,
        keyword: str | None,
        page: int,
        page_size: int,
    ) -> Select[tuple[Service, ...]]:
        """
        构建用户服务查询语句

        :param user_sub: 用户唯一标识
        :param search_type: 搜索类型
        :param keyword: 搜索关键字
        :param page: 页码
        :param page_size: 页面大小
        :return: 查询语句
        """
        # 构建基础查询
        query = select(Service).where(Service.author == user_sub)

        # 根据搜索类型和关键字添加WHERE条件
        if keyword:
            if search_type == SearchType.ALL:
                query = query.where(
                    and_(
                        Service.author == user_sub,
                        or_(
                            Service.name.like(f"%{keyword}%"),
                            Service.description.like(f"%{keyword}%"),
                            Service.author.like(f"%{keyword}%"),
                        ),
                    ),
                )
            elif search_type == SearchType.NAME:
                query = query.where(
                    and_(
                        Service.author == user_sub,
                        Service.name.like(f"%{keyword}%"),
                    ),
                )
            elif search_type == SearchType.DESCRIPTION:
                query = query.where(
                    and_(
                        Service.author == user_sub,
                        Service.description.like(f"%{keyword}%"),
                    ),
                )
            elif search_type == SearchType.AUTHOR:
                query = query.where(
                    and_(
                        Service.author == user_sub,
                        Service.author.like(f"%{keyword}%"),
                    ),
                )

        # 添加排序和分页
        return query.order_by(Service.updatedAt.desc()).offset((page - 1) * page_size).limit(page_size)


    @staticmethod
    async def fetch_user_services(
        user_sub: str,
        search_type: SearchType,
        keyword: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[ServiceCardItem], int]:
        """获取用户创建的服务"""
        if search_type == SearchType.AUTHOR:
            if keyword is not None and keyword not in user_sub:
                return [], 0
            keyword = user_sub

        async with postgres.session() as session:
            # 使用通用查询构建方法
            query = await ServiceCenterManager._build_user_service_query(
                user_sub, search_type, keyword, page, page_size,
            )
            service_pools = list((await session.scalars(query)).all())

            # 获取总数
            total_count = len(service_pools)

        fav_service_ids = await ServiceCenterManager._get_favorite_service_ids_by_user(user_sub)
        services = [
            ServiceCardItem(
                serviceId=service_pool.id,
                icon="",
                name=service_pool.name,
                description=service_pool.description,
                author=service_pool.author,
                favorited=(service_pool.id in fav_service_ids),
            )
            for service_pool in service_pools
        ]
        return services, total_count


    @staticmethod
    async def _build_favorite_service_query(
        user_sub: str,
        search_type: SearchType,
        keyword: str | None,
        page: int,
        page_size: int,
    ) -> Select[tuple[Service, ...]]:
        """
        构建收藏服务查询语句

        :param user_sub: 用户唯一标识
        :param search_type: 搜索类型
        :param keyword: 搜索关键字
        :param page: 页码
        :param page_size: 页面大小
        :return: 查询语句
        """
        # 获取用户收藏的服务ID
        fav_service_ids = await ServiceCenterManager._get_favorite_service_ids_by_user(user_sub)

        # 构建基础查询
        query = select(Service).where(Service.id.in_(fav_service_ids))

        # 根据搜索类型和关键字添加WHERE条件
        if keyword:
            if search_type == SearchType.ALL:
                query = query.where(
                    and_(
                        Service.id.in_(fav_service_ids),
                        or_(
                            Service.name.like(f"%{keyword}%"),
                            Service.description.like(f"%{keyword}%"),
                            Service.author.like(f"%{keyword}%"),
                        ),
                    ),
                )
            elif search_type == SearchType.NAME:
                query = query.where(
                    and_(
                        Service.id.in_(fav_service_ids),
                        Service.name.like(f"%{keyword}%"),
                    ),
                )
            elif search_type == SearchType.DESCRIPTION:
                query = query.where(
                    and_(
                        Service.id.in_(fav_service_ids),
                        Service.description.like(f"%{keyword}%"),
                    ),
                )
            elif search_type == SearchType.AUTHOR:
                query = query.where(
                    and_(
                        Service.id.in_(fav_service_ids),
                        Service.author.like(f"%{keyword}%"),
                    ),
                )

        # 添加排序和分页
        return query.order_by(Service.updatedAt.desc()).offset((page - 1) * page_size).limit(page_size)


    @staticmethod
    async def fetch_favorite_services(
        user_sub: str,
        search_type: SearchType,
        keyword: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[ServiceCardItem], int]:
        """获取用户收藏的服务"""
        async with postgres.session() as session:
            # 使用通用查询构建方法
            query = await ServiceCenterManager._build_favorite_service_query(
                user_sub, search_type, keyword, page, page_size,
            )
            service_pools = list((await session.scalars(query)).all())

            # 获取总数
            total_count = len(service_pools)

            services = [
                ServiceCardItem(
                    serviceId=service_pool.id,
                    icon="",
                    name=service_pool.name,
                    description=service_pool.description,
                    author=service_pool.author,
                    favorited=True,
                )
                for service_pool in service_pools
            ]
            return services, total_count


    @staticmethod
    async def create_service(
        user_sub: str,
        data: dict[str, Any],
    ) -> uuid.UUID:
        """创建服务"""
        service_id = uuid.uuid4()
        # 校验 OpenAPI 规范的 JSON Schema
        validated_data = await ServiceCenterManager._validate_service_data(data)

        # 检查是否存在相同服务
        async with postgres.session() as session:
            db_service = (await session.scalars(
                select(Service).where(
                    and_(
                        Service.name == validated_data.id,
                        Service.description == validated_data.description,
                    ),
                ),
            )).one_or_none()

            if db_service:
                msg = "[ServiceCenterManager] 已存在相同名称和描述的服务"
                raise RuntimeError(msg)

        # 存入数据库
        service_metadata = ServiceMetadata(
            id=service_id,
            name=validated_data.id,
            description=validated_data.description,
            version=validated_data.version,
            author=user_sub,
            api=ServiceApiConfig(server=validated_data.servers),
            permission=Permission(type=PermissionType.PUBLIC),  # 默认公开
        )
        service_loader = ServiceLoader()
        await service_loader.save(service_id, service_metadata, data)
        # 返回服务ID
        return service_id


    @staticmethod
    async def update_service(
        user_sub: str,
        service_id: uuid.UUID,
        data: dict[str, Any],
    ) -> uuid.UUID:
        """更新服务"""
        # 验证用户权限
        async with postgres.session() as session:
            db_service = (await session.scalars(
                select(Service).where(
                    Service.id == service_id,
                ),
            )).one_or_none()
            if not db_service:
                msg = "[ServiceCenterManager] Service not found"
                raise RuntimeError(msg)
            if db_service.author != user_sub:
                msg = "[ServiceCenterManager] Permission denied"
                raise RuntimeError(msg)
            db_service.updatedAt = datetime.now(tz=UTC)
        # 校验 OpenAPI 规范的 JSON Schema
        validated_data = await ServiceCenterManager._validate_service_data(data)
        # 存入数据库
        service_metadata = ServiceMetadata(
            id=service_id,
            name=validated_data.id,
            description=validated_data.description,
            version=validated_data.version,
            author=user_sub,
            api=ServiceApiConfig(server=validated_data.servers),
        )
        service_loader = ServiceLoader()
        await service_loader.save(service_id, service_metadata, data)
        # 返回服务ID
        return service_id


    @staticmethod
    async def get_service_apis(
        service_id: uuid.UUID,
    ) -> tuple[str, list[ServiceApiData]]:
        """获取服务API列表"""
        # 获取服务名称
        async with postgres.session() as session:
            service_name = (await session.scalars(
                select(Service.name).where(
                    Service.id == service_id,
                ),
            )).one_or_none()
            if not service_name:
                msg = "[ServiceCenterManager] Service not found"
                raise RuntimeError(msg)

            # 根据 service_id 获取 API 列表
            node_data = (await session.scalars(
                select(NodeInfo).where(
                    NodeInfo.serviceId == service_id,
                ),
            )).all()
            api_list = [
                ServiceApiData(
                    name=node.name,
                    path=f"{node.knownParams['method'].upper()} {node.knownParams['url']}"
                    if node.knownParams and "method" in node.knownParams and "url" in node.knownParams
                    else "",
                    description=node.description,
                )
                for node in node_data
            ]
            return service_name, api_list


    @staticmethod
    async def get_service_data(
        user_sub: str,
        service_id: uuid.UUID,
    ) -> tuple[str, dict[str, Any]]:
        """获取服务数据"""
        # 验证用户权限
        async with postgres.session() as session:
            db_service = (await session.scalars(
                select(Service).where(
                    and_(
                        Service.id == service_id,
                        Service.author == user_sub,
                    ),
                ),
            )).one_or_none()

            if not db_service:
                msg = "[ServiceCenterManager] Service not found or permission denied"
                raise RuntimeError(msg)

        service_path = (
            Path(config.deploy.data_dir) / "semantics" / "service" / str(service_id) / "openapi" / "api.yaml"
        )
        async with await service_path.open() as f:
            service_data = yaml.safe_load(await f.read())
        return db_service.name, service_data


    @staticmethod
    async def get_service_metadata(
        user_sub: str,
        service_id: uuid.UUID,
    ) -> ServiceMetadata:
        """获取服务元数据"""
        async with postgres.session() as session:
            allowed_user = list((await session.scalars(
                select(ServiceACL.userSub).where(
                    ServiceACL.serviceId == service_id,
                ),
            )).all())
            if user_sub in allowed_user:
                db_service = (await session.scalars(
                    select(Service).where(
                        and_(
                            Service.id == service_id,
                            Service.permission == PermissionType.PRIVATE,
                        ),
                    ),
                )).one_or_none()
            else:
                db_service = (await session.scalars(
                    select(Service).where(
                        and_(
                            Service.id == service_id,
                            or_(
                                and_(
                                    Service.author == user_sub,
                                    Service.permission == PermissionType.PRIVATE,
                                ),
                                Service.permission == PermissionType.PUBLIC,
                                Service.author == user_sub,
                            ),
                        ),
                    ),
                )).one_or_none()
            if not db_service:
                msg = "[ServiceCenterManager] Service not found or permission denied"
                raise RuntimeError(msg)

        metadata_path = (
            Path(config.deploy.data_dir) / "semantics" / "service" / str(service_id) / "metadata.yaml"
        )
        async with await metadata_path.open() as f:
            metadata_data = yaml.safe_load(await f.read())
        return ServiceMetadata.model_validate(metadata_data)


    @staticmethod
    async def delete_service(user_sub: str, service_id: uuid.UUID) -> None:
        """删除服务"""
        async with postgres.session() as session:
            db_service = (await session.scalars(
                select(Service).where(
                    and_(
                        Service.id == service_id,
                        Service.author == user_sub,
                    ),
                ),
            )).one_or_none()
            if not db_service:
                msg = "[ServiceCenterManager] Service not found or permission denied"
                raise RuntimeError(msg)

            # 删除服务
            service_loader = ServiceLoader()
            await service_loader.delete(service_id)
            # 删除ACL
            await session.execute(
                delete(ServiceACL).where(
                    ServiceACL.serviceId == service_id,
                ),
            )
            # 删除收藏
            await session.execute(
                delete(UserFavorite).where(
                    UserFavorite.itemId == service_id,
                    UserFavorite.favouriteType == UserFavoriteType.SERVICE,
                ),
            )
            await session.commit()


    @staticmethod
    async def modify_favorite_service(
        user_sub: str,
        service_id: uuid.UUID,
        *,
        favorited: bool,
    ) -> None:
        """修改收藏状态"""
        async with postgres.session() as session:
            db_service = (await session.scalars(
                select(func.count(Service.id)).where(
                    Service.id == service_id,
                ),
            )).one()
            if not db_service:
                msg = f"[ServiceCenterManager] Service未找到: {service_id}"
                logger.warning(msg)
                raise RuntimeError(msg)

            user = (await session.scalars(
                select(func.count(User.userSub)).where(
                    User.userSub == user_sub,
                ),
            )).one()
            if not user:
                msg = f"[ServiceCenterManager] 用户未找到: {user_sub}"
                logger.warning(msg)
                raise RuntimeError(msg)

            # 检查是否已收藏
            user_favourite = (await session.scalars(
                select(UserFavorite).where(
                    and_(
                        UserFavorite.itemId == service_id,
                        UserFavorite.userSub == user_sub,
                        UserFavorite.favouriteType == UserFavoriteType.SERVICE,
                    ),
                ),
            )).one_or_none()
            if not user_favourite and favorited:
                # 创建收藏条目
                user_favourite = UserFavorite(
                    itemId=service_id,
                    userSub=user_sub,
                    favouriteType=UserFavoriteType.SERVICE,
                )
                session.add(user_favourite)
                await session.commit()
            elif user_favourite and not favorited:
                # 删除收藏条目
                await session.delete(user_favourite)
                await session.commit()


    @staticmethod
    async def _get_favorite_service_ids_by_user(user_sub: str) -> list[uuid.UUID]:
        """获取用户收藏的服务ID"""
        async with postgres.session() as session:
            user_favourite = (await session.scalars(
                select(UserFavorite).where(
                    UserFavorite.userSub == user_sub,
                    UserFavorite.favouriteType == UserFavoriteType.SERVICE,
                ),
            )).all()
            return [user_favourite.itemId for user_favourite in user_favourite]


    @staticmethod
    async def _validate_service_data(data: dict[str, Any]) -> ReducedOpenAPISpec:
        """验证服务数据"""
        # 验证数据是否为空
        if not data:
            msg = "[ServiceCenterManager] 服务数据为空"
            raise ValueError(msg)
        # 校验 OpenAPI 规范的 JSON Schema
        return await OpenAPILoader().load_dict(data)
