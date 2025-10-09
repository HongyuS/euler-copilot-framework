# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Scheduler相关的大模型提示词"""

from apps.models import LanguageType

FLOW_SELECT: dict[LanguageType, str] = {
    LanguageType.CHINESE: r"""
        <instructions>
            <instruction>
                根据历史对话（包括工具调用结果）和用户问题，从给出的选项列表中，选出最符合要求的那一项。
                在输出之前，请先思考，并使用“<think>”标签给出思考过程。
                结果需要使用JSON格式输出，输出格式为：{{ "choice": "选项名称" }}
            </instruction>

            <example>
                <input>
                    <question>使用天气API，查询明天杭州的天气信息</question>

                    <options>
                        <item>
                            <name>API</name>
                            <description>HTTP请求，获得返回的JSON数据</description>
                        </item>
                        <item>
                            <name>SQL</name>
                            <description>查询数据库，获得数据库表中的数据</description>
                        </item>
                    </options>
                </input>

                <reasoning>
                    API 工具可以通过 API 来获取外部数据，而天气信息可能就存储在外部数据中，由于用户说明中明确 \
提到了天气 API 的使用，因此应该优先使用 API 工具。SQL 工具用于从数据库中获取信息，考虑到天气数据的可变性和动态性\
，不太可能存储在数据库中，因此 SQL 工具的优先级相对较低，最佳选择似乎是“API：请求特定 API，获取返回的 JSON 数据”。
                </reasoning>

                <output>
                    {{ "choice": "API" }}
                </output>
            </example>
        </instructions>

        <input>
            <question>
                {{question}}
            </question>

            <options>
                {{choice_list}}
            </options>
        </input>

        <reasoning>
          让我们一步一步思考。
    """,
    LanguageType.ENGLISH: r"""
        <instructions>
            <instruction>
                Based on the historical dialogue (including tool call results) and user question, select the \
most suitable option from the given option list.
                        Before outputting, please think carefully and use the "<think>" tag to give the thinking \
process.
                The output needs to be in JSON format, the output format is: {{ "choice": "option name" }}
            </instruction>

            <example>
                <input>
                    <question>Use the weather API to query the weather information of Hangzhou \
tomorrow</question>

                    <options>
                        <item>
                            <name>API</name>
                            <description>HTTP request, get the returned JSON data</description>
                        </item>
                        <item>
                            <name>SQL</name>
                            <description>Query the database, get the data in the database table</description>
                        </item>
                    </options>
                </input>

                <reasoning>
                    The API tool can get external data through API, and the weather information may be stored \
in external data. Since the user clearly mentioned the use of weather API, it should be given priority to the API \
tool. The SQL tool is used to get information from the database, considering the variability and dynamism of weather \
data, it is unlikely to be stored in the database, so the priority of the SQL tool is relatively low, \
The best choice seems to be "API: request a specific API, get the returned JSON data".
                </reasoning>

                <output>
                    {{ "choice": "API" }}
                </output>
            </example>
        </instructions>
        <input>
                <question>
                    {{question}}
                </question>

                <options>
                    {{choice_list}}
                </options>
            </input>

            <reasoning>
                Let's think step by step.
            </reasoning>
        </input>
    """,
}
