# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""密文加密解密模块"""

import base64
import binascii
import hashlib
import secrets

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from apps.common.config import Config


class Security:
    """密文加密解密模块"""

    @staticmethod
    def encrypt(plaintext: str) -> tuple[str, dict]:
        """
        加密公共方法

        :param plaintext: 待加密的字符串
        :return: 加密后的字符串和存放工作密钥的dict
        """
        half_key1 = Config().get_config().security.half_key1
        if half_key1 is None:
            err = "配置文件中未设置HALF_KEY1"
            raise ValueError(err)

        encrypted_work_key, encrypted_work_key_iv = Security._generate_encrypted_work_key(
            half_key1)
        encrypted_plaintext, encrypted_iv = Security._encrypt_plaintext(
            half_key1, encrypted_work_key,
            encrypted_work_key_iv, plaintext,
        )
        del plaintext
        secret_dict = {
            "encrypted_work_key": encrypted_work_key,
            "encrypted_work_key_iv": encrypted_work_key_iv,
            "encrypted_iv": encrypted_iv,
            "half_key1": half_key1,
        }
        return encrypted_plaintext, secret_dict

    @staticmethod
    def decrypt(encrypted_plaintext: str, secret_dict: dict) -> str:
        """
        解密公共方法

        :param encrypted_plaintext: 待解密的字符串
        :param secret_dict: 存放工作密钥的dict
        :return: 解密后的字符串
        """
        half_key1 = secret_dict.get("half_key1")
        if half_key1 is None:
            err = "配置文件中未设置HALF_KEY1"
            raise ValueError(err)
        return Security._decrypt_plaintext(
            half_key1=half_key1,
            encrypted_work_key=secret_dict["encrypted_work_key"],
            encrypted_work_key_iv=secret_dict["encrypted_work_key_iv"],
            encrypted_iv=secret_dict["encrypted_iv"],
            encrypted_plaintext=encrypted_plaintext,
        )

    @staticmethod
    def _get_root_key(half_key1: str) -> bytes:
        half_key2 = Config().get_config().security.half_key2
        if half_key2 is None:
            err = "配置文件中未设置HALF_KEY2"
            raise ValueError(err)

        key = (half_key1 + half_key2).encode("utf-8")
        half_key3 = Config().get_config().security.half_key3.encode("utf-8")
        hash_key = hashlib.pbkdf2_hmac("sha256", key, half_key3, 10000)
        return binascii.hexlify(hash_key)[13:45]

    @staticmethod
    def _generate_encrypted_work_key(half_key1: str) -> tuple[str, str]:
        bin_root_key = Security._get_root_key(half_key1)
        bin_work_key = secrets.token_bytes(32)
        bin_encrypted_work_key_iv = secrets.token_bytes(16)
        bin_encrypted_work_key = Security._root_encrypt(bin_root_key, bin_encrypted_work_key_iv, bin_work_key)
        encrypted_work_key = base64.b64encode(bin_encrypted_work_key).decode("ascii")
        encrypted_work_key_iv = base64.b64encode(bin_encrypted_work_key_iv).decode("ascii")
        return encrypted_work_key, encrypted_work_key_iv

    @staticmethod
    def _get_work_key(half_key1: str, encrypted_work_key: str, encrypted_work_key_iv: str) -> bytes:
        bin_root_key = Security._get_root_key(half_key1)
        bin_encrypted_work_key = base64.b64decode(encrypted_work_key.encode("ascii"))
        bin_encrypted_work_key_iv = base64.b64decode(encrypted_work_key_iv.encode("ascii"))
        return Security._root_decrypt(bin_root_key, bin_encrypted_work_key_iv, bin_encrypted_work_key)

    @staticmethod
    def _root_encrypt(key: bytes, encrypted_iv: bytes, plaintext: bytes) -> bytes:
        encryptor = Cipher(algorithms.AES(key), modes.GCM(encrypted_iv), default_backend()).encryptor()
        return encryptor.update(plaintext) + encryptor.finalize()

    @staticmethod
    def _root_decrypt(key: bytes, encrypted_iv: bytes, encrypted: bytes) -> bytes:
        encryptor = Cipher(algorithms.AES(key), modes.GCM(encrypted_iv), default_backend()).encryptor()
        return encryptor.update(encrypted)

    @staticmethod
    def _encrypt_plaintext(half_key1: str, encrypted_work_key: str, encrypted_work_key_iv: str,
                           plaintext: str) -> tuple[str, str]:
        bin_work_key = Security._get_work_key(half_key1, encrypted_work_key, encrypted_work_key_iv)
        salt = f"{half_key1}{plaintext}"
        plaintext_temp = salt.encode("utf-8")
        del plaintext
        del salt
        bin_encrypted_iv = secrets.token_bytes(16)
        bin_encrypted_plaintext = Security._root_encrypt(bin_work_key, bin_encrypted_iv, plaintext_temp)
        encrypted_plaintext = base64.b64encode(bin_encrypted_plaintext).decode("ascii")
        encrypted_iv = base64.b64encode(bin_encrypted_iv).decode("ascii")
        return encrypted_plaintext, encrypted_iv

    @staticmethod
    def _decrypt_plaintext(half_key1: str, encrypted_work_key: str, encrypted_work_key_iv: str,
                           encrypted_plaintext: str, encrypted_iv: str) -> str:
        bin_work_key = Security._get_work_key(half_key1, encrypted_work_key, encrypted_work_key_iv)
        bin_encrypted_plaintext = base64.b64decode(encrypted_plaintext.encode("ascii"))
        bin_encrypted_iv = base64.b64decode(encrypted_iv.encode("ascii"))
        plaintext_temp = Security._root_decrypt(bin_work_key, bin_encrypted_iv, bin_encrypted_plaintext)
        plaintext_salt = plaintext_temp.decode("utf-8")
        return plaintext_salt[len(half_key1):]
