"""
MCP 加载器

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

import json
import logging
import random
from asyncio import subprocess

from anyio import Path
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from sqids.sqids import Sqids

from apps.common.config import Config
from apps.entities.mcp import (
    MCPConfig,
    MCPServerSSEConfig,
    MCPServerStdioConfig,
    MCPType,
)

logger = logging.getLogger(__name__)
sqids = Sqids()
SERVICE_PATH = Path(Config().get_config().deploy.data_dir) / "semantics" / "service"
PROGRAM_PATH = Path(Config().get_config().deploy.data_dir) / "semantics" / "mcp"
DEFAULT_STDIO = MCPServerStdioConfig(
    name="MCP服务名称",
    description="MCP服务描述",
    type=MCPType.STDIO,
    icon_path="icon.png",
    command="uvx",
    args=[
        "your_package",
    ],
    env={
        "EXAMPLE_ENV": "example_value",
    },
)
DEFAULT_SSE = MCPServerSSEConfig(
    name="MCP服务名称",
    description="MCP服务描述",
    type=MCPType.SSE,
    icon_path="icon.png",
    url="http://test.domain/sse",
    env={
        "EXAMPLE_HEADER": "example_value",
    },
)


class MCPLoader:
    """MCP 加载器"""

    @staticmethod
    async def _load_config(config_path: Path) -> MCPConfig:
        """加载 MCP 配置"""
        f = await config_path.open("r", encoding="utf-8")
        f_content = json.loads(await f.read())
        await f.aclose()

        return MCPConfig(**f_content)


    @staticmethod
    async def get_default(mcp_type: MCPType) -> MCPConfig:
        """获取默认的 MCP 配置"""
        random_list = [random.randint(0, 1000000) for _ in range(5)]  # noqa: S311
        if mcp_type == MCPType.STDIO:
            return MCPConfig(
                mcpServers={
                    sqids.encode(random_list): DEFAULT_STDIO,
                },
            )
        if mcp_type == MCPType.SSE:
            return MCPConfig(
                mcpServers={
                    sqids.encode(random_list): DEFAULT_SSE,
                },
            )
        err = f"未找到默认的 MCP 配置: {mcp_type}"
        logger.error(err)
        raise ValueError(err)


    async def _install_uvx(self, mcp_id: str, config: MCPServerStdioConfig) -> MCPServerStdioConfig:
        """安装 uvx 的MCP 服务"""
        # 创建文件夹
        mcp_path = PROGRAM_PATH / mcp_id
        await mcp_path.mkdir(parents=True, exist_ok=True)

        # 找到包名
        package = ""
        for arg in config.args:
            if  "--" not in arg:
                package = arg
                break

        if not package:
            err = "未找到包名"
            logger.error(err)
            raise ValueError(err)

        # 初始化uv项目
        pipe = await subprocess.create_subprocess_exec(
            "uv",
            "init",
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            cwd=mcp_path,
        )
        _, stdout = await pipe.communicate()
        if pipe.returncode != 0:
            err = f"[MCPLoader] 初始化 uv 项目失败: {stdout.decode()}"
            logger.error(err)
            raise ValueError(err)
        logger.info("[MCPLoader] 初始化 uv 项目成功: %s; %s", mcp_path, stdout.decode())

        # 安装Python包
        pipe = await subprocess.create_subprocess_exec(
            "uv",
            "add",
            package,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            cwd=mcp_path,
        )
        _, stdout = await pipe.communicate()
        if pipe.returncode != 0:
            err = f"[MCPLoader] 安装 {package} 失败: {stdout.decode()}"
            logger.error(err)
            raise ValueError(err)
        logger.info("[MCPLoader] 安装 {package} 成功: %s; %s", mcp_path, stdout.decode())

        # 更新配置
        config.command = "uv"
        config.args = ["run", *config.args]

        return config


    async def _install_npx(self, mcp_id: str, config: MCPServerStdioConfig) -> MCPServerStdioConfig:
        """安装 npx 的MCP 服务"""
        mcp_path = PROGRAM_PATH / mcp_id
        await mcp_path.mkdir(parents=True, exist_ok=True)

        # 查找package name
        package = ""
        for arg in config.args:
            if "--" not in arg:
                package = arg
                break

        if not package:
            err = "未找到包名"
            logger.error(err)
            raise ValueError(err)

        # 安装NPM包
        pipe = await subprocess.create_subprocess_exec(
            "npm",
            "install",
            package,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            cwd=mcp_path,
        )
        _, stdout = await pipe.communicate()
        if pipe.returncode != 0:
            err = f"[MCPLoader] 安装 {package} 失败: {stdout.decode()}"
            logger.error(err)
            raise ValueError(err)
        logger.info("[MCPLoader] 安装 {package} 成功: %s; %s", mcp_path, stdout.decode())

        # 更新配置
        config.command = "npm"
        config.args = ["exec", *config.args]

        return config


    async def _install_stdio(self, mcp_id: str, config: MCPServerStdioConfig) -> None:
        """安装 Stdio的MCP 服务"""
        # 尝试自动安装MCP服务
        if config.auto_install:
            if "uv" in config.command:
                await self._install_uvx(mcp_id, config)
            elif "npx" in config.command:
                await self._install_npx(mcp_id, config)


    async def _load(self, config: MCPConfig) -> None:
        """加载 MCP 配置"""
        pass


    async def get(self, mcp_name: str) -> None:
        """获取 MCP 配置"""
        pass

