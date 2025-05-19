"""
浏览器Session Manager

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

import logging
import secrets
from datetime import UTC, datetime, timedelta

from apps.common.config import Config
from apps.constants import SESSION_TTL
from apps.entities.config import FixedUserConfig
from apps.entities.session import Session
from apps.exceptions import LoginSettingsError, SessionError
from apps.manager.blacklist import UserBlacklistManager
from apps.models.mongo import MongoDB

logger = logging.getLogger(__name__)


class SessionManager:
    """浏览器Session管理"""

    @staticmethod
    async def create_session(ip: str | None = None, user_sub: str | None = None) -> str:
        """创建浏览器Session"""
        if not ip:
            err = "用户IP错误！"
            raise ValueError(err)

        session_id = secrets.token_hex(16)
        data = Session(
            _id=session_id,
            ip=ip,
            expired_at=datetime.now(UTC) + timedelta(minutes=SESSION_TTL),
        )
        if Config().get_config().login.provider == "disable":
            login_settings = Config().get_config().login.settings
            if not isinstance(login_settings, FixedUserConfig):
                err = "固定用户配置错误！"
                raise LoginSettingsError(err)
            data.user_sub = login_settings.user_id

        if user_sub is not None:
            data.user_sub = user_sub

        try:
            collection = MongoDB().get_collection("session")
            await collection.insert_one(data.model_dump(exclude_none=True, by_alias=True))
            await collection.create_index(
                "expired_at", expireAfterSeconds=0,
            )
        except Exception as e:
            err = "创建浏览器Session失败"
            logger.exception("[SessionManager] %s", err)
            raise SessionError(err) from e
        return session_id

    @staticmethod
    async def delete_session(session_id: str) -> None:
        """删除浏览器Session"""
        if not session_id:
            return
        try:
            collection = MongoDB().get_collection("session")
            await collection.delete_one({"_id": session_id})
        except Exception as e:
            err = "删除浏览器Session失败"
            logger.exception("[SessionManager] %s", err)
            raise SessionError(err) from e

    @staticmethod
    async def get_session(session_id: str, session_ip: str) -> str:
        """获取浏览器Session"""
        if not session_id:
            return await SessionManager.create_session(session_ip)

        ip = None
        try:
            collection = MongoDB().get_collection("session")
            data = await collection.find_one({"_id": session_id})
            if not data:
                return await SessionManager.create_session(session_ip)
            ip = Session(**data).ip
        except Exception as e:
            err = "读取浏览器Session失败"
            logger.exception("[SessionManager] %s", err)
            raise SessionError(err) from e

        if not ip or ip != session_ip:
            return await SessionManager.create_session(session_ip)
        return session_id

    @staticmethod
    async def verify_user(session_id: str) -> bool:
        """验证用户是否在Session中"""
        try:
            collection = MongoDB().get_collection("session")
            data = await collection.find_one({"_id": session_id})
            if not data:
                return False
            return Session(**data).user_sub is not None
        except Exception as e:
            err = "用户不在Session中"
            logger.exception("[SessionManager] %s", err)
            raise SessionError(err) from e

    @staticmethod
    async def get_user(session_id: str) -> str | None:
        """从Session中获取用户"""
        try:
            collection = MongoDB().get_collection("session")
            data = await collection.find_one({"_id": session_id})
            if not data:
                return None
            user_sub = Session(**data).user_sub
        except Exception as e:
            err = "从Session中获取用户失败"
            logger.exception("[SessionManager] %s", err)
            raise SessionError(err) from e

        # 查询黑名单
        if user_sub and await UserBlacklistManager.check_blacklisted_users(user_sub):
            logger.error("用户在Session黑名单中")
            try:
                await collection.delete_one({"_id": session_id})
            except Exception as e:
                err = "从Session中删除用户失败"
                logger.exception("[SessionManager] %s", err)
                raise SessionError(err) from e
            return None

        return user_sub

    @staticmethod
    async def get_session_by_user_sub(user_sub: str) -> str | None:
        """根据用户sub获取Session"""
        try:
            collection = MongoDB().get_collection("session")
            data = await collection.find_one({"user_sub": user_sub})
            if not data:
                return None
            return Session(**data).id
        except Exception as e:
            err = "从Session中获取用户失败"
            logger.exception("[SessionManager] %s", err)
            raise SessionError(err) from e
