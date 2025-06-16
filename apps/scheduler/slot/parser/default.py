# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""默认值设置器"""

from typing import Any

from jsonschema import Validator

from apps.entities.enum_var import SlotType


class SlotDefaultParser:
    """给字段设置默认值"""

    type: SlotType = SlotType.KEYWORD
    name: str = "default"

    @classmethod
    def convert(cls, data: Any, **kwargs) -> Any:  # noqa: ANN003
        """
        给字段设置默认值

        如果没有对应逻辑则不实现
        """
        raise NotImplementedError

    @classmethod
    def keyword_validate(cls, validator: Validator, keyword: str, instance: Any, schema: dict[str, Any]) -> bool:
        """给字段设置默认值"""
        ...

