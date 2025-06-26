# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""加载配置文件夹的Service部分"""

import asyncio
import logging
import shutil

from anyio import Path
from fastapi.encoders import jsonable_encoder

from apps.common.config import Config
from apps.schemas.flow import Permission, ServiceMetadata
from apps.schemas.pool import NodePool, ServicePool
from apps.models.vector import NodePoolVector, ServicePoolVector
from apps.llm.embedding import Embedding
from apps.common.lance import LanceDB
from apps.common.mongo import MongoDB
from apps.scheduler.pool.check import FileChecker
from apps.scheduler.pool.loader.metadata import MetadataLoader, MetadataType
from apps.scheduler.pool.loader.openapi import OpenAPILoader

logger = logging.getLogger(__name__)
BASE_PATH = Path(Config().get_config().deploy.data_dir) / "semantics" / "service"


class ServiceLoader:
    """Service 加载器"""

    async def load(self, service_id: str, hashes: dict[str, str]) -> None:
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
            nodes: list[NodePool] = []
            async for yaml_path in (service_path / "openapi").rglob("*.yaml"):
                nodes.extend(await OpenAPILoader().load_one(service_id, yaml_path, metadata.api.server))
        except Exception:
            logger.exception("[ServiceLoader] 服务 %s 文件损坏", service_id)
            return
        # 更新数据库
        await self._update_db(nodes, metadata)


    async def save(self, service_id: str, metadata: ServiceMetadata, data: dict) -> None:
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
        await self.load(service_id, file_checker.hashes[f"service/{service_id}"])


    async def delete(self, service_id: str, *, is_reload: bool = False) -> None:
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
            # 获取 LanceDB 表
            service_table = await LanceDB().get_table("service")
            node_table = await LanceDB().get_table("node")

            # 删除数据
            await service_table.delete(f"id = '{service_id}'")
            await node_table.delete(f"id = '{service_id}'")
        except Exception:
            logger.exception("[ServiceLoader] 删除数据库失败")

        if not is_reload:
            path = BASE_PATH / service_id
            if await path.exists():
                shutil.rmtree(path)


    async def _update_db(self, nodes: list[NodePool], metadata: ServiceMetadata) -> None:  # noqa: C901, PLR0912, PLR0915
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

        # 向量化所有数据并保存
        while True:
            try:
                service_table = await LanceDB().get_table("service")
                node_table = await LanceDB().get_table("node")
                await service_table.delete(f"id = '{metadata.id}'")
                await node_table.delete(f"service_id = '{metadata.id}'")
                break
            except Exception as e:
                if "Commit conflict" in str(e):
                    logger.error("[ServiceLoader] LanceDB删除service冲突，重试中...")  # noqa: TRY400
                    await asyncio.sleep(0.01)
                else:
                    raise

        # 进行向量化，更新LanceDB
        service_vecs = await Embedding.get_embedding([metadata.description])
        service_vector_data = [
            ServicePoolVector(
                id=metadata.id,
                embedding=service_vecs[0],
            ),
        ]
        while True:
            try:
                service_table = await LanceDB().get_table("service")
                await service_table.merge_insert("id").when_matched_update_all().when_not_matched_insert_all().execute(
                    service_vector_data,
                )
                break
            except Exception as e:
                if "Commit conflict" in str(e):
                    logger.error("[ServiceLoader] LanceDB插入service冲突，重试中...")  # noqa: TRY400
                    await asyncio.sleep(0.01)
                else:
                    raise

        node_descriptions = []
        for node in nodes:
            node_descriptions += [node.description]

        node_vecs = await Embedding.get_embedding(node_descriptions)
        node_vector_data = []
        for i, vec in enumerate(node_vecs):
            node_vector_data.append(
                NodePoolVector(
                    id=nodes[i].id,
                    service_id=metadata.id,
                    embedding=vec,
                ),
            )
        while True:
            try:
                node_table = await LanceDB().get_table("node")
                await node_table.merge_insert("id").when_matched_update_all().when_not_matched_insert_all().execute(
                    node_vector_data,
                )
                break
            except Exception as e:
                if "Commit conflict" in str(e):
                    logger.error("[ServiceLoader] LanceDB插入node冲突，重试中...")  # noqa: TRY400
                    await asyncio.sleep(0.01)
                else:
                    raise

