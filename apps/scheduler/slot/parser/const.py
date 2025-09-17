# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""固定值设置器"""

from collections.abc import Generator
from typing import Any

from jsonschema import Validator
from jsonschema._utils import equal
from jsonschema.exceptions import ValidationError

from apps.schemas.enum_var import SlotType


class SlotConstParser:
    """给字段设置固定值"""

    type: SlotType = SlotType.KEYWORD
    name: str = "const"

    @classmethod
    def convert(cls, _data: Any, **kwargs) -> Any:  # noqa: ANN003
        """
        生成keyword的验证器

        如果没有对应逻辑则不实现
        """
        return kwargs.get("const")

    @classmethod
    def keyword_validate(
        cls,
        _validator: Validator,
        keyword: str,
        instance: Any,
        _schema: dict[str, Any],
    ) -> Generator[ValidationError, None, None]:
        """生成对应类型的验证器"""
        if not equal(keyword, instance):
            err = f"{instance!r} was expected"
            yield ValidationError(err)
