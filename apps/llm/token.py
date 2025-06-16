# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""用于计算Token消耗量"""

from apps.common.singleton import SingletonMeta


class TokenCalculator(metaclass=SingletonMeta):
    """用于计算Token消耗量"""

    def __init__(self) -> None:
        """初始化Tokenizer"""
        import tiktoken
        self._encoder = tiktoken.get_encoding("cl100k_base")


    def calculate_token_length(self, messages: list[dict[str, str]], *, pure_text: bool = False) -> int:
        """使用ChatGPT的cl100k tokenizer，估算Token消耗量"""
        result = 0
        if not pure_text:
            result += 3 * (len(messages) + 1)

        for msg in messages:
            result += len(self._encoder.encode(msg["content"]))

        return result
