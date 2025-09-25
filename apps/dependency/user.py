# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""用户鉴权"""

import logging

from starlette import status
from starlette.exceptions import HTTPException
from starlette.requests import HTTPConnection

from apps.common.config import config
from apps.services import PersonalTokenManager, SessionManager, UserManager

logger = logging.getLogger(__name__)


async def _extract_data(request: HTTPConnection) -> str | None:
    """
    从请求中获取 session_id

    :param request: HTTP请求
    :return: session_id
    """
    session_id = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        session_id = auth_header.split(" ", 1)[1]

    return session_id


async def verify_session(request: HTTPConnection) -> None:
    """
    验证Session是否已鉴权，并返回Session ID；未鉴权则抛出HTTP 401

    :param request: HTTP请求
    :return: Session ID
    """
    session_id = await _extract_data(request)
    if not session_id:
        return

    request.state.session_id = session_id
    user = await SessionManager.get_user(session_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session ID 鉴权失败",
        )
    request.state.user_sub = user


async def verify_personal_token(request: HTTPConnection) -> None:
    """
    验证Personal Token是否有效；无效则抛出HTTP 401；接口级dependence

    :param request: HTTP请求
    :return:
    """
    personal_token = request.headers.get("Authorization")
    if not personal_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="鉴权失败")

    user_sub = await PersonalTokenManager.get_user_by_personal_token(personal_token)
    if user_sub is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Personal Token 无效")
    request.state.user_sub = user_sub


async def verify_admin(request: HTTPConnection) -> None:
    """验证用户是否为管理员"""
    if not hasattr(request.state, "user_sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户未登录")
    user_sub = request.state.user_sub
    user = await UserManager.get_user(user_sub)
    request.state.user = user
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
    if user.userSub not in config.login.admin_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户无权限")
