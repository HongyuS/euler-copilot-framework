# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""黑名单相关数据结构"""

import uuid

from pydantic import BaseModel

from apps.models import Blacklist
from apps.schemas.response_data import ResponseData


class QuestionBlacklistRequest(BaseModel):
    """POST /api/blacklist/question 请求数据结构"""

    id: str
    question: str
    answer: str
    is_deletion: int


class UserBlacklistRequest(BaseModel):
    """POST /api/blacklist/user 请求数据结构"""

    user_sub: str
    is_ban: int


class AbuseRequest(BaseModel):
    """POST /api/blacklist/complaint 请求数据结构"""

    record_id: uuid.UUID
    reason: str
    reason_type: str


class AbuseProcessRequest(BaseModel):
    """POST /api/blacklist/abuse 请求数据结构"""

    id: uuid.UUID
    is_deletion: int


class GetBlacklistUserMsg(BaseModel):
    """GET /api/blacklist/user Result数据结构"""

    user_subs: list[str]


class GetBlacklistUserRsp(ResponseData):
    """GET /api/blacklist/user 返回数据结构"""

    result: GetBlacklistUserMsg


class GetBlacklistQuestionMsg(BaseModel):
    """GET /api/blacklist/question Result数据结构"""

    question_list: list[Blacklist]


class GetBlacklistQuestionRsp(ResponseData):
    """GET /api/blacklist/question 返回数据结构"""

    result: GetBlacklistQuestionMsg
