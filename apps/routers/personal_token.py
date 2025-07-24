# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""FastAPI API Key相关路由"""

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

from apps.dependency.user import verify_personal_token, verify_session
from apps.schemas.personal_token import PostPersonalTokenMsg, PostPersonalTokenRsp
from apps.schemas.response_data import ResponseData
from apps.services.personal_token import PersonalTokenManager

router = APIRouter(
    prefix="/api/auth/key",
    tags=["key"],
    dependencies=[
        Depends(verify_session),
        Depends(verify_personal_token),
    ],
)


@router.post("", responses={
    400: {"model": ResponseData},
}, response_model=PostPersonalTokenRsp)
async def change_personal_token(request: Request) -> JSONResponse:
    """管理用户的API密钥"""
    new_api_key: str | None = await PersonalTokenManager.update_personal_token(request.state.user_sub)
    if not new_api_key:
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=ResponseData(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="failed to update personal token",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))

    return JSONResponse(status_code=status.HTTP_200_OK, content=PostPersonalTokenRsp(
        code=status.HTTP_200_OK,
        message="success",
        result=PostPersonalTokenMsg(
            api_key=new_api_key,
        ),
    ).model_dump(exclude_none=True, by_alias=True))
