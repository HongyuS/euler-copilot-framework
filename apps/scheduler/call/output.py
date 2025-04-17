"""
输出工具：将文字和结构化数据输出至前端

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

from collections.abc import AsyncGenerator
from typing import Any

from apps.entities.enum_var import CallOutputType
from apps.entities.scheduler import CallInfo, CallOutputChunk, CallVars
from apps.scheduler.call.core import CoreCall, DataBase


class Output(CoreCall, input_type=DataBase, output_type=DataBase):
    """输出工具"""

    @classmethod
    def cls_info(cls) -> CallInfo:
        """返回Call的名称和描述"""
        return CallInfo(name="输出", description="将前一步骤的数据输出给用户")


    async def _init(self, call_vars: CallVars) -> dict[str, Any]:
        """初始化工具"""
        return {}


    async def _exec(self, input_data: dict[str, Any]) -> AsyncGenerator[CallOutputChunk, None]:
        """执行工具"""
        yield CallOutputChunk(
            type=CallOutputType.DATA,
            content={},
        )
