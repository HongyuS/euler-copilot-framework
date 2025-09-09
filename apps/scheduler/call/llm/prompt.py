# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""大模型工具的提示词"""

from textwrap import dedent

from apps.schemas.enum_var import LanguageType

LLM_CONTEXT_PROMPT: dict[LanguageType, str] = {
    LanguageType.CHINESE: dedent(
        r"""
            以下是对用户和AI间对话的简短总结，在<summary>中给出：
            <summary>
                {{ summary }}
            </summary>

            你作为AI，在回答用户的问题前，需要获取必要的信息。为此，你调用了一些工具，并获得了它们的输出：
            工具的输出数据将在<tool_data>中给出， 其中<name>为工具的名称，<output>为工具的输出数据。
            <tool_data>
                {% for tool in history_data %}
                    <tool>
                        <name>{{ tool.step_name }}</name>
                        <description>{{ tool.step_description }}</description>
                        <output>{{ tool.output_data }}</output>
                    </tool>
                {% endfor %}
            </tool_data>
        """,
    ).strip("\n"),
    LanguageType.ENGLISH: dedent(
        r"""
            The following is a brief summary of the user and AI conversation, given in <summary>:
            <summary>
                {{ summary }}
            </summary>

            As an AI, before answering the user's question, you need to obtain necessary information. For this \
purpose, you have called some tools and obtained their outputs:
            The output data of the tools will be given in <tool_data>, where <name> is the name of the tool and \
<output> is the output data of the tool.
            <tool_data>
                {% for tool in history_data %}
                    <tool>
                        <name>{{ tool.step_name }}</name>
                        <description>{{ tool.step_description }}</description>
                        <output>{{ tool.output_data }}</output>
                    </tool>
                {% endfor %}
            </tool_data>
        """,
    ).strip("\n"),
}
LLM_DEFAULT_PROMPT: str = dedent(
    r"""
        <instructions>
            你是一个乐于助人的智能助手。请结合给出的背景信息, 回答用户的提问。
            当前时间：{{ time }}，可以作为时间参照。
            用户的问题将在<user_question>中给出，上下文背景信息将在<context>中给出。
            注意：输出不要包含任何XML标签，不要编造任何信息。若你认为用户提问与背景信息无关，请忽略背景信息直接作答。
        </instructions>

        <user_question>
            {{ question }}
        </user_question>

        <context>
            {{ context }}
        </context>

        现在，输出你的回答：
    """,
).strip("\n")
