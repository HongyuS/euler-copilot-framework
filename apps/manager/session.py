"""
浏览器Session Manager

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

import base64
import hashlib
import hmac
import logging
import secrets
from datetime import UTC, datetime, timedelta

from apps.common.config import Config
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
            expired_at=datetime.now(UTC) + timedelta(minutes=Config().get_config().fastapi.session_ttl),
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
    async def create_csrf_token(session_id: str) -> str:
        """创建CSRF Token"""
        rand = secrets.token_hex(8)

        try:
            collection = MongoDB().get_collection("session")
            await collection.update_one({"_id": session_id}, {"$set": {"nonce": rand}})
        except Exception as e:
            err = "创建CSRF Token失败"
            logger.exception("[SessionManager] %s", err)
            raise SessionError(err) from e

        csrf_value = f"{session_id}{rand}"
        csrf_b64 = base64.b64encode(bytes.fromhex(csrf_value))

        jwt_key = base64.b64decode(Config().get_config().security.jwt_key)
        hmac_processor = hmac.new(key=jwt_key, msg=csrf_b64, digestmod=hashlib.sha256)
        signature = base64.b64encode(hmac_processor.digest())

        csrf_b64 = csrf_b64.decode("utf-8")
        signature = signature.decode("utf-8")
        return f"{csrf_b64}.{signature}"

    @staticmethod
    async def verify_csrf_token(session_id: str, token: str) -> bool:
        """验证CSRF Token"""
        if not token:
            return False

        token_msg = token.split(".")
        if len(token_msg) != 2:  # noqa: PLR2004
            return False

        first_part = base64.b64decode(token_msg[0]).hex()
        current_session_id = first_part[:32]
        logger.error("current_session_id: %s, session_id: %s", current_session_id, session_id)
        if current_session_id != session_id:
            return False

        current_nonce = first_part[32:]
        try:
            collection = MongoDB().get_collection("session")
            data = await collection.find_one({"_id": session_id})
            if not data:
                return False
            nonce = Session(**data).nonce
            if nonce != current_nonce:
                return False
        except Exception as e:
            err = "从Session中获取CSRF Token失败"
            logger.exception("[SessionManager] %s", err)
            raise SessionError(err) from e

        jwt_key = base64.b64decode(Config().get_config().security.jwt_key)
        hmac_obj = hmac.new(key=jwt_key, msg=token_msg[0].encode("utf-8"), digestmod=hashlib.sha256)
        signature = hmac_obj.digest()
        current_signature = base64.b64decode(token_msg[1])

        return hmac.compare_digest(signature, current_signature)
