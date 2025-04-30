"""搜索工具"""

from collections.abc import AsyncGenerator
from typing import Any

from apps.entities.scheduler import (
    CallError,
    CallInfo,
    CallOutputChunk,
    CallVars,
)
from apps.scheduler.call.core import CoreCall
from apps.scheduler.call.search.schema import SearchInput, SearchOutput


class Search(CoreCall, input_model=SearchInput, output_model=SearchOutput):
    """搜索工具"""

    @classmethod
    def info(cls) -> CallInfo:
        """返回Call的名称和描述"""
        return CallInfo(name="搜索", description="获取搜索引擎的结果")


    async def _init(self, call_vars: CallVars) -> SearchInput:
        """初始化工具"""
        pass


    async def _exec(self, input_data: dict[str, Any]) -> AsyncGenerator[CallOutputChunk, None]:
        """执行工具"""
        pass

