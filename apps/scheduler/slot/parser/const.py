# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""固定值设置器"""

from typing import Any

from jsonschema import Validator

from apps.schemas.enum_var import SlotType


class SlotConstParser:
    """给字段设置固定值"""

    type: SlotType = SlotType.KEYWORD
    name: str = "const"

    @classmethod
    def convert(cls, data: Any, **kwargs) -> Any:  # noqa: ANN003
        """
        生成keyword的验证器

        如果没有对应逻辑则不实现
        """
        raise NotImplementedError

    @classmethod
    def keyword_validate(cls, validator: Validator, keyword: str, instance: Any, schema: dict[str, Any]) -> bool:
        """生成对应类型的验证器"""
        ...

