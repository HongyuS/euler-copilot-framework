# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""标签相关的Pydantic模型"""

from pydantic import BaseModel


class UserTagInfo(BaseModel):
    """用户标签信息"""

    name: str
    """标签名称"""
    count: int
    """标签频次"""


class UserTagListResponse(BaseModel):
    """用户标签列表响应"""

    tags: list[UserTagInfo]
    """标签列表"""
