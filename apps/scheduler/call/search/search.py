"""搜索工具"""

from typing import Any, ClassVar

from apps.entities.scheduler import CallVars
from apps.scheduler.call.core import CoreCall
from apps.scheduler.call.search.schema import SearchInput, SearchRet


class Search(CoreCall, input_model=SearchInput, output_model=SearchRet):
    """搜索工具"""

    name: ClassVar[str] = "搜索"
    description: ClassVar[str] = "获取搜索引擎的结果"

    async def _init(self, call_vars: CallVars, **kwargs: Any) -> SearchInput:
        """初始化工具"""
        self._query: str = kwargs["query"]
        return SearchInput(query=self._query)


    async def _exec(self) -> dict[str, Any]:
        """执行工具"""
        return {}

