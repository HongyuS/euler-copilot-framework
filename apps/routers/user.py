# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""用户相关接口"""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from apps.dependency import get_user
from apps.entities.response_data import UserGetMsp, UserGetRsp
from apps.entities.user import UserInfo
from apps.manager.user import UserManager

router = APIRouter(
    prefix="/api/user",
    tags=["user"],
)


@router.get("")
async def chat(
    user_sub: Annotated[str, Depends(get_user)],
) -> JSONResponse:
    """查询所有用户接口"""
    user_list = await UserManager.get_all_user_sub()
    user_info_list = []
    for user in user_list:
        # user_info = await UserManager.get_userinfo_by_user_sub(user) 暂时不需要查询user_name
        if user == user_sub:
            continue
        info = UserInfo(
            userName=user,
            userSub=user,
        )
        user_info_list.append(info)

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=UserGetRsp(
            code=status.HTTP_200_OK,
            message="用户数据详细信息获取成功",
            result=UserGetMsp(userInfoList=user_info_list),
        ).model_dump(exclude_none=True, by_alias=True),
    )
