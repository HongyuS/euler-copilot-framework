# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""用户鉴权"""

import logging

from starlette import status
from starlette.exceptions import HTTPException
from starlette.requests import HTTPConnection

from apps.common.config import config
from apps.services.personal_token import PersonalTokenManager
from apps.services.session import SessionManager
from apps.services.user import UserManager

logger = logging.getLogger(__name__)


async def verify_personal_token(request: HTTPConnection) -> None:
    """
    验证Personal Token是否有效；作为第一层鉴权检查

    - 如果Authorization头不存在，抛出401
    - 如果Authorization头存在，检测是否为合法的API Key
    - 合法则设置user_sub，不合法则不抛出异常（由后续依赖处理）

    :param request: HTTP请求
    :return:
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="鉴权失败")

    # 尝试验证是否为合法的Personal Token
    user_sub = await PersonalTokenManager.get_user_by_personal_token(auth_header)
    if user_sub is not None:
        request.state.user_sub = user_sub
    # 不合法时不抛出异常，由verify_session继续处理


async def verify_session(request: HTTPConnection) -> None:
    """
    验证Session是否已鉴权；作为第二层鉴权检查

    - 如果已经通过verify_personal_token设置了user_sub，则跳过
    - 如果Authorization不以Bearer开头，抛出401
    - 如果不是合法session，抛出401
    - 是合法session则设置user

    :param request: HTTP请求
    :return:
    """
    # 如果已经通过Personal Token验证，则跳过
    if hasattr(request.state, "user_sub"):
        return

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session 鉴权失败：需要Bearer token",
        )

    session_id = auth_header.split(" ", 1)[1]
    request.state.session_id = session_id
    user = await SessionManager.get_user(session_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session ID 鉴权失败",
        )
    request.state.user_sub = user

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
