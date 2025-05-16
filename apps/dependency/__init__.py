"""
FastAPI 依赖注入模块

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

from apps.dependency.user import (
    get_session,
    get_user,
    get_user_by_api_key,
    verify_api_key,
    verify_user,
)

__all__ = [
    "get_session",
    "get_user",
    "get_user_by_api_key",
    "verify_api_key",
    "verify_user",
]
