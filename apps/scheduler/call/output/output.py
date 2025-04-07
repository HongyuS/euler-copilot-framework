"""输出工具：将文字和结构化数据输出至前端"""
from collections.abc import AsyncGenerator
from typing import Annotated, Any, ClassVar

from pydantic import Field

from apps.entities.enum_var import CallOutputType
from apps.entities.scheduler import CallOutputChunk, CallVars
from apps.scheduler.call.core import CoreCall
from apps.scheduler.call.output.schema import OutputInput, OutputOutput


class Output(CoreCall, input_type=OutputInput, output_type=OutputOutput):
    """输出工具"""

    name: ClassVar[Annotated[str, Field(description="工具名称", exclude=True, frozen=True)]] = "输出"
    description: ClassVar[Annotated[str, Field(description="工具描述", exclude=True, frozen=True)]] = "将文字和结构化数据输出至前端"

    template: str = Field(description="输出模板（只能使用直接变量引用）")


    async def _init(self, syscall_vars: CallVars) -> dict[str, Any]:
        """初始化工具"""
        self._text: AsyncGenerator[str, None] = kwargs["text"]
        self._data: dict[str, Any] = kwargs["data"]

        return {
            "text": self._text,
            "data": self._data,
        }


    async def _exec(self, input_data: dict[str, Any]) -> AsyncGenerator[CallOutputChunk, None]:
        """执行工具"""
        yield CallOutputChunk(
            type=CallOutputType.TEXT,
            content=OutputOutput(
                output=self._text,
            ).model_dump(by_alias=True, exclude_none=True),
        )
