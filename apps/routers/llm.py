# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""FastAPI 大模型相关接口"""

from typing import Annotated, Optional

from fastapi import APIRouter, Body, Depends, Query, status
from fastapi.responses import JSONResponse

from apps.dependency import get_user, verify_user
from apps.entities.request_data import (
    UpdateLLMReq,
)
from apps.entities.response_data import (
    ListLLMProviderRsp,
    ListLLMRsp,
    ResponseData,
)
from apps.manager.llm import LLMManager

router = APIRouter(
    prefix="/api/llm",
    tags=["llm"],
    dependencies=[
        Depends(verify_user),
    ],
)


@router.get("/provider", response_model=ListLLMProviderRsp, responses={
    status.HTTP_404_NOT_FOUND: {"model": ResponseData},
},
)
async def list_llm_provider(
    user_sub: Annotated[str, Depends(get_user)],
) -> JSONResponse:
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
            responses={
                status.HTTP_404_NOT_FOUND: {"model": ResponseData},
            },
            )
async def list_llm(
    user_sub: Annotated[str, Depends(get_user)],
    llm_id: Optional[str] = Query(default=None, description="大模型ID", alias="llmId"),
) -> JSONResponse:
    llm_list = await LLMManager.list_llm(user_sub, llm_id)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=ListLLMRsp(
            code=status.HTTP_200_OK,
            message="success",
            result=llm_list
        ).model_dump(exclude_none=True, by_alias=True),
    )


@router.put(
    "",
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ResponseData},
    },
)
async def create_llm(
    user_sub: Annotated[str, Depends(get_user)],
    llm_id: Optional[str] = Query(default=None, description="大模型ID", alias="llmId"),
    req: UpdateLLMReq = Body(...),
) -> JSONResponse:
    llm_id = await LLMManager.update_llm(user_sub, llm_id, req)
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
    user_sub: Annotated[str, Depends(get_user)],
    llm_id: Optional[str] = Query(default=None, description="大模型ID", alias="llmId"),
) -> JSONResponse:
    llm_id = await LLMManager.delete_llm(user_sub, llm_id)
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
async def update_conv_llm(
    user_sub: Annotated[str, Depends(get_user)],
    conversation_id: Optional[str] = Query(default=None, description="对话ID", alias="conversationId"),
    llm_id: str = Query(default="empty", description="llm ID", alias="llmId"),
) -> JSONResponse:
    """更新对话的知识库"""
    llm_id = await LLMManager.update_conversation_llm(user_sub, conversation_id, llm_id)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=ResponseData(
            code=status.HTTP_200_OK,
            message="success",
            result=llm_id,
        ).model_dump(exclude_none=True, by_alias=True),
    )
