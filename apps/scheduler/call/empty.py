# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""空白Call"""

from collections.abc import AsyncGenerator
from typing import Any

from apps.scheduler.call.core import CoreCall, DataBase
from apps.schemas.enum_var import CallOutputType
from apps.schemas.scheduler import CallInfo, CallOutputChunk, CallVars


class Empty(CoreCall, input_model=DataBase, output_model=DataBase):
    """空Call"""

    @classmethod
    def info(cls) -> CallInfo:
        """
        返回Call的名称和描述

        :return: Call的名称和描述
        :rtype: CallInfo
        """
        return CallInfo(name="空白", description="空白节点，用于占位")


    async def _init(self, call_vars: CallVars) -> DataBase:
        """
        初始化Call

        :param CallVars call_vars: 由Executor传入的变量，包含当前运行信息
        :return: Call的输入
        :rtype: DataBase
        """
        return DataBase()


    async def _exec(self, input_data: dict[str, Any]) -> AsyncGenerator[CallOutputChunk, None]:
        """
        执行Call

        :param dict[str, Any] input_data: 填充后的Call的最终输入
        :return: Call的输出
        :rtype: AsyncGenerator[CallOutputChunk, None]
        """
        output = CallOutputChunk(type=CallOutputType.DATA, content={})
        yield output
