# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""FastAPI 大模型相关接口"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import JSONResponse

from apps.dependency import verify_admin, verify_personal_token, verify_session
from apps.schemas.request_data import (
    UpdateLLMReq,
)
from apps.schemas.response_data import (
    ListLLMProviderRsp,
    ListLLMRsp,
    ResponseData,
)
from apps.services.llm import LLMManager

router = APIRouter(
    prefix="/api/llm",
    tags=["llm"],
    dependencies=[
        Depends(verify_session),
        Depends(verify_personal_token),
    ],
)
admin_router = APIRouter(
    prefix="/api/llm",
    tags=["llm"],
    dependencies=[
        Depends(verify_session),
        Depends(verify_personal_token),
        Depends(verify_admin),
    ],
)


@admin_router.get("/provider", response_model=ListLLMProviderRsp,
    responses={status.HTTP_404_NOT_FOUND: {"model": ResponseData}},
)
async def list_llm_provider() -> JSONResponse:
    """获取大模型提供商列表"""
    llm_provider_list = await LLMManager.list_llm_provider()
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=ListLLMProviderRsp(
            code=status.HTTP_200_OK,
            message="success",
            result=llm_provider_list,
        ).model_dump(exclude_none=True, by_alias=True),
    )


@router.get("", response_model=ListLLMRsp,
    responses={status.HTTP_404_NOT_FOUND: {"model": ResponseData}},
)
async def list_llm(llmId: uuid.UUID | None = None) -> JSONResponse:  # noqa: N803
    """获取大模型列表"""
    llm_list = await LLMManager.list_llm(llmId)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=ListLLMRsp(
            code=status.HTTP_200_OK,
            message="success",
            result=llm_list,
        ).model_dump(exclude_none=True, by_alias=True),
    )


@admin_router.put("",
    responses={status.HTTP_404_NOT_FOUND: {"model": ResponseData}},
)
async def create_llm(
    req: UpdateLLMReq,
    llmId: uuid.UUID | None = None,  # noqa: N803
) -> JSONResponse:
    """创建或更新大模型配置"""
    await LLMManager.update_llm(llmId, req)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=ResponseData(
            code=status.HTTP_200_OK,
            message="success",
            result=llm_id,
        ).model_dump(exclude_none=True, by_alias=True),
    )


@admin_router.delete("",
    responses={status.HTTP_404_NOT_FOUND: {"model": ResponseData}},
)
async def delete_llm(request: Request, llmId: uuid.UUID) -> JSONResponse:  # noqa: N803
    """删除大模型配置"""
    await LLMManager.delete_llm(request.state.user_sub, llmId)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=ResponseData(
            code=status.HTTP_200_OK,
            message="success",
            result=llmId,
        ).model_dump(exclude_none=True, by_alias=True),
    )


@router.put("/conv",
    responses={status.HTTP_404_NOT_FOUND: {"model": ResponseData}},
)
async def update_user_llm(
    request: Request,
    llmId: uuid.UUID,  # noqa: N803
) -> JSONResponse:
    """更新用户所选的大模型"""
    try:
        await LLMManager.update_user_default_llm(request.state.user_sub, llmId)
    except ValueError as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ResponseData(
                code=status.HTTP_400_BAD_REQUEST,
                message=str(e),
                result=None,
            ).model_dump(exclude_none=True, by_alias=True),
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=ResponseData(
            code=status.HTTP_200_OK,
            message="success",
            result=llmId,
        ).model_dump(exclude_none=True, by_alias=True),
    )
