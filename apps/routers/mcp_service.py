# Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
"""FastAPI 语义接口中心相关路由"""

import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, UploadFile, status
from fastapi.responses import JSONResponse

from apps.dependency.user import verify_admin, verify_personal_token, verify_session
from apps.schemas.enum_var import SearchType
from apps.schemas.request_data import ActiveMCPServiceRequest, UpdateMCPServiceRequest
from apps.schemas.response_data import (
    ActiveMCPServiceRsp,
    BaseMCPServiceOperationMsg,
    DeleteMCPServiceRsp,
    EditMCPServiceMsg,
    GetMCPServiceDetailMsg,
    GetMCPServiceDetailRsp,
    GetMCPServiceListMsg,
    GetMCPServiceListRsp,
    ResponseData,
    UpdateMCPServiceMsg,
    UpdateMCPServiceRsp,
    UploadMCPServiceIconMsg,
    UploadMCPServiceIconRsp,
)
from apps.services.mcp_service import MCPServiceManager

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/mcp",
    tags=["mcp-service"],
    dependencies=[
        Depends(verify_session),
        Depends(verify_personal_token),
    ],
)
admin_router = APIRouter(
    prefix="/api/admin/mcp",
    tags=["mcp-service"],
    dependencies=[
        Depends(verify_session),
        Depends(verify_personal_token),
        Depends(verify_admin),
    ],
)


@router.get("", response_model=GetMCPServiceListRsp | ResponseData)
async def get_mcpservice_list(
    request: Request,
    searchType: SearchType = SearchType.ALL,  # noqa: N803
    keyword: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
) -> JSONResponse:
    """获取服务列表"""
    user_sub = request.state.user_sub
    try:
        service_cards = await MCPServiceManager.fetch_mcp_services(
            searchType,
            user_sub,
            keyword,
            page,
        )
    except Exception as e:
        err = f"[MCPServiceCenter] 获取MCP服务列表失败: {e}"
        logger.exception(err)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseData(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="ERROR",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=GetMCPServiceListRsp(
            code=status.HTTP_200_OK,
            message="OK",
            result=GetMCPServiceListMsg(
                currentPage=page,
                services=service_cards,
            ),
        ).model_dump(exclude_none=True, by_alias=True),
    )


@admin_router.post("", response_model=UpdateMCPServiceRsp)
async def create_or_update_mcpservice(
    request: Request,
    data: UpdateMCPServiceRequest,
) -> JSONResponse:
    """新建或更新MCP服务"""
    if not data.service_id:
        try:
            service_id = await MCPServiceManager.create_mcpservice(data, request.state.user_sub)
        except Exception as e:
            logger.exception("[MCPServiceCenter] MCP服务创建失败")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content=ResponseData(
                    code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message=f"MCP服务创建失败: {e!s}",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            )
    else:
        try:
            service_id = await MCPServiceManager.update_mcpservice(data, request.state.user_sub)
        except Exception as e:
            logger.exception("[MCPService] 更新MCP服务失败")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content=ResponseData(
                    code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message=f"更新MCP服务失败: {e!s}",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            )
    return JSONResponse(status_code=status.HTTP_200_OK, content=UpdateMCPServiceRsp(
        code=status.HTTP_200_OK,
        message="OK",
        result=UpdateMCPServiceMsg(
            serviceId=service_id,
            name=data.name,
        ),
    ).model_dump(exclude_none=True, by_alias=True))


