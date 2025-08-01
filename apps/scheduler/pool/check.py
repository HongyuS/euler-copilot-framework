# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""文件检查器"""

import logging
import uuid
from hashlib import sha256

from anyio import Path
from sqlalchemy import select

from apps.common.config import config
from apps.common.postgres import postgres
from apps.models.app import App, AppHashes
from apps.models.service import Service, ServiceHashes
from apps.schemas.enum_var import MetadataType

logger = logging.getLogger(__name__)


class FileChecker:
    """文件检查器"""

    def __init__(self) -> None:
        """初始化文件检查器"""
        self.hashes = {}
        self._dir_path = Path(config.deploy.data_dir) / "semantics"

    async def check_one(self, path: Path) -> dict[str, str]:
        """检查单个App/Service文件是否有变动"""
        hashes = {}
        if not await path.exists():
            err = FileNotFoundError(f"File {path} not found")
            raise err
        if not await path.is_dir():
            err = NotADirectoryError(f"Path {path} is not a directory")
            raise err

        async for file in path.iterdir():
            if await file.is_file():
                relative_path = file.relative_to(self._resource_path)
                hashes[relative_path.as_posix()] = sha256(await file.read_bytes()).hexdigest()
            elif await file.is_dir():
                hashes.update(await self.check_one(file))

        return hashes


    async def diff_one(self, path: Path, previous_hashes: AppHashes | ServiceHashes | None = None) -> bool:
        """检查文件是否发生变化"""
        self._resource_path = path
        semantics_path = Path(config.deploy.data_dir) / "semantics"
        path_diff = self._resource_path.relative_to(semantics_path)
        # FIXME 不能使用字典比对，必须一条条比对
        self.hashes[path_diff.as_posix()] = await self.check_one(path)
        return self.hashes[path_diff.as_posix()] != previous_hashes


    async def diff(self, check_type: MetadataType) -> tuple[list[uuid.UUID], list[uuid.UUID]]:
        """生成更新列表和删除列表"""
        async with postgres.session() as session:
            # 判断类型
            if check_type == MetadataType.APP:
                self._dir_path = Path(config.deploy.data_dir) / "semantics" / "app"
                items = list((await session.scalars(select(App.id))).all())
            elif check_type == MetadataType.SERVICE:
                self._dir_path = Path(config.deploy.data_dir) / "semantics" / "service"
                items = list((await session.scalars(select(Service.id))).all())

            changed_list = []
            deleted_list = []

            # 遍历列表
            for list_item in items:
                # 判断是否存在？
                if not await Path(self._dir_path / str(list_item)).exists():
                    deleted_list.append(list_item)
                    continue

                # 获取Hash
                if check_type == MetadataType.APP:
                    hashes = (
                        await session.scalars(select(AppHashes).where(AppHashes.appId == list_item))
                    ).one()
                elif check_type == MetadataType.SERVICE:
                    hashes = (
                        await session.scalars(select(ServiceHashes).where(ServiceHashes.serviceId == list_item))
                    ).one()
                # 判断是否发生变化
                if await self.diff_one(Path(self._dir_path / str(list_item)), hashes):
                    changed_list.append(list_item)

            logger.info("[FileChecker] 文件变动: %s；文件删除: %s", changed_list, deleted_list)
            # 遍历目录
            item_names = list(items)
            async for service_folder in self._dir_path.iterdir():
                # 判断是否新增？
                if (
                    service_folder.name not in item_names
                    and service_folder.name not in deleted_list
                    and service_folder.name not in changed_list
                ):
                    changed_list += [service_folder.name]
                    # 触发一次hash计算
                    await self.diff_one(service_folder)

            return changed_list, deleted_list
