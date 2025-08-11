# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""用户相关接口"""

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

from apps.dependency import verify_personal_token, verify_session
from apps.schemas.response_data import UserGetMsp, UserGetRsp
from apps.schemas.user import UserInfo
from apps.services.user import UserManager

router = APIRouter(
    prefix="/api/user",
    tags=["user"],
    dependencies=[Depends(verify_session), Depends(verify_personal_token)],
)


@router.get("")
async def list_user(
    request: Request, page_size: int = 10, page_num: int = 1,
) -> JSONResponse:
    """查询不包含当前用户的所有用户信息，返回给前端，用以进行应用权限设置"""
    user_list, total = await UserManager.list_user(page_size, page_num)
    user_info_list = []
    for user in user_list:
        if user.userSub == request.state.user_sub:
            continue
        info = UserInfo(
            userName=user.userSub,
            userSub=user.userSub,
        )
        user_info_list.append(info)

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=UserGetRsp(
            code=status.HTTP_200_OK,
            message="用户数据详细信息获取成功",
            result=UserGetMsp(userInfoList=user_info_list, total=total),
        ).model_dump(exclude_none=True, by_alias=True),
    )


@router.post("")
async def update_user_info(request: Request, data: UserUpdateRequest) -> JSONResponse:
    """更新用户信息接口"""
    # 更新用户信息

    result = await UserManager.update_userinfo_by_user_sub(request.state.user_sub, data)
    if not result:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"code": status.HTTP_200_OK, "message": "用户信息更新成功"},
        )
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"code": status.HTTP_404_NOT_FOUND, "message": "用户信息更新失败"},
    )
