"""OpenEuler OIDC Provider"""

import logging
from typing import Any

import aiohttp
from fastapi import status

from apps.common.config import Config
from apps.common.oidc_provider.base import OIDCProviderBase
from apps.entities.config import OIDCConfig

logger = logging.getLogger(__name__)


class OpenEulerOIDCProvider(OIDCProviderBase):
    """OpenEuler OIDC Provider"""

    @classmethod
    def _get_login_config(cls) -> OIDCConfig:
        """获取并验证登录配置"""
        login_config = Config().get_config().login.settings
        if not isinstance(login_config, OIDCConfig):
            err = "OpenEuler OIDC配置错误"
            raise TypeError(err)
        return login_config


    @classmethod
    async def get_oidc_token(cls, code: str) -> dict[str, Any]:
        """获取OIDC Token"""
        login_config = cls._get_login_config()

        data = {
            "client_id": login_config.app_id,
            "client_secret": login_config.app_secret,
            "redirect_uri": login_config.login_api,
            "grant_type": "authorization_code",
            "code": code,
        }
        url = await cls.get_access_token_url()
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }
        result = None
        async with (
            aiohttp.ClientSession() as session,
            session.post(url, headers=headers, data=data, timeout=aiohttp.ClientTimeout(total=10)) as resp,
        ):
            if resp.status != status.HTTP_200_OK:
                err = f"[OpenEuler] 获取OIDC Token失败: {resp.status}，完整输出: {await resp.text()}"
                raise RuntimeError(err)
            logger.info("[OpenEuler] 获取OIDC Token成功: %s", await resp.text())
            result = await resp.json()
        return {
            "access_token": result["access_token"],
            "refresh_token": result["refresh_token"],
        }


    @classmethod
    async def get_oidc_user(cls, access_token: str) -> dict:
        """获取OIDC用户"""
        login_config = cls._get_login_config()

        if not access_token:
            err = "Access token is empty."
            raise RuntimeError(err)
        url = login_config.host_inner.rstrip("/") + "/oneid/oidc/user"
        headers = {
            "Authorization": access_token,
        }

        result = None
        async with (
            aiohttp.ClientSession() as session,
            session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp,
        ):
            if resp.status != status.HTTP_200_OK:
                err = f"[OpenEuler] 获取OIDC用户失败: {resp.status}，完整输出: {await resp.text()}"
                raise RuntimeError(err)
            logger.info("[OpenEuler] 获取OIDC用户成功: %s", await resp.text())
            result = await resp.json()

        if not result["phone_number_verified"]:
            err = "Could not validate credentials."
            raise RuntimeError(err)

        return {
            "user_sub": result["sub"],
        }


    @classmethod
    async def get_login_status(cls, _cookie: dict[str, str]) -> dict[str, Any]:
        """检查登录状态"""
        return {}


    @classmethod
    async def oidc_logout(cls, _cookie: dict[str, str]) -> None:
        """触发OIDC的登出"""
        ...


    @classmethod
    async def get_redirect_url(cls) -> str:
        """获取OpenEuler OIDC 重定向URL"""
        login_config = cls._get_login_config()
        return (f"{login_config.host.rstrip('/')}/oneid/oidc/authorize"
                f"?client_id={login_config.app_id}"
                f"&response_type=code&access_type=offline&redirect_uri={login_config.login_api}"
                "&scope=openid+profile+email+phone+offline_access")


    @classmethod
    async def get_access_token_url(cls) -> str:
        """获取OpenEuler OIDC 访问Token URL"""
        login_config = cls._get_login_config()
        return login_config.host_inner.rstrip("/") + "/oneid/oidc/token"
