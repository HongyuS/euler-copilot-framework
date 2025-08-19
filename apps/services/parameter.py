# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Parameter Manager"""

import logging
import uuid

from apps.scheduler.call.choice.condition_handler import ConditionHandler
from apps.scheduler.call.choice.schema import BoolOperate, DictOperate, ListOperate, NumberOperate, StringOperate, Type
from apps.scheduler.slot.slot import Slot
from apps.schemas.flow_topology import FlowItem
from apps.schemas.response_data import (
    OperateAndBindType,
    StepParams,
)
from apps.services.node import NodeManager

logger = logging.getLogger(__name__)


class ParameterManager:
    """Parameter Manager"""

    @staticmethod
    async def get_operate_and_bind_type(param_type: Type) -> list[OperateAndBindType]:
        """Get operate and bind type"""
        result = []
        operate = None
        if param_type == Type.NUMBER:
            operate = NumberOperate
        elif param_type == Type.STRING:
            operate = StringOperate
        elif param_type == Type.LIST:
            operate = ListOperate
        elif param_type == Type.BOOL:
            operate = BoolOperate
        elif param_type == Type.DICT:
            operate = DictOperate
        if operate:
            for item in operate:
                result += [
                    OperateAndBindType(
                        operate=item,
                        bind_type=(await ConditionHandler.get_value_type_from_operate(item)),
                    ),
                ]
        return result

    @staticmethod
    async def get_pre_params_by_flow_and_step_id(flow: FlowItem, step_id: uuid.UUID) -> list[StepParams]:
        """Get pre params by flow and step id"""
        index = 0
        q = [step_id]
        in_edges = {}
        step_id_to_node_id = {}
        step_id_to_node_name = {}
        for step in flow.nodes:
            step_id_to_node_id[step.step_id] = step.node_id
            step_id_to_node_name[step.step_id] = step.name
        for edge in flow.edges:
            if edge.target_node not in in_edges:
                in_edges[edge.target_node] = []
            in_edges[edge.target_node].append(edge.source_node)
        while index < len(q):
            tmp_step_id = q[index]
            index += 1
            for i in range(len(in_edges.get(tmp_step_id, []))):
                pre_node_id = in_edges[tmp_step_id][i]
                if pre_node_id not in q:
                    q.append(pre_node_id)
        pre_step_params = []
        for i in range(1, len(q)):
            step_id = q[i]
            if step_id == "start" or step_id == "end":
                continue
            node_id: str | None = step_id_to_node_id.get(step_id)
            node_name: str | None = step_id_to_node_name.get(step_id)
            if node_id is None or node_name is None:
                err = f"[ParameterManager] 节点 {step_id} 不存在"
                logger.error(err)
                continue
            _, output_schema = await NodeManager.get_node_params(node_id)
            slot = Slot(output_schema)
            params_node = slot.get_params_node_from_schema()
            pre_step_params.append(
                StepParams(
                    stepId=step_id,
                    name=node_name,
                    paramsNode=params_node,
                ),
            )
        return pre_step_params
