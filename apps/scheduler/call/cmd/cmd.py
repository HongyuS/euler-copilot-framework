# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""自然语言生成命令"""

from collections.abc import AsyncGenerator
from typing import Any

from pydantic import Field

from apps.scheduler.call.core import CoreCall
from apps.schemas.enum_var import LanguageType
from apps.schemas.scheduler import CallInfo, CallOutputChunk


class Cmd(CoreCall):
    """Cmd工具。用于根据BTDL描述文件，生成命令。"""

    exec_name: str | None = Field(default=None, description="命令中可执行文件的名称，可选")
    args: list[str] = Field(default=[], description="命令中可执行文件的参数（例如 `--help`），可选")

    @classmethod
    def info(cls, language: LanguageType = LanguageType.CHINESE) -> CallInfo:
        """返回Call的名称和描述"""
        i18n_info = {
            LanguageType.CHINESE: CallInfo(name="Cmd", description="根据BTDL描述文件，生成命令。"),
            LanguageType.ENGLISH: CallInfo(
                name="Cmd", description="Generate commands based on BTDL description files.",
            ),
        }
        return i18n_info[language]

    async def _exec(self, _slot_data: dict[str, Any]) -> AsyncGenerator[CallOutputChunk, None]:
        """调用Cmd工具"""

