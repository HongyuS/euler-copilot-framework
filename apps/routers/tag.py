# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""FastAPI 用户标签相关API"""

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from apps.dependency.user import verify_user
from apps.schemas.request_data import PostTagData
from apps.schemas.response_data import ResponseData
from apps.services.tag import TagManager

router = APIRouter(
    prefix="/api/tag",
    tags=["tag"],
    dependencies=[
        Depends(verify_user),
    ],
)


@router.post("", response_model=ResponseData)
async def add_tags(post_body: PostTagData) -> JSONResponse:
    """添加用户标签"""
    if await TagManager.get_tag_by_name(post_body.tag):
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=ResponseData(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="[Tag] Add tag name is exist.",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))

    try:
        await TagManager.add_tag(post_body)
    except Exception as e:  # noqa: BLE001
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=ResponseData(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=f"[Tag] Add tag failed: {e!s}",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))
    return JSONResponse(status_code=status.HTTP_200_OK, content=ResponseData(
        code=status.HTTP_200_OK,
        message="[Tag] Add tag success.",
        result={},
    ).model_dump(exclude_none=True, by_alias=True))


@router.put("", response_model=ResponseData)
async def update_tag(post_body: PostTagData) -> JSONResponse:
    """更新用户领域画像"""
    if not await TagManager.get_tag_by_name(post_body.tag):
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=ResponseData(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="[Tag] Update tag name is not exist.",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))
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


@router.delete("", response_model=ResponseData)
async def delete_tag(post_body: PostTagData) -> JSONResponse:
    """删除用户领域画像"""
    if not await TagManager.get_tag_by_name(post_body.tag):
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=ResponseData(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="[Tag] Delete tag name is not exist.",
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
