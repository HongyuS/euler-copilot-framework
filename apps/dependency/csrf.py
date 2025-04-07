"""
CSRF Token校验

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

from fastapi import HTTPException, Request, Response, status

from apps.common.config import Config
from apps.manager.session import SessionManager


async def verify_csrf_token(request: Request, response: Response) -> Response | None:
    """验证CSRF Token"""
    if not Config().get_config().fastapi.csrf:
        return None

    csrf_token = request.headers["x-csrf-token"].strip('"')
    session = request.cookies["ECSESSION"]

    if not await SessionManager.verify_csrf_token(session, csrf_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token is invalid.")

    new_csrf_token = await SessionManager.create_csrf_token(session)
    if not new_csrf_token:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Renew CSRF token failed.")

    if Config().get_config().deploy.cookie == "DEBUG":
        response.set_cookie("_csrf_tk", new_csrf_token, max_age=Config().get_config().fastapi.session_ttl * 60,
                            domain=Config().get_config().fastapi.domain)
    else:
        response.set_cookie("_csrf_tk", new_csrf_token, max_age=Config().get_config().fastapi.session_ttl * 60,
                            secure=True, domain=Config().get_config().fastapi.domain, samesite="strict")
    return response

