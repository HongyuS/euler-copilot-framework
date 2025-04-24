"""
工具：API调用

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

import aiohttp
from aiohttp.client import _RequestContextManager
from fastapi import status
from pydantic import Field
from pydantic.json_schema import SkipJsonSchema

from apps.common.oidc import oidc_provider
from apps.entities.enum_var import CallOutputType, ContentType, HTTPMethod
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

    enable_filling: SkipJsonSchema[bool] = Field(description="是否需要进行自动参数填充", default=True)

    url: str = Field(description="API接口的完整URL")
    method: HTTPMethod = Field(description="API接口的HTTP Method")
    content_type: ContentType | None = Field(description="API接口的Content-Type", default=None)
    timeout: int = Field(description="工具超时时间", default=300, gt=30)

    body: dict[str, Any] = Field(description="已知的部分请求体", default={})
    query: dict[str, Any] = Field(description="已知的部分请求参数", default={})

    @classmethod
    def info(cls) -> CallInfo:
        """返回Call的名称和描述"""
        return CallInfo(name="API调用", description="向某一个API接口发送HTTP请求，获取数据。")

    async def _init(self, call_vars: CallVars) -> APIInput:
        """初始化API调用工具"""
        self._service_id = ""
        self._session_id = call_vars.ids.session_id
        self._auth = None

        if self.node:
            # 获取对应API的Service Metadata
            try:
                service_metadata = await ServiceCenterManager.get_service_metadata(
                    call_vars.ids.user_sub,
                    self.node.service_id or "",
                )
            except Exception as e:
                raise CallError(
                    message="API接口的Service Metadata获取失败",
                    data={},
                ) from e

            # 获取Service对应的Auth
            self._auth = service_metadata.api.auth
            self._service_id = self.node.service_id or ""

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
        input_obj = APIInput.model_validate(input_data)
        try:
            result = await self._call_api(input_obj)
            yield CallOutputChunk(
                type=CallOutputType.DATA,
                content=result.model_dump(exclude_none=True, by_alias=True),
            )
        finally:
            await self._session.close()

    async def _make_api_call(self, data: APIInput, files: aiohttp.FormData) -> _RequestContextManager:
        """组装API请求Session"""
        # 获取必要参数
        if self._auth:
            req_header, req_cookie, req_params = await self._apply_auth()
        else:
            req_header = {}
            req_cookie = {}
            req_params = {}

        if self.method in [HTTPMethod.GET.value, HTTPMethod.DELETE.value]:
            return await self._handle_query_request(data, req_header, req_cookie, req_params)

        if self.method in [HTTPMethod.POST.value, HTTPMethod.PUT.value, HTTPMethod.PATCH.value]:
            return await self._handle_body_request(data, files, req_header, req_cookie)

        raise CallError(
            message="API接口的HTTP Method不支持",
            data={},
        )

    async def _apply_auth(self) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
        """应用认证信息到请求参数中"""
        # self._auth可能是None或ServiceApiAuth类型
        # ServiceApiAuth类型包含header、cookie、query和oidc属性
        req_header = {}
        req_cookie = {}
        req_params = {}

        if self._auth.header:  # type: ignore[attr-defined] # 如果header列表非空
            for item in self._auth.header:  # type: ignore[attr-defined]
                req_header[item.name] = item.value
        elif self._auth.cookie:  # type: ignore[attr-defined] # 如果cookie列表非空
            for item in self._auth.cookie:  # type: ignore[attr-defined]
                req_cookie[item.name] = item.value
        elif self._auth.query:  # type: ignore[attr-defined] # 如果query列表非空
            for item in self._auth.query:  # type: ignore[attr-defined]
                req_params[item.name] = item.value
        elif self._auth.oidc:  # type: ignore[attr-defined] # 如果oidc配置存在
            token = await TokenManager.get_plugin_token(
                self._service_id,
                self._session_id,
                await oidc_provider.get_access_token_url(),
                30,
            )
            req_header.update({"access-token": token})

        return req_header, req_cookie, req_params

    async def _handle_query_request(
        self, data: APIInput, req_header: dict[str, str], req_cookie: dict[str, str], req_params: dict[str, str],
    ) -> _RequestContextManager:
        """处理GET和DELETE请求"""
        req_params.update(data.query)
        return self._session.request(
            self.method,
            self.url,
            params=req_params,
            headers=req_header,
            cookies=req_cookie,
            timeout=self._timeout,
        )

    async def _handle_body_request(
        self, data: APIInput, files: aiohttp.FormData, req_header: dict[str, str], req_cookie: dict[str, str],
    ) -> _RequestContextManager:
        """处理POST、PUT和PATCH请求"""
        if not self.content_type:
            raise CallError(
                message="API接口的Content-Type未指定",
                data={},
            )

        req_body = data.body

        if self.content_type in [ContentType.FORM_URLENCODED.value, ContentType.MULTIPART_FORM_DATA.value]:
            return await self._handle_form_request(req_body, files, req_header, req_cookie)

        if self.content_type == ContentType.JSON.value:
            return await self._handle_json_request(req_body, req_header, req_cookie)

        raise CallError(
            message="API接口的Content-Type不支持",
            data={},
        )

    async def _handle_form_request(
        self,
        req_body: dict[str, Any],
        form_data: aiohttp.FormData,
        req_header: dict[str, str],
        req_cookie: dict[str, str],
    ) -> _RequestContextManager:
        """处理表单类型的请求"""
        for key, val in req_body.items():
            form_data.add_field(key, val)

        return self._session.request(
            self.method,
            self.url,
            data=form_data,
            headers=req_header,
            cookies=req_cookie,
            timeout=self._timeout,
        )

    async def _handle_json_request(
        self, req_body: dict[str, Any], req_header: dict[str, str], req_cookie: dict[str, str],
    ) -> _RequestContextManager:
        """处理JSON类型的请求"""
        return self._session.request(
            self.method,
            self.url,
            json=req_body,
            headers=req_header,
            cookies=req_cookie,
            timeout=self._timeout,
        )

    async def _call_api(self, final_data: APIInput) -> APIOutput:
        """实际调用API，并处理返回值"""
        # 获取必要参数
        logger.info("[API] 调用接口 %s，请求数据为 %s", self.url, final_data)

        session_context = await self._make_api_call(final_data, aiohttp.FormData())
        async with session_context as response:
            if response.status not in SUCCESS_HTTP_CODES:
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
        except Exception as e:
            raise CallError(
                message="API接口的返回值不是JSON格式",
                data={},
            ) from e

        return APIOutput(
            http_code=response_status,
            result=response_dict,
        )
