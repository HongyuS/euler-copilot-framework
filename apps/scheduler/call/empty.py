"""
空白Call

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

from collections.abc import AsyncGenerator
from typing import Any

from apps.entities.enum_var import CallOutputType
from apps.entities.scheduler import CallInfo, CallOutputChunk, CallVars
from apps.scheduler.call.core import CoreCall, DataBase


class Empty(CoreCall, input_model=DataBase, output_model=DataBase):
    """空Call"""

    @classmethod
    def info(cls) -> CallInfo:
        """返回Call的名称和描述"""
        return CallInfo(name="空白", description="空白节点，用于占位")


    async def _init(self, call_vars: CallVars) -> DataBase:
        """初始化"""
        return DataBase()


    async def _exec(self, input_data: dict[str, Any]) -> AsyncGenerator[CallOutputChunk, None]:
        """执行"""
        output = CallOutputChunk(type=CallOutputType.DATA, content={})
        yield output
