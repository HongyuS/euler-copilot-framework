# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Convert工具的Schema"""

from pydantic import Field

from apps.scheduler.call.core import DataBase


class ConvertInput(DataBase):
    """定义Convert工具的输入"""



class ConvertOutput(DataBase):
    """定义Convert工具的输出"""

    text: str = Field(description="格式化后的文字信息")
    data: dict = Field(description="格式化后的结果")
