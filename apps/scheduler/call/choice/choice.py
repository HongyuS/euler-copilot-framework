"""
工具：使用大模型或使用程序做出判断

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""
from enum import Enum

from apps.scheduler.call.choice.schema import ChoiceInput, ChoiceOutput
from apps.scheduler.call.core import CoreCall


class Operator(str, Enum):
    """Choice工具支持的运算符"""

    pass


class Choice(CoreCall, input_model=ChoiceInput, output_model=ChoiceOutput):
    """Choice工具"""

    pass
