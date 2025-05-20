# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""自然语言生成命令"""

from typing import Any

from pydantic import BaseModel, Field

from apps.scheduler.call.core import CoreCall


class _CmdParams(BaseModel):
    """Cmd工具的参数"""

    exec_name: str | None = Field(default=None, description="命令中可执行文件的名称，可选")
    args: list[str] = Field(default=[], description="命令中可执行文件的参数（例如 `--help`），可选")


class _CmdOutput(BaseModel):
    """Cmd工具的输出"""



class Cmd(CoreCall):
    """Cmd工具。用于根据BTDL描述文件，生成命令。"""

    name: str = "cmd"
    description: str = "根据BTDL描述文件，生成命令。"

    async def _exec(self, _slot_data: dict[str, Any]) -> _CmdOutput:
        """调用Cmd工具"""
        pass
