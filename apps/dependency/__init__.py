# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""FastAPI 依赖注入模块"""

from apps.dependency.user import (
    verify_personal_token,
    verify_session,
)

__all__ = [
    "verify_personal_token",
    "verify_session",
]
