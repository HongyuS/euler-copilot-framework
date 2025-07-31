# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Flow加载器"""

import logging
import uuid
from hashlib import sha256
from typing import Any

import aiofiles
import yaml
from anyio import Path
from sqlalchemy import and_, delete, func, select

from apps.common.config import config
from apps.common.postgres import postgres
from apps.llm.embedding import Embedding
from apps.models.app import App, AppHashes
from apps.models.flow import Flow as FlowInfo
from apps.models.vectors import FlowPoolVector
from apps.scheduler.util import yaml_enum_presenter, yaml_str_presenter
from apps.schemas.enum_var import EdgeType
from apps.schemas.flow import Flow
from apps.services.node import NodeManager

logger = logging.getLogger(__name__)
BASE_PATH = Path(config.deploy.data_dir) / "semantics" / "app"


class FlowLoader:
    """工作流加载器"""

    async def _load_yaml_file(self, flow_path: Path) -> dict[str, Any]:
        """从YAML文件加载工作流配置"""
        try:
            async with aiofiles.open(flow_path, encoding="utf-8") as f:
                return yaml.safe_load(await f.read())
        except Exception:
            logger.exception("[FlowLoader] 加载YAML文件失败：%s", flow_path)
            return {}

    async def _validate_basic_fields(self, flow_yaml: dict[str, Any], flow_path: Path) -> dict[str, Any]:
        """验证工作流基本字段"""
        if "name" not in flow_yaml or not flow_yaml["name"]:
            logger.error("[FlowLoader] 工作流名称不能为空：%s", flow_path)
            return {}

        if "description" not in flow_yaml or not flow_yaml["description"]:
            logger.error("[FlowLoader] 工作流描述不能为空：%s", flow_path)
            return {}

        if "start" not in flow_yaml["steps"] or "end" not in flow_yaml["steps"]:
            logger.error("[FlowLoader] 工作流必须包含开始和结束节点：%s", flow_path)
            return {}

        return flow_yaml

    async def _process_edges(self, flow_yaml: dict[str, Any], flow_id: uuid.UUID, app_id: uuid.UUID) -> dict[str, Any]:
        """处理工作流边的转换"""
        logger.info("[FlowLoader] 应用 %s：解析工作流 %s 的边", flow_id, app_id)
        try:
            for edge in flow_yaml["edges"]:
                if "from" in edge:
                    edge["edge_from"] = edge.pop("from")
                if "to" in edge:
                    edge["edge_to"] = edge.pop("to")
                if "type" in edge:
                    edge["edge_type"] = EdgeType[edge.pop("type").upper()]
        except Exception:
            logger.exception("[FlowLoader] 处理边时发生错误")
            return {}
        else:
            return flow_yaml

    async def _process_steps(self, flow_yaml: dict[str, Any], flow_id: uuid.UUID, app_id: uuid.UUID) -> dict[str, Any]:
        """处理工作流步骤的转换"""
        logger.info("[FlowLoader] 应用 %s：解析工作流 %s 的步骤", flow_id, app_id)
        for key, step in flow_yaml["steps"].items():
            if key[0] == "_":
                err = f"[FlowLoader] 步骤名称不能以下划线开头：{key}"
                logger.error(err)
                raise ValueError(err)
            if key == "start":
                step["name"] = "开始"
                step["description"] = "开始节点"
                step["type"] = "start"
            elif key == "end":
                step["name"] = "结束"
                step["description"] = "结束节点"
                step["type"] = "end"
            else:
                node_info = await NodeManager.get_node(step["node"])
                try:
                    step["type"] = node_info.callId
                except ValueError as e:
                    logger.warning("[FlowLoader] 获取节点call_id失败：%s，错误信息：%s", node_info.id, e)
                    step["type"] = "Empty"
                step["name"] = (
                    node_info.name
                    if "name" not in step or step["name"] == ""
                    else step["name"]
                )
        return flow_yaml


    async def load(self, app_id: uuid.UUID, flow_id: uuid.UUID) -> Flow | None:
        """从文件系统中加载【单个】工作流"""
        logger.info("[FlowLoader] 应用 %s：加载工作流 %s...", flow_id, app_id)

        # 构建工作流文件路径
        flow_path = BASE_PATH / str(app_id) / "flow" / f"{flow_id}.yaml"
        if not await flow_path.exists():
            logger.error("[FlowLoader] 应用 %s：工作流文件 %s 不存在", app_id, flow_path)
            return None

        try:
            # 加载YAML文件
            flow_yaml = await self._load_yaml_file(flow_path)
            if not flow_yaml:
                return None

            # 按顺序处理工作流配置
            for processor in [
                lambda y: self._validate_basic_fields(y, flow_path),
                lambda y: self._process_edges(y, flow_id, app_id),
                lambda y: self._process_steps(y, flow_id, app_id),
            ]:
                flow_yaml = await processor(flow_yaml)
                if not flow_yaml:
                    return None
            flow_config = Flow.model_validate(flow_yaml)
            await self._update_db(
                app_id,
                FlowInfo(
                    appId=app_id,
                    id=flow_id,
                    name=flow_config.name,
                    description=flow_config.description,
                    enabled=True,
                    path=str(flow_path),
                    debug=flow_config.debug,
                ),
            )
            return Flow.model_validate(flow_yaml)
        except Exception:
            logger.exception("[FlowLoader] 应用 %s：工作流 %s 格式不合法", app_id, flow_id)
            return None


    async def save(self, app_id: uuid.UUID, flow_id: uuid.UUID, flow: Flow) -> None:
        """保存工作流"""
        flow_path = BASE_PATH / str(app_id) / "flow" / f"{flow_id}.yaml"
        if not await flow_path.parent.exists():
            await flow_path.parent.mkdir(parents=True)

        flow_dict = flow.model_dump(by_alias=True, exclude_none=True)
        async with aiofiles.open(flow_path, mode="w", encoding="utf-8") as f:
            yaml.add_representer(str, yaml_str_presenter)
            yaml.add_representer(EdgeType, yaml_enum_presenter)
            await f.write(
                yaml.dump(
                    flow_dict,
                    allow_unicode=True,
                    sort_keys=False,
                ),
            )
        await self._update_db(
            app_id,
            FlowInfo(
                appId=app_id,
                id=flow_id,
                name=flow.name,
                description=flow.description,
                enabled=True,
                path=str(flow_path),
                debug=flow.debug,
            ),
        )


    async def delete(self, app_id: uuid.UUID, flow_id: uuid.UUID) -> bool:
        """删除指定工作流文件"""
        flow_path = BASE_PATH / str(app_id) / "flow" / f"{flow_id}.yaml"
        # 确保目标为文件且存在
        if await flow_path.exists():
            try:
                await flow_path.unlink()
                logger.info("[FlowLoader] 成功删除工作流文件：%s", flow_path)
            except Exception:
                logger.exception("[FlowLoader] 删除工作流文件失败：%s", flow_path)
                return False

            async with postgres.session() as session:
                await session.execute(delete(FlowPoolVector).where(FlowPoolVector.id == flow_id))
            return True
        logger.warning("[FlowLoader] 工作流文件不存在或不是文件：%s", flow_path)
        return True


    async def _update_db(self, app_id: uuid.UUID, metadata: FlowInfo) -> None:
        """更新数据库"""
        # 检查App是否存在
        async with postgres.session() as session:
            app_num = (await session.scalars(
                select(func.count(App.id)).where(App.id == app_id),
            )).one()
            if app_num == 0:
                err = f"[FlowLoader] App {app_id} 不存在"
                logger.error(err)
                return

            # 删除旧的Flow数据
            await session.execute(delete(FlowInfo).where(FlowInfo.appId == app_id))
            await session.execute(delete(AppHashes).where(
                and_(
                    AppHashes.appId == app_id,
                    AppHashes.filePath == f"flow/{metadata.id}.yaml",
                ),
            ))
            await session.execute(delete(FlowPoolVector).where(FlowPoolVector.id == metadata.id))

            # 创建新的Flow数据
            session.add(metadata)

            flow_path = BASE_PATH / str(app_id) / "flow" / f"{metadata.id}.yaml"
            async with aiofiles.open(flow_path, "rb") as f:
                new_hash = sha256(await f.read()).hexdigest()

            flow_hash = AppHashes(
                appId=app_id,
                hash=new_hash,
                filePath=f"flow/{metadata.id}.yaml",
            )
            session.add(flow_hash)

            # 进行向量化
            service_embedding = await Embedding.get_embedding([metadata.description])
            vector_data = [
                FlowPoolVector(
                    id=metadata.id,
                    appId=app_id,
                    embedding=service_embedding[0],
                ),
            ]
            session.add_all(vector_data)
            await session.commit()
