# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""基础大模型范式抽象类"""

from abc import ABC, abstractmethod
from textwrap import dedent

from apps.schemas.enum_var import LanguageType


class CorePattern(ABC):
    """基础大模型范式抽象类"""

    @staticmethod
    def _default() -> tuple[dict[LanguageType, str], dict[LanguageType, str]]:
        """默认的Prompt内容；分别返回系统提示词和用户提示词"""
        return {}, {}

    def __init__(
        self,
        system_prompt: dict[LanguageType, str] | None = None,
        user_prompt: dict[LanguageType, str] | None = None,
    ) -> None:
        """
        检查是否已经自定义了Prompt；有的话就用自定义的；同时对Prompt进行空格清除

        :param system_prompt: 系统提示词，f-string格式
        :param user_prompt: 用户提示词，f-string格式
        """
        self.input_tokens = 0
        self.output_tokens = 0

        self.system_prompt, self.user_prompt = self._default()

        if system_prompt is not None:
            self.system_prompt = system_prompt

        if user_prompt is not None:
            self.user_prompt = user_prompt

        self.system_prompt = {lang: dedent(prompt).strip("\n") for lang, prompt in self.system_prompt.items()}
        self.user_prompt = {lang: dedent(prompt).strip("\n") for lang, prompt in self.user_prompt.items()}

    @abstractmethod
    async def generate(self, **kwargs):  # noqa: ANN003, ANN201
        """调用大模型，生成结果"""
        raise NotImplementedError