@admin_router.get("/{serviceId}", response_model=GetMCPServiceDetailRsp)
async def get_service_detail(
    request: Request,
    service_id: Annotated[str, Path(..., alias="serviceId", description="服务ID")],
    *,
    edit: Annotated[bool, Query(..., description="是否为编辑模式")] = False,
) -> JSONResponse:
    """获取MCP服务详情"""
    # 获取MCP服务详情
    try:
        data = await MCPServiceManager.get_mcp_service(service_id)
        config, icon = await MCPServiceManager.get_mcp_config(service_id)
    except Exception as e:
        err = f"[MCPService] 获取MCP服务API失败: {e}"
        logger.exception(err)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseData(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="ERROR",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )

    if edit:
        # 组装编辑所需信息
        detail = EditMCPServiceMsg(
            serviceId=service_id,
            icon=icon,
            name=data.name,
            description=data.description,
            overview=config.overview,
            data=json.dumps(
                config.config.model_dump(by_alias=True, exclude_none=True),
                indent=4,
                ensure_ascii=False,
            ),
            mcpType=config.mcpType,
        )
    else:
        # 组装详情所需信息
        detail = GetMCPServiceDetailMsg(
            serviceId=service_id,
            icon=icon,
            name=data.name,
            description=data.description,
            overview=config.overview,
            tools=data.tools,
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=GetMCPServiceDetailRsp(
            code=status.HTTP_200_OK,
            message="OK",
            result=detail,
        ).model_dump(exclude_none=True, by_alias=True),
    )


@admin_router.get("/{serviceId}", response_model=GetMCPServiceDetailRsp)
async def get_service_detail(serviceId: Annotated[str, Path()]) -> JSONResponse:  # noqa: N803
    """获取MCP服务详情"""
    try:
        data = await MCPServiceManager.get_mcp_service(serviceId)
        config, icon = await MCPServiceManager.get_mcp_config(serviceId)
    except Exception as e:
        pass


@admin_router.delete("/{serviceId}", response_model=DeleteMCPServiceRsp)
async def delete_service(serviceId: Annotated[str, Path()]) -> JSONResponse:  # noqa: N803
    """删除服务"""
    try:
        await MCPServiceManager.delete_mcpservice(serviceId)
    except Exception as e:
        err = f"[MCPServiceManager] 删除MCP服务失败: {e}"
        logger.exception(err)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseData(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="ERROR",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=DeleteMCPServiceRsp(
            code=status.HTTP_200_OK,
            message="OK",
            result=BaseMCPServiceOperationMsg(serviceId=serviceId),
        ).model_dump(exclude_none=True, by_alias=True),
    )


@admin_router.post("/icon", response_model=UpdateMCPServiceRsp)
async def update_mcp_icon(
    serviceId: Annotated[str, Path()],  # noqa: N803
    icon: UploadFile,
) -> JSONResponse:
    """更新MCP服务图标"""
    # 检查当前MCP是否存在
    try:
        await MCPServiceManager.get_mcp_service(serviceId)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"MCP服务未找到: {e!s}") from e

    # 判断文件的size
    if not icon.size or icon.size == 0 or icon.size > 1024 * 1024 * 1:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ResponseData(
                code=status.HTTP_400_BAD_REQUEST,
                message="图标文件为空或超过1MB",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )
    try:
        url = await MCPServiceManager.save_mcp_icon(serviceId, icon)
    except Exception as e:
        err = f"[MCPServiceManager] 更新MCP服务图标失败: {e}"
        logger.exception(err)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseData(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message=err,
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=UploadMCPServiceIconRsp(
            code=status.HTTP_200_OK,
            message="OK",
            result=UploadMCPServiceIconMsg(serviceId=serviceId, url=url),
        ).model_dump(exclude_none=True, by_alias=True),
    )


@router.post("/{mcpId}", response_model=ActiveMCPServiceRsp)
async def active_or_deactivate_mcp_service(
    request: Request,
    mcpId: Annotated[str, Path()],  # noqa: N803
    data: ActiveMCPServiceRequest,
) -> JSONResponse:
    """激活/取消激活mcp"""
    try:
        if data.active:
            await MCPServiceManager.active_mcpservice(request.state.user_sub, service_id, data.mcp_env)
        else:
            await MCPServiceManager.deactive_mcpservice(request.state.user_sub, mcpId)
    except Exception as e:
        err = f"[MCPService] 激活mcp服务失败: {e!s}" if data.active else f"[MCPService] 取消激活mcp服务失败: {e!s}"
        logger.exception(err)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseData(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message=err,
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=ActiveMCPServiceRsp(
            code=status.HTTP_200_OK,
            message="OK",
            result=BaseMCPServiceOperationMsg(serviceId=mcpId),
        ).model_dump(exclude_none=True, by_alias=True),
    )
