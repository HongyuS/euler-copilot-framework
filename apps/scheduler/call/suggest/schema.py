"""问题推荐工具的输入输出"""

from pydantic import BaseModel, Field

from apps.scheduler.call.core import DataBase


class SingleFlowSuggestionConfig(BaseModel):
    """涉及单个Flow的问题推荐配置"""

    flow_id: str
    question: str | None = Field(default=None, description="固定的推荐问题")


class SuggestionOutputItem(BaseModel):
    """问题推荐结果的单个条目"""

    question: str
    app_id: str
    flow_id: str
    flow_description: str


class SuggestionInput(DataBase):
    """问题推荐输入"""

    question: str
    task_id: str
    user_sub: str


class SuggestionOutput(DataBase):
    """问题推荐结果"""

    output: list[SuggestionOutputItem]
