# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""参数填充工具的Schema"""

from typing import Any

from pydantic import Field

from apps.scheduler.call.core import DataBase


class SlotInput(DataBase):
    """参数填充工具的输入"""

    remaining_schema: dict[str, Any] = Field(description="剩余的Schema", default={})


class SlotOutput(DataBase):
    """参数填充工具的输出"""

    slot_data: dict[str, Any] = Field(description="填充后的数据", default={})
    remaining_schema: dict[str, Any] = Field(description="剩余的Schema", default={})
