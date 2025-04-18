"""搜索工具"""
from typing import Any, ClassVar

from pydantic import BaseModel, Field

from apps.entities.scheduler import CallVars
from apps.scheduler.call.core import CoreCall


class SearchRet(BaseModel):
    """搜索工具返回值"""

    data: list[dict[str, Any]] = Field(description="搜索结果")


class Search(CoreCall, ret_type=SearchRet):
    """搜索工具"""

    name: ClassVar[str] = "搜索"
    description: ClassVar[str] = "获取搜索引擎的结果"

    async def _init(self, syscall_vars: CallVars, **kwargs: Any) -> dict[str, Any]:
        """初始化工具"""
        self._query: str = kwargs["query"]
        return {}


    async def _exec(self) -> dict[str, Any]:
        """执行工具"""
        return {}

