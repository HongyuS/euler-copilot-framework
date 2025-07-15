# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""FastAPI API Key相关路由"""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from apps.dependency.user import get_user, verify_user
from apps.schemas.personal_token import PostPersonalTokenMsg, PostPersonalTokenRsp
from apps.schemas.response_data import ResponseData
from apps.services.personal_token import PersonalTokenManager

router = APIRouter(
    prefix="/api/auth/key",
    tags=["key"],
    dependencies=[Depends(verify_user)],
)


@router.post("", responses={
    400: {"model": ResponseData},
}, response_model=PostPersonalTokenRsp)
async def manage_personal_token(action: str, user_sub: Annotated[str, Depends(get_user)]) -> JSONResponse:
    """管理用户的API密钥"""
    action = action.lower()
    if action == "update":
        api_key: str | None = await PersonalTokenManager.update_personal_token(user_sub)
    else:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content=ResponseData(
            code=status.HTTP_400_BAD_REQUEST,
            message="invalid request",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))
    return JSONResponse(status_code=status.HTTP_200_OK, content=PostPersonalTokenRsp(
        code=status.HTTP_200_OK,
        message="success",
        result=PostPersonalTokenMsg(
            api_key=api_key,
        ),
    ).model_dump(exclude_none=True, by_alias=True))
