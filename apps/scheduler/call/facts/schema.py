"""Facts工具的输入和输出"""

from pydantic import Field

from apps.scheduler.call.core import DataBase


class FactsInput(DataBase):
    """提取事实工具的输入"""

    user_sub: str = Field(description="用户ID")
    message: list[dict[str, str]] = Field(description="消息")


class FactsOutput(DataBase):
    """提取事实工具的输出"""

    facts: list[str] = Field(description="提取的事实")
    domain: list[str] = Field(description="提取的领域")
