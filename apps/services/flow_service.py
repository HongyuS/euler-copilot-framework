# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""flow拓扑相关函数"""

import logging
import uuid
from typing import TYPE_CHECKING

from apps.exceptions import FlowBranchValidationError, FlowEdgeValidationError, FlowNodeValidationError
from apps.scheduler.pool.pool import pool
from apps.schemas.enum_var import NodeType, SpecialCallType
from apps.schemas.flow_topology import EdgeItem, FlowItem

if TYPE_CHECKING:
    from pydantic import BaseModel

logger = logging.getLogger(__name__)
BRANCH_ILLEGAL_CHARS = [
    ".",
]


class FlowServiceManager:
    """flow拓扑相关函数"""

    @staticmethod
    async def remove_excess_structure_from_flow(flow_item: FlowItem) -> FlowItem:  # noqa: C901, PLR0912
        """移除流程图中的多余结构"""
        node_branch_map = {}
        for node in flow_item.nodes:
            if node.node_id not in {"start", "end", SpecialCallType.EMPTY.value}:
                try:
                    call_class: type[BaseModel] = await pool.get_call(node.call_id)
                    if not call_class:
                        node.node_id = SpecialCallType.EMPTY.value
                        node.description = "【对应的api工具被删除！节点不可用！请联系相关人员！】\n\n"+node.description
                except Exception:
                    node.node_id = SpecialCallType.EMPTY.value
                    node.description = "【对应的api工具被删除！节点不可用！请联系相关人员！】\n\n"+node.description
                    logger.exception("[FlowService] 获取步骤的call_id失败%s", node.call_id)
            node_branch_map[node.step_id] = set()
            if node.call_id == NodeType.CHOICE.value:
                input_parameters = node.parameters["input_parameters"]
                if "choices" not in input_parameters:
                    err = f"[FlowService] 节点{node.name}的分支字段缺失"
                    logger.error(err)
                    raise FlowBranchValidationError(err)
                if not input_parameters["choices"]:
                    err = f"[FlowService] 节点{node.name}的分支字段为空"
                    logger.error(err)
                    raise FlowBranchValidationError(err)
                for choice in input_parameters["choices"]:
                    if "branch_id" not in choice:
                        err = f"[FlowService] 节点{node.name}的分支choice缺少branch_id字段"
                        logger.error(err)
                        raise FlowBranchValidationError(err)
                    if choice["branch_id"] in node_branch_map[node.step_id]:
                        err = f"[FlowService] 节点{node.name}的分支{choice['branch_id']}重复"
                        logger.error(err)
                        raise ValueError(err)
                    for illegal_char in BRANCH_ILLEGAL_CHARS:
                        if illegal_char in choice["branch_id"]:
                            err = f"[FlowService] 节点{node.name}的分支{choice['branch_id']}名称中含有非法字符"
                            logger.error(err)
                            raise ValueError(err)
                    node_branch_map[node.step_id].add(choice["branch_id"])
            else:
                node_branch_map[node.step_id].add("")
        valid_edges = []
        for edge in flow_item.edges:
            if edge.source_branch not in node_branch_map:
                continue
            if edge.target_branch not in node_branch_map:
                continue
            if edge.branch_id not in node_branch_map[edge.source_branch]:
                continue
            valid_edges.append(edge)
        flow_item.edges = valid_edges
        return flow_item

    @staticmethod
    async def _validate_node_ids(flow_item: FlowItem) -> tuple[uuid.UUID, uuid.UUID]:
        """验证节点ID的唯一性并验证basicConfig中的start_id和end_id是否在节点列表中存在"""
        nodes = flow_item.nodes
        ids = set()

        # 验证节点ID的唯一性
        for node in nodes:
            if node.step_id in ids:
                err = f"[FlowService] 节点{node.name}的id重复"
                logger.error(err)
                raise FlowNodeValidationError(err)
            ids.add(node.step_id)

        # 验证basicConfig中的start_id和end_id是否在节点列表中存在
        if flow_item.basic_config is None:
            err = "[FlowService] Flow的基本配置为空"
            logger.error(err)
            raise FlowNodeValidationError(err)

        start_id = flow_item.basic_config.startStep
        end_id = flow_item.basic_config.endStep

        if start_id not in ids:
            err = f"[FlowService] 起始节点ID {start_id} 在节点列表中不存在"
            logger.error(err)
            raise FlowNodeValidationError(err)

        if end_id not in ids:
            err = f"[FlowService] 终止节点ID {end_id} 在节点列表中不存在"
            logger.error(err)
            raise FlowNodeValidationError(err)

        return start_id, end_id

    @staticmethod
    async def validate_flow_illegal(flow_item: FlowItem) -> tuple[uuid.UUID, uuid.UUID]:
        """验证流程图是否合法；当流程图不合法时抛出异常"""
        # 验证节点ID并获取起始和终止节点
        start_id, end_id = await FlowServiceManager._validate_node_ids(flow_item)

        # 验证边的合法性并获取节点的入度和出度
        in_deg, out_deg = await FlowServiceManager._validate_edges(flow_item.edges)

        # 验证起始和终止节点的入度和出度
        await FlowServiceManager._validate_node_degrees(str(start_id), str(end_id), in_deg, out_deg)

        return start_id, end_id

    @staticmethod
    async def _validate_edges(edges: list[EdgeItem]) -> tuple[dict[str, int], dict[str, int]]:
        """验证边的合法性并计算节点的入度和出度；当边的ID重复、起始终止节点相同、分支重复或分支包含非法字符时抛出异常"""
        ids = set()
        branches = {}
        in_deg = {}
        out_deg = {}

        for e in edges:
            # 验证分支ID是否包含非法字符
            for illegal_char in BRANCH_ILLEGAL_CHARS:
                if illegal_char in e.branch_id:
                    err = f"[FlowService] 边{e.edge_id}的分支{e.branch_id}名称中含有非法字符"
                    logger.error(err)
                    raise FlowEdgeValidationError(err)

            if e.edge_id in ids:
                err = f"[FlowService] 边{e.edge_id}的id重复"
                logger.error(err)
                raise FlowEdgeValidationError(err)
            ids.add(e.edge_id)

            if e.source_branch == e.target_branch:
                err = f"[FlowService] 边{e.edge_id}的起始节点和终止节点相同"
                logger.error(err)
                raise FlowEdgeValidationError(err)

            if e.source_branch not in branches:
                branches[e.source_branch] = set()
            if e.branch_id in branches[e.source_branch]:
                err = f"[FlowService] 边{e.edge_id}的分支{e.branch_id}重复"
                logger.error(err)
                raise FlowEdgeValidationError(err)

            branches[e.source_branch].add(e.branch_id)

            in_deg[e.target_branch] = in_deg.get(e.target_branch, 0) + 1
            out_deg[e.source_branch] = out_deg.get(e.source_branch, 0) + 1

        return in_deg, out_deg

    @staticmethod
    async def _validate_node_degrees(
        start_id: str, end_id: str, in_deg: dict[str, int], out_deg: dict[str, int],
    ) -> None:
        """验证起始和终止节点的入度和出度；当起始节点入度不为0或终止节点出度不为0时抛出异常"""
        if start_id in in_deg and in_deg[start_id] != 0:
            err = f"[FlowService] 起始节点{start_id}的入度不为0"
            logger.error(err)
            raise FlowNodeValidationError(err)
        if end_id in out_deg and out_deg[end_id] != 0:
            err = f"[FlowService] 终止节点{end_id}的出度不为0"
            logger.error(err)
            raise FlowNodeValidationError(err)

    @staticmethod
    async def validate_flow_connectivity(flow_item: FlowItem) -> bool:  # noqa: C901
        """
        验证流程图的连通性

        检查:
        1. 是否所有节点都能从起始节点到达
        2. 是否能从起始节点到达终止节点
        3. 是否存在非终止节点没有出边
        """
        # 找到起始和终止节点
        start_id = None
        end_id = None
        for node in flow_item.nodes:
            if node.call_id == NodeType.START.value:
                start_id = node.step_id
            if node.call_id == NodeType.END.value:
                end_id = node.step_id

        # 构建邻接表
        adj = {}
        for edge in flow_item.edges:
            if edge.source_branch not in adj:
                adj[edge.source_branch] = []
            adj[edge.source_branch].append(edge.target_branch)

        # BFS遍历检查连通性
        vis = {start_id}
        q = [start_id]  # 使用list替代queue.Queue

        while q:  # 使用while q替代while not q.empty()
            cur = q.pop(0)  # 使用pop(0)替代q.get()
            # 检查非终止节点是否有出边
            if cur != end_id and cur not in adj:
                return False

            # 遍历所有出边
            if cur in adj:
                for nxt in adj[cur]:
                    if nxt not in vis:
                        vis.add(nxt)
                        q.append(nxt)  # 使用append替代q.put()

        # 检查是否能到达终止节点
        return end_id in vis
