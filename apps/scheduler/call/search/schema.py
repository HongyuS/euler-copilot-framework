"""Search Call的输入和输出"""

from typing import Any

from pydantic import Field

from apps.scheduler.call.core import DataBase


class SearchInput(DataBase):
    """搜索工具输入"""

    query: str = Field(description="搜索关键词")


class SearchRet(DataBase):
    """搜索工具返回值"""

    data: list[dict[str, Any]] = Field(description="搜索结果")
