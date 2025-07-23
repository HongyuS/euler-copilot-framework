# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""FastAPI 黑名单相关路由"""

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

from apps.dependency.user import verify_admin, verify_personal_token, verify_session
from apps.schemas.request_data import (
    AbuseProcessRequest,
    AbuseRequest,
    QuestionBlacklistRequest,
    UserBlacklistRequest,
)
from apps.schemas.response_data import (
    GetBlacklistQuestionMsg,
    GetBlacklistQuestionRsp,
    GetBlacklistUserMsg,
    GetBlacklistUserRsp,
    ResponseData,
)
from apps.services.blacklist import (
    AbuseManager,
    QuestionBlacklistManager,
    UserBlacklistManager,
)

admin_router = APIRouter(
    prefix="/api/blacklist",
    tags=["blacklist"],
    dependencies=[
        Depends(verify_session),
        Depends(verify_personal_token),
        Depends(verify_admin),
    ],
)
user_router = APIRouter(
    prefix="/api/blacklist",
    tags=["blacklist"],
    dependencies=[
        Depends(verify_session),
        Depends(verify_personal_token),
    ],
)
PAGE_SIZE = 20
MAX_CREDIT = 100


@admin_router.get("/user", response_model=GetBlacklistUserRsp)
async def get_blacklist_user(page: int = 0) -> JSONResponse:
    """获取黑名单用户"""
    # 计算分页
    user_list = await UserBlacklistManager.get_blacklisted_users(
        PAGE_SIZE,
        page * PAGE_SIZE,
    )

    return JSONResponse(status_code=status.HTTP_200_OK, content=GetBlacklistUserRsp(
        code=status.HTTP_200_OK,
        message="ok",
        result=GetBlacklistUserMsg(user_subs=user_list),
    ).model_dump(exclude_none=True, by_alias=True))


@admin_router.post("/user", response_model=ResponseData)
async def change_blacklist_user(request: UserBlacklistRequest) -> JSONResponse:
    """操作黑名单用户"""
    # 拉黑用户
    if request.is_ban:
        result = await UserBlacklistManager.change_blacklisted_users(
            request.user_sub,
            -MAX_CREDIT,
        )
    # 解除拉黑
    else:
        result = await UserBlacklistManager.change_blacklisted_users(
            request.user_sub,
            MAX_CREDIT,
        )

    if not result:
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=ResponseData(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Change user blacklist error.",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))
    return JSONResponse(status_code=status.HTTP_200_OK, content=ResponseData(
        code=status.HTTP_200_OK,
        message="ok",
        result={},
    ).model_dump(exclude_none=True, by_alias=True))

@admin_router.get("/question", response_model=GetBlacklistQuestionRsp)
async def get_blacklist_question(page: int = 0) -> JSONResponse:
    """
    获取黑名单问题

    目前情况下，先直接输出问题，不做用户类型校验
    """
    # 计算分页
    question_list = await QuestionBlacklistManager.get_blacklisted_questions(
        PAGE_SIZE,
        page * PAGE_SIZE,
        is_audited=True,
    )
    return JSONResponse(status_code=status.HTTP_200_OK, content=GetBlacklistQuestionRsp(
        code=status.HTTP_200_OK,
        message="ok",
        result=GetBlacklistQuestionMsg(question_list=question_list),
    ).model_dump(exclude_none=True, by_alias=True))

@admin_router.post("/question", response_model=ResponseData)
async def change_blacklist_question(request: QuestionBlacklistRequest) -> JSONResponse:
    """黑名单问题检测或操作"""
    # 删问题
    if request.is_deletion:
        result = await QuestionBlacklistManager.change_blacklisted_questions(
            request.id,
            request.question,
            request.answer,
            is_deletion=True,
        )
    else:
        # 改问题
        result = await QuestionBlacklistManager.change_blacklisted_questions(
            request.id,
            request.question,
            request.answer,
            is_deletion=False,
        )

    if not result:
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=ResponseData(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Modify question blacklist error.",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))
    return JSONResponse(status_code=status.HTTP_200_OK, content=ResponseData(
        code=status.HTTP_200_OK,
        message="ok",
        result={},
    ).model_dump(exclude_none=True, by_alias=True))


@admin_router.post("/complaint", response_model=ResponseData)
async def abuse_report(raw_request: Request, request: AbuseRequest) -> JSONResponse:
    """用户实施举报"""
    result = await AbuseManager.change_abuse_report(
        raw_request.state.user_sub,
        request.record_id,
        request.reason_type,
        request.reason,
    )

    if not result:
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=ResponseData(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Report abuse complaint error.",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))
    return JSONResponse(status_code=status.HTTP_200_OK, content=ResponseData(
        code=status.HTTP_200_OK,
        message="ok",
        result={},
    ).model_dump(exclude_none=True, by_alias=True))


@admin_router.get("/abuse", response_model=GetBlacklistQuestionRsp)
async def get_abuse_report(page: int = 0) -> JSONResponse:
    """获取待审核的问答对"""
    # 此处前端需记录ID
    result = await QuestionBlacklistManager.get_blacklisted_questions(
        PAGE_SIZE,
        page * PAGE_SIZE,
        is_audited=False,
    )
    return JSONResponse(status_code=status.HTTP_200_OK, content=GetBlacklistQuestionRsp(
        code=status.HTTP_200_OK,
        message="ok",
        result=GetBlacklistQuestionMsg(question_list=result),
    ).model_dump(exclude_none=True, by_alias=True))

@admin_router.post("/abuse", response_model=ResponseData)
async def change_abuse_report(request: AbuseProcessRequest) -> JSONResponse:
    """对被举报问答对进行操作"""
    if request.is_deletion:
        result = await AbuseManager.audit_abuse_report(
            request.id,
            is_deletion=True,
        )
    else:
        result = await AbuseManager.audit_abuse_report(
            request.id,
            is_deletion=False,
        )

    if not result:
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=ResponseData(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Audit abuse question error.",
            result={},
        ).model_dump(exclude_none=True, by_alias=True))
    return JSONResponse(status_code=status.HTTP_200_OK, content=ResponseData(
        code=status.HTTP_200_OK,
        message="ok",
        result={},
    ).model_dump(exclude_none=True, by_alias=True))
