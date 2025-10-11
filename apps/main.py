# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""主程序"""

import asyncio
import logging

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_profiler import Profiler
from rich.console import Console
from rich.logging import RichHandler

from .common.config import config
from .common.postgres import postgres
from .routers import (
    appcenter,
    auth,
    blacklist,
    chat,
    comment,
    conversation,
    document,
    flow,
    health,
    llm,
    mcp_service,
    parameter,
    record,
    service,
    tag,
    user,
)
from .scheduler.pool.pool import pool

# 定义FastAPI app
app = FastAPI(redoc_url=None)
Profiler(app)
# 定义FastAPI全局中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.fastapi.domain],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# 关联API路由
app.include_router(appcenter.router)
app.include_router(auth.admin_router)
app.include_router(auth.router)
app.include_router(blacklist.admin_router)
app.include_router(blacklist.router)
app.include_router(chat.router)
app.include_router(comment.router)
app.include_router(conversation.router)
app.include_router(document.router)
app.include_router(flow.router)
app.include_router(health.router)
app.include_router(llm.router)
app.include_router(llm.admin_router)
app.include_router(mcp_service.router)
app.include_router(mcp_service.admin_router)
app.include_router(parameter.router)
app.include_router(record.router)
app.include_router(service.router)
app.include_router(service.admin_router)
app.include_router(tag.admin_router)
app.include_router(user.router)

# logger配置
LOGGER_FORMAT = "%(funcName)s() - %(message)s"
DATE_FORMAT = "%y-%b-%d %H:%M:%S"
logging.basicConfig(
    level=logging.INFO,
    format=LOGGER_FORMAT,
    datefmt=DATE_FORMAT,
    handlers=[RichHandler(rich_tracebacks=True, console=Console(
        color_system="256",
        width=160,
    ))],
)


async def init_resources() -> None:
    """初始化必要资源"""
    await postgres.init()
    await pool.init()

# 运行
if __name__ == "__main__":
    # 初始化必要资源
    asyncio.run(init_resources())

    # 启动FastAPI
    uvicorn.run(app, host="0.0.0.0", port=8002, log_level="info", log_config=None)
