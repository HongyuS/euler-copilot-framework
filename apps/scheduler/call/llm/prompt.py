# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""大模型工具的提示词"""

from textwrap import dedent

from apps.schemas.enum_var import LanguageType

LLM_CONTEXT_PROMPT: dict[LanguageType, str] = {
    LanguageType.CHINESE: dedent(
        r"""
            以下是AI处理用户指令时所做的思考，在<reasoning>中给出：
            <reasoning>
                {{ reasoning }}
            </reasoning>

            你作为AI，在完成用户指令前，需要获取必要的信息。为此，你调用了一些工具，并获得了它们的输出：
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
            The following is the thinking of the AI when processing the user's instruction, given in <reasoning>:
            <reasoning>
                {{ reasoning }}
            </reasoning>

            As an AI, before completing the user's instruction, you need to obtain necessary information. For this \
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
