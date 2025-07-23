# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""FastAPI 大模型相关接口"""

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


@router.get("/provider", response_model=ListLLMProviderRsp, responses={
        status.HTTP_404_NOT_FOUND: {"model": ResponseData},
    },
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


@router.get("", response_model=ListLLMRsp, responses={
        status.HTTP_404_NOT_FOUND: {"model": ResponseData},
    },
)
async def list_llm(
    request: Request,
    llm_id: Annotated[str | None, Query(description="大模型ID", alias="llmId")] = None,
) -> JSONResponse:
    """获取大模型列表"""
    llm_list = await LLMManager.list_llm(request.state.user_sub, llm_id)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=ListLLMRsp(
            code=status.HTTP_200_OK,
            message="success",
            result=llm_list,
        ).model_dump(exclude_none=True, by_alias=True),
    )


@router.put("", responses={
        status.HTTP_404_NOT_FOUND: {"model": ResponseData},
    },
)
async def create_llm(
    request: Request,
    req: UpdateLLMReq,
    llm_id: Annotated[str | None, Query(description="大模型ID", alias="llmId")] = None,
) -> JSONResponse:
    """创建或更新大模型配置"""
    llm_id = await LLMManager.update_llm(request.state.user_sub, llm_id, req)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=ResponseData(
            code=status.HTTP_200_OK,
            message="success",
            result=llm_id,
        ).model_dump(exclude_none=True, by_alias=True),
    )


@router.delete(
    "",
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ResponseData},
    },
)
async def delete_llm(
    request: Request,
    llm_id: Annotated[str, Query(description="大模型ID", alias="llmId")],
) -> JSONResponse:
    """删除大模型配置"""
    await LLMManager.delete_llm(request.state.user_sub, llm_id)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=ResponseData(
            code=status.HTTP_200_OK,
            message="success",
            result=llm_id,
        ).model_dump(exclude_none=True, by_alias=True),
    )


@router.put(
    "/conv",
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ResponseData},
    },
)
async def update_user_llm(
    request: Request,
    conversation_id: Annotated[str, Query(description="对话ID", alias="conversationId")],
    llm_id: Annotated[str, Query(description="llm ID", alias="llmId")] = "empty",
) -> JSONResponse:
    """更新对话的知识库"""
    llm_id = await LLMManager.update_user_llm(request.state.user_sub, conversation_id, llm_id)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=ResponseData(
            code=status.HTTP_200_OK,
            message="success",
            result=llm_id,
        ).model_dump(exclude_none=True, by_alias=True),
    )
