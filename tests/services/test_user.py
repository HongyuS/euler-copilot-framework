# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from apps.models import User
from apps.schemas.request_data import UserUpdateRequest
from apps.services.user import UserManager


@pytest.fixture
def mock_session():
    """创建模拟的数据库会话"""
    session = AsyncMock(spec=AsyncSession)
    return session


@pytest.fixture
def mock_user():
    """创建测试用户对象"""
    user = User(
        userSub="test_user_sub",
        isActive=True,
        isWhitelisted=False,
        credit=100,
    )
    return user


@pytest.mark.asyncio
class TestUserManager:
    """测试 UserManager 类"""

    @patch("apps.services.user.postgres.session")
    async def test_list_user(self, mock_session_maker, mock_session):
        """测试 list_user 方法"""
        # 准备测试数据
        mock_users = [
            User(userSub="user1", isActive=True, isWhitelisted=False, credit=100),
            User(userSub="user2", isActive=False, isWhitelisted=True, credit=200),
        ]

        # 配置模拟会话
        mock_session_maker.return_value.__aenter__.return_value = mock_session
        mock_session.scalar.return_value = 2
        mock_session.scalars.return_value.all.return_value = mock_users

        # 调用被测试方法
        users, count = await UserManager.list_user(n=10, page=1)

        # 验证结果
        assert len(users) == 2
        assert count == 2
        mock_session.scalar.assert_called_once()
        mock_session.scalars.assert_called_once()

    @patch("apps.services.user.postgres.session")
    async def test_get_user_found(self, mock_session_maker, mock_user):
        """测试 get_user 方法 - 找到用户"""
        # 配置模拟会话
        mock_session_maker.return_value.__aenter__.return_value = mock_user
        mock_session = AsyncMock()
        mock_session_maker.return_value.__aenter__.return_value = mock_session
        mock_session.scalars.return_value.one_or_none.return_value = mock_user

        # 调用被测试方法
        result = await UserManager.get_user("test_user_sub")

        # 验证结果
        assert result == mock_user
        mock_session.scalars.assert_called_once()

    @patch("apps.services.user.postgres.session")
    async def test_get_user_not_found(self, mock_session_maker):
        """测试 get_user 方法 - 未找到用户"""
        # 配置模拟会话
        mock_session = AsyncMock()
        mock_session_maker.return_value.__aenter__.return_value = mock_session
        mock_session.scalars.return_value.one_or_none.return_value = None

        # 调用被测试方法
        result = await UserManager.get_user("nonexistent_user")

        # 验证结果
        assert result is None
        mock_session.scalars.assert_called_once()

    @patch("apps.services.user.postgres.session")
    async def test_update_user_create_new(self, mock_session_maker, mock_user):
        """测试 update_user 方法 - 创建新用户"""
        # 配置模拟会话
        mock_session = AsyncMock()
        mock_session_maker.return_value.__aenter__.return_value = mock_session
        mock_session.scalars.return_value.one_or_none.return_value = None

        # 准备测试数据
        update_data = UserUpdateRequest(
            isActive=True,
            isWhitelisted=False,
            credit=150,
        )

        # 调用被测试方法
        await UserManager.update_user("new_user_sub", update_data)

        # 验证调用
        mock_session.merge.assert_called_once()
        mock_session.commit.assert_called_once()

    @patch("apps.services.user.postgres.session")
    async def test_update_user_update_existing(self, mock_session_maker, mock_user):
        """测试 update_user 方法 - 更新现有用户"""
        # 配置模拟会话
        mock_session = AsyncMock()
        mock_session_maker.return_value.__aenter__.return_value = mock_session
        mock_session.scalars.return_value.one_or_none.return_value = mock_user

        # 准备测试数据
        update_data = UserUpdateRequest(
            isActive=False,
            credit=200
        )

        # 调用被测试方法
        await UserManager.update_user("test_user_sub", update_data)

        # 验证调用
        assert mock_user.isActive == False
        assert mock_user.credit == 200
        assert mock_user.lastLogin is not None
        mock_session.commit.assert_called_once()

    @patch("apps.services.user.postgres.session")
    async def test_delete_user_found(self, mock_session_maker, mock_user):
        """测试 delete_user 方法 - 找到并删除用户"""
        # 配置模拟会话
        mock_session = AsyncMock()
        mock_session_maker.return_value.__aenter__.return_value = mock_session
        mock_session.scalars.return_value.one_or_none.return_value = mock_user

        # 调用被测试方法
        await UserManager.delete_user("test_user_sub")

        # 验证调用
        mock_session.delete.assert_called_once_with(mock_user)
        mock_session.commit.assert_called_once()

    @patch("apps.services.user.postgres.session")
    async def test_delete_user_not_found(self, mock_session_maker):
        """测试 delete_user 方法 - 未找到用户"""
        # 配置模拟会话
        mock_session = AsyncMock()
        mock_session_maker.return_value.__aenter__.return_value = mock_session
        mock_session.scalars.return_value.one_or_none.return_value = None

        # 调用被测试方法
        await UserManager.delete_user("nonexistent_user")

        # 验证调用
        mock_session.delete.assert_not_called()
        mock_session.commit.assert_not_called()
