# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""API密钥相关数据结构"""

from pydantic import BaseModel

from .response_data import ResponseData


class PostPersonalTokenMsg(BaseModel):
    """POST /api/auth/key Result数据结构"""

    api_key: str


class PostPersonalTokenRsp(ResponseData):
    """POST /api/auth/key 返回数据结构"""

    result: PostPersonalTokenMsg
