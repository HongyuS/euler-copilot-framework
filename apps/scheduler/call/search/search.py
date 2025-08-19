"""搜索工具"""

from collections.abc import AsyncGenerator
from typing import Any

from apps.scheduler.call.core import CoreCall
from apps.schemas.enum_var import LanguageType
from apps.schemas.scheduler import (
    CallError,
    CallInfo,
    CallOutputChunk,
    CallVars,
)

from .schema import SearchInput, SearchOutput


class Search(CoreCall, input_model=SearchInput, output_model=SearchOutput):
    """搜索工具"""

    @classmethod
    def info(cls, language: LanguageType = LanguageType.CHINESE) -> CallInfo:
        """返回Call的名称和描述"""
        i18n_info = {
            LanguageType.CHINESE: CallInfo(name="搜索", description="获取搜索引擎的结果"),
            LanguageType.ENGLISH: CallInfo(name="Search", description="Get the results of the search engine."),
        }
        return i18n_info[language]


    async def _init(self, call_vars: CallVars) -> SearchInput:
        """初始化工具"""
        pass


    async def _exec(self, input_data: dict[str, Any]) -> AsyncGenerator[CallOutputChunk, None]:
        """执行工具"""
        pass

