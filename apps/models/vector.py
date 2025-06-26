# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""向量数据库数据结构；数据将存储在LanceDB中"""

from lancedb.pydantic import LanceModel, Vector


class FlowPoolVector(LanceModel):
    """App向量信息"""

    id: str
    app_id: str
    embedding: Vector(dim=1024)  # type: ignore[call-arg]


class ServicePoolVector(LanceModel):
    """Service向量信息"""

    id: str
    embedding: Vector(dim=1024)  # type: ignore[call-arg]


class CallPoolVector(LanceModel):
    """Call向量信息"""

    id: str
    embedding: Vector(dim=1024)  # type: ignore[call-arg]


class NodePoolVector(LanceModel):
    """Node向量信息"""

    id: str
    service_id: str
    embedding: Vector(dim=1024)  # type: ignore[call-arg]
