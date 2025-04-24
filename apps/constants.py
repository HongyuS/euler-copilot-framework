"""
常量数据

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

# 新对话默认标题
NEW_CHAT = "新对话"
# 滑动窗口限流 默认窗口期
SLIDE_WINDOW_TIME = 60
# OIDC 访问Token 过期时间（分钟）
OIDC_ACCESS_TOKEN_EXPIRE_TIME = 30
# OIDC 刷新Token 过期时间（分钟）
OIDC_REFRESH_TOKEN_EXPIRE_TIME = 180
# 滑动窗口限流 最大请求数
SLIDE_WINDOW_QUESTION_COUNT = 10
# API Call 最大返回值长度（字符）
MAX_API_RESPONSE_LENGTH = 8192
# Executor最大步骤历史数
STEP_HISTORY_SIZE = 3

REASONING_BEGIN_TOKEN = [
    "<think>",
]
REASONING_END_TOKEN = [
    "</think>",
]
