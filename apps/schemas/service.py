from pydantic import BaseModel, Field


import uuid
from typing import Any


class UpdateServiceRequest(BaseModel):
    """POST /api/service 请求数据结构"""

    service_id: uuid.UUID | None = Field(None, alias="serviceId", description="服务ID（更新时传递）")
    data: dict[str, Any] = Field(..., description="对应 YAML 内容的数据对象")


class ChangeFavouriteServiceRequest(BaseModel):
    """PUT /api/service/{serviceId} 请求数据结构"""

    favorited: bool = Field(..., description="是否收藏")