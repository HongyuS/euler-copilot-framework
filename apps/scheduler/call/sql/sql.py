# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""SQL工具"""

import logging
from collections.abc import AsyncGenerator
from typing import Any

import httpx
from fastapi import status
from pydantic import Field

from apps.common.config import config
from apps.models import LanguageType
from apps.scheduler.call.core import CoreCall
from apps.schemas.enum_var import CallOutputType
from apps.schemas.scheduler import (
    CallError,
    CallInfo,
    CallOutputChunk,
    CallVars,
)

from .schema import SQLInput, SQLOutput

logger = logging.getLogger(__name__)
MESSAGE = {
    "fail": {
        LanguageType.CHINESE: "SQL查询错误：SQL语句执行失败！",
        LanguageType.ENGLISH: "SQL query error: SQL statement execution failed!",
    },
}


class SQL(CoreCall, input_model=SQLInput, output_model=SQLOutput):
    """SQL工具。用于调用外置的Chat2DB工具的API，获得SQL语句；再在PostgreSQL中执行SQL语句，获得数据。"""

    database_type: str = Field(description="数据库类型",default="postgres") # mysql mongodb opengauss postgres
    host: str = Field(description="数据库地址",default="localhost")
    port: int = Field(description="数据库端口",default=5432)
    username: str = Field(description="数据库用户名",default="root")
    password: str = Field(description="数据库密码",default="root")
    database: str = Field(description="数据库名称",default="postgres")
    table_name_list: list[str] = Field(description="表名列表",default=[])


    @classmethod
    def info(cls, language: LanguageType = LanguageType.CHINESE) -> CallInfo:
        """返回Call的名称和描述"""
        i18n_info = {
            LanguageType.CHINESE: CallInfo(
                name="SQL查询",
                description="使用大模型生成SQL语句，用于查询数据库中的结构化数据",
            ),
            LanguageType.ENGLISH: CallInfo(
                name="SQL Query",
                description="Use LLM to generate SQL statements, for querying structured data in the database",
            ),
        }
        return i18n_info[language]


    async def _init(self, call_vars: CallVars) -> SQLInput:
        """初始化SQL工具。"""
        return SQLInput(
            question=call_vars.question,
        )


    async def _exec(self, input_data: dict[str, Any]) -> AsyncGenerator[CallOutputChunk, None]:
        """运行SQL工具, 支持MySQL, MongoDB, PostgreSQL, OpenGauss"""
        data = SQLInput(**input_data)

        headers = {"Content-Type": "application/json"}
        post_data = {
            "type": self.database_type,
            "host": self.host,
            "port": self.port,
            "username": self.username,
            "password": self.password,
            "database": self.database,
            "goal": data.question,
            "table_list": self.table_name_list,
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    config.extra.sql_url + "/sql/handler",
                    headers=headers,
                    json=post_data,
                    timeout=60.0,
                )

                result = response.json()
                if response.status_code == status.HTTP_200_OK:
                    if result["code"] == status.HTTP_200_OK:
                        result_data = result["result"]
                        sql_exec_results = result_data.get("execute_result")
                        sql_exec = result_data.get("sql")
                        sql_exec_risk = result_data.get("risk")
                        logger.info(
                            "[SQL] 调用成功\n[SQL 语句]: %s\n[SQL 结果]: %s\n[SQL 风险]: %s",
                            sql_exec,
                            sql_exec_results,
                            sql_exec_risk,
                        )

                else:
                    logger.error("[SQL] 调用失败：%s", response.text)
                    logger.error("[SQL] 错误信息：%s", response.json()["result"])
        except Exception as e:
            logger.exception("[SQL] 调用失败")
            raise CallError(
                message=MESSAGE["fail"][self._sys_vars.language],
                data={},
            ) from e

        # 返回结果
        data = SQLOutput(
            result=sql_exec_results,
            sql=sql_exec,
        ).model_dump(exclude_none=True, by_alias=True)

        yield CallOutputChunk(
            content=data,
            type=CallOutputType.DATA,
        )
