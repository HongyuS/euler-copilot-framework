# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""FastAPI 聊天接口"""

import asyncio
import logging
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, StreamingResponse

from apps.common.queue import MessageQueue
from apps.common.wordscheck import WordsCheck
from apps.dependency import verify_personal_token, verify_session
from apps.scheduler.scheduler import Scheduler
from apps.scheduler.scheduler.context import save_data
from apps.schemas.enum_var import FlowStatus
from apps.schemas.request_data import RequestData, RequestDataApp
from apps.schemas.response_data import ResponseData
from apps.schemas.task import Task
from apps.services.activity import Activity
from apps.services.blacklist import QuestionBlacklistManager, UserBlacklistManager
from apps.services.conversation import ConversationManager
from apps.services.flow import FlowManager
from apps.services.record import RecordManager
from apps.services.task import TaskManager

RECOMMEND_TRES = 5
logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api",
    tags=["chat"],
    dependencies=[
        Depends(verify_session),
        Depends(verify_personal_token),
    ],
)


async def init_task(post_body: RequestData, user_sub: str, session_id: str) -> Task:
    """初始化Task"""
    # 更改信息并刷新数据库
    if post_body.task_id is None:
        conversation = await ConversationManager.get_conversation_by_conversation_id(
            user_sub=user_sub,
            conversation_id=post_body.conversation_id,
        )
        if not conversation:
            err = "[Chat] 用户没有权限访问该对话！"
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=err)
        task_ids = await TaskManager.delete_tasks_by_conversation_id(post_body.conversation_id)
        await RecordManager.update_record_flow_status_to_cancelled_by_task_ids(task_ids)
        task = await TaskManager.init_new_task(user_sub=user_sub, session_id=session_id, post_body=post_body)
        task.runtime.question = post_body.question
        task.state.app_id = post_body.app.app_id if post_body.app else ""
    else:
        if not post_body.task_id:
            err = "[Chat] task_id 不可为空！"
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="task_id cannot be empty")
        task = await TaskManager.get_task_by_task_id(post_body.task_id)
        post_body.app = RequestDataApp(appId=task.state.app_id)
        post_body.conversation_id = task.ids.conversation_id
        post_body.language = task.language
        post_body.question = task.runtime.question
    return task


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

        task = await init_task(post_body, user_sub, session_id)

        # 创建queue；由Scheduler进行关闭
        queue = MessageQueue()
        await queue.init()

        # 在单独Task中运行Scheduler，拉齐queue.get的时机
        scheduler = Scheduler(task, queue, post_body)
        logger.info(f"[Chat] 用户是否活跃: {await Activity.is_active(user_sub)}")
        scheduler_task = asyncio.create_task(scheduler.run())

        # 处理每一条消息
        async for content in queue.get():
            if content[:6] == "[DONE]":
                break

            yield "data: " + content + "\n\n"
        # 等待Scheduler运行完毕
        await scheduler_task

        # 获取最终答案
        task = scheduler.task
        if task.state.flow_status == FlowStatus.ERROR:
            logger.error("[Chat] 生成答案失败")
            yield "data: [ERROR]\n\n"
            await Activity.remove_active(user_sub)
            return

        # 对结果进行敏感词检查
        if await WordsCheck().check(task.runtime.answer) != 1:
            yield "data: [SENSITIVE]\n\n"
            logger.info("[Chat] 答案包含敏感词！")
            await Activity.remove_active(user_sub)
            return

        # 创建新Record，存入数据库
        await save_data(task, user_sub, post_body)

        if post_body.app and post_body.app.flow_id:
            await FlowManager.update_flow_debug_by_app_and_flow_id(
                post_body.app.app_id,
                post_body.app.flow_id,
                debug=True,
            )

        yield "data: [DONE]\n\n"

    except Exception:
        logger.exception("[Chat] 生成答案失败")
        yield "data: [ERROR]\n\n"

    finally:
        await Activity.remove_active(user_sub)


@router.post("/chat")
async def chat(request: Request, post_body: RequestData) -> StreamingResponse:
    """LLM流式对话接口"""
    session_id = request.state.session_id
    user_sub = request.state.user_sub
    # 问题黑名单检测
    if (post_body.question is not None) and (
        not await QuestionBlacklistManager.check_blacklisted_questions(input_question=post_body.question)
    ):
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


@router.post("/stop", response_model=ResponseData)
async def stop_generation(request: Request) -> JSONResponse:
    """停止生成"""
    await Activity.remove_active(request.state.user_sub)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=ResponseData(
            code=status.HTTP_200_OK,
            message="stop generation success",
            result={},
        ).model_dump(exclude_none=True, by_alias=True),
    )
