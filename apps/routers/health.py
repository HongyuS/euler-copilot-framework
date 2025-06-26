# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""FastAPI 健康检查接口"""

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from apps.schemas.response_data import HealthCheckRsp

router = APIRouter(
    prefix="/health_check",
    tags=["health_check"],
)


@router.get("", response_model=HealthCheckRsp)
def health_check() -> JSONResponse:
    """健康检查接口"""
    return JSONResponse(status_code=status.HTTP_200_OK, content=HealthCheckRsp(
        status="ok",
    ).model_dump(exclude_none=True, by_alias=True))
