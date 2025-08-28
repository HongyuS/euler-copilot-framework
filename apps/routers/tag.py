# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""FastAPI 用户标签相关API"""

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

from apps.dependency.user import verify_admin, verify_personal_token, verify_session
from apps.schemas.request_data import PostTagData
from apps.schemas.response_data import ResponseData
from apps.services.tag import TagManager

admin_router = APIRouter(
    prefix="/api/admin/tag",
    tags=["tag"],
    dependencies=[
        Depends(verify_session),
        Depends(verify_personal_token),
        Depends(verify_admin),
    ],
)
router = APIRouter(
    prefix="/api/tag",
    tags=["tag"],
    dependencies=[
        Depends(verify_session),
        Depends(verify_personal_token),
    ],
)


@router.get("")
async def get_user_tag(
    request: Request,
    *,
    user_only: bool = False,
) -> JSONResponse:
    """获取所有标签；传入user_sub的时候获取特定用户的标签信息，不传则获取所有标签"""
    if user_only:
        return JSONResponse(status_code=status.HTTP_200_OK, content=ResponseData(
            code=status.HTTP_200_OK,
            message="[Tag] Get user tag success.",
            result=await TagManager.get_tag_by_user_sub(request.state.user_sub),
        ).model_dump(exclude_none=True, by_alias=True))
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
