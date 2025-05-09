"""
MCP 加载器

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

import json
import logging
import shutil
from typing import ClassVar

import asyncer
from anyio import Path

from apps.common.config import Config
from apps.common.singleton import SingletonMeta
from apps.entities.mcp import (
    MCPCollection,
    MCPConfig,
    MCPServerSSEConfig,
    MCPServerStdioConfig,
    MCPType,
)
from apps.models.lance import LanceDB
from apps.models.mongo import MongoDB
from apps.scheduler.pool.mcp.client import SSEMCPClient, StdioMCPClient
from apps.scheduler.pool.mcp.install import install_npx, install_uvx

logger = logging.getLogger(__name__)
MCP_PATH = Path(Config().get_config().deploy.data_dir) / "semantics" / "mcp"


class MCPLoader(metaclass=SingletonMeta):
    """
    MCP加载模块

    创建MCP Client，启动MCP进程，并将MCP基本信息（名称、描述、工具列表等）写入数据库
    """

    data: ClassVar[dict[str, dict[str, StdioMCPClient | SSEMCPClient]]] = {}
    """MCP客户端数据，在内存中存储；用户ID -> MCP ID -> MCP Client"""

    @staticmethod
    async def _check_dir() -> None:
        """
        检查MCP目录是否存在

        :return: 无
        """
        if not await (MCP_PATH / "template").exists() or not await (MCP_PATH / "template").is_dir():
            logger.warning("[MCPLoader] template目录不存在，创建中")
            await (MCP_PATH / "template").unlink(missing_ok=True)
            await (MCP_PATH / "template").mkdir(parents=True, exist_ok=True)

        if not await (MCP_PATH / "users").exists() or not await (MCP_PATH / "users").is_dir():
            logger.warning("[MCPLoader] users目录不存在，创建中")
            await (MCP_PATH / "users").unlink(missing_ok=True)
            await (MCP_PATH / "users").mkdir(parents=True, exist_ok=True)


    @staticmethod
    async def _load_config(config_path: Path) -> MCPConfig:
        """
        加载 MCP 配置

        :param Path config_path: MCP配置文件路径
        :return: MCP配置
        :raises FileNotFoundError: 如果配置文件不存在，则抛出异常
        """
        if not await config_path.exists():
            err = f"MCP配置文件不存在: {config_path}"
            logger.error(err)
            raise FileNotFoundError(err)

        f = await config_path.open("r", encoding="utf-8")
        f_content = json.loads(await f.read())
        await f.aclose()

        return MCPConfig.model_validate(f_content)


    async def init_one_template(
            self,
            mcp_id: str,
            config: MCPServerSSEConfig | MCPServerStdioConfig,
    ) -> MCPServerSSEConfig | MCPServerStdioConfig | None:
        """
        初始化MCP模板

        单个MCP模板的初始化。若模板中 ``auto_install`` 为 ``True`` ，则自动安装MCP环境

        :param str mcp_id: MCP模板ID
        :param MCPServerSSEConfig | MCPServerStdioConfig config: MCP配置
        :return: 无
        """
        # 跳过自动安装
        if not config.auto_install:
            logger.info("[MCPLoader] autoInstall为False，跳过自动安装: %s", mcp_id)
            return None

        # 自动安装
        if isinstance(config, MCPServerStdioConfig):
            logger.info("[MCPLoader] Stdio方式的MCP模板，开始自动安装: %s", mcp_id)
            if "uv" in config.command:
                config = await install_uvx(mcp_id, config)
            elif "npx" in config.command:
                config = await install_npx(mcp_id, config)
        else:
            logger.info("[MCPLoader] SSE方式的MCP模板，无法自动安装: %s", mcp_id)
            return None

        # 将配置保存到config.json
        logger.info("[MCPLoader] 更新MCP模板配置: %s", mcp_id)

        config.auto_install = False
        return config


    async def _init_all_template(self) -> None:
        """
        初始化所有MCP模板

        遍历 ``template`` 目录下的所有MCP模板，并初始化。在Framework启动时进行此流程，确保所有MCP均可正常使用。
        """
        template_path = MCP_PATH / "template"
        logger.info("[MCPLoader] 初始化所有MCP模板: %s", template_path)

        # 遍历所有模板
        async for mcp_dir in template_path.iterdir():
            # 目录非法
            if not await mcp_dir.is_dir():
                logger.warning("[MCPLoader] 跳过非目录: %s", mcp_dir)
                continue

            # 检查配置文件是否存在
            config_path = mcp_dir / "config.json"
            if not await config_path.exists():
                logger.warning("[MCPLoader] 跳过没有配置文件的MCP模板: %s", mcp_dir)
                continue

            # 读取配置并加载
            config = await self._load_config(config_path)
            for server_id, server in config.mcp_servers.items():
                server_config = await self.init_one_template(mcp_dir.name, server)
                if server_config:
                    await self._insert_template_db(mcp_dir.name, server_config)
                    config.mcp_servers[server_id] = server_config

            # 保存配置
            f = await config_path.open("w+", encoding="utf-8")
            config_data = config.model_dump(by_alias=True, exclude_none=True)
            await f.write(json.dumps(config_data, indent=4, ensure_ascii=False))
            await f.aclose()


    async def _insert_template_db(self, mcp_id: str, config: MCPServerSSEConfig | MCPServerStdioConfig) -> None:
        """
        插入MCP模板信息到数据库

        :param str mcp_id: MCP模板ID
        :param MCPServerSSEConfig | MCPServerStdioConfig config: MCP配置
        :return: 无
        """
        mcp_collection = MongoDB.get_collection("mcp")
        await mcp_collection.insert_one(
            MCPCollection(
                _id=mcp_id,
                name=config.name,
                description=config.description,
                type=config.type,
            ).model_dump(by_alias=True, exclude_none=True),
        )

    async def save_one_template(self, mcp_id: str, config: MCPConfig) -> None:
        """
        保存单个MCP模板的配置文件（即``template``下的``config.json``文件）

        :param str mcp_id: MCP模板ID
        :param MCPConfig config: MCP配置
        :return: 无
        """
        config_path = MCP_PATH / "template" / mcp_id / "config.json"

        f = await config_path.open("w+", encoding="utf-8")
        config_dict = config.model_dump(by_alias=True, exclude_none=True)
        await f.write(json.dumps(config_dict, indent=4, ensure_ascii=False))
        await f.aclose()

    async def load_one_user(self, user_sub: str, config: MCPConfig) -> dict[str, SSEMCPClient | StdioMCPClient]:
        """
        加载特定用户的单个MCP配置

        MCP Client对象的初始化也在这一步操作。注意：一个config中可能包含多个MCP服务。

        :param str user_sub: 用户ID
        :param MCPConfig config: MCP配置
        :return: 字典，key为MCP模板ID，value为MCP Client对象。
        :rtype: dict[str, SSEMCPClient | StdioMCPClient]
        """
        mcp_dict = {}

        for server_id, server in config.mcp_servers.items():
            if server.type == MCPType.STDIO and isinstance(server, MCPServerStdioConfig):
                logger.info("[MCPLoader] 加载Stdio方式的MCP服务: %s，名称为%s", server_id, server.name)
                mcp_dict[server_id] = StdioMCPClient()
                await mcp_dict[server_id].init(user_sub, server_id, server)
            elif server.type == MCPType.SSE and isinstance(server, MCPServerSSEConfig):
                logger.info("[MCPLoader] 加载SSE方式的MCP服务: %s，名称为%s", server_id, server.name)
                mcp_dict[server_id] = SSEMCPClient()
                await mcp_dict[server_id].init(user_sub, server_id, server)
            else:
                err = f"MCP {server_id}：未知的MCP服务类型“{server.type}”"
                logger.error(err)

        return mcp_dict

    async def _load_all_user(self) -> dict[str, dict[str, SSEMCPClient | StdioMCPClient]]:
        """
        加载所有用户的所有MCP配置

        遍历 ``users`` 目录下的所有用户文件夹，并加载其MCP配置。

        :return: 二层字典，用户ID -> MCP模板ID -> MCP Client对象
        :rtype: dict[str, dict[str, SSEMCPClient | StdioMCPClient]]
        """
        result = {}
        async for user_sub in (MCP_PATH / "users").iterdir():
            if not user_sub.is_dir():
                logger.warning("[MCPLoader] 跳过非目录: %s", user_sub)
                continue

            result[user_sub.name] = {}
            async for mcp_id in user_sub.iterdir():
                if not mcp_id.is_dir():
                    logger.warning("[MCPLoader] 跳过非目录: %s", mcp_id)
                    continue

                config_path = mcp_id / "config.json"
                if not config_path.exists():
                    logger.warning("[MCPLoader] 跳过没有配置文件的MCP模板: %s", mcp_id)
                    continue

                f = await config_path.open("r", encoding="utf-8")
                config = json.loads(await f.read())
                result[user_sub.name][mcp_id.name] = await self.load_one_user(user_sub.name, config)
                await f.aclose()

        return result

    async def _activate_template_db(self, user_sub: str, mcp_id: str) -> None:
        """
        更新数据库，设置MCP模板为激活状态

        :param str user_sub: 用户ID
        :param str mcp_id: MCP模板ID
        :return: 无
        """
        mcp_collection = MongoDB.get_collection("mcp")
        await mcp_collection.update_one(
            {"_id": mcp_id},
            {"$addToSet": {"activated": user_sub}},
        )

    async def _deactivate_template_db(self, user_sub: str, mcp_id: str) -> None:
        """
        更新数据库，设置MCP模板为非激活状态

        :param str user_sub: 用户ID
        :param str mcp_id: MCP模板ID
        :return: 无
        """
        mcp_collection = MongoDB.get_collection("mcp")
        await mcp_collection.update_one(
            {"_id": mcp_id},
            {"$pull": {"activated": user_sub}},
        )

    async def user_active_template(self, user_sub: str, mcp_id: str) -> None:
        """
        用户激活MCP模板

        激活MCP模板时，将已安装的环境拷贝一份到用户目录，并更新数据库

        :param str user_sub: 用户ID
        :param str mcp_id: MCP模板ID
        :return: 无
        :raises FileExistsError: MCP模板已存在或有同名文件，无法激活
        """
        template_path = MCP_PATH / "template" / mcp_id
        user_path = MCP_PATH / "users" / user_sub / mcp_id

        # 判断是否存在
        if user_path.exists():
            err = f"MCP模板“{mcp_id}”已存在或有同名文件，无法激活"
            logger.error(err)
            raise FileExistsError(err)

        # 拷贝文件
        asyncer.asyncify(shutil.copytree)(template_path.as_posix(), user_path.as_posix(), dirs_exist_ok=True)

        # 加载配置
        config_path = user_path / "config.json"
        f = await config_path.open("r", encoding="utf-8")
        config = json.loads(await f.read())
        await f.aclose()
        # 运行进程
        await self.load_one_user(user_sub, config)

        # 更新数据库
        await self._activate_template_db(user_sub, mcp_id)

    async def user_deactive_template(self, user_sub: str, mcp_id: str) -> None:
        """
        取消激活MCP模板

        取消激活MCP模板时，删除用户目录下对应的MCP环境文件夹，并更新数据库

        :param str user_sub: 用户ID
        :param str mcp_id: MCP模板ID
        :return: 无
        """
        # 停止进程
        await self.data[user_sub][mcp_id].stop()

        # 删除用户目录
        user_path = MCP_PATH / "users" / user_sub / mcp_id
        asyncer.asyncify(shutil.rmtree)(user_path.as_posix(), ignore_errors=True)

        # 更新数据库
        await self._deactivate_template_db(user_sub, mcp_id)

    async def init(self) -> None:
        """
        初始化MCP加载器

        :return: 无
        """
        await self._check_dir()
        await self._init_all_template()
        await self._load_all_user()
