# Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
"""应用中心 Manager"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, select

from apps.common.postgres import postgres
from apps.constants import APP_DEFAULT_HISTORY_LEN, SERVICE_PAGE_SIZE
from apps.exceptions import InstancePermissionError
from apps.models.app import App
from apps.models.user import User, UserAppUsage, UserFavorite, UserFavoriteType
from apps.scheduler.pool.loader.app import AppLoader
from apps.schemas.agent import AgentAppMetadata
from apps.schemas.appcenter import AppCenterCardItem, AppData, AppPermissionData
from apps.schemas.enum_var import AppFilterType, AppType, PermissionType
from apps.schemas.flow import AppMetadata, MetadataType, Permission
from apps.schemas.response_data import RecentAppList, RecentAppListItem

from .mcp_service import MCPServiceManager
from .user import UserManager

logger = logging.getLogger(__name__)


class AppCenterManager:
    """应用中心管理器"""

    @staticmethod
    async def validate_user_app_access(user_sub: str, app_id: uuid.UUID) -> bool:
        """
        验证用户对应用的访问权限

        :param user_sub: 用户唯一标识符
        :param app_id: 应用id
        :return: 如果用户具有所需权限则返回True，否则返回False
        """
        mongo = MongoDB()
        app_collection = mongo.get_collection("app")
        query = {
            "_id": app_id,
            "$or": [
                {"author": user_sub},
                {"permission.type": PermissionType.PUBLIC.value},
                {
                    "$and": [
                        {"permission.type": PermissionType.PROTECTED.value},
                        {"permission.users": user_sub},
                    ],
                },
            ],
        }

        result = await app_collection.find_one(query)
        return result is not None


    @staticmethod
    async def validate_app_belong_to_user(user_sub: str, app_id: uuid.UUID) -> bool:
        """
        验证用户对应用的属权

        :param user_sub: 用户唯一标识符
        :param app_id: 应用id
        :return: 如果应用属于用户则返回True，否则返回False
        """
        async with postgres.session() as session:
            app_obj = (await session.scalars(
                select(App).where(
                    and_(
                        App.id == app_id,
                        App.author == user_sub,
                    ),
                ),
            )).one_or_none()
            if not app_obj:
                msg = f"[AppCenterManager] 应用不存在或权限不足: {app_id}"
                raise ValueError(msg)
            return True


    @staticmethod
    async def fetch_apps(
        user_sub: str,
        keyword: str | None,
        app_type: AppType | None,
        page: int,
        filter_type: AppFilterType,
    ) -> tuple[list[AppCenterCardItem], int]:
        """
        获取应用列表

        :param user_sub: 用户唯一标识
        :param keyword: 搜索关键字
        :param app_type: 应用类型
        :param page: 页码
        :param filter_type: 过滤类型
        :return: 应用列表, 总应用数
        """
        filters: dict[str, Any] = {
            "$or": [
                {"permission.type": PermissionType.PUBLIC.value},
                {"$and": [
                    {"permission.type": PermissionType.PROTECTED.value},
                    {"permission.users": {"$in": [user_sub]}},
                ]},
                {"$and": [
                    {"permission.type": PermissionType.PRIVATE.value},
                    {"author": user_sub},
                ]},
            ],
        }

        user_favorite_app_ids = await AppCenterManager._get_favorite_app_ids_by_user(user_sub)

        if filter_type == AppFilterType.ALL:
            # 获取所有已发布的应用
            filters["published"] = True
        elif filter_type == AppFilterType.USER:
            # 获取用户创建的应用
            filters["author"] = user_sub
        elif filter_type == AppFilterType.FAVORITE:
            # 获取用户收藏的应用
            filters = {
                "_id": {"$in": user_favorite_app_ids},
                "published": True,
            }

        # 添加关键字搜索条件
        if keyword:
            filters["$or"] = [
                {"name": {"$regex": keyword, "$options": "i"}},
                {"description": {"$regex": keyword, "$options": "i"}},
                {"author": {"$regex": keyword, "$options": "i"}},
            ]

        # 添加应用类型过滤条件
        if app_type is not None:
            filters["app_type"] = app_type.value

        # 获取应用列表
        apps, total_apps = await AppCenterManager._search_apps_by_filter(filters, page, SERVICE_PAGE_SIZE)

        # 构建返回的应用卡片列表
        app_cards = [
            AppCenterCardItem(
                appId=app.id,
                appType=app.app_type,
                icon=app.icon,
                name=app.name,
                description=app.description,
                author=app.author,
                favorited=(app.id in user_favorite_app_ids),
                published=app.published,
            )
            for app in apps
        ]

        return app_cards, total_apps


    @staticmethod
    async def fetch_app_data_by_id(app_id: uuid.UUID) -> App:
        """
        根据应用ID获取应用元数据（使用PostgreSQL）

        :param app_id: 应用唯一标识
        :return: 应用数据
        """
        async with postgres.session() as session:
            app_obj = (await session.scalars(
                select(App).where(App.id == app_id),
            )).one_or_none()
            if not app_obj:
                msg = f"[AppCenterManager] 应用不存在: {app_id}"
                raise ValueError(msg)
            return app_obj


    @staticmethod
    async def create_app(user_sub: str, data: AppData) -> uuid.UUID:
        """
        创建应用

        :param user_sub: 用户唯一标识
        :param data: 应用数据
        :return: 应用唯一标识
        """
        app_id = uuid.uuid4()
        await AppCenterManager._process_app_and_save(
            app_type=data.app_type,
            app_id=app_id,
            user_sub=user_sub,
            data=data,
        )
        return app_id


    @staticmethod
    async def update_app(user_sub: str, app_id: uuid.UUID, data: AppData) -> None:
        """
        更新应用

        :param user_sub: 用户唯一标识
        :param app_id: 应用唯一标识
        :param data: 应用数据
        """
        # 获取应用数据并验证权限
        app_data = await AppCenterManager._get_app_data(app_id, user_sub)

        # 不允许更改应用类型
        if app_data.appType != data.app_type:
            err = f"【AppCenterManager】不允许更改应用类型: {app_data.app_type} -> {data.app_type}"
            raise ValueError(err)

        await AppCenterManager._process_app_and_save(
            app_type=data.app_type,
            app_id=app_id,
            user_sub=user_sub,
            data=data,
            app_data=app_data,
        )


    @staticmethod
    async def update_app_publish_status(app_id: uuid.UUID, user_sub: str) -> bool:
        """
        发布应用

        :param app_id: 应用唯一标识
        :param user_sub: 用户唯一标识
        :return: 发布状态
        """
        # 获取应用数据并验证权限
        app_data = await AppCenterManager._get_app_data(app_id, user_sub)

        # 计算发布状态
        published = True
        for flow in app_data.flows:
            if not flow.debug:
                published = False
                break

        # 更新数据库
        async with postgres.session() as session:
            app_obj = (await session.scalars(
                select(App).where(App.id == app_id),
            )).one_or_none()
            if not app_obj:
                msg = f"[AppCenterManager] 应用不存在: {app_id}"
                raise ValueError(msg)
            app_obj.isPublished = published
            await session.merge(app_obj)
            await session.commit()

        await AppCenterManager._process_app_and_save(
            app_type=app_data.app_type,
            app_id=app_id,
            user_sub=user_sub,
            app_data=app_data,
            published=published,
        )

        return published


    @staticmethod
    async def modify_favorite_app(app_id: uuid.UUID, user_sub: str, *, favorited: bool) -> None:
        """
        修改收藏状态

        :param app_id: 应用唯一标识
        :param user_sub: 用户唯一标识
        :param favorited: 是否收藏
        """
        async with postgres.session() as session:
            app_obj = (await session.scalars(
                select(App).where(App.id == app_id),
            )).one_or_none()
            if not app_obj:
                msg = f"[AppCenterManager] 应用不存在: {app_id}"
                raise ValueError(msg)

            app_favorite = (await session.scalars(
                select(UserFavorite).where(
                    and_(
                        UserFavorite.userSub == user_sub,
                        UserFavorite.itemId == app_id,
                        UserFavorite.type == UserFavoriteType.APP,
                    ),
                ),
            )).one_or_none()
            if not app_favorite and favorited:
                # 添加收藏
                app_favorite = UserFavorite(
                    userSub=user_sub,
                    type=UserFavoriteType.APP,
                    itemId=app_id,
                )
                session.add(app_favorite)
            elif app_favorite and not favorited:
                # 删除收藏
                await session.delete(app_favorite)
            else:
                # 重复操作
                msg = f"[AppCenterManager] 重复操作: {app_id}"
                raise ValueError(msg)


    @staticmethod
    async def delete_app(app_id: uuid.UUID, user_sub: str) -> None:
        """
        删除应用

        :param app_id: 应用唯一标识
        :param user_sub: 用户唯一标识
        """
        async with postgres.session() as session:
            app_obj = (await session.scalars(
                select(App).where(App.id == app_id),
            )).one_or_none()
            if not app_obj:
                msg = f"[AppCenterManager] 应用不存在: {app_id}"
                raise ValueError(msg)
            if app_obj.author != user_sub:
                msg = f"[AppCenterManager] 权限不足: {user_sub} -> {app_obj.author}"
                raise InstancePermissionError(msg)
            await session.delete(app_obj)
            await session.commit()


    @staticmethod
    async def get_recently_used_apps(count: int, user_sub: str) -> RecentAppList:
        """
        获取用户最近使用的应用列表

        :param count: 应用数量
        :param user_sub: 用户唯一标识
        :return: 最近使用的应用列表
        """
        # 获取用户使用情况
        async with postgres.session() as session:
            recent_apps = list((await session.scalars(
                select(UserAppUsage.appId).where(
                    UserAppUsage.userSub == user_sub,
                ).order_by(
                    UserAppUsage.lastUsed.desc(),
                ).limit(count),
            )).all())
            # 批量查询AppName
            result = []
            for app_id in recent_apps:
                name = (await session.scalars(select(App.name).where(App.id == app_id))).one_or_none()
                if name:
                    result.append(RecentAppListItem(appId=app_id, name=name))

            return RecentAppList(applications=result)


    @staticmethod
    async def update_recent_app(user_sub: str, app_id: uuid.UUID) -> None:
        """
        更新用户的最近使用应用列表

        :param user_sub: 用户唯一标识
        :param app_id: 应用唯一标识
        :return: 更新是否成功
        """
        if str(app_id) == "00000000-0000-0000-0000-000000000000":
            return

        async with postgres.session() as session:
            app_usages = list((await session.scalars(
                select(UserAppUsage).where(UserAppUsage.userSub == user_sub),
            )).all())
            if not app_usages:
                msg = f"[AppCenterManager] 用户不存在: {user_sub}"
                raise ValueError(msg)

            for app_data in app_usages:
                if app_data.appId == app_id:
                    app_data.lastUsed = datetime.now(UTC)
                    app_data.usageCount += 1
                    await session.merge(app_data)
                    break
            else:
                app_data = UserAppUsage(userSub=user_sub, appId=app_id, lastUsed=datetime.now(UTC), usageCount=1)
                await session.merge(app_data)
            await session.commit()
            return


    @staticmethod
    async def _search_apps_by_filter(
        search_conditions: dict[str, Any],
        page: int,
        page_size: int,
    ) -> tuple[list[App], int]:
        """根据过滤条件搜索应用并计算总页数"""
        mongo = MongoDB()
        app_collection = mongo.get_collection("app")
        total_apps = await app_collection.count_documents(search_conditions)
        db_data = (
            await app_collection.find(search_conditions)
            .sort("created_at", -1)
            .skip((page - 1) * page_size)
            .limit(page_size)
            .to_list(length=page_size)
        )
        apps = [App.model_validate(doc) for doc in db_data]
        return apps, total_apps


    @staticmethod
    async def _get_app_data(app_id: uuid.UUID, user_sub: str, *, check_author: bool = True) -> AppData:
        """
        从数据库获取应用数据并验证权限

        :param app_id: 应用唯一标识
        :param user_sub: 用户唯一标识
        :param check_author: 是否检查作者
        :return: 应用数据
        """
        async with postgres.session() as session:
            app_data = (await session.scalars(
                select(App).where(App.id == app_id),
            )).one_or_none()
            if not app_data:
                msg = f"【AppCenterManager】应用不存在: {app_id}"
                raise ValueError(msg)
            if check_author and app_data.author != user_sub:
                msg = f"【AppCenterManager】权限不足: {user_sub} -> {app_data.author}"
                raise InstancePermissionError(msg)
            return app_data


    @staticmethod
    def _create_flow_metadata(
        common_params: dict,
        data: AppData | None = None,
        app_data: App | None = None,
        *,
        published: bool | None = None,
    ) -> AppMetadata:
        """创建工作流应用的元数据"""
        metadata = AppMetadata(**common_params)

        # 设置工作流应用特有属性
        if data:
            metadata.links = data.links
            metadata.first_questions = data.first_questions
        elif app_data:
            metadata.links = app_data.links
            metadata.first_questions = app_data.first_questions

        # 处理 'flows' 字段
        if app_data:
            # 更新场景 (update_app, update_app_publish_status):
            # 总是使用 app_data 中已存在的 flows。
            metadata.flows = app_data.flows
        else:
            # 创建场景 (create_app, app_data is None):
            # flows 默认为空列表。
            metadata.flows = []

        # 处理 'published' 字段
        if app_data:
            if published is None:  # 对应 update_app
                metadata.published = getattr(app_data, "published", False)
            else:  # 对应 update_app_publish_status
                metadata.published = published
        elif published is not None:  # 对应 _process_app_and_save 被直接调用且提供了 published，但无 app_data
            metadata.published = published
        else:  # 对应 create_app (app_data is None, published 参数为 None)
            metadata.published = False

        return metadata


    @staticmethod
    def _create_agent_metadata(
        common_params: dict,
        user_sub: str,
        data: AppData | None = None,
        app_data: App | None = None,
        *,
        published: bool | None = None,
    ) -> AgentAppMetadata:
        """创建 Agent 应用的元数据"""
        metadata = AgentAppMetadata(**common_params)

        # mcp_service 逻辑
        if data is not None and hasattr(data, "mcp_service") and data.mcp_service:
            # 创建应用场景，验证传入的 mcp_service 状态，确保只使用已经激活的 (create_app)
            metadata.mcp_service = [svc for svc in data.mcp_service if MCPServiceManager.is_active(user_sub, svc)]
        elif data is not None and hasattr(data, "mcp_service"):
            # 更新应用场景，使用 data 中的 mcp_service (update_app)
            metadata.mcp_service = data.mcp_service if data.mcp_service is not None else []
        elif app_data is not None and hasattr(app_data, "mcp_service"):
            # 更新应用发布状态场景，使用 app_data 中的 mcp_service (update_app_publish_status)
            metadata.mcp_service = app_data.mcp_service if app_data.mcp_service is not None else []
        else:
            # 在预期的条件下，如果在 data 或 app_data 中找不到 mcp_service，则默认回退为空列表。
            metadata.mcp_service = []

        # Agent 应用的发布状态逻辑
        if published is not None:  # 从 update_app_publish_status 调用，'published' 参数已提供
            metadata.published = published
        else:  # 从 create_app 或 update_app 调用 (此时传递给 _create_metadata 的 'published' 参数为 None)
            # 'published' 状态重置为 False。
            metadata.published = False

        return metadata

    @staticmethod
    async def _create_metadata(
        app_type: AppType,
        app_id: uuid.UUID,
        user_sub: str,
        **kwargs: Any,
    ) -> AppMetadata | AgentAppMetadata:
        """
        创建应用元数据

        :param app_type: 应用类型
        :param app_id: 应用唯一标识
        :param user_sub: 用户唯一标识
        :param kwargs: 可选参数，包含:
            - data: 应用数据，用于新建或更新时提供
            - app_data: 现有应用数据，用于更新时提供
            - published: 发布状态，用于更新时提供
        :return: 应用元数据
        :raises ValueError: 无效应用类型或缺少必要数据
        """
        data: AppData | None = kwargs.get("data")
        app_data: App | None = kwargs.get("app_data")
        published: bool | None = kwargs.get("published")

        # 验证必要数据
        source = data if data else app_data
        if not source:
            msg = "必须提供 data 或 app_data 参数"
            raise ValueError(msg)
        # 构建通用参数
        common_params = {
            "type": MetadataType.APP,
            "id": app_id,
            "version": "1.0.0",
            "author": user_sub,
            "icon": source.icon,
            "name": source.name,
            "description": source.description,
            "history_len": data.history_len if data else APP_DEFAULT_HISTORY_LEN,
        }
        # 设置权限
        if data:
            common_params["permission"] = Permission(
                type=data.permission.type,
                users=data.permission.users or [],
            )
        elif app_data:
            common_params["permission"] = app_data.permission

        # 根据应用类型创建不同的元数据
        if app_type == AppType.FLOW:
            return AppCenterManager._create_flow_metadata(common_params, data, app_data, published)

        if app_type == AppType.AGENT:
            return AppCenterManager._create_agent_metadata(common_params, user_sub, data, app_data, published)

        msg = "无效的应用类型"
        raise ValueError(msg)


    @staticmethod
    async def _process_app_and_save(
        app_type: AppType,
        app_id: uuid.UUID,
        user_sub: str,
        **kwargs: Any,
    ) -> Any:
        """
        处理应用元数据创建和保存

        :param app_type: 应用类型
        :param app_id: 应用唯一标识
        :param user_sub: 用户唯一标识
        :param kwargs: 其他可选参数(data, app_data, published)
        :return: 应用元数据
        """
        # 创建应用元数据
        metadata = await AppCenterManager._create_metadata(
            app_type=app_type,
            app_id=app_id,
            user_sub=user_sub,
            **kwargs,
        )

        # 保存应用
        app_loader = AppLoader()
        await app_loader.save(metadata, app_id)
        return metadata


    @staticmethod
    async def _get_favorite_app_ids_by_user(user_sub: str) -> list[uuid.UUID]:
        """获取用户收藏的应用ID"""
        async with postgres.session() as session:
            favorite_apps = list((await session.scalars(
                select(UserFavorite.itemId).where(
                    and_(
                        UserFavorite.userSub == user_sub,
                        UserFavorite.type == UserFavoriteType.APP,
                    ),
                ),
            )).all())
            if not favorite_apps:
                msg = f"[AppCenterManager] 用户错误或收藏为空: {user_sub}"
                raise ValueError(msg)

            return favorite_apps
