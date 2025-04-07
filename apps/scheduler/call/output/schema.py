"""输出工具的数据结构"""

from pydantic import Field

from apps.scheduler.call.core import DataBase


class OutputInput(DataBase):
    """输出工具的输入"""


class OutputOutput(DataBase):
    """输出工具的输出"""

    output: str = Field(description="输出工具的输出")
