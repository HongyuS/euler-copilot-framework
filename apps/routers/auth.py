# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""FastAPI 用户认证相关路由"""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from apps.common.config import config
from apps.common.oidc import oidc_provider
from apps.dependency import verify_personal_token, verify_session
from apps.schemas.response_data import (
    AuthUserMsg,
    AuthUserRsp,
    OidcRedirectMsg,
    OidcRedirectRsp,
    ResponseData,
)
from apps.services.session import SessionManager
from apps.services.token import TokenManager
from apps.services.user import UserManager

router = APIRouter(
    prefix="/api/auth",
    tags=["auth"],
)
user_router = APIRouter(
    prefix="/api/user",
    tags=["user"],
    dependencies=[Depends(verify_session), Depends(verify_personal_token)],
)
logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


@router.get("/login")
async def oidc_login(request: Request, code: str) -> HTMLResponse:
    """
    OIDC login

    :param request: Request object
    :param code: OIDC code
    :return: HTMLResponse
    """
    try:
        token = await oidc_provider.get_oidc_token(code)
        user_info = await oidc_provider.get_oidc_user(token["access_token"])

        user_sub: str | None = user_info.get("user_sub", None)
        if user_sub:
            await oidc_provider.set_token(user_sub, token["access_token"], token["refresh_token"])
    except Exception as e:
        logger.exception("User login failed")
        status_code = status.HTTP_400_BAD_REQUEST if "auth error" in str(e) else status.HTTP_403_FORBIDDEN
        return templates.TemplateResponse(
            "login_failed.html.j2",
            {"request": request, "reason": "无法验证登录信息，请关闭本窗口并重试。"},
            status_code=status_code,
        )

    if not request.client:
        return templates.TemplateResponse(
            "login_failed.html.j2",
            {"request": request, "reason": "无法获取用户信息，请关闭本窗口并重试。"},
            status_code=status.HTTP_403_FORBIDDEN,
        )
    user_host = request.client.host

    if not user_sub:
        logger.error("OIDC no user_sub associated.")
        return templates.TemplateResponse(
            "login_failed.html.j2",
            {"request": request, "reason": "未能获取用户信息，请关闭本窗口并重试。"},
            status_code=status.HTTP_403_FORBIDDEN,
        )

    await UserManager.update_user(user_sub)

    current_session = await SessionManager.create_session(user_sub, user_host)
    return templates.TemplateResponse(
        "login_success.html.j2",
        {"request": request, "current_session": current_session},
    )


# 用户主动logout
@user_router.get("/logout", response_model=ResponseData)
async def logout(request: Request) -> JSONResponse:
    """用户登出EulerCopilot"""
    if not request.client:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ResponseData(
                code=status.HTTP_400_BAD_REQUEST,
                message="IP error",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )
    await TokenManager.delete_plugin_token(request.state.user_sub)

    if hasattr(request.state, "session_id"):
        await SessionManager.delete_session(request.state.session_id)

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=ResponseData(
            code=status.HTTP_200_OK,
            message="success",
            result={},
        ).model_dump(exclude_none=True, by_alias=True),
    )


@router.get("/redirect", response_model=OidcRedirectRsp)
async def oidc_redirect() -> JSONResponse:
    """OIDC重定向URL"""
    redirect_url = await oidc_provider.get_redirect_url()
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=OidcRedirectRsp(
            code=status.HTTP_200_OK,
            message="success",
            result=OidcRedirectMsg(url=redirect_url),
        ).model_dump(exclude_none=True, by_alias=True),
    )


# TODO(zwt): OIDC主动触发logout
@router.post("/logout", response_model=ResponseData)
async def oidc_logout(token: str) -> JSONResponse:
    """OIDC主动触发登出"""
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=ResponseData(
            code=status.HTTP_200_OK,
            message="success",
            result={},
        ).model_dump(exclude_none=True, by_alias=True),
    )


@user_router.get("/user", response_model=AuthUserRsp)
async def userinfo(request: Request) -> JSONResponse:
    """获取用户信息"""
    user = await UserManager.get_user(user_sub=request.state.user_sub)
    if not user:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseData(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="Get UserInfo failed.",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )
    is_admin = user.userSub in config.login.admin_user
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=AuthUserRsp(
            code=status.HTTP_200_OK,
            message="success",
            result=AuthUserMsg(
                user_sub=request.state.user_sub,
                revision=user.isActive,
                is_admin=is_admin,
            ),
        ).model_dump(exclude_none=True, by_alias=True),
    )
