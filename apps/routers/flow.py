# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""FastAPI Flow拓扑结构展示API"""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query, Request, status
from fastapi.responses import JSONResponse

from apps.dependency import verify_personal_token, verify_session
from apps.schemas.request_data import PutFlowReq
from apps.schemas.response_data import (
    FlowStructureDeleteMsg,
    FlowStructureDeleteRsp,
    FlowStructureGetMsg,
    FlowStructureGetRsp,
    FlowStructurePutMsg,
    FlowStructurePutRsp,
    NodeServiceListMsg,
    NodeServiceListRsp,
    ResponseData,
)
from apps.services.appcenter import AppCenterManager
from apps.services.flow import FlowManager
from apps.services.flow_validate import FlowService

router = APIRouter(
    prefix="/api/flow",
    tags=["flow"],
    dependencies=[
        Depends(verify_session),
        Depends(verify_personal_token),
    ],
)


@router.get("/service", responses={
        status.HTTP_200_OK: {"model": NodeServiceListRsp},
        status.HTTP_404_NOT_FOUND: {"model": ResponseData},
    },
)
async def get_services(request: Request) -> NodeServiceListRsp:
    """获取用户可访问的节点元数据所在服务的信息"""
    services = await FlowManager.get_service_by_user_id(request.state.user_sub)
    if services is None:
        return NodeServiceListRsp(
            code=status.HTTP_404_NOT_FOUND,
            message="未找到符合条件的Service",
            result=NodeServiceListMsg(),
        )

    return NodeServiceListRsp(
        code=status.HTTP_200_OK,
        message="Node所在Service获取成功",
        result=NodeServiceListMsg(services=services),
    )


@router.get("", response_model=FlowStructureGetRsp, responses={
        status.HTTP_403_FORBIDDEN: {"model": ResponseData},
        status.HTTP_404_NOT_FOUND: {"model": ResponseData},
    },
)
async def get_flow(request: Request, appId: str, flowId: str) -> JSONResponse:  # noqa: N803
    """获取流拓扑结构"""
    if not await AppCenterManager.validate_user_app_access(request.state.user_sub, appId):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=FlowStructureGetRsp(
                code=status.HTTP_403_FORBIDDEN,
                message="用户没有权限访问该Workflow",
                result=FlowStructureGetMsg(),
            ).model_dump(exclude_none=True, by_alias=True),
        )
    result = await FlowManager.get_flow_by_app_and_flow_id(appId, flowId)
    if result is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=FlowStructureGetRsp(
                code=status.HTTP_404_NOT_FOUND,
                message="应用的Workflow获取失败",
                result=FlowStructureGetMsg(),
            ).model_dump(exclude_none=True, by_alias=True),
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=FlowStructureGetRsp(
            code=status.HTTP_200_OK,
            message="应用的Workflow获取成功",
            result=FlowStructureGetMsg(flow=result),
        ).model_dump(exclude_none=True, by_alias=True),
    )


@router.put("", response_model=FlowStructurePutRsp, responses={
        status.HTTP_400_BAD_REQUEST: {"model": ResponseData},
        status.HTTP_403_FORBIDDEN: {"model": ResponseData},
        status.HTTP_404_NOT_FOUND: {"model": ResponseData},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ResponseData},
    },
)
async def put_flow(
    request: Request,
    appId: Annotated[str, Query()],  # noqa: N803
    flowId: Annotated[str, Query()],  # noqa: N803
    put_body: Annotated[PutFlowReq, Body()],
) -> JSONResponse:
    """修改流拓扑结构"""
    if not await AppCenterManager.validate_app_belong_to_user(request.state.user_sub, appId):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=FlowStructurePutRsp(
                code=status.HTTP_403_FORBIDDEN,
                message="用户没有权限访问该流",
                result=FlowStructurePutMsg(),
            ).model_dump(exclude_none=True, by_alias=True),
        )
    put_body.flow = await FlowService.remove_excess_structure_from_flow(put_body.flow)
    await FlowService.validate_flow_illegal(put_body.flow)
    put_body.flow.connectivity = await FlowService.validate_flow_connectivity(put_body.flow)
    result = await FlowManager.put_flow_by_app_and_flow_id(appId, flowId, put_body.flow)
    if result is None:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=FlowStructurePutRsp(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="应用下流更新失败",
                result=FlowStructurePutMsg(),
            ).model_dump(exclude_none=True, by_alias=True),
        )
    flow = await FlowManager.get_flow_by_app_and_flow_id(appId, flowId)
    await AppCenterManager.update_app_publish_status(appId, request.state.user_sub)
    if flow is None:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=FlowStructurePutRsp(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="应用下流更新后获取失败",
                result=FlowStructurePutMsg(),
            ).model_dump(exclude_none=True, by_alias=True),
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=FlowStructurePutRsp(
            code=status.HTTP_200_OK,
            message="应用下流更新成功",
            result=FlowStructurePutMsg(flow=flow),
        ).model_dump(exclude_none=True, by_alias=True),
    )


@router.delete("", response_model=FlowStructureDeleteRsp, responses={
        status.HTTP_404_NOT_FOUND: {"model": ResponseData},
    },
)
async def delete_flow(request: Request, appId: str, flowId: str) -> JSONResponse:  # noqa: N803
    """删除流拓扑结构"""
    if not await AppCenterManager.validate_app_belong_to_user(request.state.user_sub, appId):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=FlowStructureDeleteRsp(
                code=status.HTTP_403_FORBIDDEN,
                message="用户没有权限访问该流",
                result=FlowStructureDeleteMsg(),
            ).model_dump(exclude_none=True, by_alias=True),
        )
    result = await FlowManager.delete_flow_by_app_and_flow_id(appId, flowId)
    if result is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=FlowStructureDeleteRsp(
                code=status.HTTP_404_NOT_FOUND,
                message="应用下流程删除失败",
                result=FlowStructureDeleteMsg(),
            ).model_dump(exclude_none=True, by_alias=True),
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=FlowStructureDeleteRsp(
            code=status.HTTP_200_OK,
            message="应用下流程删除成功",
            result=FlowStructureDeleteMsg(flowId=result),
        ).model_dump(exclude_none=True, by_alias=True),
    )
