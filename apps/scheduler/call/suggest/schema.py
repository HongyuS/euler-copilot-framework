"""问题推荐工具的输入输出"""

from pydantic import BaseModel, Field

from apps.scheduler.call.core import DataBase


class SingleFlowSuggestionConfig(BaseModel):
    """涉及单个Flow的问题推荐配置"""

    flow_id: str
    question: str | None = Field(default=None, description="固定的推荐问题")


class SuggestionInput(DataBase):
    """问题推荐输入"""

    question: str
    user_sub: str
    history_questions: list[str]


class SuggestionOutput(DataBase):
    """问题推荐结果"""

    question: str
    flow_name: str = Field(alias="flowName")
    flow_id: str = Field(alias="flowId")
    flow_description: str = Field(alias="flowDescription")
