# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""FastAPI 评论相关接口"""

import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from apps.dependency import get_user, verify_user
from apps.entities.record import RecordComment
from apps.entities.request_data import AddCommentData
from apps.entities.response_data import ResponseData
from apps.manager.comment import CommentManager
from apps.manager.record import RecordManager

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/comment",
    tags=["comment"],
    dependencies=[
        Depends(verify_user),
    ],
)


@router.post("", response_model=ResponseData)
async def add_comment(post_body: AddCommentData, user_sub: Annotated[str, Depends(get_user)]) -> JSONResponse:
    """给Record添加评论"""
    if not await RecordManager.verify_record_in_group(post_body.group_id, post_body.record_id, user_sub):
        logger.error("[Comment] record_id 不存在")
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content=ResponseData(
            code=status.HTTP_400_BAD_REQUEST,
            message="record_id not found",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))

    comment_data = RecordComment(
        comment=post_body.comment,
        dislike_reason=post_body.dislike_reason.split(";")[:-1],
        reason_link=post_body.reason_link,
        reason_description=post_body.reason_description,
        feedback_time=round(datetime.now(tz=UTC).timestamp(), 3),
    )
    await CommentManager.update_comment(post_body.group_id, post_body.record_id, comment_data)
    return JSONResponse(status_code=status.HTTP_200_OK, content=ResponseData(
        code=status.HTTP_200_OK,
        message="success",
        result={},
    ).model_dump(exclude_none=True, by_alias=True))
