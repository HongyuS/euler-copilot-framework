# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""评论相关的数据结构"""

from pydantic import BaseModel, Field

from apps.models import CommentType


class AddCommentData(BaseModel):
    """添加评论"""

    record_id: str
    comment: CommentType
    dislike_reason: str = Field(default="", max_length=200)
    reason_link: str = Field(default="", max_length=200)
    reason_description: str = Field(default="", max_length=500)
