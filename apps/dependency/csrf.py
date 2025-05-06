"""
CSRF Token校验

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

from fastapi import Depends, HTTPException, Request, status

from apps.common.config import Config
from apps.dependency.user import get_session
from apps.manager.session import SessionManager


async def verify_csrf_token(request: Request, session: str = Depends(get_session)) -> None:
    """验证CSRF Token"""
    if not Config().get_config().fastapi.csrf:
        return

    csrf_token = request.headers["x-csrf-token"].strip('"')

    if not await SessionManager.verify_csrf_token(session, csrf_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token is invalid.")
