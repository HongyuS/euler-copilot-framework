# Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
"""FastAPI 语义接口中心相关路由"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status
from fastapi.responses import JSONResponse

from apps.dependency.user import get_user, verify_user
from apps.entities.enum_var import SearchType
from apps.entities.request_data import ActiveMCPServiceRequest, UpdateMCPServiceRequest
from apps.entities.response_data import (
    ActiveMCPServiceRsp,
    BaseMCPServiceOperationMsg,
    DeleteMCPServiceRsp,
    GetMCPServiceDetailMsg,
    GetMCPServiceDetailRsp,
    GetMCPServiceListMsg,
    GetMCPServiceListRsp,
    ResponseData,
    UpdateMCPServiceMsg,
    UpdateMCPServiceRsp,
)
from apps.exceptions import InstancePermissionError, ServiceIDError
from apps.manager.mcp_service import MCPServiceManager
from apps.manager.user import UserManager

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/mcp",
    tags=["mcp-service"],
    dependencies=[Depends(verify_user)],
)


@router.get("", response_model=GetMCPServiceListRsp | ResponseData)
async def get_mcpservice_list(
        user_sub: Annotated[str, Depends(get_user)],
        search_type: Annotated[
            SearchType, Query(..., alias="searchType", description="搜索类型"),
        ] = SearchType.ALL,
        keyword: Annotated[str | None, Query(..., alias="keyword", description="搜索关键字")] = None,
        page: Annotated[int, Query(..., alias="page", ge=1, description="页码")] = 1,
) -> JSONResponse:
    """获取服务列表"""
    try:
        service_cards = await MCPServiceManager.fetch_mcp_services(
            search_type,
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


@router.post("", response_model=UpdateMCPServiceRsp)
async def create_or_update_mcpservice(
        user_sub: Annotated[str, Depends(get_user)],  # TODO: get_user直接获取所有用户信息
        data: UpdateMCPServiceRequest,
) -> JSONResponse:
    """新建或更新MCP服务"""
    user_data = await UserManager.get_userinfo_by_user_sub(user_sub)
    if not user_data or not user_data.is_admin:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=ResponseData(
                code=status.HTTP_403_FORBIDDEN,
                message="非管理员无法注册更新mcp",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )
    # TODO：不要使用base64编码
    if not data.service_id:
        try:
            service_id = await MCPServiceManager.create_mcpservice(data)
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
            service_id = await MCPServiceManager.update_mcpservice(data)
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


@router.get("/{serviceId}", response_model=GetMCPServiceDetailRsp)
async def get_service_detail(
        user_sub: Annotated[str, Depends(get_user)],
        service_id: Annotated[str, Path(..., alias="serviceId", description="服务ID")],
        *,
        edit: Annotated[bool, Query(..., description="是否为编辑模式")] = False,
) -> JSONResponse:
    """获取MCP服务详情"""
    # 示例：返回指定MCP服务的详情
    if edit:
        pass

    try:
        data = await MCPServiceManager.get_mcp_service_detail(service_id)
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
    detail = GetMCPServiceDetailMsg(
        serviceId=service_id,
        icon=data.icon,
        name=data.name,
        description=data.description,
        tools=data.tools,
        data=data.config_str,
        mcpType=data.mcp_type,
    )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=GetMCPServiceDetailRsp(
            code=status.HTTP_200_OK,
            message="OK",
            result=detail,
        ).model_dump(exclude_none=True, by_alias=True),
    )


@router.delete("/{serviceId}", response_model=DeleteMCPServiceRsp)
async def delete_service(
        user_sub: Annotated[str, Depends(get_user)],
        service_id: Annotated[str, Path(..., alias="serviceId", description="服务ID")],
) -> JSONResponse:
    """删除服务"""
    try:
        await MCPServiceManager.delete_mcpservice(user_sub, service_id)
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
            result=BaseMCPServiceOperationMsg(serviceId=service_id),
        ).model_dump(exclude_none=True, by_alias=True),
    )


@router.post("/{serviceId}", response_model=ActiveMCPServiceRsp)
async def active_or_deactivate_mcp_service(
        user_sub: Annotated[str, Depends(get_user)],
        service_id: Annotated[str, Path(..., alias="serviceId", description="服务ID")],
        data: ActiveMCPServiceRequest,
) -> JSONResponse:
    """激活/取消激活mcp"""
    try:
        if data.active:
            await MCPServiceManager.active_mcpservice(user_sub, service_id)
        else:
            await MCPServiceManager.deactive_mcpservice(user_sub, service_id)
    except Exception as e:
        err = f"[MCPService] 激活mcp服务失败: {e}" if data.active else f"[MCPService] 取消激活mcp服务失败: {e}"
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
            result=BaseMCPServiceOperationMsg(serviceId=service_id),
        ).model_dump(exclude_none=True, by_alias=True),
    )
