# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""前端展示flow用到的数据结构"""

import uuid
from typing import Any

from pydantic import BaseModel, Field

from .enum_var import EdgeType, SpecialCallType


class NodeMetaDataBase(BaseModel):
    """节点元数据基类"""

    node_id: str = Field(alias="nodeId")
    call_id: str = Field(alias="callId")
    name: str
    updated_at: float | None = Field(alias="updatedAt")


class NodeMetaDataItem(NodeMetaDataBase):
    """节点元数据类"""

    description: str
    parameters: dict[str, Any] | None


class NodeServiceItem(BaseModel):
    """GET /api/flow/service 中单个service信息以及service下的节点元数据的信息"""

    service_id: uuid.UUID = Field(..., alias="serviceId", description="服务ID")
    name: str = Field(..., description="服务名称")
    data: list[NodeMetaDataBase] = Field(default=[])
    created_at: str | None = Field(default=None, alias="createdAt", description="创建时间")


class PositionItem(BaseModel):
    """请求/响应中的前端相对位置变量类"""

    x: float = Field(default=0.0)
    y: float = Field(default=0.0)


class NodeItem(BaseModel):
    """请求/响应中的节点变量类"""

    step_id: uuid.UUID = Field(alias="stepId", default=uuid.uuid4())
    service_id: uuid.UUID = Field(alias="serviceId", default=uuid.uuid4())
    node_id: str = Field(alias="nodeId", default="")
    name: str = Field(default="")
    call_id: str = Field(alias="callId", default=SpecialCallType.EMPTY.value)
    description: str = Field(default="")
    parameters: dict[str, Any] = Field(default={})
    position: PositionItem = Field(default=PositionItem())


class EdgeItem(BaseModel):
    """请求/响应中的边变量类"""

    edge_id: uuid.UUID = Field(alias="edgeId")
    source_branch: str = Field(alias="sourceNode")
    target_branch: str = Field(alias="targetNode")
    type: str = Field(default=EdgeType.NORMAL.value)
    branch_id: str = Field(alias="branchId")


class FlowBasicConfig(BaseModel):
    """Flow的基本配置"""

    startStep: uuid.UUID = Field(description="开始节点ID")  # noqa: N815
    endStep: uuid.UUID = Field(description="结束节点ID")  # noqa: N815
    focusPoint: PositionItem | None = Field(description="当前焦点节点", default=PositionItem(x=0, y=0))  # noqa: N815


class FlowCheckStatus(BaseModel):
    """Flow的配置检查状态"""

    debug: bool = Field(description="是否经过调试", default=False)
    connectivity: bool = Field(default=False, description="图的开始节点和结束节点是否联通，并且除结束节点都有出边")


class FlowItem(BaseModel):
    """请求/响应中的流变量类"""

    flow_id: str = Field(alias="flowId", default="")
    name: str = Field(default="工作流名称")
    description: str = Field(default="工作流描述")
    enable: bool = Field(default=True)
    nodes: list[NodeItem] = Field(default=[])
    edges: list[EdgeItem] = Field(default=[])
    created_at: float | None = Field(alias="createdAt", default=0)
    basic_config: FlowBasicConfig | None = Field(alias="basicConfig", default=None, description="Flow的基本配置")
    check_status: FlowCheckStatus = Field(alias="checkStatus", default=FlowCheckStatus())
