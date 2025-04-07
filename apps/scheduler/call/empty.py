"""
空白Call

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

from collections.abc import AsyncGenerator
from typing import Any, ClassVar

from pydantic import BaseModel, Field

from apps.entities.enum_var import CallOutputType
from apps.entities.scheduler import CallOutputChunk, CallVars
from apps.scheduler.call.core import CoreCall, DataBase


class EmptyInput(BaseModel):
    """空输入"""


class EmptyOutput(DataBase):
    """空输出"""


class Empty(CoreCall, input_type=EmptyInput, output_type=EmptyOutput):
    """空Call"""

    name: ClassVar[str] = Field("空白", exclude=True, frozen=True)
    description: ClassVar[str] = Field("空白节点，用于占位", exclude=True, frozen=True)


    async def _init(self, syscall_vars: CallVars) -> dict[str, Any]:
        """初始化"""
        return {}


    async def _exec(self, input_data: dict[str, Any]) -> AsyncGenerator[CallOutputChunk, None]:
        """执行"""
        output = CallOutputChunk(type=CallOutputType.TEXT, content="")
        yield output
