# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""FastAPI：对话相关接口"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import JSONResponse

from apps.dependency import verify_personal_token, verify_session
from apps.models.conversation import Conversation
from apps.schemas.request_data import (
    ChangeConversationData,
    DeleteConversationData,
)
from apps.schemas.response_data import (
    AddConversationMsg,
    AddConversationRsp,
    ConversationListItem,
    ConversationListMsg,
    ConversationListRsp,
    DeleteConversationMsg,
    DeleteConversationRsp,
    ResponseData,
    UpdateConversationRsp,
)
from apps.services.appcenter import AppCenterManager
from apps.services.conversation import ConversationManager
from apps.services.document import DocumentManager

router = APIRouter(
    prefix="/api/conversation",
    tags=["conversation"],
    dependencies=[
        Depends(verify_session),
        Depends(verify_personal_token),
    ],
)
logger = logging.getLogger(__name__)


async def create_new_conversation(
    title: str, user_sub: str, app_id: uuid.UUID | None = None,
    *,
    debug: bool = False,
) -> Conversation:
    """判断并创建新对话"""
    # 新建对话
    if app_id and not await AppCenterManager.validate_user_app_access(user_sub, app_id):
        err = "Invalid app_id."
        raise RuntimeError(err)
    new_conv = await ConversationManager.add_conversation_by_user_sub(
        title=title,
        user_sub=user_sub,
        app_id=app_id,
        debug=debug,
    )
    if not new_conv:
        err = "Create new conversation failed."
        raise RuntimeError(err)
    return new_conv

@router.get("", response_model=ConversationListRsp, responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ResponseData},
    },
)
async def get_conversation_list(request: Request) -> JSONResponse:
    """获取对话列表"""
    conversations = await ConversationManager.get_conversation_by_user_sub(
        request.state.user_sub,
    )
    # 把已有对话转换为列表
    result_conversations = []
    for conv in conversations:
        conversation_list_item = ConversationListItem(
            conversationId=conv.id,
            title=conv.title,
            docCount=await DocumentManager.get_doc_count(conv.id),
            createdTime=conv.createdAt.strftime("%Y-%m-%d %H:%M:%S"),
            appId=conv.appId,
            debug=conv.isTemporary,
        )
        result_conversations.append(conversation_list_item)

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=ConversationListRsp(
            code=status.HTTP_200_OK,
            message="success",
            result=ConversationListMsg(conversations=result_conversations),
        ).model_dump(exclude_none=True, by_alias=True),
    )


@router.post("", response_model=AddConversationRsp)
async def add_conversation(
    request: Request,
    appId: Annotated[uuid.UUID | None, Query()] = None,  # noqa: N803
    title: str = "New Chat",
    *,
    debug: Annotated[bool, Query()] = False,
) -> JSONResponse:
    """手动创建新对话"""
    # 尝试创建新对话
    try:
        debug = debug if debug is not None else False
        new_conv = await create_new_conversation(
            title=title,
            user_sub=request.state.user_sub,
            app_id=appId,
            debug=debug,
        )
    except RuntimeError as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseData(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message=str(e),
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=AddConversationRsp(
            code=status.HTTP_200_OK,
            message="success",
            result=AddConversationMsg(conversationId=new_conv.id),
        ).model_dump(exclude_none=True, by_alias=True),
    )


@router.put("", response_model=UpdateConversationRsp)
async def update_conversation(
    user_sub: Annotated[str, Depends(get_user)],
    conversation_id: Annotated[str, Query(..., alias="conversationId")],
    post_body: ChangeConversationData,
) -> JSONResponse:
    """更新特定Conversation的数据"""
    # 判断Conversation是否合法
    conv = await ConversationManager.get_conversation_by_conversation_id(user_sub, conversation_id)
    if not conv or conv.userSub != user_sub:
        logger.error("[Conversation] conversation_id 不存在")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ResponseData(
                code=status.HTTP_400_BAD_REQUEST,
                message="conversation_id not found",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )

    # 更新Conversation数据
    try:
        await ConversationManager.update_conversation_by_conversation_id(
            user_sub,
            conversation_id,
            {
                "title": post_body.title,
            },
        )
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseData(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="update conversation failed",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=UpdateConversationRsp(
            code=status.HTTP_200_OK,
            message="success",
            result=ConversationListItem(
                conversationId=conv.id,
                title=conv.title,
                docCount=await DocumentManager.get_doc_count(user_sub, conv.id),
                createdTime=datetime.fromtimestamp(conv.createdAt, tz=pytz.timezone("Asia/Shanghai")).strftime(
                    "%Y-%m-%d %H:%M:%S",
                ),
                appId=conv.appId if conv.appId else "",
                debug=conv.debug if conv.debug else False,
            ),
        ).model_dump(exclude_none=True, by_alias=True),
    )


@router.delete("", response_model=ResponseData)
async def delete_conversation(
    request: Request,
    post_body: DeleteConversationData,
) -> JSONResponse:
    """删除特定对话"""
    deleted_conversation = []
    for conversation_id in post_body.conversation_list:
        # 删除对话
        await ConversationManager.delete_conversation_by_conversation_id(
            request.state.user_sub,
            conversation_id,
        )
        # 删除对话对应的文件
        await DocumentManager.delete_document_by_conversation_id(
            request.state.user_sub,
            conversation_id,
        )
        deleted_conversation.append(conversation_id)

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=DeleteConversationRsp(
            code=status.HTTP_200_OK,
            message="success",
            result=DeleteConversationMsg(conversationIdList=deleted_conversation),
        ).model_dump(exclude_none=True, by_alias=True),
    )
