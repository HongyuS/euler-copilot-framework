"""
输出工具：将文字和结构化数据输出至前端

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

from collections.abc import AsyncGenerator
from typing import Annotated, Any, ClassVar

from pydantic import Field

from apps.entities.enum_var import CallOutputType
from apps.entities.scheduler import CallOutputChunk, CallVars
from apps.scheduler.call.core import CoreCall, DataBase


class Output(CoreCall, input_type=DataBase, output_type=DataBase):
    """输出工具"""

    name: ClassVar[Annotated[str, Field(description="工具名称", exclude=True, frozen=True)]] = "输出"
    description: ClassVar[
        Annotated[str, Field(description="工具描述", exclude=True, frozen=True)]
    ] = "将前一步骤的数据输出给用户"


    async def _init(self, syscall_vars: CallVars) -> dict[str, Any]:
        """初始化工具"""
        return {}


    async def _exec(self, input_data: dict[str, Any]) -> AsyncGenerator[CallOutputChunk, None]:
        """执行工具"""
        yield CallOutputChunk(
            type=CallOutputType.DATA,
            content={},
        )
