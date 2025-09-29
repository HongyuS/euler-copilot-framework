# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""问题推荐工具的提示词"""

from textwrap import dedent

from apps.models import LanguageType

SUGGEST_PROMPT: dict[LanguageType, str] = {
    LanguageType.CHINESE: dedent(
        r"""
            <instructions>
                <instruction>
                    根据先前的历史对话和提供的附加信息（用户倾向、问题列表、工具信息等）生成指定数量的预测问题。
                    <question_list>中包含了用户已提出过的所有问题，请避免重复生成这些问题。
                    用户倾向将在<domain>标签中给出，工具信息将在<tool_info>标签中给出。

                    生成预测问题时的要求：
                        1. 以用户口吻生成预测问题，数量必须为指定的数量，必须为疑问句或祈使句，必须少于30字。
                        2. 预测问题必须精简，不得发生重复，不得在问题中掺杂非必要信息，不得输出除问题以外的文字。
                        3. 输出必须按照如下格式：

                        ```json
                        {
                            "predicted_questions": [
                                "预测问题1",
                                "预测问题2",
                                ...
                            ]
                        }
                        ```
                </instruction>

                <example>
                    <question_list>
                        <question>简单介绍一下杭州</question>
                        <question>杭州有哪些著名景点？</question>
                        <question>杭州西湖景区的门票价格是多少？</question>
                    </question_list>
                    <target_num>3</target_num>
                    <tool_info>
                        <name>景点查询</name>
                        <description>查询景点信息</description>
                    </tool_info>
                    <domain>["杭州", "旅游"]</domain>

                    现在，进行问题生成：

                    {
                        "predicted_questions": [
                            "杭州的天气怎么样？",
                            "杭州有什么特色美食？"
                        ]
                    }
                </example>
            </instructions>

            下面是实际的数据：

            以下是问题列表，请参考其内容并避免重复生成：
            {% if history or generated %}
                <question_list>
                {% for question in history %}
                    <question>{{ question }}</question>
                {% endfor %}
                {% for question in generated %}
                    <question>{{ question }}</question>
                {% endfor %}
                </question_list>
            {% else %}
                (无已知问题)
            {% endif %}

            {% if target_num %}
            请生成{{ target_num }}个问题。
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
                    Generate the specified number of predicted questions based on the previous historical
                    dialogue and provided additional information (user preferences, question list,
                    tool information, etc.).
                    The <question_list> contains all the questions that the user has asked before,
                    please avoid duplicating these questions when generating predictions.
                    User preferences will be given in the <domain> tag, and tool information will be
                    given in the <tool_info> tag.

                    Requirements for generating predicted questions:
                        1. Generate predicted questions in the user's voice, the quantity must be the specified
                           number, must be interrogative or imperative sentences, and must be less than 30 words.
                        2. Predicted questions must be concise, without duplication, without unnecessary
                           information, and without text other than the questions.
                        3. The output must be in the following format:

                        ```json
                        {
                            "predicted_questions": [
                                "Predicted question 1",
                                "Predicted question 2",
                                ...
                            ]
                        }
                        ```
                </instruction>

                <example>
                    <question_list>
                        <question>Briefly introduce Hangzhou</question>
                        <question>What are the famous attractions in Hangzhou?</question>
                        <question>What is the ticket price for the West Lake Scenic Area in Hangzhou?</question>
                    </question_list>
                    <target_num>3</target_num>
                    <tool_info>
                        <name>Scenic Spot Search</name>
                        <description>Search for scenic spot information</description>
                    </tool_info>
                    <domain>["Hangzhou", "Tourism"]</domain>

                    Now, generate questions:

                    {
                        "predicted_questions": [
                            "What's the weather like in Hangzhou?",
                            "What are the local specialties in Hangzhou?"
                        ]
                    }
                </example>
            </instructions>

            Here is the actual data:

            The following is a list of questions, please refer to its content and avoid duplicate generation:
            {% if history or generated %}
                <question_list>
                {% for question in history %}
                    <question>{{ question }}</question>
                {% endfor %}
                {% for question in generated %}
                    <question>{{ question }}</question>
                {% endfor %}
                </question_list>
            {% else %}
                (No known questions)
            {% endif %}

            {% if target_num %}
            Please generate {{ target_num }} questions.
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
                    (No user preference)
                {% endif %}
            </domain>

            Now, generate questions:
        """,
    ),
}
