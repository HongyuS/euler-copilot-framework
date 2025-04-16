"""
SQL工具。

用于调用外置的Chat2DB工具的API，获得SQL语句；再在PostgreSQL中执行SQL语句，获得数据。
Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

import logging
from collections.abc import AsyncGenerator
from typing import Annotated, Any, ClassVar

import aiohttp
from fastapi import status
from pydantic import Field

from apps.common.config import Config
from apps.entities.enum_var import CallOutputType
from apps.entities.scheduler import CallError, CallOutputChunk, CallVars
from apps.scheduler.call.core import CoreCall
from apps.scheduler.call.sql.schema import SQLInput, SQLOutput

logger = logging.getLogger(__name__)


class SQL(CoreCall, input_type=SQLInput, output_type=SQLOutput):
    """SQL工具。用于调用外置的Chat2DB工具的API，获得SQL语句；再在PostgreSQL中执行SQL语句，获得数据。"""

    name: ClassVar[Annotated[str, Field(description="工具名称", exclude=True, frozen=True)]] = "数据库查询"
    description: ClassVar[
        Annotated[str, Field(description="工具描述", exclude=True, frozen=True)]
    ] = "使用大模型生成SQL语句，用于查询数据库中的结构化数据"

    database_url: str = Field(description="数据库连接地址")
    table_name_list: list[str] = Field(description="表名列表",default=[])
    top_k: int = Field(description="生成SQL语句数量",default=5)
    use_llm_enhancements: bool = Field(description="是否使用大模型增强", default=False)


    async def _init(self, call_vars: CallVars) -> dict[str, Any]:
        """初始化SQL工具。"""
        return SQLInput(
            question=call_vars.question,
        ).model_dump(by_alias=True, exclude_none=True)


    async def _exec(self, input_data: dict[str, Any]) -> AsyncGenerator[CallOutputChunk, None]:
        """运行SQL工具"""
        # 获取必要参数
        data = SQLInput(**input_data)
        post_data = {
            "database_url": self.database_url,
            "table_name_list": self.table_name_list,
            "question": data.question,
            "topk": self.top_k,
            "use_llm_enhancements": self.use_llm_enhancements,
        }
        headers = {
            "Content-Type": "application/json",
        }

        # 生成sql,重试3次直到sql生成数量大于等于top_k
        sql_list = []
        retry = 0
        max_retry = 3
        while retry < max_retry:
            try:
                async with aiohttp.ClientSession() as session, session.post(
                    Config().get_config().extra.sql_url+"/database/sql",
                    headers=headers,
                    json=post_data,
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as response:
                    if response.status == status.HTTP_200_OK:
                        result = await response.json()
                        sub_sql_list = result["result"]["sql_list"]
                        sql_list += sub_sql_list
                        retry += 1
                    else:
                        text = await response.text()
                        logger.error("[SQL] 生成失败：%s", text)
                        retry += 1
                        continue
            except Exception:
                logger.exception("[SQL] 生成失败")
                retry += 1
                continue

            if len(sql_list) >= self.top_k:
                break
        #执行sql,并将执行结果保存在sql_exec_results中
        sql_exec_results = []
        for sql_dict in sql_list:
            database_id = sql_dict["database_id"]
            sql = sql_dict["sql"]
            post_data = {
                "database_id": database_id,
                "sql": sql,
            }
            try:
                async with aiohttp.ClientSession() as session, session.post(
                    Config().get_config().extra.sql_url+"/sql/execute",
                    headers=headers,
                    json=post_data,
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as response:
                    if response.status == status.HTTP_200_OK:
                        result = await response.json()
                        sql_exec_result = result["result"]
                        sql_exec_results.append(sql_exec_result)
                    else:
                        text = await response.text()
                        logger.error("[SQL] 调用失败：%s", text)
                        continue
            except Exception:
                logger.exception("[SQL] 调用失败")
                continue
        if len(sql_exec_results) > 0:
            data = SQLOutput(
                dataset=sql_exec_results,
            ).model_dump(exclude_none=True, by_alias=True)
            yield CallOutputChunk(
                content=data,
                type=CallOutputType.DATA,
            )
        raise CallError(
            message="SQL查询错误：SQL语句错误，数据库查询失败！",
            data={},
        )
