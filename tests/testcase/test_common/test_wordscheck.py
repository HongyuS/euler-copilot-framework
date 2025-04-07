"""
UT: /apps/common

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

import unittest
from pathlib import Path
from typing import Self
from unittest.mock import MagicMock, patch

from apps.common.config import Config
from apps.common.wordscheck import WordsCheck


class MockConfig:
    """Mock Config类"""

    def __init__(self) -> None:
        """初始化Mock Config类"""
        self.check = MagicMock()
        self.check.enable = False
        self.check.words_list = "words.txt"

    def get_config(self) -> Self:
        """获取Mock Config类"""
        return self


class TestWordsCheck(unittest.IsolatedAsyncioTestCase):
    """测试敏感词检查工具"""

    def setUp(self) -> None:
        """设置测试环境"""
        self.mock_config = MockConfig()
        # 使用 patch.object 来模拟 Config 类的实例
        self.patcher = patch.object(Config, "__new__", return_value=self.mock_config)
        self.patcher.start()

    def tearDown(self) -> None:
        """清理测试环境"""
        self.patcher.stop()

    def test_singleton(self) -> None:
        """测试单例模式"""
        instance1 = WordsCheck()
        instance2 = WordsCheck()
        assert instance1 is instance2

    async def test_check_disabled(self) -> None:
        """测试检查功能关闭的情况"""
        self.mock_config.check.enable = False

        checker = WordsCheck()
        result = await checker.check("test message")
        assert result == 1

    @patch.object(Path, "open")
    async def test_check_with_sensitive_word(self, mock_open: MagicMock) -> None:
        """测试包含敏感词的情况"""
        self.mock_config.check.enable = True
        self.mock_config.check.words_list = "words.txt"

        mock_open.return_value.__enter__.return_value.read.return_value = "敏感词1\n敏感词2\n"

        checker = WordsCheck()
        result = await checker.check("敏感词1")
        assert result == 1

    @patch.object(Path, "open")
    async def test_check_without_sensitive_word(self, mock_open: MagicMock) -> None:
        """测试不包含敏感词的情况"""
        self.mock_config.check.enable = True
        self.mock_config.check.words_list = "words.txt"

        mock_open.return_value.__enter__.return_value.read.return_value = "敏感词1\n敏感词2\n"

        checker = WordsCheck()
        result = await checker.check("正常消息")
        assert result == 0

    @patch.object(Path, "open", side_effect=Exception("文件读取错误"))
    async def test_check_init_failed(self, mock_open: MagicMock) -> None:
        """测试初始化失败的情况"""
        self.mock_config.check.enable = True
        self.mock_config.check.words_list = "words.txt"

        checker = WordsCheck()
        result = await checker.check("test message")
        assert result == -1


if __name__ == "__main__":
    unittest.main()
