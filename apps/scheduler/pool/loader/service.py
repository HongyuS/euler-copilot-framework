# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""加载配置文件夹的Service部分"""

import logging
import shutil
import uuid

from anyio import Path
from sqlalchemy import delete

from apps.common.config import config
from apps.common.postgres import postgres
from apps.llm.embedding import Embedding
from apps.models.node import NodeInfo
from apps.models.service import Service, ServiceACL, ServiceHashes
from apps.models.vectors import NodePoolVector, ServicePoolVector
from apps.scheduler.pool.check import FileChecker
from apps.schemas.flow import PermissionType, ServiceMetadata

from .metadata import MetadataLoader, MetadataType
from .openapi import OpenAPILoader

logger = logging.getLogger(__name__)
BASE_PATH = Path(config.deploy.data_dir) / "semantics" / "service"


class ServiceLoader:
    """Service 加载器"""

    @staticmethod
    async def load(service_id: uuid.UUID, hashes: dict[str, str]) -> None:
        """加载单个Service"""
        service_path = BASE_PATH / str(service_id)
        # 载入元数据
        metadata = await MetadataLoader().load_one(service_path / "metadata.yaml")
        if not isinstance(metadata, ServiceMetadata):
            err = f"[ServiceLoader] 元数据类型错误: {service_path}/metadata.yaml"
            logger.error(err)
            raise TypeError(err)
        metadata.hashes = hashes

        # 载入OpenAPI文档，获取Node列表
        try:
            nodes: list[NodeInfo] = []
            async for yaml_path in (service_path / "openapi").rglob("*.yaml"):
                nodes.extend(await OpenAPILoader().load_one(service_id, yaml_path, metadata.api.server))
        except Exception:
            logger.exception("[ServiceLoader] 服务 %s 文件损坏", service_id)
            return
        # 更新数据库
        await ServiceLoader._update_db(nodes, metadata)


    @staticmethod
    async def save(service_id: uuid.UUID, metadata: ServiceMetadata, data: dict) -> None:
        """在文件系统上保存Service，并更新数据库"""
        service_path = BASE_PATH / str(service_id)
        # 创建文件夹
        if not await service_path.exists():
            await service_path.mkdir(parents=True, exist_ok=True)
        if not await (service_path / "openapi").exists():
            await (service_path / "openapi").mkdir(parents=True, exist_ok=True)
        openapi_path = service_path / "openapi" / "api.yaml"
        # 保存元数据
        await MetadataLoader().save_one(MetadataType.SERVICE, metadata, service_id)
        # 保存 OpenAPI 文档
        await OpenAPILoader().save_one(openapi_path, data)
        # 重新载入
        file_checker = FileChecker()
        await file_checker.diff_one(service_path)
        await ServiceLoader.load(service_id, file_checker.hashes[f"service/{service_id}"])


    @staticmethod
    async def delete(service_id: uuid.UUID, *, is_reload: bool = False) -> None:
        """删除Service，并更新数据库"""
        async with postgres.session() as session:
            await session.execute(delete(Service).where(Service.id == service_id))
            await session.execute(delete(NodeInfo).where(NodeInfo.serviceId == service_id))
            await session.execute(delete(ServiceACL).where(ServiceACL.serviceId == service_id))
            await session.execute(delete(ServiceHashes).where(ServiceHashes.serviceId == service_id))
            await session.execute(delete(ServicePoolVector).where(ServicePoolVector.id == service_id))
            await session.execute(delete(NodePoolVector).where(NodePoolVector.serviceId == service_id))
            await session.commit()

        if not is_reload:
            path = BASE_PATH / str(service_id)
            if await path.exists():
                shutil.rmtree(path)


    @staticmethod
    async def _update_db(nodes: list[NodeInfo], metadata: ServiceMetadata) -> None:
        """更新数据库"""
        if not metadata.hashes:
            err = f"[ServiceLoader] 服务 {metadata.id} 的哈希值为空"
            logger.error(err)
            raise ValueError(err)

        # 更新数据库
        async with postgres.session() as session:
            # 删除旧的数据
            await session.execute(delete(Service).where(Service.id == metadata.id))
            await session.execute(delete(NodeInfo).where(NodeInfo.serviceId == metadata.id))

            # 插入新的数据
            service_data = Service(
                id=metadata.id,
                name=metadata.name,
                description=metadata.description,
                author=metadata.author,
                permission=PermissionType.PRIVATE,
            )
            session.add(service_data)

            for node in nodes:
                session.add(node)
            await session.commit()

        # 删除旧的向量数据
        async with postgres.session() as session:
            await session.execute(delete(ServicePoolVector).where(ServicePoolVector.id == metadata.id))
            await session.execute(delete(NodePoolVector).where(NodePoolVector.serviceId == metadata.id))
            await session.commit()

        # 进行向量化，更新postgres
        service_vecs = await Embedding.get_embedding([metadata.description])
        async with postgres.session() as session:
            pool_data = ServicePoolVector(
                id=metadata.id,
                embedding=service_vecs[0],
            )
            session.add(pool_data)
            await session.commit()

        node_descriptions = []
        for node in nodes:
            node_descriptions += [node.description]
        node_vecs = await Embedding.get_embedding(node_descriptions)

        async with postgres.session() as session:
            for vec in node_vecs:
                node_data = NodePoolVector(
                    id=node.id,
                    serviceId=metadata.id,
                    embedding=vec,
                )
                session.add(node_data)
            await session.commit()
