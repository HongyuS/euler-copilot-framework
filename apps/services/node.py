# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Node管理器"""

import logging
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from apps.common.postgres import postgres
from apps.models import NodeInfo
from apps.schemas.enum_var import SpecialCallType

if TYPE_CHECKING:
    from pydantic import BaseModel

logger = logging.getLogger(__name__)


class NodeManager:
    """Node管理器"""

    @staticmethod
    async def get_node(node_id: str) -> NodeInfo:
        """获取Node信息"""
        async with postgres.session() as session:
            node = (await session.scalars(
                select(NodeInfo).where(NodeInfo.id == node_id),
            )).one_or_none()
            if not node:
                err = f"[NodeManager] Node {node_id} not found."
                raise ValueError(err)
            return node


    @staticmethod
    def merge_params_schema(params_schema: dict[str, Any], known_params: dict[str, Any]) -> dict[str, Any]:
        """递归合并参数Schema，将known_params中的值填充到params_schema的对应位置"""
        if not isinstance(params_schema, dict):
            return params_schema

        if params_schema.get("type") == "object":
            properties = params_schema.get("properties", {})
            for key, value in properties.items():
                if key in known_params:
                    # 如果在known_params中找到匹配的键，更新default值
                    properties[key]["default"] = known_params[key]
                # 递归处理嵌套的schema
                properties[key] = NodeManager.merge_params_schema(value, known_params)

        elif params_schema.get("type") == "array":
            items = params_schema.get("items", {})
            # 递归处理数组项
            params_schema["items"] = NodeManager.merge_params_schema(items, known_params)

        return params_schema


    @staticmethod
    async def get_node_params(node_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        """获取Node数据"""
        # 在此处获取pool单例，避免循环导入
        from apps.scheduler.pool.pool import pool  # noqa: PLC0415

        # 查找Node信息
        if node_id == SpecialCallType.EMPTY.value:
            # 如果是空节点，返回空Schema
            return {}, {}
        logger.info("[NodeManager] 获取节点 %s", node_id)
        node_data = await NodeManager.get_node(node_id)
        call_id = node_data.callId

        # 查找Call信息
        logger.info("[NodeManager] 获取Call %s", call_id)
        call_class: type[BaseModel] = await pool.get_call(str(call_id))
        if not call_class:
            err = f"[NodeManager] Call {call_id} 不存在"
            logger.error(err)
            raise ValueError(err)

        # 返回参数Schema
        return (
            NodeManager.merge_params_schema(call_class.model_json_schema(), node_data.knownParams or {}),
            call_class.output_model.model_json_schema(  # type: ignore[attr-defined]
                override=node_data.overrideOutput if node_data.overrideOutput else {},
            ),
        )
