# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""使用大模型生成Executor的思考内容"""

from typing import TYPE_CHECKING

from apps.llm.reasoning import ReasoningLLM
from apps.llm.snippet import convert_context_to_prompt, facts_to_prompt
from apps.schemas.enum_var import LanguageType

from .core import CorePattern

if TYPE_CHECKING:
    from apps.schemas.scheduler import ExecutorBackground


class ExecutorSummary(CorePattern):
    """使用大模型进行生成Executor初始背景"""

    @staticmethod
    def _default() -> tuple[dict[LanguageType, str], dict[LanguageType, str]]:
        """默认的Prompt内容"""
        return {
            LanguageType.CHINESE: r"You are a helpful assistant.",
            LanguageType.ENGLISH: r"You are a helpful assistant.",
        }, {
            LanguageType.CHINESE: r"""
                <instructions>
                    根据给定的对话记录和关键事实，生成一个三句话背景总结。这个总结将用于后续对话的上下文理解。

                    生成总结的要求如下：
                    1. 突出重要信息点，例如时间、地点、人物、事件等。
                    2. “关键事实”中的内容可在生成总结时作为已知信息。
                    3. 输出时请不要包含XML标签，确保信息准确性，不得编造信息。
                    4. 总结应少于3句话，应少于300个字。

                    对话记录将在<conversation>标签中给出，关键事实将在<facts>标签中给出。
                </instructions>

                {conversation}

                <facts>
                    {facts}
                </facts>

                现在，请开始生成背景总结：
            """,
            LanguageType.ENGLISH: r"""
                <instructions>
                    Based on the given conversation records and key facts, generate a three-sentence background \
summary.This summary will be used for context understanding in subsequent conversations.

                    The requirements for generating the summary are as follows:
                    1. Highlight important information points, such as time, location, people, events, etc.
                    2. The content in the "key facts" can be used as known information when generating the summary.
                    3. Do not include XML tags in the output, ensure the accuracy of the information, and do not \
make up information.
                    4. The summary should be less than 3 sentences and less than 300 words.

                    The conversation records will be given in the <conversation> tag, and the key facts will be given \
in the <facts> tag.
                </instructions>

                {conversation}

                <facts>
                    {facts}
                </facts>

                Now, please start generating the background summary:
            """,
        }

    async def generate(self, **kwargs) -> str:  # noqa: ANN003
        """进行初始背景生成"""
        background: ExecutorBackground = kwargs["background"]
        conversation_str = convert_context_to_prompt(background.conversation)
        facts_str = facts_to_prompt(background.facts)
        language = kwargs.get("language", LanguageType.CHINESE)

        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {
                "role": "user",
                "content": self.user_prompt[language].format(
                    facts=facts_str,
                    conversation=conversation_str,
                ),
            },
        ]

        result = ""
        llm = ReasoningLLM()
        async for chunk in llm.call(messages, streaming=False, temperature=0.7):
            result += chunk
        self.input_tokens = llm.input_tokens
        self.output_tokens = llm.output_tokens

        return result.strip().strip("\n")
