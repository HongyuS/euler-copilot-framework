# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""App加载器"""

import logging
import shutil
import uuid

from anyio import Path
from sqlalchemy import delete

from apps.common.config import config
from apps.common.postgres import postgres
from apps.models.app import App, AppACL, AppHashes
from apps.models.flow import Flow
from apps.models.user import UserAppUsage, UserFavorite
from apps.scheduler.pool.check import FileChecker
from apps.schemas.agent import AgentAppMetadata
from apps.schemas.enum_var import AppType
from apps.schemas.flow import AppFlow, AppMetadata, MetadataType, PermissionType

from .flow import FlowLoader
from .metadata import MetadataLoader

logger = logging.getLogger(__name__)
BASE_PATH = Path(config.deploy.data_dir) / "semantics" / "app"


class AppLoader:
    """应用加载器"""

    @staticmethod
    async def load(app_id: uuid.UUID, hashes: dict[str, str]) -> None:
        """
        从文件系统中加载应用

        :param app_id: 应用 ID
        """
        app_path = BASE_PATH / str(app_id)
        metadata = await AppLoader.read_metadata(app_id)
        metadata.hashes = hashes
        if metadata.app_type == AppType.FLOW and isinstance(metadata, AppMetadata):
            # 加载工作流
            flow_path = app_path / "flow"

            flow_ids = [app_flow.id for app_flow in metadata.flows]
            new_flows: list[AppFlow] = []
            async for flow_file in flow_path.rglob("*.yaml"):
                if flow_file.stem not in flow_ids:
                    logger.warning("[AppLoader] 工作流 %s 不在元数据中", flow_file)
                flow = await FlowLoader.load(app_id, flow_file.stem)
                if not flow:
                    err = f"[AppLoader] 工作流 {flow_file} 加载失败"
                    raise ValueError(err)
                if not flow.debug:
                    metadata.published = False
                new_flows.append(
                    AppFlow(
                        id=uuid.UUID(flow_file.stem),
                        name=flow.name,
                        description=flow.description,
                        path=flow_file.as_posix(),
                        debug=flow.debug,
                    ),
                )
            metadata.flows = new_flows
            try:
                metadata = AppMetadata.model_validate(metadata)
            except Exception as e:
                err = "[AppLoader] Flow应用元数据验证失败"
                logger.exception(err)
                raise RuntimeError(err) from e
        elif metadata.app_type == AppType.AGENT and isinstance(metadata, AgentAppMetadata):
            # 加载模型
            try:
                metadata = AgentAppMetadata.model_validate(metadata)
                logger.info("[AppLoader] Agent应用元数据验证成功: %s", metadata)
            except Exception as e:
                err = "[AppLoader] Agent应用元数据验证失败"
                logger.exception(err)
                raise RuntimeError(err) from e
        await AppLoader._update_db(metadata)


    @staticmethod
    async def read_metadata(app_id: uuid.UUID) -> AppMetadata | AgentAppMetadata:
        """读取应用元数据"""
        metadata_path = BASE_PATH / str(app_id) / "metadata.yaml"
        metadata = await MetadataLoader().load_one(metadata_path)
        if not metadata:
            err = f"[AppLoader] 元数据不存在: {metadata_path}"
            raise ValueError(err)
        if not isinstance(metadata, (AppMetadata, AgentAppMetadata)):
            err = f"[AppLoader] 元数据类型错误: {metadata_path}"
            raise TypeError(err)
        return metadata


    @staticmethod
    async def save(metadata: AppMetadata | AgentAppMetadata, app_id: uuid.UUID) -> None:
        """
        保存应用

        :param metadata: 应用元数据
        :param app_id: 应用 ID
        """
        # 创建文件夹
        app_path = BASE_PATH / str(app_id)
        if not await app_path.exists():
            await app_path.mkdir(parents=True, exist_ok=True)
        # 保存元数据
        await MetadataLoader().save_one(MetadataType.APP, metadata, app_id)
        # 重新载入
        file_checker = FileChecker()
        await file_checker.diff_one(app_path)
        await AppLoader.load(app_id, file_checker.hashes[f"app/{app_id}"])


    @staticmethod
    async def delete(app_id: uuid.UUID, *, is_reload: bool = False) -> None:
        """
        删除App，并更新数据库

        :param app_id: 应用 ID
        """
        async with postgres.session() as session:
            await session.execute(delete(App).where(App.id == app_id))
            await session.execute(delete(AppACL).where(AppACL.appId == app_id))
            await session.execute(delete(AppHashes).where(AppHashes.appId == app_id))
            await session.execute(delete(Flow).where(Flow.appId == app_id))
            await session.execute(delete(UserAppUsage).where(UserAppUsage.appId == app_id))
            await session.execute(delete(UserFavorite).where(UserFavorite.itemId == app_id))
            await session.commit()

        if not is_reload:
            app_path = BASE_PATH / str(app_id)
            if await app_path.exists():
                shutil.rmtree(str(app_path), ignore_errors=True)


    @staticmethod
    async def _update_db(metadata: AppMetadata | AgentAppMetadata) -> None:
        """更新数据库"""
        if not metadata.hashes:
            err = f"[AppLoader] 应用 {metadata.id} 的哈希值为空"
            logger.error(err)
            raise ValueError(err)
        # 更新应用数据
        async with postgres.session() as session:
            # 保存App表
            app_info = App(
                id=metadata.id,
                name=metadata.name,
                description=metadata.description,
                author=metadata.author,
                appType=metadata.app_type,
                isPublished=metadata.published,
                permission=metadata.permission.type if metadata.permission else PermissionType.PRIVATE,
            )
            await session.merge(app_info)
            # 增加Permission
            if (
                metadata.permission
                and metadata.permission.type == PermissionType.PROTECTED
                and metadata.permission.users
            ):
                for user_sub in metadata.permission.users:
                    await session.merge(AppACL(
                        appId=metadata.id,
                        userSub=user_sub,
                        action="",
                    ))
            # 保存AppHashes表
            await session.commit()

            # FIXME 更新Hash值？
