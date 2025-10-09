# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""用于FunctionCall的大模型"""

import json
import logging
import re
from textwrap import dedent
from typing import Any

from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment
from jsonschema import Draft7Validator

from apps.constants import JSON_GEN_MAX_TRIAL
from apps.models import LLMData, LLMProvider

from .prompt import JSON_GEN_BASIC
from .providers import (
    BaseProvider,
    OllamaProvider,
    OpenAIProvider,
)

_logger = logging.getLogger(__name__)
_CLASS_DICT: dict[LLMProvider, type[BaseProvider]] = {
    LLMProvider.OLLAMA: OllamaProvider,
    LLMProvider.OPENAI: OpenAIProvider,
}


class FunctionLLM:
    """用于FunctionCall的模型"""

    def __init__(self, llm_config: LLMData | None = None) -> None:
        """初始化大模型客户端"""
        if not llm_config:
            err = "[FunctionLLM] 未设置LLM配置"
            _logger.error(err)
            raise RuntimeError(err)

        if llm_config.provider not in _CLASS_DICT:
            err = "[FunctionLLM] 未支持的LLM类型: %s", llm_config.provider
            _logger.error(err)
            raise RuntimeError(err)

        self._provider = _CLASS_DICT[llm_config.provider](llm_config)

    @staticmethod
    async def process_response(response: str) -> str:
        """处理大模型的输出"""
        # 尝试解析JSON
        response = dedent(response).strip()
        error_flag = False
        try:
            json.loads(response)
        except Exception:  # noqa: BLE001
            error_flag = True

        if not error_flag:
            return response

        # 尝试提取```json中的JSON
        _logger.warning("[FunctionCall] 直接解析失败！尝试提取```json中的JSON")
        try:
            json_str = re.findall(r"```json(.*)```", response, re.DOTALL)[-1]
            json_str = dedent(json_str).strip()
            json.loads(json_str)
        except Exception:  # noqa: BLE001
            # 尝试直接通过括号匹配JSON
            _logger.warning("[FunctionCall] 提取失败！尝试正则提取JSON")
            try:
                json_str = re.findall(r"\{.*\}", response, re.DOTALL)[-1]
                json_str = dedent(json_str).strip()
                json.loads(json_str)
            except Exception:  # noqa: BLE001
                json_str = "{}"

        return json_str


    async def call(
        self,
        messages: list[dict[str, Any]],
        schema: dict[str, Any],
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        """
        调用FunctionCall小模型

        不开放流式输出
        """
        try:
            return json.loads(json_str)
        except Exception:  # noqa: BLE001
            _logger.error("[FunctionCall] 大模型JSON解析失败：%s", json_str)  # noqa: TRY400
            return {}


class JsonGenerator:
    """JSON生成器"""

    def xml_parser(self, xml: str) -> dict[str, Any]:
        """XML解析器"""
        return {}

    def __init__(
        self, llm: FunctionLLM, query: str, conversation: list[dict[str, str]], schema: dict[str, Any],
    ) -> None:
        """初始化JSON生成器"""
        self._query = query
        self._conversation = conversation
        self._schema = schema
        self._llm = llm

        self._trial = {}
        self._count = 0
        self._env = SandboxedEnvironment(
            loader=BaseLoader(),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
            extensions=["jinja2.ext.loopcontrols"],
        )
        self._err_info = ""

    async def _single_trial(self, max_tokens: int | None = None, temperature: float | None = None) -> dict[str, Any]:
        """单次尝试"""
        # 检查类型

        # 渲染模板
        template = self._env.from_string(JSON_GEN_BASIC)
        return template.render(
            query=self._query,
            conversation=self._conversation,
            previous_trial=self._trial,
            schema=self._schema,
            function_call=function_call,
            err_info=self._err_info,
        )

        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ]
        return await self._llm.call(messages, self._schema, max_tokens, temperature)


    async def generate(self) -> dict[str, Any]:
        """生成JSON"""
        Draft7Validator.check_schema(self._schema)
        validator = Draft7Validator(self._schema)

        while self._count < JSON_GEN_MAX_TRIAL:
            self._count += 1
            result = await self._single_trial()
            try:
                validator.validate(result)
            except Exception as err:  # noqa: BLE001
                err_info = str(err)
                err_info = err_info.split("\n\n")[0]
                self._err_info = err_info
                _logger.info("[JSONGenerator] 验证失败：%s", self._err_info)
                continue
            return result

        return {}
