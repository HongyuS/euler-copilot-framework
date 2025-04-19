"""
工具：API调用

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

import json
import logging
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any, Self

import aiohttp
from fastapi import status
from pydantic import Field

from apps.common.oidc import oidc_provider
from apps.entities.enum_var import CallOutputType, ContentType, HTTPMethod
from apps.entities.flow import ServiceMetadata
from apps.entities.scheduler import (
    CallError,
    CallInfo,
    CallOutputChunk,
    CallVars,
)
from apps.manager.service import ServiceCenterManager
from apps.manager.token import TokenManager
from apps.scheduler.call.api.schema import APIInput, APIOutput
from apps.scheduler.call.core import CoreCall

if TYPE_CHECKING:
    from apps.scheduler.executor.step import StepExecutor


logger = logging.getLogger(__name__)
SUCCESS_HTTP_CODES = [
    status.HTTP_200_OK,
    status.HTTP_201_CREATED,
    status.HTTP_202_ACCEPTED,
    status.HTTP_203_NON_AUTHORITATIVE_INFORMATION,
    status.HTTP_204_NO_CONTENT,
    status.HTTP_205_RESET_CONTENT,
    status.HTTP_206_PARTIAL_CONTENT,
    status.HTTP_207_MULTI_STATUS,
    status.HTTP_208_ALREADY_REPORTED,
    status.HTTP_226_IM_USED,
    status.HTTP_301_MOVED_PERMANENTLY,
    status.HTTP_302_FOUND,
    status.HTTP_303_SEE_OTHER,
    status.HTTP_304_NOT_MODIFIED,
    status.HTTP_307_TEMPORARY_REDIRECT,
    status.HTTP_308_PERMANENT_REDIRECT,
]


class API(CoreCall, input_model=APIInput, output_model=APIOutput):
    """API调用工具"""

    url: str = Field(description="API接口的完整URL")
    method: HTTPMethod = Field(description="API接口的HTTP Method")
    content_type: ContentType = Field(description="API接口的Content-Type")
    timeout: int = Field(description="工具超时时间", default=300, gt=30)

    body: dict[str, Any] = Field(description="已知的部分请求体", default={})
    query: dict[str, Any] = Field(description="已知的部分请求参数", default={})


    @classmethod
    def info(cls) -> CallInfo:
        """返回Call的名称和描述"""
        return CallInfo(name="API调用", description="向某一个API接口发送HTTP请求，获取数据。")


    async def _init(self, call_vars: CallVars) -> APIInput:
        """初始化API调用工具"""
        # 获取对应API的Service Metadata
        try:
            service_metadata = await ServiceCenterManager.get_service_data(
                call_vars.ids.user_sub, self.node.service_id or "",
            )
            service_metadata = ServiceMetadata.model_validate(service_metadata)
        except Exception as e:
            raise CallError(
                message="API接口的Service Metadata获取失败",
                data={},
            ) from e

        # 获取Service对应的Auth
        self._auth = service_metadata.api.auth
        self._session_id = call_vars.ids.session_id
        self._service_id = call_vars.ids.service_id

        return APIInput(
            url=self.url,
            method=self.method,
            query=self.query,
            body=self.body,
        )


    async def _exec(self, input_data: dict[str, Any]) -> AsyncGenerator[CallOutputChunk, None]:
        """调用API，然后返回LLM解析后的数据"""
        self._session = aiohttp.ClientSession()
        self._timeout = aiohttp.ClientTimeout(total=self.timeout)
        try:
            result = await self._call_api(input_data)
            yield CallOutputChunk(
                type=CallOutputType.DATA,
                content=result.model_dump(exclude_none=True, by_alias=True),
            )
        finally:
            await self._session.close()


    async def _make_api_call(self, data: dict | None, files: aiohttp.FormData):  # noqa: ANN202
        """组装API请求Session"""
        # 获取必要参数
        req_header = {
            "Content-Type": self.content_type.value,
        }
        req_cookie = {}
        req_params = {}

        data = data or {}

        if self._auth:
            if self._auth.header:
                for item in self._auth.header:
                    req_header[item.name] = item.value
            elif self._auth.cookie:
                for item in self._auth.cookie:
                    req_cookie[item.name] = item.value
            elif self._auth.query:
                for item in self._auth.query:
                    req_params[item.name] = item.value
            elif self._auth.oidc:
                token = await TokenManager.get_plugin_token(
                    self._service_id,
                    self._session_id,
                    await oidc_provider.get_access_token_url(),
                    30,
                )
                req_header.update({"access-token": token})

        if self.method in ["get", "delete"]:
            req_params.update(data)
            return self._session.request(
                self.method,
                self.url,
                params=req_params,
                headers=req_header,
                cookies=req_cookie,
                timeout=self._timeout,
            )

        if self.method in ["post", "put", "patch"]:
            if self.content_type == "form":
                form_data = files
                for key, val in data.items():
                    form_data.add_field(key, val)
                return self._session.request(
                    self.method,
                    self.url,
                    data=form_data,
                    headers=req_header,
                    cookies=req_cookie,
                    timeout=self._timeout,
                )
            return self._session.request(
                self.method,
                self.url,
                json=data,
                headers=req_header,
                cookies=req_cookie,
                timeout=self._timeout,
            )

        err = "Method not implemented."
        raise NotImplementedError(err)

    async def _call_api(self, final_data: dict[str, Any] | None = None) -> APIOutput:
        """实际调用API，并处理返回值"""
        # 获取必要参数
        logger.info("[API] 调用接口 %s，请求数据为 %s", self.url, final_data)

        session_context = await self._make_api_call(final_data, aiohttp.FormData())
        async with session_context as response:
            if response.status in SUCCESS_HTTP_CODES:
                text = f"API发生错误：API返回状态码{response.status}, 原因为{response.reason}。"
                logger.error(text)
                raise CallError(
                    message=text,
                    data={"api_response_data": await response.text()},
                )

            response_status = response.status
            response_data = await response.text()

        logger.info("[API] 调用接口 %s，结果为 %s", self.url, response_data)

        # 如果没有返回结果
        if not response_data:
            return APIOutput(
                http_code=response_status,
                result={},
            )

        # 如果返回值是JSON
        try:
            response_dict = json.loads(response_data)
        except Exception:
            logger.exception("[API] 返回值不是JSON格式！")

        return APIOutput(
            http_code=response_status,
            result=response_dict,
        )
