"""
LLM Pattern: 从问答中提取领域信息

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

from typing import Any, ClassVar

from apps.llm.patterns.core import CorePattern
from apps.llm.patterns.json_gen import Json
from apps.llm.reasoning import ReasoningLLM
from apps.llm.snippet import convert_context_to_prompt


class Domain(CorePattern):
    """从问答中提取领域信息"""

    user_prompt: str = r"""
        <instructions>
          <instruction>
            根据对话上文，提取推荐系统所需的关键词标签，要求：
            1. 实体名词、技术术语、时间范围、地点、产品等关键信息均可作为关键词标签
            2. 至少一个关键词与对话的话题有关
            3. 标签需精简，不得重复，不得超过10个字
            4. 使用JSON格式输出，不要包含XML标签，不要包含任何解释说明
          </instruction>

          <example>
            <conversation>
              <user>北京天气如何？</user>
              <assistant>北京今天晴。</assistant>
            </conversation>

            <output>
              {{
                "keywords": ["北京", "天气"]
              }}
            </output>
          </example>
        </instructions>

        {conversation}
        <output>
    """
    """用户提示词"""

    slot_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "keywords": {
                "type": "array",
                "description": "feature tags and categories, can be empty",
            },
        },
        "required": ["keywords"],
    }
    """最终输出的JSON Schema"""

    def __init__(self, system_prompt: str | None = None, user_prompt: str | None = None) -> None:
        """初始化Reflect模式"""
        super().__init__(system_prompt, user_prompt)


    async def generate(self, **kwargs) -> list[str]:  # noqa: ANN003
        """从问答中提取领域信息"""
        conversation = convert_context_to_prompt(kwargs["conversation"])
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.user_prompt.format(conversation=conversation)},
        ]

        result = ""
        llm = ReasoningLLM()
        async for chunk in llm.call(messages, streaming=False):
            result += chunk
        self.input_tokens = llm.input_tokens
        self.output_tokens = llm.output_tokens

        messages += [
            {"role": "assistant", "content": result},
        ]

        output = await Json().generate(conversation=messages, spec=self.slot_schema)
        return output.get("keywords", [])
