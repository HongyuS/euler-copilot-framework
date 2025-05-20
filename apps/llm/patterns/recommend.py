# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""使用大模型进行推荐问题生成"""

import logging

from pydantic import BaseModel, Field

from apps.llm.function import JsonGenerator
from apps.llm.patterns.core import CorePattern
from apps.llm.reasoning import ReasoningLLM
from apps.llm.snippet import convert_context_to_prompt, history_questions_to_prompt

logger = logging.getLogger(__name__)


class RecommendResult(BaseModel):
    """推荐问题生成结果"""

    predicted_questions: list[str] = Field(description="预测的问题列表")


class Recommend(CorePattern):
    """使用大模型进行推荐问题生成"""

    system_prompt: str = "You are a helpful assistant."
    """系统提示词"""

    user_prompt: str = r"""
        <instructions>
            <instruction>
                根据提供的对话和附加信息（用户倾向、历史问题列表、工具信息等），生成三个预测问题。
                历史提问列表展示的是用户发生在历史对话之前的提问，仅为背景参考作用。
                对话将在<conversation>标签中给出，用户倾向将在<domain>标签中给出，\
                历史问题列表将在<history_list>标签中给出，工具信息将在<tool_info>标签中给出。

                生成预测问题时的要求：
                    1. 以用户口吻生成预测问题，数量必须为3个，必须为疑问句或祈使句，必须少于30字。
                    2. 预测问题必须精简，不得发生重复，不得在问题中掺杂非必要信息，不得输出除问题以外的文字。
                    3. 输出必须按照如下格式：

                    ```json
                    {{
                        "predicted_questions": [
                            "预测问题1",
                            "预测问题2",
                            "预测问题3"
                        ]
                    }}
                    ```
            </instruction>

            <example>
                <conversation>
                    <user>杭州有哪些著名景点？</user>
                    <assistant>杭州西湖是中国浙江省杭州市的一个著名景点，以其美丽的自然风光和丰富的文化遗产而闻名。西湖周围有许多著名的景点，包括著名的苏堤、白堤、断桥、三潭印月等。西湖以其清澈的湖水和周围的山脉而著名，是中国最著名的湖泊之一。</assistant>
                </conversation>
                <history_list>
                    <question>简单介绍一下杭州</question>
                    <question>杭州有哪些著名景点？</question>
                </history_list>
                <tool_info>
                    <tool>
                        <name>景点查询</name>
                        <description>查询景点信息</description>
                    </tool>
                </tool_info>
                <domain>["杭州", "旅游"]</domain>

                现在，进行问题生成：

                {{
                    "predicted_questions": [
                        "杭州西湖景区的门票价格是多少？",
                        "杭州有哪些著名景点？",
                        "杭州的天气怎么样？"
                    ]
                }}
            </example>
        </instructions>


        <conversation>
            {conversation}
        </conversation>

        <history_list>
            {history_questions}
        </history_list>

        <tool_info>
            <name>{tool_name}</name>
            <description>{tool_description}</description>
        </tool_info>

        <domain>{user_preference}</domain>

        现在，进行问题生成：
    """
    """用户提示词"""


    def __init__(self, system_prompt: str | None = None, user_prompt: str | None = None) -> None:
        """初始化推荐问题生成Prompt"""
        super().__init__(system_prompt, user_prompt)


    async def generate(self, **kwargs) -> list[str]:  # noqa: ANN003
        """生成推荐问题"""
        if "user_preference" not in kwargs or not kwargs["user_preference"]:
            user_preference = "[Empty]"
        else:
            user_preference = kwargs["user_preference"]

        if "history_questions" not in kwargs or not kwargs["history_questions"]:
            history_questions = "[Empty]"
        else:
            history_questions = history_questions_to_prompt(kwargs["history_questions"])

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.user_prompt.format(
                conversation=convert_context_to_prompt(kwargs["conversation"]),
                history_questions=history_questions,
                user_preference=user_preference,
                tool_name=kwargs["tool_name"],
                tool_description=kwargs["tool_description"],
            )},
        ]

        result = ""
        llm = ReasoningLLM()
        async for chunk in llm.call(messages, streaming=False, temperature=0.7):
            result += chunk
        self.input_tokens = llm.input_tokens
        self.output_tokens = llm.output_tokens

        messages += [{"role": "assistant", "content": result}]

        json_gen = JsonGenerator(
            query="根据给定的背景信息，生成预测问题", conversation=messages, schema=RecommendResult.model_json_schema(),
        )
        try:
            question_dict = RecommendResult.model_validate(await json_gen.generate())
        except Exception:
            logger.exception("[Recommend] 推荐问题生成失败")
            return []

        return question_dict.predicted_questions
