"""
UT: /apps/common

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

import unittest
from unittest.mock import patch

from apps.common.cryptohub import CryptoHub


class TestCryptoHub(unittest.TestCase):
    """CryptoHub类的测试用例"""

    def setUp(self) -> None:
        """测试前的准备工作"""
        self.test_plain_text = "test_plain_text"

    def test_generate_str_from_sha256(self) -> None:
        """测试SHA256哈希生成"""
        # 测试正常输入
        result = CryptoHub.generate_str_from_sha256("hello")
        expected = "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
        assert result == expected

        # 测试空字符串
        empty_result = CryptoHub.generate_str_from_sha256("")
        empty_expected = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        assert empty_result == empty_expected

    def test_decrypt_with_config(self) -> None:
        """测试配置解密"""
        # 准备测试数据
        encrypted_data = "test_cipher_text"
        config_dict = {
            CryptoHub.generate_str_from_sha256("encrypted_work_key"): "work_key",
            CryptoHub.generate_str_from_sha256("encrypted_work_key_iv"): "work_key_iv",
            CryptoHub.generate_str_from_sha256("encrypted_iv"): "iv",
            CryptoHub.generate_str_from_sha256("half_key1"): "half_key",
        }
        test_input = [encrypted_data, config_dict]

        # Mock Security.decrypt
        with patch("apps.common.security.Security.decrypt") as mock_decrypt:
            mock_decrypt.return_value = "decrypted_text"
            result = CryptoHub.decrypt_with_config(test_input)
            assert result == "decrypted_text"
            mock_decrypt.assert_called_once_with(encrypted_data, {
                "encrypted_work_key": "work_key",
                "encrypted_work_key_iv": "work_key_iv",
                "encrypted_iv": "iv",
                "half_key1": "half_key",
            })


if __name__ == "__main__":
    unittest.main()
