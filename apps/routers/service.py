# Copyright (c) Huawei Technologies Co., Ltd. 2024-2025. All rights reserved.
"""FastAPI 语义接口中心相关路由"""

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request, status
from fastapi.responses import JSONResponse

from apps.dependency.user import verify_personal_token, verify_session
from apps.exceptions import InstancePermissionError
from apps.schemas.enum_var import SearchType
from apps.schemas.request_data import ChangeFavouriteServiceRequest, UpdateServiceRequest
from apps.schemas.response_data import (
    BaseServiceOperationMsg,
    ChangeFavouriteServiceMsg,
    ChangeFavouriteServiceRsp,
    DeleteServiceRsp,
    GetServiceDetailMsg,
    GetServiceDetailRsp,
    GetServiceListMsg,
    GetServiceListRsp,
    ResponseData,
    UpdateServiceMsg,
    UpdateServiceRsp,
)
from apps.services.service import ServiceCenterManager

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/service",
    tags=["service-center"],
    dependencies=[
        Depends(verify_session),
        Depends(verify_personal_token),
    ],
)


@router.get("", response_model=GetServiceListRsp | ResponseData)
async def get_service_list(  # noqa: PLR0913
    request: Request,
    *,
    createdByMe: bool = False, favorited: bool = False,  # noqa: N803
    searchType: SearchType = SearchType.ALL, keyword: str | None = None,  # noqa: N803
    page: int = 1, pageSize: int = 16,  # noqa: N803
) -> JSONResponse:
    """获取服务列表"""
    if createdByMe and favorited:  # 只能同时选择一个筛选条件
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ResponseData(
                code=status.HTTP_400_BAD_REQUEST,
                message="INVALID_PARAMETER",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )

    service_cards, total_count = [], -1
    try:
        if createdByMe:  # 筛选我创建的
            service_cards, total_count = await ServiceCenterManager.fetch_user_services(
                request.state.user_sub,
                searchType,
                keyword,
                page,
                pageSize,
            )
        elif favorited:  # 筛选我收藏的
            service_cards, total_count = await ServiceCenterManager.fetch_favorite_services(
                request.state.user_sub,
                searchType,
                keyword,
                page,
                pageSize,
            )
        else:  # 获取所有服务
            service_cards, total_count = await ServiceCenterManager.fetch_all_services(
                request.state.user_sub,
                searchType,
                keyword,
                page,
                pageSize,
            )
    except Exception:
        logger.exception("[ServiceCenter] 获取服务列表失败")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseData(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="ERROR",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )
    if total_count == -1:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ResponseData(
                code=status.HTTP_400_BAD_REQUEST,
                message="INVALID_PARAMETER",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=GetServiceListRsp(
            code=status.HTTP_200_OK,
            message="OK",
            result=GetServiceListMsg(
                currentPage=page,
                totalCount=total_count,
                services=service_cards,
            ),
        ).model_dump(exclude_none=True, by_alias=True),
    )


@router.post("", response_model=UpdateServiceRsp)
async def update_service(request: Request, data: UpdateServiceRequest) -> JSONResponse:
    """上传并解析服务"""
    if not data.service_id:
        try:
            service_id = await ServiceCenterManager.create_service(request.state.user_sub, data.data)
        except Exception as e:
            logger.exception("[ServiceCenter] 创建服务失败")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content=ResponseData(
                    code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message=f"OpenAPI解析错误: {e!s}",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            )
    else:
        try:
            service_id = await ServiceCenterManager.update_service(request.state.user_sub, data.service_id, data.data)
        except InstancePermissionError:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content=ResponseData(
                    code=status.HTTP_403_FORBIDDEN,
                    message="未授权访问",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            )
        except Exception as e:
            logger.exception("[ServiceCenter] 更新服务失败")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content=ResponseData(
                    code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message=f"更新服务失败: {e!s}",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            )
    try:
        name, apis = await ServiceCenterManager.get_service_apis(service_id)
    except Exception as e:
        logger.exception("[ServiceCenter] 获取服务API失败")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseData(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message=f"获取服务API失败: {e!s}",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )
    msg = UpdateServiceMsg(serviceId=service_id, name=name, apis=apis)
    rsp = UpdateServiceRsp(code=status.HTTP_200_OK, message="OK", result=msg)
    return JSONResponse(status_code=status.HTTP_200_OK, content=rsp.model_dump(exclude_none=True, by_alias=True))


