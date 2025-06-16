# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""API密钥相关数据结构"""

from pydantic import BaseModel

from apps.entities.response_data import ResponseData


class _GetAuthKeyMsg(BaseModel):
    """GET /api/auth/key Result数据结构"""

    api_key_exists: bool


class GetAuthKeyRsp(ResponseData):
    """GET /api/auth/key 返回数据结构"""

    result: _GetAuthKeyMsg


class PostAuthKeyMsg(BaseModel):
    """POST /api/auth/key Result数据结构"""

    api_key: str


class PostAuthKeyRsp(ResponseData):
    """POST /api/auth/key 返回数据结构"""

    result: PostAuthKeyMsg
