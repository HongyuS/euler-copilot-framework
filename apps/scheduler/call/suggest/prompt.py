# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""问题推荐工具的提示词"""

from textwrap import dedent

SUGGEST_PROMPT = dedent(r"""
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
            <conversation>
                <user>杭州有哪些著名景点？</user>
                <assistant>杭州西湖是中国浙江省杭州市的一个著名景点，以其美丽的自然风光和丰富的文化遗产而闻名。西湖周围有许多著名的景点，包括著名的苏堤、白堤、断桥、三潭印月等。西湖以其清澈的湖水和周围的山脉而著名，是中国最著名的湖泊之一。</assistant>
            </conversation>
            <history_list>
                <question>简单介绍一下杭州</question>
                <question>杭州有哪些著名景点？</question>
            </history_list>
            <tool_info>
                <name>景点查询</name>
                <description>查询景点信息</description>
            </tool_info>
            <domain>["杭州", "旅游"]</domain>

            现在，进行问题生成：

            {
                "predicted_questions": [
                    "杭州西湖景区的门票价格是多少？",
                    "杭州有哪些著名景点？",
                    "杭州的天气怎么样？"
                ]
            }
        </example>
    </instructions>

    下面是实际的数据：

    <conversation>
        {% for message in conversation %}
            <{{ message.role }}>{{ message.content }}</{{ message.role }}>
        {% endfor %}
    </conversation>

    <history_list>
        {% if history %}
            {% for question in history %}
                <question>{{ question }}</question>
            {% endfor %}
        {% else %}
            (无历史问题)
        {% endif %}
    </history_list>

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
""")
