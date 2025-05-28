# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP 加载器"""

import asyncio
import json
import logging
import shutil

import asyncer
from anyio import Path

from apps.common.config import Config
from apps.common.process_handler import ProcessHandler
from apps.common.singleton import SingletonMeta
from apps.entities.mcp import (
    MCPCollection,
    MCPConfig,
    MCPServerSSEConfig,
    MCPServerStdioConfig,
    MCPStatus,
    MCPTool,
    MCPToolVector,
    MCPType,
    MCPVector,
)
from apps.llm.embedding import Embedding
from apps.manager.mcp_service import MCPServiceManager
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

    @staticmethod
    async def _install_template_task(
        mcp_id: str, config: MCPServerSSEConfig | MCPServerStdioConfig, user_subs: list[str]
    ) -> None:
        """
        安装依赖

        :param str mcp_id: MCP模板ID
        :param MCPServerSSEConfig | MCPServerStdioConfig config: MCP配置
        :param list[str] user_subs: 用户IDs
        :return: 无
        """
        await MCPLoader.update_template_status(mcp_id, MCPStatus.INSTALLING)
        if isinstance(config, MCPServerStdioConfig):
            logger.info("[MCPLoader] Stdio方式的MCP模板，开始自动安装: %s", mcp_id)
            try:
                if "uv" in config.command:
                    await install_uvx(mcp_id, config)
                elif "npx" in config.command:
                    await install_npx(mcp_id, config)
            except:
                await MCPLoader.update_template_status(mcp_id, MCPStatus.FAILED)
                raise
        else:
            logger.info("[MCPLoader] SSE方式的MCP模板，无法自动安装: %s", mcp_id)
        # 更新数据库
        await MCPLoader._insert_template_db(mcp_id, config)
        await MCPLoader.update_template_status(mcp_id, MCPStatus.READY)
        logger.info("[MCPLoader] MCP模板安装成功: %s", mcp_id)

    @staticmethod
    async def _process_install_config(
        mcp_id: str,
        config: MCPServerSSEConfig | MCPServerStdioConfig,
        user_subs: list[str] | None = None
    ) -> None:
        """
        异步安装依赖，并把template同步给用户

        :param str mcp_id: MCP模板ID
        :param MCPServerSSEConfig | MCPServerStdioConfig config: MCP配置
        :param list[str] | None user_subs: 用户IDs
        :return: 无
        """
        if user_subs is None:
            user_subs = []
        mcp_ids = await MCPServiceManager.get_all_failed_or_ready_mcp_ids()
        for mcp_id in mcp_ids:
            await ProcessHandler.remove_task(mcp_id)
        if not ProcessHandler.add_task(mcp_id, MCPLoader._install_template_task, mcp_id, config, user_subs):
            logger.warning("安装任务暂时无法执行，请稍后重试: %s", mcp_id)
            await MCPLoader.update_template_status(mcp_id, MCPStatus.INSTALLING)

    @staticmethod
    async def _install_template(
            mcp_id: str,
            config: MCPServerSSEConfig | MCPServerStdioConfig,
            user_subs: list[str] | None = None
    ) -> MCPServerSSEConfig | MCPServerStdioConfig:
        """
        初始化MCP模板

        单个MCP模板的初始化。若模板中 ``auto_install`` 为 ``True`` ，则自动安装MCP环境

        :param str mcp_id: MCP模板ID
        :param MCPServerSSEConfig | MCPServerStdioConfig config: MCP配置
        :param list[str] | None user_subs: 用户IDs
        :return: 无
        """
        # 跳过自动安装
        if not config.auto_install:
            logger.info("[MCPLoader] autoInstall为False，跳过自动安装: %s", mcp_id)
            return config

        # 自动安装
        await MCPLoader._process_install_config(mcp_id, config, user_subs)

        config.auto_install = False
        return config

    @staticmethod
    async def process_install_mcp(mcp_id: str, user_subs: list[str]) -> None:
        """
        异步安装依赖

        :param str mcp_id: MCP模板ID
        :param list[str] user_subs: 用户IDs
        :return: 无
        """
        config_path = MCP_PATH / "template" / mcp_id / "config.json"

        config = await MCPLoader._load_config(config_path)
        for server in config.mcp_servers.values():
            await MCPLoader._process_install_config(mcp_id, server, user_subs)

    @staticmethod
    async def init_one_template(
            mcp_id: str,
            config: MCPServerSSEConfig | MCPServerStdioConfig,
            user_subs: list[str] | None = None
    ) -> None:
        """
        初始化单个MCP模板

        :param str mcp_id: MCP模板ID
        :param MCPServerSSEConfig | MCPServerStdioConfig config: MCP配置
        :param list[str] | None user_subs: 用户IDs
        :return: 无
        """
        # 安装MCP模板
        new_server_config = await MCPLoader._install_template(mcp_id, config, user_subs)
        new_config = MCPConfig(
            mcpServers={
                mcp_id: new_server_config,
            },
        )

        # 保存config
        template_config = MCP_PATH / "template" / mcp_id / "config.json"
        await Path.mkdir(template_config.parent, parents=True, exist_ok=True)
        f = await template_config.open("w+", encoding="utf-8")
        config_data = new_config.model_dump(by_alias=True, exclude_none=True)
        await f.write(json.dumps(config_data, indent=4, ensure_ascii=False))
        await f.aclose()

    @staticmethod
    async def _init_all_template() -> None:
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
            config = await MCPLoader._load_config(config_path)
            if len(config.mcp_servers) == 0:
                logger.warning("[MCPLoader] 跳过没有MCP Server的MCP模板: %s", mcp_dir.as_posix())
                continue
            if len(config.mcp_servers) > 1:
                logger.warning("[MCPLoader] MCP模板中包含多个MCP Server，只会使用第一个: %s", mcp_dir.as_posix())

            # 初始化第一个MCP Server
            server_id, server = next(iter(config.mcp_servers.items()))
            logger.info("[MCPLoader] 初始化MCP模板: %s", mcp_dir.as_posix())
            await MCPLoader.init_one_template(mcp_dir.name, server)

    @staticmethod
    async def _get_template_tool(
            mcp_id: str,
            config: MCPServerSSEConfig | MCPServerStdioConfig,
            user_sub: str | None = None,
    ) -> list[MCPTool]:
        """
        获取MCP模板的工具列表

        :param str mcp_id: MCP模板ID
        :param MCPServerSSEConfig | MCPServerStdioConfig config: MCP配置
        :param str | None user_sub: 用户ID,默认为None
        :return: 工具列表
        :rtype: list[str]
        """
        # 创建客户端
        if config.type == MCPType.STDIO and isinstance(config, MCPServerStdioConfig):
            client = StdioMCPClient()
        elif config.type == MCPType.SSE and isinstance(config, MCPServerSSEConfig):
            client = SSEMCPClient()
        else:
            err = f"MCP {mcp_id}：未知的MCP服务类型“{config.type}”"
            logger.error(err)
            raise ValueError(err)

        await client.init(user_sub, mcp_id, config)

        # 获取工具列表
        tool_list = []
        for item in client.tools:
            tool_list += [MCPTool(
                id=f"{mcp_id}/{item.name}",
                name=item.name,
                mcp_id=mcp_id,
                description=item.description or "",
                input_schema=item.inputSchema,
            )]
        await client.stop()
        return tool_list

    @staticmethod
    async def _insert_template_db(mcp_id: str, config: MCPServerSSEConfig | MCPServerStdioConfig) -> None:
        """
        插入单个MCP Server模板信息到数据库

        :param str mcp_id: MCP模板ID
        :param MCPServerSSEConfig | MCPServerStdioConfig config: MCP配置
        :return: 无
        """
        # 获取工具列表
        tool_list = await MCPLoader._get_template_tool(mcp_id, config)

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

        while True:
            try:
                mcp_table = await LanceDB().get_table("mcp")
                await mcp_table.merge_insert("id").when_matched_update_all().when_not_matched_insert_all().execute([
                    MCPVector(
                        id=mcp_id,
                        embedding=embedding[0],
                    ),
                ])
                break
            except Exception as e:
                if "Commit conflict" in str(e):
                    logger.error("[MCPLoader] LanceDB插入mcp冲突，重试中...")  # noqa: TRY400
                    await asyncio.sleep(0.01)
                else:
                    raise

        # 工具向量化
        tool_desc_list = [tool.description for tool in tool_list]
        tool_embedding = await Embedding.get_embedding(tool_desc_list)
        for tool, embedding in zip(tool_list, tool_embedding, strict=True):
            while True:
                try:
                    mcp_tool_table = await LanceDB().get_table("mcp_tool")
                    await mcp_tool_table.merge_insert("id").when_matched_update_all().when_not_matched_insert_all().execute([
                        MCPToolVector(
                            id=tool.id,
                            mcp_id=mcp_id,
                            embedding=embedding,
                        ),
                    ])
                    break
                except Exception as e:
                    if "Commit conflict" in str(e):
                        logger.error("[MCPLoader] LanceDB插入mcp_tool冲突，重试中...")  # noqa: TRY400
                        await asyncio.sleep(0.01)
                    else:
                        raise
        await LanceDB().create_index("mcp_tool")

    @staticmethod
    async def save_one(user_sub: str | None, mcp_id: str, config: MCPConfig) -> None:
        """
        保存单个MCP模板的配置文件（即``template``下的``config.json``文件）

        :param str user_sub: 用户ID
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

    @staticmethod
    async def update_template_status(mcp_id: str, status: MCPStatus) -> None:
        """
        更新数据库中MCP模板状态

        :param str mcp_id: MCP模板ID
        :param MCPStatus status: MCP模板status
        :return: 无
        """
        # 更新数据库
        mongo = MongoDB()
        mcp_collection = mongo.get_collection("mcp")
        await mcp_collection.update_one(
            {"_id": mcp_id},
            {"$set": {"status": status}},
            upsert=True,
        )

    @staticmethod
    async def user_active_template(user_sub: str, mcp_id: str) -> None:
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
        await asyncer.asyncify(shutil.copytree)(
            template_path.as_posix(),
            user_path.as_posix(),
            dirs_exist_ok=True,
            symlinks=True,
        )

        # 更新数据库
        mongo = MongoDB()
        mcp_collection = mongo.get_collection("mcp")
        await mcp_collection.update_one(
            {"_id": mcp_id},
            {"$addToSet": {"activated": user_sub}},
        )

    @staticmethod
    async def user_deactive_template(user_sub: str, mcp_id: str) -> None:
        """
        取消激活MCP模板

        取消激活MCP模板时，删除用户目录下对应的MCP环境文件夹，并更新数据库

        :param str user_sub: 用户ID
        :param str mcp_id: MCP模板ID
        :return: 无
        """
        # 删除用户目录
        user_path = MCP_PATH / "users" / user_sub / mcp_id
        await asyncer.asyncify(shutil.rmtree)(user_path.as_posix(), ignore_errors=True)

        # 更新数据库
        mongo = MongoDB()
        mcp_collection = mongo.get_collection("mcp")
        await mcp_collection.update_one(
            {"_id": mcp_id},
            {"$pull": {"activated": user_sub}},
        )

    @staticmethod
    async def _find_deleted_mcp() -> list[str]:
        """
        查找在文件系统中被修改和被删除的MCP

        :return: 被修改的MCP列表和被删除的MCP列表
        :rtype: tuple[list[str], list[str]]
        """
        deleted_mcp_list = []

        mcp_collection = MongoDB().get_collection("mcp")
        mcp_list = await mcp_collection.find({}, {"_id": 1}).to_list(None)
        for db_item in mcp_list:
            mcp_path: Path = MCP_PATH / "template" / db_item["_id"]
            if not await mcp_path.exists():
                deleted_mcp_list.append(db_item["_id"])
        logger.info("[MCPLoader] 这些MCP在文件系统中被删除: %s", deleted_mcp_list)
        return deleted_mcp_list

    @staticmethod
    async def remove_deleted_mcp(deleted_mcp_list: list[str]) -> None:
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
        for mcp_id in deleted_mcp_list:
            while True:
                try:
                    mcp_table = await LanceDB().get_table("mcp")
                    await mcp_table.delete(f"id == '{mcp_id}'")
                    break
                except Exception as e:
                    if "Commit conflict" in str(e):
                        logger.error("[MCPLoader] LanceDB删除mcp冲突，重试中...")  # noqa: TRY400
                        await asyncio.sleep(0.01)
                    else:
                        raise
        logger.info("[MCPLoader] 清除LanceDB中无效的MCP")

    @staticmethod
    async def delete_mcp(mcp_id: str) -> None:
        """
        删除MCP

        :param str mcp_id: 被删除的MCP ID
        :return: 无
        """
        await MCPLoader.remove_deleted_mcp([mcp_id])
        template_path = MCP_PATH / "template" / mcp_id
        if await template_path.exists():
            await asyncer.asyncify(shutil.rmtree)(template_path.as_posix(), ignore_errors=True)

    @staticmethod
    async def _load_user_mcp() -> None:
        """
        加载用户MCP

        :return: 用户MCP列表
        :rtype: dict[str, list[str]]
        """
        user_path = MCP_PATH / "users"
        if not await user_path.exists():
            logger.warning("[MCPLoader] users目录不存在，跳过加载用户MCP")
            return

        mongo = MongoDB()
        mcp_collection = mongo.get_collection("mcp")

        mcp_list = {}
        # 遍历users目录
        async for user_dir in user_path.iterdir():
            if not await user_dir.is_dir():
                continue

            # 遍历单个用户的目录
            async for mcp_dir in user_dir.iterdir():
                # 检查数据库中是否有这个MCP
                mcp_item = await mcp_collection.find_one({"_id": mcp_dir.name})
                if not mcp_item:
                    # 数据库中不存在，当前文件夹无效，删除
                    await asyncer.asyncify(shutil.rmtree)(mcp_dir.as_posix(), ignore_errors=True)

                # 添加到dict
                if mcp_dir.name not in mcp_list:
                    mcp_list[mcp_dir.name] = []
                mcp_list[mcp_dir.name].append(user_dir.name)

        # 更新所有MCP的activated情况
        for mcp_id, user_list in mcp_list.items():
            await mcp_collection.update_one(
                {"_id": mcp_id},
                {"$set": {"activated": user_list}},
            )
            # 确保已激活的MCP依赖已安装
            await MCPLoader.process_install_mcp(mcp_id, user_list)

    @staticmethod
    async def init() -> None:
        """
        初始化MCP加载器

        :return: 无
        """
        # 清空数据库
        deleted_mcp_list = await MCPLoader._find_deleted_mcp()
        await MCPLoader.remove_deleted_mcp(deleted_mcp_list)

        # 检查目录
        await MCPLoader._check_dir()

        # 初始化所有模板
        await MCPLoader._init_all_template()

        # 加载用户MCP
        await MCPLoader._load_user_mcp()
