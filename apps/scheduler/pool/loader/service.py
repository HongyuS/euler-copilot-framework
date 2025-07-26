# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""加载配置文件夹的Service部分"""

import logging
import shutil

from anyio import Path
from fastapi.encoders import jsonable_encoder
from sqlalchemy import delete, insert

from apps.common.config import config
from apps.common.postgres import postgres
from apps.llm.embedding import Embedding
from apps.models.node import NodeInfo
from apps.models.service import Service
from apps.models.vectors import NodePoolVector, ServicePoolVector
from apps.scheduler.pool.check import FileChecker
from apps.schemas.flow import Permission, ServiceMetadata

from .metadata import MetadataLoader, MetadataType
from .openapi import OpenAPILoader

logger = logging.getLogger(__name__)
BASE_PATH = Path(config.deploy.data_dir) / "semantics" / "service"


class ServiceLoader:
    """Service 加载器"""

    @staticmethod
    async def load(service_id: str, hashes: dict[str, str]) -> None:
        """加载单个Service"""
        service_path = BASE_PATH / service_id
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
    async def save(service_id: str, metadata: ServiceMetadata, data: dict) -> None:
        """在文件系统上保存Service，并更新数据库"""
        service_path = BASE_PATH / service_id
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
    async def delete(service_id: str, *, is_reload: bool = False) -> None:
        """删除Service，并更新数据库"""
        mongo = MongoDB()
        service_collection = mongo.get_collection("service")
        node_collection = mongo.get_collection("node")
        try:
            await service_collection.delete_one({"_id": service_id})
            await node_collection.delete_many({"service_id": service_id})
        except Exception:
            logger.exception("[ServiceLoader] 删除Service失败")

        try:
            # 删除postgres中的向量数据
            async with postgres.session() as session:
                await session.execute(delete(ServicePoolVector).where(ServicePoolVector.service_id == service_id))
                await session.execute(delete(NodePoolVector).where(NodePoolVector.serviceId == service_id))
                await session.commit()
        except Exception:
            logger.exception("[ServiceLoader] 删除数据库失败")

        if not is_reload:
            path = BASE_PATH / service_id
            if await path.exists():
                shutil.rmtree(path)


    @staticmethod
    async def _update_db(nodes: list[NodeInfo], metadata: ServiceMetadata) -> None:
        """更新数据库"""
        if not metadata.hashes:
            err = f"[ServiceLoader] 服务 {metadata.id} 的哈希值为空"
            logger.error(err)
            raise ValueError(err)
        # 更新MongoDB
        mongo = MongoDB()
        service_collection = mongo.get_collection("service")
        node_collection = mongo.get_collection("node")
        try:
            # 先删除旧的节点
            await node_collection.delete_many({"service_id": metadata.id})
            # 插入或更新 Service
            await service_collection.update_one(
                {"_id": metadata.id},
                {
                    "$set": jsonable_encoder(
                        ServicePool(
                            _id=metadata.id,
                            name=metadata.name,
                            description=metadata.description,
                            author=metadata.author,
                            permission=metadata.permission if metadata.permission else Permission(),
                            hashes=metadata.hashes,
                        ),
                    ),
                },
                upsert=True,
            )
            for node in nodes:
                await node_collection.update_one({"_id": node.id}, {"$set": jsonable_encoder(node)}, upsert=True)
        except Exception as e:
            err = f"[ServiceLoader] 更新 MongoDB 失败：{e}"
            logger.exception(err)
            raise RuntimeError(err) from e

        # 删除旧的向量数据
        async with postgres.session() as session:
            await session.execute(delete(ServicePoolVector).where(ServicePoolVector.service_id == metadata.id))
            await session.execute(delete(NodePoolVector).where(NodePoolVector.serviceId == metadata.id))
            await session.commit()

        # 进行向量化，更新postgres
        service_vecs = await Embedding.get_embedding([metadata.description])
        async with postgres.session() as session:
            await session.execute(
                insert(ServicePoolVector),
                [
                    {
                        "service_id": metadata.id,
                        "embedding": service_vecs[0],
                    },
                ],
            )
            await session.commit()

        node_descriptions = []
        for node in nodes:
            node_descriptions += [node.description]

        node_vecs = await Embedding.get_embedding(node_descriptions)
        async with postgres.session() as session:
            await session.execute(
                insert(NodePoolVector),
                [
                    {
                        "service_id": metadata.id,
                        "embedding": vec,
                    }
                    for vec in node_vecs
                ],
            )
            await session.commit()
