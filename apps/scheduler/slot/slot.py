"""
参数槽位管理

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

import json
import logging
import traceback
from collections.abc import Mapping
from typing import Any

from jsonschema import Draft7Validator
from jsonschema.exceptions import ValidationError
from jsonschema.protocols import Validator
from jsonschema.validators import extend

from apps.scheduler.slot.parser import (
    SlotConstParser,
    SlotDateParser,
    SlotDefaultParser,
    SlotTimestampParser,
)
from apps.scheduler.slot.util import escape_path, patch_json

logger = logging.getLogger(__name__)

# 各类检查器
_TYPE_CHECKER = [
    SlotDateParser,
    SlotTimestampParser,
]
_FORMAT_CHECKER = []
_KEYWORD_CHECKER = {
    "const": SlotConstParser.keyword_validate,
    "default": SlotDefaultParser.keyword_validate,
}

# 各类转换器
_TYPE_CONVERTER = [
    SlotDateParser,
    SlotTimestampParser,
]
_KEYWORD_CONVERTER = {
    "const": SlotConstParser,
    "default": SlotDefaultParser,
}


class Slot:
    """
    参数槽

    （1）检查提供的JSON和JSON Schema的有效性
    （2）找到不满足要求的JSON字段，并提取成平铺的JSON，交由前端处理
    （3）可对特殊格式的字段进行处理
    """

    def __init__(self, schema: dict) -> None:
        """初始化参数槽处理器"""
        try:
            # 导入所有校验器，动态生成新的类
            self._validator_cls = Slot._construct_validator()
        except Exception as e:
            err = f"Invalid JSON Schema validator: {e!s}\n{traceback.format_exc()}"
            raise ValueError(err) from e

        # 预初始化变量
        self._json = {}

        try:
            # 校验提供的JSON Schema是否合法
            self._validator_cls.check_schema(schema)
        except Exception as e:
            err = f"Invalid JSON Schema: {e!s}"
            raise ValueError(err) from e

        self._validator = self._validator_cls(schema)
        self._schema = schema

    @staticmethod
    def _construct_validator() -> type[Validator]:
        """构造JSON Schema验证器"""
        type_checker = Draft7Validator.TYPE_CHECKER
        # 把所有type_checker都添加
        for checker in _TYPE_CHECKER:
            type_checker = type_checker.redefine(checker.type, checker.type_validate)

        format_checker = Draft7Validator.FORMAT_CHECKER
        # 把所有format_checker都添加
        for checker in _FORMAT_CHECKER:
            format_checker = format_checker.redefine(checker.type, checker.type_validate)

        return extend(
            Draft7Validator, type_checker=type_checker, format_checker=format_checker, validators=_KEYWORD_CHECKER,
        )

    @staticmethod
    def _process_json_value(json_value: Any, spec_data: dict[str, Any]) -> Any:  # noqa: C901, PLR0911, PLR0912
        """
        使用递归的方式对JSON返回值进行处理

        :param json_value: 返回值中的字段
        :param spec_data: 返回值字段对应的JSON Schema
        :return: 处理后的这部分返回值字段
        """
        if "allOf" in spec_data:
            processed_dict = {}
            for item in spec_data["allOf"]:
                processed_dict.update(Slot._process_json_value(json_value, item))
            return processed_dict

        for key in ("anyOf", "oneOf"):
            if key in spec_data:
                for item in spec_data[key]:
                    processed_dict = Slot._process_json_value(json_value, item)
                    if processed_dict is not None:
                        return processed_dict

        if "type" in spec_data:
            if spec_data["type"] == "array" and isinstance(json_value, list):
                # 若Schema不标准，则不进行处理
                if "items" not in spec_data:
                    return json_value
                # Schema标准
                return [Slot._process_json_value(item, spec_data["items"]) for item in json_value]
            if spec_data["type"] == "object" and isinstance(json_value, dict):
                # 若Schema不标准，则不进行处理
                if "properties" not in spec_data:
                    return json_value
                # Schema标准
                processed_dict = {}
                for key, val in json_value.items():
                    if key not in spec_data["properties"]:
                        processed_dict[key] = val
                        continue
                    processed_dict[key] = Slot._process_json_value(val, spec_data["properties"][key])
                return processed_dict

            for converter in _TYPE_CONVERTER:
                # 如果是自定义类型
                if converter.name == spec_data["type"]:
                    # 如果类型有附加字段
                    if converter.name in spec_data:
                        return converter.convert(json_value, **spec_data[converter.name])
                    return converter.convert(json_value)

        return json_value

    def process_json(self, json_data: str | dict[str, Any]) -> dict[str, Any]:
        """将提供的JSON数据进行处理"""
        if isinstance(json_data, str):
            json_data = json.loads(json_data)

        # 遍历JSON，处理每一个字段
        return Slot._process_json_value(json_data, self._schema)

    def _flatten_schema(self, schema: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        """将JSON Schema扁平化"""
        result = {}
        required = []

        # 合并处理 allOf、anyOf、oneOf
        for key in ("allOf", "anyOf", "oneOf"):
            if key in schema:
                for item in schema[key]:
                    sub_result, sub_required = self._flatten_schema(item)
                    result.update(sub_result)
                    required.extend(sub_required)

        # 处理type
        if "type" in schema:
            if schema["type"] == "object" and "properties" in schema:
                sub_result, sub_required = self._flatten_schema(schema["properties"])
                result.update(sub_result)
                required.extend(sub_required)
            else:
                result[schema["type"]] = schema
                required.append(schema["type"])

        return result, required

    def _strip_error(self, error: ValidationError) -> tuple[dict[str, Any], list[str]]:
        """裁剪发生错误的JSON Schema，并返回可能的附加路径"""
        # required的错误是在上层抛出的，需要裁剪schema
        if error.validator == "required":
            # 从错误信息中提取字段
            try:
                # 注意：此处与Validator文本有关，注意版本问题
                key = error.message.split("'")[1]
            except IndexError:
                logger.exception("[Slot] 错误信息不合法: %s", error.message)
                return {}, []

            # 如果字段存在，则返回裁剪后的schema
            if isinstance(error.schema, Mapping) and "properties" in error.schema and key in error.schema["properties"]:
                schema = error.schema["properties"][key]
                # 将默认值改为当前值
                schema["default"] = ""
                return schema, [key]

            # 如果字段不存在，则返回空
            logger.exception("[Slot] 错误schema不合法: %s", error.schema)
            return {}, []

        # 默认无需裁剪
        if isinstance(error.schema, Mapping):
            return dict(error.schema.items()), []

        logger.exception("[Slot] 错误schema不合法: %s", error.schema)
        return {}, []

    def convert_json(self, json_data: str | dict[str, Any]) -> dict[str, Any]:
        """将用户手动填充的参数专为真实JSON"""
        json_dict = json.loads(json_data) if isinstance(json_data, str) else json_data

        # 对JSON进行处理
        patch_list = []
        plain_data = {}
        for key, val in json_dict.items():
            # 如果是patch，则构建
            if key[0] == "/":
                patch_list.append({"op": "add", "path": key, "value": val})
            else:
                plain_data[key] = val

        # 对JSON进行patch
        final_json = patch_json(patch_list)
        final_json.update(plain_data)

        return final_json

    def check_json(self, json_data: dict[str, Any]) -> dict[str, Any]:
        """检测槽位是否合法、是否填充完成"""
        empty = True
        schema_template = {
            "type": "object",
            "properties": {},
            "required": [],
        }

        for error in self._validator.iter_errors(json_data):
            # 如果有错误，说明填充参数不通过
            empty = False

            # 处理错误
            slot_schema, additional_path = self._strip_error(error)
            # 组装JSON Pointer
            pointer = "/" + "/".join([escape_path(str(v)) for v in error.path])
            if additional_path:
                pointer = pointer.rstrip("/") + "/" + "/".join(additional_path)
            schema_template["properties"][pointer] = slot_schema

        # 如果有错误
        if not empty:
            return schema_template

        return {}
