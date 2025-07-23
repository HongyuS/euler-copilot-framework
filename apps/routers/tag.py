# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""FastAPI 用户标签相关API"""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from apps.dependency.user import get_user, verify_user
from apps.schemas.request_data import PostTagData
from apps.schemas.response_data import ResponseData
from apps.services.tag import TagManager

admin_router = APIRouter(
    prefix="/api/tag",
    tags=["tag"],
    dependencies=[
        Depends(verify_user),
    ],
)
router = APIRouter(
    prefix="/api/tag",
    tags=["tag"],
)


@router.get("")
async def get_user_tag(
    user_sub: Annotated[str, Depends(get_user)],
) -> JSONResponse:
    """获取所有标签；传入user_sub的时候获取特定用户的标签信息，不传则获取所有标签"""
    return JSONResponse(status_code=status.HTTP_200_OK, content=ResponseData(
        code=status.HTTP_200_OK,
        message="[Tag] Get all tag success.",
        result=await TagManager.get_all_tag(),
    ).model_dump(exclude_none=True, by_alias=True))


@admin_router.post("", response_model=ResponseData)
async def update_tag(post_body: PostTagData) -> JSONResponse:
    """添加或改动特定标签定义"""
    if not await TagManager.update_tag_by_name(post_body):
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=ResponseData(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="[Tag] Update tag failed",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))
    return JSONResponse(status_code=status.HTTP_200_OK, content=ResponseData(
        code=status.HTTP_200_OK,
        message="[Tag] Update tag success.",
        result={},
    ).model_dump(exclude_none=True, by_alias=True))


@admin_router.delete("", response_model=ResponseData)
async def delete_tag(post_body: PostTagData) -> JSONResponse:
    """删除某个标签"""
    if not await TagManager.get_tag_by_name(post_body.tag):
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=ResponseData(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="[Tag] Tag does not exist.",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))
    try:
        await TagManager.delete_tag(post_body)
    except Exception as e:  # noqa: BLE001
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=ResponseData(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=f"[Tag] Delete tag failed: {e!s}",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))
    return JSONResponse(status_code=status.HTTP_200_OK, content=ResponseData(
        code=status.HTTP_200_OK,
        message="[Tag] Delete tag success.",
        result={},
    ).model_dump(exclude_none=True, by_alias=True))
