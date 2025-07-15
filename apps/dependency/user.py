# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""用户鉴权"""

import logging

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from starlette import status
from starlette.exceptions import HTTPException
from starlette.requests import HTTPConnection

from apps.services.personal_token import PersonalTokenManager
from apps.services.session import SessionManager

logger = logging.getLogger(__name__)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


async def _extract_session_id(request: HTTPConnection) -> str | None:
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


async def verify_user(request: HTTPConnection) -> None:
    """
    验证Session是否已鉴权；未鉴权则抛出HTTP 401；接口级dependence

    :param request: HTTP请求
    :return: None
    """
    request.state.session_id = await get_session(request)


async def get_session(request: HTTPConnection) -> str:
    """
    验证Session是否已鉴权，并返回Session ID；未鉴权则抛出HTTP 401；参数级dependence

    :param request: HTTP请求
    :return: Session ID
    """
    session_id = await _extract_session_id(request)
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session ID 不存在",
        )
    if not await SessionManager.verify_user(session_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session ID 鉴权失败",
        )
    return session_id


async def get_user(request: HTTPConnection) -> str:
    """
    验证Session是否已鉴权；若已鉴权，查询对应的user_sub；若未鉴权，抛出HTTP 401；参数级dependence

    :param request: HTTP请求体
    :return: 用户sub
    """
    session_id = await _extract_session_id(request)
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session ID 不存在",
        )

    user_sub = await SessionManager.get_user(session_id)
    if not user_sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session ID 鉴权失败",
        )

    request.state.user_sub = user_sub
    request.state.session_id = session_id
    return user_sub


async def verify_personal_token(personal_token: str = Depends(oauth2_scheme)) -> None:
    """
    验证Personal Token是否有效；无效则抛出HTTP 401；接口级dependence

    :param personal_token: Personal Token
    :return:
    """
    if not await PersonalTokenManager.verify_personal_token(personal_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Personal Token!")


async def get_personal_token_user(personal_token: str = Depends(oauth2_scheme)) -> str:
    """
    验证Personal Token是否有效；若有效，返回对应的user_sub；若无效，抛出HTTP 401；参数级dependence

    :param personal_token: Personal Token
    :return: 用户sub
    """
    user_sub = await PersonalTokenManager.get_user_by_personal_token(personal_token)
    if user_sub is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Personal Token!")
    return user_sub
