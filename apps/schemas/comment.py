from apps.schemas.enum_var import CommentType


from pydantic import BaseModel, Field


class AddCommentData(BaseModel):
    """添加评论"""

    record_id: str
    comment: CommentType
    dislike_reason: str = Field(default="", max_length=200)
    reason_link: str = Field(default="", max_length=200)
    reason_description: str = Field(default="", max_length=500)