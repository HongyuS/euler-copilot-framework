# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""配置加载器"""

from apps.scheduler.pool.loader.app import AppLoader
from apps.scheduler.pool.loader.call import CallLoader
from apps.scheduler.pool.loader.flow import FlowLoader
from apps.scheduler.pool.loader.mcp import MCPLoader
from apps.scheduler.pool.loader.service import ServiceLoader

__all__ = [
    "AppLoader",
    "CallLoader",
    "FlowLoader",
    "MCPLoader",
    "ServiceLoader",
]
