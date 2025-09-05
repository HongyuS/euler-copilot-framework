from pydantic import BaseModel, Field


class ChangeConversationData(BaseModel):
    """修改会话信息"""

    title: str = Field(..., min_length=1, max_length=2000)


class DeleteConversationData(BaseModel):
    """删除会话"""

    conversation_list: list[uuid.UUID] = Field(alias="conversationList")