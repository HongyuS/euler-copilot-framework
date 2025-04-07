"""
API调用工具的输入和输出

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

from typing import Any

from pydantic import Field

from apps.scheduler.call.core import DataBase


class APIInput(DataBase):
    """API调用工具的输入"""

    service_id: str = Field(description="API调用工具的Service ID")
    url: str = Field(description="API调用工具的URL")
    method: str = Field(description="API调用工具的HTTP方法")

    query: dict[str, Any] = Field(description="API调用工具的请求参数")
    body: dict[str, Any] = Field(description="API调用工具的请求体")


class APIOutput(DataBase):
    """API调用工具的输出"""

    http_code: int = Field(description="API调用工具的HTTP返回码")
    result: dict[str, Any] | str = Field(description="API调用工具的输出")
