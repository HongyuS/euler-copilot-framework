# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""FastAPI 用户资产库路由"""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, status
from fastapi.responses import JSONResponse

from apps.dependency import get_user, verify_user
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
        Depends(verify_user),
    ],
)


@router.get("", response_model=ListTeamKnowledgeRsp, responses={
    status.HTTP_404_NOT_FOUND: {"model": ResponseData},
},
)
async def list_kb(user_sub: Annotated[str, Depends(get_user)]) -> JSONResponse:
    """获取当前用户的知识库ID"""
    team_kb_list = await KnowledgeBaseManager.get_selected_kb(user_sub)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=ListTeamKnowledgeRsp(
            code=status.HTTP_200_OK,
            message="success",
            result=ListTeamKnowledgeMsg(teamKbList=team_kb_list),
        ).model_dump(exclude_none=True, by_alias=True),
    )


@router.put("", response_model=ResponseData)
async def update_kb(
    user_sub: Annotated[str, Depends(get_user)],
    put_body: Annotated[UpdateKbReq, Body(...)],
) -> JSONResponse:
    """更新当前用户的知识库ID"""
    kb_ids_update_success = await KnowledgeBaseManager.save_selected_kb(user_sub, put_body.kb_ids)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=ResponseData(
            code=status.HTTP_200_OK,
            message="success",
            result=kb_ids_update_success,
        ).model_dump(exclude_none=True, by_alias=True),
    )
