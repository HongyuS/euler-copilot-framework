# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""问题推荐工具的提示词"""

from textwrap import dedent

from apps.schemas.enum_var import LanguageType

SUGGEST_PROMPT: dict[LanguageType, str] = {
    LanguageType.CHINESE: dedent(
        r"""
            <instructions>
                <instruction>
                    根据先前的历史对话和提供的附加信息（用户倾向、问题列表、工具信息等）生成三个预测问题。
                    问题列表展示的是用户的过往问题，请避免重复生成这些问题。
                    用户倾向将在<domain>标签中给出，历史问题列表将在<history_questions>标签中给出，
                    工具信息将在<tool_info>标签中给出。

                    生成预测问题时的要求：
                        1. 以用户口吻生成预测问题，数量必须为3个，必须为疑问句或祈使句，必须少于30字。
                        2. 预测问题必须精简，不得发生重复，不得在问题中掺杂非必要信息，不得输出除问题以外的文字。
                        3. 输出必须按照如下格式：

                        ```json
                        {
                            "predicted_questions": [
                                "预测问题1",
                                "预测问题2",
                                "预测问题3"
                            ]
                        }
                        ```

                </instruction>
                <example>
                    <history_questions>
                        <question>简单介绍一下杭州</question>
                        <question>杭州有哪些著名景点？</question>
                    </history_questions>
                    <tool_info>
                        <name>景点查询</name>
                        <description>查询景点信息</description>
                    </tool_info>
                    <domain>["杭州", "旅游"]</domain>

                    现在，进行问题生成：

                    {
                        "predicted_questions": [
                            "杭州西湖景区的门票价格是多少？",
                            "杭州的天气怎么样？",
                            "杭州有什么特色美食？"
                        ]
                    }
                </example>
            </instructions>

            下面是实际的数据：

            请参考以下历史问题进行问题生成，避免重复已提出的问题：
            {% if history %}
                <history_questions>
                {% for question in history %}
                    <question>{{ question }}</question>
                {% endfor %}
                </history_questions>
            {% else %}
                (无历史问题)
            {% endif %}

            <tool_info>
                {% if tool %}
                    <name>{{ tool.name }}</name>
                    <description>{{ tool.description }}</description>
                {% else %}
                    (无工具信息)
                {% endif %}
            </tool_info>

            <domain>
                {% if preference %}
                    {{ preference }}
                {% else %}
                    (无用户倾向)
                {% endif %}
            </domain>

            现在，进行问题生成：
        """,
    ),
    LanguageType.ENGLISH: dedent(
        r"""
            <instructions>
                <instruction>
                    Generate three predicted questions based on the previous historical dialogue and provided \
additional information (user preferences, historical question list, tool information, etc.).
                    The question list displays the user's past questions, which should be avoided when generating \
predictions.
                    The user preferences will be given in the <domain> tag,
                    the historical question list will be given in the <history_questions> tag, and the tool \
information will be given in the <tool_info> tag.

                    Requirements for generating predicted questions:

                        1. Generate three predicted questions in the user's voice. They must be interrogative or \
imperative sentences and must be less than 30 words.

                        2. Predicted questions must be concise, without repetition, unnecessary information, or text \
other than the question.

                        3. Output must be in the following format:

                        ```json
                        {
                            "predicted_questions": [
                                "Predicted question 1",
                                "Predicted question 2",
                                "Predicted question 3"
                            ]
                        }
                        ```
                </instruction>
                <example>
                    <history_questions>
                        <question>Briefly introduce Hangzhou</question>
                        <question>What are the famous attractions in Hangzhou ? </question>
                    </history_questions>
                    <tool_info>
                        <name>Scenic Spot Search</name>
                        <description>Scenic Spot Information Search</description>
                    </tool_info>
                    <domain>["Hangzhou", "Tourism"]</domain>

                    Now, generate questions:

                    {
                        "predicted_questions": [
                            "What is the ticket price for the West Lake Scenic Area in Hangzhou?",
                            "What's the weather like in Hangzhou?",
                            "What are the local specialties in Hangzhou?"
                        ]
                    }
                </example>
            </instructions>

            Here's the actual data:

            Please refer to the following history questions for question generation, avoiding duplicate questions:
            {% if history %}
                <history_questions>
                {% for question in history %}
                    <question>{{ question }}</question>
                {% endfor %}
                </history_questions>
            {% else %}
                (No history question)
            {% endif %}

            <tool_info>
                {% if tool %}
                    <name>{{ tool.name }}</name>
                    <description>{{ tool.description }}</description>
                {% else %}
                    (No tool information)
                {% endif %}
            </tool_info>

            <domain>
                {% if preference %}
                    {{ preference }}
                {% else %}
                    (no user preference)
                {% endif %}
            </domain>

            Now, generate questions:
        """,
    ),
}
