"""
自定义异常类

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""


class FlowBranchValidationError(Exception):
    """service.flow 流程分支验证错误"""


class FlowNodeValidationError(Exception):
    """service.flow 流程节点验证错误"""


class FlowEdgeValidationError(Exception):
    """service.flow 流程边验证错误"""


class LoginSettingsError(Exception):
    """manager.session 登录设置错误"""


class SessionError(Exception):
    """manager.session Session错误"""


class ActivityError(Exception):
    """service.activity 活动错误"""
