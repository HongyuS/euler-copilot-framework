"""
配置文件处理模块

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""
import os
from copy import deepcopy
from pathlib import Path

import toml

from apps.common.singleton import SingletonMeta
from apps.entities.config import ConfigModel


class Config(metaclass=SingletonMeta):
    """配置文件读取和使用Class"""

    _config: ConfigModel

    def __init__(self) -> None:
        """读取配置文件；当PROD环境变量设置时，配置文件将在读取后删除"""
        config_file = os.getenv("CONFIG")
        if config_file is None:
            config_file = "./config/config.toml"
        self._config = ConfigModel.model_validate(toml.load(config_file))

        if os.getenv("PROD"):
            Path(config_file).unlink()

    def get_config(self) -> ConfigModel:
        """获取配置文件内容"""
        return deepcopy(self._config)
