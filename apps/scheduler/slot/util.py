# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""JSON处理函数"""

import logging
from typing import Any

import jsonpath

logger = logging.getLogger(__name__)


def escape_path(key: str) -> str:
    """对JSON Path进行处理，转译关键字"""
    key = key.replace("~", "~0")
    return key.replace("/", "~1")


def patch_json(operation_list: list[dict[str, Any]], json_data: dict[str, Any] | None = None) -> dict[str, Any]:
    """应用JSON Patch，获得JSON数据"""
    if json_data is None:
        json_data = {}

    operation_list.reverse()

    while operation_list:
        current_operation = operation_list.pop()
        try:
            jsonpath.patch.apply([current_operation], json_data)
        except Exception:
            logger.exception("[Slot] 无法应用 JSON patch 操作: %s", current_operation)
            operation_list.append(current_operation)
            path_list = current_operation["path"].split("/")
            path_list.pop()
            for i in range(1, len(path_list) + 1):
                path = "/".join(path_list[:i])
                try:
                    jsonpath.resolve(path, json_data)
                    continue
                except Exception:
                    logger.exception("[Slot] 无法解析 JSON path: %s", path)
                    new_operation = {"op": "add", "path": path, "value": {}}
                    operation_list.append(new_operation)

    return json_data
