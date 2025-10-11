# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""敏感词检查模块"""

import logging
from pathlib import Path

from .config import config

logger = logging.getLogger(__name__)


class _WordsCheck:
    """敏感词检查工具（内部类）"""

    def __init__(self) -> None:
        """初始化"""
        self._words_list: list[str] = []
        self._initialized = False

    def _init_words_list(self) -> None:
        """同步初始化敏感词列表"""
        if not self._initialized and config.check.enable:
            with Path(config.check.words_list).open(encoding="utf-8") as f:
                self._words_list = f.read().splitlines()
            self._initialized = True

    async def _check_wordlist(self, message: str) -> int:
        """使用关键词列表检查敏感词"""
        if not self._initialized:
            self._init_words_list()
        for word in self._words_list:
            if word in message:
                return 1
        return 0

    async def check(self, message: str) -> int:
        """
        检查消息是否包含关键词

        异常-1，拦截0，正常1
        """
        if config.check.enable:
            return await self._check_wordlist(message)
        # 不设置检查类型，默认不拦截
        return 1


# 全局单例对象
words_check = _WordsCheck()