@router.get("/{serviceId}", response_model=GetServiceDetailRsp)
async def get_service_detail(
    request: Request, serviceId: Annotated[uuid.UUID, Path()],  # noqa: N803
    *, edit: bool = False,
) -> JSONResponse:
    """获取服务详情"""
    # 示例：返回指定服务的详情
    if edit:
        try:
            name, data = await ServiceCenterManager.get_service_data(request.state.user_sub, serviceId)
        except ServiceIDError:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=ResponseData(
                    code=status.HTTP_400_BAD_REQUEST,
                    message="Service ID错误",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            )
        except InstancePermissionError:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content=ResponseData(
                    code=status.HTTP_403_FORBIDDEN,
                    message="未授权访问",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            )
        except Exception:
            logger.exception("[ServiceCenter] 获取服务数据失败")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content=ResponseData(
                    code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message="ERROR",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            )
        detail = GetServiceDetailMsg(serviceId=serviceId, name=name, data=data)
    else:
        try:
            name, apis = await ServiceCenterManager.get_service_apis(serviceId)
        except ServiceIDError:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=ResponseData(
                    code=status.HTTP_400_BAD_REQUEST,
                    message="Service ID错误",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            )
        except Exception:
            logger.exception("[ServiceCenter] 获取服务API失败")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content=ResponseData(
                    code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    message="ERROR",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            )
        detail = GetServiceDetailMsg(serviceId=serviceId, name=name, apis=apis)
    rsp = GetServiceDetailRsp(code=status.HTTP_200_OK, message="OK", result=detail)
    return JSONResponse(status_code=status.HTTP_200_OK, content=rsp.model_dump(exclude_none=True, by_alias=True))


@router.delete("/{serviceId}", response_model=DeleteServiceRsp)
async def delete_service(request: Request, serviceId: Annotated[uuid.UUID, Path()]) -> JSONResponse:  # noqa: N803
    """删除服务"""
    try:
        await ServiceCenterManager.delete_service(request.state.user_sub, serviceId)
    except ServiceIDError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ResponseData(
                code=status.HTTP_400_BAD_REQUEST,
                message="Service ID错误",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )
    except InstancePermissionError:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=ResponseData(
                code=status.HTTP_403_FORBIDDEN,
                message="未授权访问",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )
    except Exception:
        logger.exception("[ServiceCenter] 删除服务失败")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseData(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="ERROR",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )
    msg = BaseServiceOperationMsg(serviceId=serviceId)
    rsp = DeleteServiceRsp(code=status.HTTP_200_OK, message="OK", result=msg)
    return JSONResponse(status_code=status.HTTP_200_OK, content=rsp.model_dump(exclude_none=True, by_alias=True))


@router.put("/{serviceId}", response_model=ChangeFavouriteServiceRsp)
async def modify_favorite_service(
    request: Request,
    serviceId: Annotated[uuid.UUID, Path()],  # noqa: N803
    data: ChangeFavouriteServiceRequest,
) -> JSONResponse:
    """修改服务收藏状态"""
    try:
        success = await ServiceCenterManager.modify_favorite_service(
            request.state.user_sub,
            serviceId,
            favorited=data.favorited,
        )
        if not success:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=ResponseData(
                    code=status.HTTP_400_BAD_REQUEST,
                    message="INVALID_PARAMETER",
                    result={},
                ).model_dump(exclude_none=True, by_alias=True),
            )
    except ServiceIDError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ResponseData(
                code=status.HTTP_400_BAD_REQUEST,
                message="Service ID错误",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )
    except Exception:
        logger.exception("[ServiceCenter] 修改服务收藏状态失败")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ResponseData(
                code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="ERROR",
                result={},
            ).model_dump(exclude_none=True, by_alias=True),
        )
    msg = ChangeFavouriteServiceMsg(serviceId=serviceId, favorited=data.favorited)
    rsp = ChangeFavouriteServiceRsp(code=status.HTTP_200_OK, message="OK", result=msg)
    return JSONResponse(status_code=status.HTTP_200_OK, content=rsp.model_dump(exclude_none=True, by_alias=True))
