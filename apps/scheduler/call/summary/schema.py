"""总结工具的输入和输出"""

from pydantic import Field

from apps.scheduler.call.core import DataBase


class SummaryOutput(DataBase):
    """总结工具的输出"""

    summary: str = Field(description="对问答上下文的总结内容")
