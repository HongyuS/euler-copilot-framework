# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP 加载器"""

import json
import logging
import shutil
from hashlib import md5
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
    MCPTool,
    MCPToolVector,
    MCPType,
    MCPVector,
)
from apps.llm.embedding import Embedding
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
    """MCP客户端数据，在内存中存储 MCP ID -> 用户 ID -> MCP Client"""

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


    async def _install_template(
            self,
            mcp_id: str,
            config: MCPServerSSEConfig | MCPServerStdioConfig,
    ) -> MCPServerSSEConfig | MCPServerStdioConfig:
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
            return config

        # 自动安装
        if isinstance(config, MCPServerStdioConfig):
            logger.info("[MCPLoader] Stdio方式的MCP模板，开始自动安装: %s", mcp_id)
            if "uv" in config.command:
                config = await install_uvx(mcp_id, config)
            elif "npx" in config.command:
                config = await install_npx(mcp_id, config)
        else:
            logger.info("[MCPLoader] SSE方式的MCP模板，无法自动安装: %s", mcp_id)

        config.auto_install = False
        return config


    async def init_one_template(self, mcp_id: str, config: MCPServerSSEConfig | MCPServerStdioConfig) -> None:
        """
        初始化单个MCP模板

        :param str mcp_id: MCP模板ID
        :param MCPServerSSEConfig | MCPServerStdioConfig config: MCP配置
        :return: 无
        """
        # 安装MCP模板
        new_server_config = await self._install_template(mcp_id, config)
        new_config = MCPConfig(
            mcpServers={
                mcp_id: new_server_config,
            },
        )

        # 更新数据库
        await self._insert_template_db(mcp_id, config)

        # 保存config
        f = await (MCP_PATH / "template" / mcp_id / "config.json").open("w+", encoding="utf-8")
        config_data = new_config.model_dump(by_alias=True, exclude_none=True)
        await f.write(json.dumps(config_data, indent=4, ensure_ascii=False))
        await f.aclose()


    async def _init_all_template(self) -> None:
        """
        初始化所有MCP模板

        遍历 ``template`` 目录下的所有MCP模板，并初始化。在Framework启动时进行此流程，确保所有MCP均可正常使用。
        这一过程会与数据库内的条目进行对比，若发生修改，则重新创建数据库条目。
        """
        template_path = MCP_PATH / "template"
        logger.info("[MCPLoader] 初始化所有MCP模板: %s", template_path)

        # 遍历所有模板
        async for mcp_dir in template_path.iterdir():
            # 不是目录
            if not await mcp_dir.is_dir():
                logger.warning("[MCPLoader] 跳过非目录: %s", mcp_dir.as_posix())
                continue

            # 检查配置文件是否存在
            config_path = mcp_dir / "config.json"
            if not await config_path.exists():
                logger.warning("[MCPLoader] 跳过没有配置文件的MCP模板: %s", mcp_dir.as_posix())
                continue

            # 读取配置并加载
            config = await self._load_config(config_path)
            if len(config.mcp_servers) == 0:
                logger.warning("[MCPLoader] 跳过没有MCP Server的MCP模板: %s", mcp_dir.as_posix())
                continue
            if len(config.mcp_servers) > 1:
                logger.warning("[MCPLoader] MCP模板中包含多个MCP Server，只会使用第一个: %s", mcp_dir.as_posix())

            # 初始化第一个MCP Server
            server_id, server = next(iter(config.mcp_servers.items()))
            logger.info("[MCPLoader] 初始化MCP模板: %s", mcp_dir.as_posix())
            await self.init_one_template(mcp_dir.name, server)


    async def _create_client(
            self,
            user_sub: str | None,
            mcp_id: str,
            config: MCPServerSSEConfig | MCPServerStdioConfig,
    ) -> SSEMCPClient | StdioMCPClient:
        """
        创建MCP Client

        :param str mcp_id: MCP模板ID
        :param MCPServerSSEConfig | MCPServerStdioConfig config: MCP配置
        :return: MCP Client
        :rtype: SSEMCPClient | StdioMCPClient
        """
        if config.type == MCPType.STDIO and isinstance(config, MCPServerStdioConfig):
            client = StdioMCPClient()
        elif config.type == MCPType.SSE and isinstance(config, MCPServerSSEConfig):
            client = SSEMCPClient()
        else:
            err = f"MCP {mcp_id}：未知的MCP服务类型“{config.type}”"
            logger.error(err)
            raise ValueError(err)

        await client.init(user_sub, mcp_id, config)
        return client


    async def _get_template_tool(
            self,
            mcp_id: str,
            config: MCPServerSSEConfig | MCPServerStdioConfig,
    ) -> list[MCPTool]:
        """
        获取MCP模板的工具列表

        :param str mcp_id: MCP模板ID
        :return: 工具列表
        :rtype: list[str]
        """
        client = await self._create_client(None, mcp_id, config)
        tool_list = []
        for item in client.tools:
            tool_list += [MCPTool(
                id=md5(f"{mcp_id}/{item.name}".encode()).hexdigest(),  # noqa: S324
                name=item.name,
                description=item.description or "",
                input_schema=item.inputSchema,
            )]
        await client.stop()
        return tool_list


    async def _insert_template_db(self, mcp_id: str, config: MCPServerSSEConfig | MCPServerStdioConfig) -> None:
        """
        插入单个MCP Server模板信息到数据库

        :param str mcp_id: MCP模板ID
        :param MCPServerSSEConfig | MCPServerStdioConfig config: MCP配置
        :return: 无
        """
        # 获取工具列表
        tool_list = await self._get_template_tool(mcp_id, config)

        # 基本信息插入数据库
        mcp_collection = MongoDB().get_collection("mcp")
        await mcp_collection.update_one(
            {"_id": mcp_id},
            {
                "$set": MCPCollection(
                    _id=mcp_id,
                    name=config.name,
                    description=config.description,
                    type=config.type,
                    tools=tool_list,
                ).model_dump(by_alias=True, exclude_none=True),
            },
            upsert=True,
        )
        # 服务本身向量化
        embedding = await Embedding.get_embedding([config.description])
        mcp_table = await LanceDB().get_table("mcp")
        await mcp_table.merge_insert("id").when_matched_update_all().when_not_matched_insert_all().execute([
            MCPVector(
                id=mcp_id,
                embedding=embedding[0],
            ),
        ])

        # 工具向量化
        mcp_tool_table = await LanceDB().get_table("mcp_tool")
        tool_desc_list = [tool.description for tool in tool_list]
        tool_embedding = await Embedding.get_embedding(tool_desc_list)
        for tool, embedding in zip(tool_list, tool_embedding, strict=True):
            await mcp_tool_table.merge_insert("id").when_matched_update_all().when_not_matched_insert_all().execute([
                MCPToolVector(
                    id=tool.id,
                    mcp_id=mcp_id,
                    embedding=embedding,
                ),
            ])
        await LanceDB().create_index("mcp_tool")


    async def save_one(self, user_sub: str | None, mcp_id: str, config: MCPConfig) -> None:
        """
        保存单个MCP模板的配置文件（即``template``下的``config.json``文件）

        :param str mcp_id: MCP模板ID
        :param MCPConfig config: MCP配置
        :return: 无
        """
        if user_sub:
            config_path = MCP_PATH / "users" / user_sub / mcp_id / "config.json"
        else:
            config_path = MCP_PATH / "template" / mcp_id / "config.json"
        await Path.mkdir(config_path.parent, parents=True, exist_ok=True)
        f = await config_path.open("w+", encoding="utf-8")
        config_dict = config.model_dump(by_alias=True, exclude_none=True)
        await f.write(json.dumps(config_dict, indent=4, ensure_ascii=False))
        await f.aclose()


    async def load_one_user(
            self, user_sub: str, mcp_id: str, config: MCPConfig,
    ) -> dict[str, SSEMCPClient | StdioMCPClient]:
        """
        加载特定用户的单个MCP配置

        MCP Client对象的初始化也在这一步操作。注意：一个config中可能包含多个MCP服务。

        :param str user_sub: 用户ID
        :param str mcp_id: MCP模板ID
        :param MCPConfig config: MCP配置
        :return: 字典，key为MCP模板ID，value为MCP Client对象。
        :rtype: dict[str, SSEMCPClient | StdioMCPClient]
        """
        if len(config.mcp_servers) == 0:
            err = f"[MCPLoader] MCP模板“{mcp_id}”中没有MCP Server"
            logger.error(err)
            raise ValueError(err)
        if len(config.mcp_servers) > 1:
            err = f"[MCPLoader] MCP模板“{mcp_id}”中包含多个MCP Server，只会使用第一个"
            logger.error(err)
            raise ValueError(err)

        server_id, server = next(iter(config.mcp_servers.items()))
        client = await self._create_client(user_sub, mcp_id, server)
        return {server_id: client}


    async def _load_all_user(self) -> dict[str, dict[str, SSEMCPClient | StdioMCPClient]]:
        """
        加载所有用户的所有MCP配置

        遍历 ``users`` 目录下的所有用户文件夹，并加载其MCP配置。

        :return: 二层字典，用户ID -> MCP模板ID -> MCP Client对象
        :rtype: dict[str, dict[str, SSEMCPClient | StdioMCPClient]]
        """
        result = {}
        async for user_proj in (MCP_PATH / "users").iterdir():
            if not await user_proj.is_dir():
                logger.warning("[MCPLoader] 跳过非目录: %s", user_proj)
                continue

            result[user_proj.name] = {}
            async for mcp_id in user_proj.iterdir():
                if not await mcp_id.is_dir():
                    logger.warning("[MCPLoader] 跳过非目录: %s", mcp_id)
                    continue

                config_path = mcp_id / "config.json"
                if not await config_path.exists():
                    logger.warning("[MCPLoader] 跳过没有配置文件的MCP模板: %s", mcp_id)
                    continue

                f = await config_path.open("r", encoding="utf-8")
                config = MCPConfig.model_validate(json.loads(await f.read()))
                result[user_proj.name][mcp_id.name] = await self.load_one_user(user_proj.name, mcp_id.name, config)
                await f.aclose()

        return result


    async def _activate_template_db(self, user_sub: str, mcp_id: str) -> None:
        """
        更新数据库，设置MCP模板为激活状态

        :param str user_sub: 用户ID
        :param str mcp_id: MCP模板ID
        :return: 无
        """
        mcp_collection = MongoDB().get_collection("mcp")
        await mcp_collection.update_one(
            {"_id": mcp_id},
            {"$addToSet": {"activated": user_sub}},
            upsert=True
        )


    async def _deactivate_template_db(self, user_sub: str, mcp_id: str) -> None:
        """
        更新数据库，设置MCP模板为非激活状态

        :param str user_sub: 用户ID
        :param str mcp_id: MCP模板ID
        :return: 无
        """
        mcp_collection = MongoDB().get_collection("mcp")
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
        if await user_path.exists():
            err = f"MCP模板“{mcp_id}”已存在或有同名文件，无法激活"
            logger.error(err)
            raise FileExistsError(err)

        # 拷贝文件
        await asyncer.asyncify(shutil.copytree)(template_path.as_posix(), user_path.as_posix(), dirs_exist_ok=True)

        # 加载配置
        config_path = user_path / "config.json"
        f = await config_path.open("r", encoding="utf-8")
        config = MCPConfig.model_validate(json.loads(await f.read()))
        await f.aclose()
        # 运行进程
        await self.load_one_user(user_sub, mcp_id, config)

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
        try:
            await self.data[mcp_id][user_sub].stop()
        except KeyError:
            logger.warning("[MCPLoader] MCP模板“%s”中没有用户“%s”", mcp_id, user_sub)

        # 删除用户目录
        user_path = MCP_PATH / "users" / user_sub / mcp_id
        await asyncer.asyncify(shutil.rmtree)(user_path.as_posix(), ignore_errors=True)

        # 更新数据库
        await self._deactivate_template_db(user_sub, mcp_id)

    async def _find_deleted_mcp(self) -> list[str]:
        """
        查找在文件系统中被修改和被删除的MCP

        :return: 被修改的MCP列表和被删除的MCP列表
        :rtype: tuple[list[str], list[str]]
        """
        deleted_mcp_list = []

        mcp_collection = MongoDB().get_collection("mcp")
        mcp_list = await mcp_collection.find({}, {"_id": 1, "hash": 1}).to_list(None)
        for db_item in mcp_list:
            mcp_id: str = db_item["_id"]
            mcp_path: Path = MCP_PATH / "template" / mcp_id
            if not await mcp_path.exists():
                deleted_mcp_list.append(mcp_id)
        logger.info("[MCPLoader] 这些MCP在文件系统中被删除: %s", deleted_mcp_list)
        return deleted_mcp_list


    async def _remove_deleted_mcp(self, deleted_mcp_list: list[str]) -> None:
        """
        删除无效的MCP在数据库中的记录

        :param list[str] deleted_mcp_list: 被删除的MCP列表
        :return: 无
        """
        # 从MongoDB中移除
        mcp_collection = MongoDB().get_collection("mcp")
        await mcp_collection.delete_many({"_id": {"$in": deleted_mcp_list}})
        logger.info("[MCPLoader] 清除数据库中无效的MCP")

        # 从LanceDB中移除
        mcp_table = await LanceDB().get_table("mcp")
        for mcp_id in deleted_mcp_list:
            await mcp_table.delete(f"id == '{mcp_id}'")
        logger.info("[MCPLoader] 清除LanceDB中无效的MCP")


    async def init(self) -> None:
        """
        初始化MCP加载器

        :return: 无
        """
        # 清空数据库
        deleted_mcp_list = await self._find_deleted_mcp()
        await self._remove_deleted_mcp(deleted_mcp_list)

        # 检查目录
        await self._check_dir()

        # 初始化所有模板
        await self._init_all_template()

        # 加载所有用户
        await self._load_all_user()
