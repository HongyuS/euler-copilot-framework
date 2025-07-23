# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""FastAPI 用户资产库路由"""

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

from apps.dependency import verify_personal_token, verify_session
from apps.schemas.request_data import (
    UpdateKbReq,
)
from apps.schemas.response_data import (
    ListTeamKnowledgeMsg,
    ListTeamKnowledgeRsp,
    ResponseData,
)
from apps.services.knowledge import KnowledgeBaseManager

router = APIRouter(
    prefix="/api/knowledge",
    tags=["knowledge"],
    dependencies=[
        Depends(verify_session),
        Depends(verify_personal_token),
    ],
)


@router.get("", response_model=ListTeamKnowledgeRsp, responses={
    status.HTTP_404_NOT_FOUND: {"model": ResponseData},
},
)
async def list_kb(request: Request) -> JSONResponse:
    """获取当前用户的知识库ID"""
    kb_list = await KnowledgeBaseManager.get_selected_kb(request.state.user_sub)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=ListTeamKnowledgeRsp(
            code=status.HTTP_200_OK,
            message="success",
            result=ListTeamKnowledgeMsg(teamKbList=kb_list),
        ).model_dump(exclude_none=True, by_alias=True),
    )


@router.put("", response_model=ResponseData)
async def update_kb(request: Request, put_body: UpdateKbReq) -> JSONResponse:
    """更新当前用户的知识库ID"""
    kb_ids_update_success = await KnowledgeBaseManager.save_selected_kb(
        request.state.user_sub, put_body.kb_ids,
    )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=ResponseData(
            code=status.HTTP_200_OK,
            message="success",
            result=kb_ids_update_success,
        ).model_dump(exclude_none=True, by_alias=True),
    )
