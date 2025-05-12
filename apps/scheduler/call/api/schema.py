"""
API调用工具的输入和输出

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

from typing import Any

from pydantic import Field
from pydantic.json_schema import SkipJsonSchema

from apps.scheduler.call.core import DataBase


class APIInput(DataBase):
    """API调用工具的输入"""

    url: SkipJsonSchema[str] = Field(description="API调用工具的URL")
    method: SkipJsonSchema[str] = Field(description="API调用工具的HTTP方法")

    query: dict[str, Any] = Field(description="API调用工具的请求参数")
    body: dict[str, Any] = Field(description="API调用工具的请求体")


class APIOutput(DataBase):
    """API调用工具的输出"""

    http_code: int = Field(description="API调用工具的HTTP返回码")
    result: dict[str, Any] | str = Field(description="API调用工具的输出")
