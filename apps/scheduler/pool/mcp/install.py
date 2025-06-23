# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP 安装"""

import logging
from asyncio import subprocess

from apps.constants import MCP_PATH
from apps.entities.mcp import MCPServerStdioConfig

logger = logging.getLogger(__name__)


async def install_uvx(mcp_id: str, config: MCPServerStdioConfig) -> MCPServerStdioConfig:
    """
    安装使用uvx包管理器的MCP服务

    安装在 ``template`` 目录下，会作为可拷贝的MCP模板

    :param str mcp_id: MCP模板ID
    :param MCPServerStdioConfig config: MCP配置
    :return: MCP配置
    :rtype: MCPServerStdioConfig
    :raises ValueError: 未找到MCP Server对应的Python包
    """
    # 创建文件夹
    mcp_path = MCP_PATH / "template" / mcp_id / "project"
    await mcp_path.mkdir(parents=True, exist_ok=True)

    # 找到包名
    package = ""
    for arg in config.args:
        if not arg.startswith("-"):
            package = arg
            break

    if not package:
        err = "未找到包名"
        logger.error(err)
        raise ValueError(err)

    # 如果有pyproject.toml文件，则使用sync
    if await (mcp_path / "pyproject.toml").exists():
        pipe = await subprocess.create_subprocess_exec(
            "uv",
            "sync",
            "--index-url",
            "https://pypi.tuna.tsinghua.edu.cn/simple",
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            cwd=mcp_path,
        )
        stdout, _ = await pipe.communicate()
        if pipe.returncode != 0:
            err = f"[MCPLoader] 检查依赖失败: {stdout.decode() if stdout else '（无输出信息）'}"
            logger.error(err)
            raise ValueError(err)
        logger.info("[MCPLoader] 检查依赖成功: %s; %s", mcp_path, stdout.decode() if stdout else "（无输出信息）")

        config.command = "uv"
        config.args = ["run", *config.args]

        return config

    # 否则，初始化uv项目
    pipe = await subprocess.create_subprocess_exec(
        "uv",
        "init",
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        cwd=mcp_path,
    )
    stdout, _ = await pipe.communicate()

    # 安装Python包
    pipe = await subprocess.create_subprocess_exec(
        "uv",
        "add",
        "--index-url",
        "https://pypi.tuna.tsinghua.edu.cn/simple",
        package,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        cwd=mcp_path,
    )
    stdout, _ = await pipe.communicate()
    if pipe.returncode != 0:
        err = f"[MCPLoader] 安装 {package} 失败: {stdout.decode() if stdout else '（无输出信息）'}"
        logger.error(err)
        raise ValueError(err)
    logger.info("[MCPLoader] 安装 %s 成功: %s; %s", package, mcp_path, stdout.decode() if stdout else "（无输出信息）")

    # 更新配置
    config.command = "uv"
    config.args = ["run", *config.args]

    return config


async def install_npx(mcp_id: str, config: MCPServerStdioConfig) -> MCPServerStdioConfig:
    """
    安装使用npx包管理器的MCP服务

    安装在 ``template`` 目录下，会作为可拷贝的MCP模板

    :param str mcp_id: MCP模板ID
    :param MCPServerStdioConfig config: MCP配置
    :return: MCP配置
    :rtype: MCPServerStdioConfig
    :raises ValueError: 未找到MCP Server对应的npm包
    """
    mcp_path = MCP_PATH / "template" / mcp_id / "project"
    await mcp_path.mkdir(parents=True, exist_ok=True)

    # 如果有node_modules文件夹，则认为已安装
    if await (mcp_path / "node_modules").exists():
        config.command = "npm"
        config.args = ["exec", *config.args]
        return config

    # 查找package name
    package = ""
    for arg in config.args:
        if not arg.startswith("-"):
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
    stdout, _ = await pipe.communicate()
    if pipe.returncode != 0:
        err = f"[MCPLoader] 安装 {package} 失败: {stdout.decode() if stdout else '（无输出信息）'}"
        logger.error(err)
        raise ValueError(err)
    logger.info("[MCPLoader] 安装 %s 成功: %s; %s", package, mcp_path, stdout.decode() if stdout else "（无输出信息）")

    # 更新配置
    config.command = "npm"
    config.args = ["exec", *config.args]

    return config
