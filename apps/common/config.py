# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""配置文件处理模块"""

import os
from pathlib import Path
from typing import Self

import toml
from pydantic import ConfigDict

from apps.schemas.config import ConfigModel


class Config(ConfigModel):
    """配置文件读取和使用Class"""

    model_config = ConfigDict(frozen=True)

    @classmethod
    def init_config(cls) -> Self:
        """读取配置文件；当PROD环境变量设置时，配置文件将在读取后删除"""
        config_file = os.getenv("CONFIG")
        if config_file is None:
            config_file = Path(__file__).parents[2] / "config" / "config.toml"
        config = cls.model_validate(toml.load(config_file))

        if os.getenv("PROD"):
            Path(config_file).unlink()

        return config

config = Config.init_config()
