"""
基础大模型范式抽象类

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

from abc import ABC, abstractmethod
from textwrap import dedent


class CorePattern(ABC):
    """基础大模型范式抽象类"""

    system_prompt: str = ""
    """系统提示词"""
    user_prompt: str = ""
    """用户提示词"""
    input_tokens: int = 0
    """输入Token数量"""
    output_tokens: int = 0
    """输出Token数量"""


    def __init__(self, system_prompt: str | None = None, user_prompt: str | None = None) -> None:
        """
        检查是否已经自定义了Prompt；有的话就用自定义的；同时对Prompt进行空格清除

        :param system_prompt: 系统提示词，f-string格式
        :param user_prompt: 用户提示词，f-string格式
        """
        if system_prompt is not None:
            self.system_prompt = system_prompt

        if user_prompt is not None:
            self.user_prompt = user_prompt

        if not self.user_prompt:
            err = "必须设置用户提示词！"
            raise ValueError(err)

        self.system_prompt = dedent(self.system_prompt).strip("\n")
        self.user_prompt = dedent(self.user_prompt).strip("\n")

    @abstractmethod
    async def generate(self, **kwargs):  # noqa: ANN003, ANN201
        """调用大模型，生成结果"""
        raise NotImplementedError
