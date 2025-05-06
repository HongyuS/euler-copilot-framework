"""
FastAPI 用户认证相关路由

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import HTMLResponse, JSONResponse

from apps.common.config import Config
from apps.common.oidc import oidc_provider
from apps.dependency import get_session, get_user, verify_csrf_token, verify_user
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
        error_html = """<!DOCTYPE html>
<html><head><title>登录失败</title></head>
<body>
<h1>登录失败</h1>
<p>无法验证登录信息，请关闭本窗口并重试。</p>
</body></html>"""
        if "auth error" in str(e):
            return HTMLResponse(content=error_html, status_code=status.HTTP_400_BAD_REQUEST)
        return HTMLResponse(content=error_html, status_code=status.HTTP_403_FORBIDDEN)

    user_host = request.client.host if request.client else None

    if not user_sub:
        logger.error("OIDC no user_sub associated.")
        error_html = """<!DOCTYPE html>
<html><head><title>登录失败</title></head>
<body>
<h1>登录失败</h1>
<p>未能获取用户信息，请关闭本窗口并重试。</p>
</body></html>"""
        data = Audit(
            http_method="get",
            module="auth",
            client_ip=user_host,
            message="/api/auth/login: OIDC no user_sub associated.",
        )
        await AuditLogManager.add_audit_log(data)
        return HTMLResponse(content=error_html, status_code=status.HTTP_403_FORBIDDEN)

    await UserManager.update_userinfo_by_user_sub(user_sub)

    current_session = await SessionManager.create_session(user_host, user_sub)
    new_csrf_token = await SessionManager.create_csrf_token(current_session)

    data = Audit(
        user_sub=user_sub,
        http_method="get",
        module="auth",
        client_ip=user_host,
        message="/api/auth/login: User login.",
    )
    await AuditLogManager.add_audit_log(data)

    web_domain = Config().get_config().fastapi.domain
    scheme = "https" if Config().get_config().deploy.mode != "debug" else "http"
    target_origin_url = f"{scheme}://{web_domain}"
    target_origin_js = f"'{target_origin_url}'"

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>登录成功</title>
    <script>
        try {{
            const sessionId = "{current_session}";
            const csrfToken = "{new_csrf_token}";
            const targetOrigin = {target_origin_js};

            if (window.opener && window.opener !== window) {{
                console.log('发送认证信息到主窗口:', {{ sessionId, csrfToken }}, '目标源:', targetOrigin);
                window.opener.postMessage({{
                    type: 'auth_success',
                    session_id: sessionId,
                    csrf_token: csrfToken
                }}, targetOrigin);

                document.getElementById('message').innerText = "登录成功，窗口即将自动关闭…";
                setTimeout(window.close, 1500);
            }} else {{
                console.warn('未找到 window.opener 或 opener 等于自身，无法 postMessage。');
                document.getElementById('message').innerText = "登录成功，但未能自动返回主页面，请手动关闭本窗口。";
            }}
        }} catch (e) {{
            console.error("postMessage 脚本出错:", e);
            document.getElementById('message').innerText = "登录流程发生异常，请关闭本窗口并重试。";
        }}
    </script>
</head>
<body>
    <h1 id="message">正在处理登录…</h1>
</body>
</html>
"""
    return HTMLResponse(content=html_content)


# 用户主动logout
@router.get("/logout", response_model=ResponseData)
async def logout(
    request: Request,
    user_sub: Annotated[str, Depends(get_user)],
    session_id: Annotated[str, Depends(get_session)],
) -> JSONResponse:
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
    await TokenManager.delete_plugin_token(user_sub)
    await SessionManager.delete_session(session_id)

    data = Audit(
        http_method="get",
        module="auth",
        client_ip=request.client.host,
        user_sub=user_sub,
        message="/api/auth/logout: User logout succeeded.",
    )
    await AuditLogManager.add_audit_log(data)

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
# 002
@router.post("/logout", dependencies=[Depends(verify_user)], response_model=ResponseData)
async def oidc_logout(token: str) -> JSONResponse:
    """OIDC主动触发登出"""


@router.get("/user", response_model=AuthUserRsp)
async def userinfo(
    user_sub: Annotated[str, Depends(get_user)],
    _: Annotated[None, Depends(verify_user)],
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
