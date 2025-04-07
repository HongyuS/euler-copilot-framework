"""
提取或格式化Step输出

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any, ClassVar

import pytz
from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment
from pydantic import Field

from apps.entities.enum_var import CallOutputType
from apps.entities.scheduler import CallVars
from apps.scheduler.call.convert.schema import ConvertInput, ConvertOutput
from apps.scheduler.call.core import CallOutputChunk, CoreCall


class Convert(CoreCall, input_type=ConvertInput, output_type=ConvertOutput):
    """Convert 工具，用于对生成的文字信息和原始数据进行格式化"""

    name: ClassVar[str] = "模板转换"
    description: ClassVar[str] = "使用jinja2语法和jsonnet语法，将自然语言信息和原始数据进行格式化。"

    text_template: str | None = Field(description="自然语言信息的格式化模板，jinja2语法", default=None)
    data_template: str | None = Field(description="原始数据的格式化模板，jinja2语法", default=None)


    async def _init(self, syscall_vars: CallVars) -> dict[str, Any]:
        """初始化工具"""
        await super()._init(syscall_vars)

        self._history = syscall_vars.history
        self._question = syscall_vars.question
        self._env = SandboxedEnvironment(
            loader=BaseLoader(),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        return ConvertInput().model_dump(exclude_none=True, by_alias=True)


    async def _exec(self) -> AsyncGenerator[CallOutputChunk, None]:
        """
        调用Convert工具

        :param _slot_data: 经用户确认后的参数（目前未使用）
        :return: 提取出的字段
        """
        # 判断用户是否给了值
        time = datetime.now(tz=pytz.timezone("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")
        if self.text_template is None:
            result_message = last_output.get("message", "")
        else:
            text_template = self._env.from_string(self.text_template)
            result_message = text_template.render(time=time, history=self._history, question=self._question)

        if self.data_template is None:
            result_data = last_output.get("output", {})
        else:
            data_template = self._env.from_string(self.data_template)
            result_data = data_template.render(
                time=time,
                question=self._question,
                history=[item.output_data["output"] for item in self._history if "output" in item.output_data],
            )

        yield CallOutputChunk(
            type=CallOutputType.DATA,
            content=result_message,
        )
