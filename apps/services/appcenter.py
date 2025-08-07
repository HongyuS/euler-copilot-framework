# Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
"""应用中心 Manager"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, func, or_, select

from apps.common.postgres import postgres
from apps.constants import APP_DEFAULT_HISTORY_LEN, SERVICE_PAGE_SIZE
from apps.exceptions import InstancePermissionError
from apps.models.app import App, AppACL
from apps.models.user import UserAppUsage, UserFavorite, UserFavoriteType
from apps.scheduler.pool.loader.app import AppLoader
from apps.schemas.agent import AgentAppMetadata
from apps.schemas.appcenter import AppCenterCardItem, AppData, AppPermissionData
from apps.schemas.enum_var import AppFilterType, AppType, PermissionType
from apps.schemas.flow import AppMetadata, MetadataType, Permission
from apps.schemas.response_data import RecentAppList, RecentAppListItem

from .mcp_service import MCPServiceManager

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
        async with postgres.session() as session:
            protected_apps = select(AppACL.appId).where(
                AppACL.userSub == user_sub,
            )
            app_data = select(App).where(
                or_(
                    App.permission == PermissionType.PUBLIC,
                    and_(
                        App.permission == PermissionType.PRIVATE,
                        App.author == user_sub,
                    ),
                    and_(
                        App.permission == PermissionType.PROTECTED,
                        App.id.in_(protected_apps),
                    ),
                ),
            ).cte()

            # 获取用户所有收藏的应用
            user_favourite_apps = select(UserFavorite.itemId).where(
                and_(
                    UserFavorite.userSub == user_sub,
                    UserFavorite.favouriteType == UserFavoriteType.APP,
                ),
            )

            # 根据搜索类型加入搜索条件
            if filter_type == AppFilterType.ALL:
                filtered_apps = select(app_data).where(App.isPublished == True).cte()  # noqa: E712
            elif filter_type == AppFilterType.USER:
                filtered_apps = select(app_data).where(App.author == user_sub).cte()
            elif filter_type == AppFilterType.FAVORITE:
                filtered_apps = select(app_data).where(
                    and_(
                        App.id.in_(user_favourite_apps),
                        App.isPublished == True,  # noqa: E712
                    ),
                ).cte()

            # 根据应用类型加入搜索条件
            if app_type is not None:
                type_apps = select(filtered_apps).where(App.appType == AppType(app_type)).cte()
            else:
                type_apps = filtered_apps

            # 加入关键字搜索条件
            if keyword:
                keyword_apps = select(type_apps).where(
                    or_(
                        App.name.ilike(f"%{keyword}%"),
                        App.description.ilike(f"%{keyword}%"),
                        App.author.ilike(f"%{keyword}%"),
                    ),
                ).cte()
            else:
                keyword_apps = type_apps

            # 进行搜索
            total_apps = (await session.scalars(
                select(func.count()).select_from(keyword_apps),
            )).one()
            result: list[App] = list((await session.scalars(
                select(keyword_apps).order_by(App.updatedAt.desc())
                .offset((page - 1) * SERVICE_PAGE_SIZE).limit(SERVICE_PAGE_SIZE),
            )).all())

            # 构建返回的应用卡片列表
            app_cards = [
                AppCenterCardItem(
                    appId=app.id,
                    appType=app.appType,
                    icon=app.icon,
                    name=app.name,
                    description=app.description,
                    author=app.author,
                    favorited=(app.id in user_favourite_apps),
                    published=app.isPublished,
                )
                for app in result
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
            err = f"【AppCenterManager】不允许更改应用类型: {app_data.appType} -> {data.app_type}"
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
            app_type=app_data.appType,
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
                        UserFavorite.favouriteType == UserFavoriteType.APP,
                    ),
                ),
            )).one_or_none()
            if not app_favorite and favorited:
                # 添加收藏
                app_favorite = UserFavorite(
                    userSub=user_sub,
                    favouriteType=UserFavoriteType.APP,
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
    async def _get_app_data(app_id: uuid.UUID, user_sub: str, *, check_author: bool = True) -> App:
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
            metadata.first_questions = app_data.firstQuestions

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
            metadata.mcp_service = [svc.id for svc in data.mcp_service if MCPServiceManager.is_active(user_sub, svc.id)]
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
    async def _create_metadata(  # noqa: PLR0913
        app_type: AppType,
        app_id: uuid.UUID,
        user_sub: str,
        data: AppData | None = None,
        app_data: App | None = None,
        *,
        published: bool | None = None,
    ) -> AppMetadata | AgentAppMetadata:
        """
        创建应用元数据

        :param app_type: 应用类型
        :param app_id: 应用唯一标识
        :param user_sub: 用户唯一标识
        :param data: 应用数据，用于新建或更新时提供
        :param app_data: 现有应用数据，用于更新时提供
        :param published: 发布状态，用于更新时提供
        :return: 应用元数据
        :raises ValueError: 无效应用类型或缺少必要数据
        """
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
            "permission": Permission(
                type=data.permission.type,
                users=data.permission.users or [],
            ) if data else (app_data.permission if app_data else None),
        }

        # 根据应用类型创建不同的元数据
        if app_type == AppType.AGENT:
            return AppCenterManager._create_agent_metadata(common_params, user_sub, data, app_data, published=published)

        return AppCenterManager._create_flow_metadata(common_params, data, app_data, published=published)


    @staticmethod
    async def _process_app_and_save(  # noqa: PLR0913
        app_type: AppType,
        app_id: uuid.UUID,
        user_sub: str,
        data: AppData | None = None,
        app_data: App | None = None,
        *,
        published: bool | None = None,
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
            data=data,
            app_data=app_data,
            published=published,
        )

        # 保存应用
        await AppLoader.save(metadata, app_id)
        return metadata
