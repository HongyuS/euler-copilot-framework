"""
FastAPI 用户认证相关路由

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse

from apps.common.config import Config
from apps.common.oidc import oidc_provider
from apps.constants import SESSION_TTL
from apps.dependency import get_user, verify_csrf_token, verify_user
from apps.entities.collection import Audit
from apps.entities.response_data import (
    AuthUserMsg,
    AuthUserRsp,
    OidcRedirectMsg,
    OidcRedirectRsp,
    ResponseData,
)
from apps.manager.audit_log import AuditLogManager
from apps.manager.session import SessionManager
from apps.manager.token import TokenManager
from apps.manager.user import UserManager

router = APIRouter(
    prefix="/api/auth",
    tags=["auth"],
)
logger = logging.getLogger(__name__)


@router.get("/login")
async def oidc_login(request: Request, code: str, redirect_index: str | None = None) -> RedirectResponse:
    """
    OIDC login

    :param request: Request object
    :param code: OIDC code
    :param redirect_index: redirect index
    :return: RedirectResponse
    """
    if redirect_index:
        response = RedirectResponse(redirect_index, status_code=status.HTTP_301_MOVED_PERMANENTLY)
    else:
        response = RedirectResponse("/", status_code=status.HTTP_301_MOVED_PERMANENTLY)
    try:
        token = await oidc_provider.get_oidc_token(code)
        user_info = await oidc_provider.get_oidc_user(token["access_token"])

        user_sub: str | None = user_info.get("user_sub", None)
        if user_sub:
            await oidc_provider.set_token(user_sub, token["access_token"], token["refresh_token"])
    except Exception as e:
        logger.exception("User login failed")
        if "auth error" in str(e):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="auth error") from e
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User login failed.") from e

    user_host = None
    if request.client is not None:
        user_host = request.client.host

    if not user_sub:
        logger.error("OIDC no user_sub associated.")
        data = Audit(
            http_method="get",
            module="auth",
            client_ip=user_host,
            message="/api/auth/login: OIDC no user_sub associated.",
        )
        await AuditLogManager.add_audit_log(data)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User login failed.")

    await UserManager.update_userinfo_by_user_sub(user_sub)

    try:
        current_session = request.cookies["ECSESSION"]
        await SessionManager.delete_session(current_session)
    except Exception:
        logger.exception("Change session failed")

    current_session = await SessionManager.create_session(user_host, user_sub)
    new_csrf_token = await SessionManager.create_csrf_token(current_session)
    if Config().get_config().deploy.mode == "debug":
        response.set_cookie(
            "_csrf_tk",
            new_csrf_token,
        )
        response.set_cookie(
            "ECSESSION",
            current_session,
        )
    else:
        response.set_cookie(
            "_csrf_tk",
            new_csrf_token,
            max_age=SESSION_TTL * 60,
            secure=True,
            domain=Config().get_config().fastapi.domain,
            samesite="strict",
        )
        response.set_cookie(
            "ECSESSION",
            current_session,
            max_age=SESSION_TTL * 60,
            secure=True,
            domain=Config().get_config().fastapi.domain,
            httponly=True,
            samesite="strict",
        )
    data = Audit(
        user_sub=user_sub,
        http_method="get",
        module="auth",
        client_ip=user_host,
        message="/api/auth/login: User login.",
    )

    await AuditLogManager.add_audit_log(data)
    return response


# 用户主动logout
@router.get("/logout", dependencies=[Depends(verify_csrf_token)], response_model=ResponseData)
async def logout(request: Request, response: Response, user_sub: Annotated[str, Depends(get_user)]) -> JSONResponse:
    """用户登出EulerCopilot"""
    session_id = request.cookies["ECSESSION"]
    if not request.client:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ResponseData(
                code=status.HTTP_400_BAD_REQUEST,
                message="IP error",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )
    await TokenManager.delete_plugin_token(user_sub)
    await SessionManager.delete_session(session_id)
    new_session = await SessionManager.create_session(request.client.host)

    response.set_cookie(
        "ECSESSION",
        new_session,
        max_age=SESSION_TTL * 60,
        httponly=True,
        secure=True,
        samesite="strict",
        domain=Config().get_config().fastapi.domain,
    )
    response.delete_cookie("_csrf_tk")

    data = Audit(
        http_method="get",
        module="auth",
        client_ip=request.client.host,
        user_sub=user_sub,
        message="/api/auth/logout: User logout succeeded.",
    )
    await AuditLogManager.add_audit_log(data)

    await oidc_provider.oidc_logout(request.cookies)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=ResponseData(
            code=status.HTTP_200_OK,
            message="success",
            result={},
        ).model_dump(exclude_none=True, by_alias=True),
    )


@router.get("/redirect", response_model=OidcRedirectRsp)
async def oidc_redirect(request: Request, action: Annotated[str, Query()] = "login") -> JSONResponse:
    """OIDC重定向URL"""
    if action == "login":
        redirect_url = await oidc_provider.get_redirect_url()
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=OidcRedirectRsp(
                code=status.HTTP_200_OK,
                message="success",
                result=OidcRedirectMsg(url=redirect_url),
            ).model_dump(exclude_none=True, by_alias=True),
        )
    if action == "logout":
        await oidc_provider.oidc_logout(request.cookies)
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=OidcRedirectRsp(
                code=status.HTTP_200_OK,
                message="success",
                result=OidcRedirectMsg(url=Config().get_config().fastapi.domain),
            ).model_dump(exclude_none=True, by_alias=True),
        )
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=ResponseData(
            code=status.HTTP_400_BAD_REQUEST,
            message="invalid action",
            result={},
        ).model_dump(exclude_none=True, by_alias=True),
    )


# TODO(zwt): OIDC主动触发logout
# 002
@router.post("/logout", dependencies=[Depends(verify_user)], response_model=ResponseData)
async def oidc_logout(token: str) -> JSONResponse:
    """OIDC主动触发登出"""


@router.get("/user", response_model=AuthUserRsp)
async def userinfo(
    user_sub: Annotated[str, Depends(get_user)], _: Annotated[None, Depends(verify_user)],
) -> JSONResponse:
    """获取用户信息"""
    user = await UserManager.get_userinfo_by_user_sub(user_sub=user_sub)
    if not user:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseData(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="Get UserInfo failed.",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=AuthUserRsp(
            code=status.HTTP_200_OK,
            message="success",
            result=AuthUserMsg(
                user_sub=user_sub,
                revision=user.is_active,
            ),
        ).model_dump(exclude_none=True, by_alias=True),
    )


@router.post(
    "/update_revision_number",
    dependencies=[Depends(verify_user), Depends(verify_csrf_token)],
    response_model=AuthUserRsp,
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ResponseData},
    },
)
async def update_revision_number(_post_body, user_sub: Annotated[str, Depends(get_user)]) -> JSONResponse:
    """更新用户协议信息"""
    ret: bool = await UserManager.update_userinfo_by_user_sub(user_sub, refresh_revision=True)
    if not ret:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseData(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="update revision failed",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=AuthUserRsp(
            code=status.HTTP_200_OK,
            message="success",
            result=AuthUserMsg(
                user_sub=user_sub,
                revision=False,
            ),
        ).model_dump(exclude_none=True, by_alias=True),
    )
