"""
FastAPI 聊天接口

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

import asyncio
import logging
import uuid
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse, StreamingResponse

from apps.common.queue import MessageQueue
from apps.common.wordscheck import WordsCheck
from apps.dependency import (
    get_session,
    get_user,
    verify_csrf_token,
    verify_user,
)
from apps.entities.request_data import RequestData
from apps.entities.response_data import ResponseData
from apps.manager.blacklist import QuestionBlacklistManager, UserBlacklistManager
from apps.manager.flow import FlowManager
from apps.manager.task import TaskManager
from apps.scheduler.scheduler import Scheduler
from apps.scheduler.scheduler.context import save_data
from apps.service.activity import Activity

RECOMMEND_TRES = 5
logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api",
    tags=["chat"],
)


async def init_task(post_body: RequestData, user_sub: str, session_id: str) -> str:
    """初始化Task"""
    # 生成group_id
    group_id = str(uuid.uuid4()) if not post_body.group_id else post_body.group_id
    post_body.group_id = group_id
    # 创建或还原Task
    task = await TaskManager.get_task(session_id=session_id, post_body=post_body, user_sub=user_sub)
    task_id = task.id
    # 更改信息并刷新数据库
    task.runtime.question = post_body.question
    await TaskManager.save_task(task_id, task)
    return task_id


async def chat_generator(post_body: RequestData, user_sub: str, session_id: str) -> AsyncGenerator[str, None]:
    """进行实际问答，并从MQ中获取消息"""
    try:
        await Activity.set_active(user_sub)

        # 敏感词检查
        if await WordsCheck().check(post_body.question) != 1:
            yield "data: [SENSITIVE]\n\n"
            logger.info("[Chat] 问题包含敏感词！")
            await Activity.remove_active(user_sub)
            return

        task_id = await init_task(post_body, user_sub, session_id)

        # 创建queue；由Scheduler进行关闭
        queue = MessageQueue()
        await queue.init(task_id)

        # 在单独Task中运行Scheduler，拉齐queue.get的时机
        scheduler = Scheduler(task_id, queue, post_body)
        scheduler_task = asyncio.create_task(scheduler.run())

        # 处理每一条消息
        async for content in queue.get():
            if content[:6] == "[DONE]":
                break

            yield "data: " + content + "\n\n"
        # 等待Scheduler运行完毕
        await scheduler_task

        # 获取最终答案
        task = await TaskManager.get_task(task_id)
        answer_text = task.runtime.answer
        if not answer_text:
            logger.error("[Chat] 答案为空")
            yield "data: [ERROR]\n\n"
            await Activity.remove_active(user_sub)
            return

        # 对结果进行敏感词检查
        if await WordsCheck().check(answer_text) != 1:
            yield "data: [SENSITIVE]\n\n"
            logger.info("[Chat] 答案包含敏感词！")
            await Activity.remove_active(user_sub)
            return

        # 创建新Record，存入数据库
        await save_data(task_id, user_sub, post_body, scheduler.used_docs)

        yield "data: [DONE]\n\n"

        if post_body.app and post_body.app.flow_id:
            await FlowManager.update_flow_debug_by_app_and_flow_id(
                post_body.app.app_id,
                post_body.app.flow_id,
                debug=True,
            )

    except Exception:
        logger.exception("[Chat] 生成答案失败")
        yield "data: [ERROR]\n\n"

    finally:
        await Activity.remove_active(user_sub)


@router.post("/chat", dependencies=[Depends(verify_csrf_token), Depends(verify_user)])
async def chat(
    post_body: RequestData,
    user_sub: Annotated[str, Depends(get_user)],
    session_id: Annotated[str, Depends(get_session)],
) -> StreamingResponse:
    """LLM流式对话接口"""
    # 问题黑名单检测
    if not await QuestionBlacklistManager.check_blacklisted_questions(input_question=post_body.question):
        # 用户扣分
        await UserBlacklistManager.change_blacklisted_users(user_sub, -10)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="question is blacklisted")

    # 限流检查
    if await Activity.is_active(user_sub):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests")

    res = chat_generator(post_body, user_sub, session_id)
    return StreamingResponse(
        content=res,
        media_type="text/event-stream",
        headers={
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/stop", response_model=ResponseData, dependencies=[Depends(verify_csrf_token)])
async def stop_generation(user_sub: Annotated[str, Depends(get_user)]):  # noqa: ANN201
    """停止生成"""
    await Activity.remove_active(user_sub)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=ResponseData(
            code=status.HTTP_200_OK,
            message="stop generation success",
            result={},
        ).model_dump(exclude_none=True, by_alias=True),
    )
