# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""图表相关提示词"""

from apps.models import LanguageType

GENERATE_STYLE_PROMPT: dict[LanguageType, str] = {
    LanguageType.CHINESE: r"""
        <instructions>
            <instruction>
                你的目标是：帮助用户在绘制图表时做出样式选择。
                请以JSON格式输出你的选择。

                图表类型：
                    - `bar`: 柱状图
                    - `pie`: 饼图
                    - `line`: 折线图
                    - `scatter`: 散点图
                柱状图的附加样式：
                    - `normal`: 普通柱状图
                    - `stacked`: 堆叠柱状图
                饼图的附加样式：
                    - `normal`: 普通饼图
                    - `ring`: 环形饼图
                可用坐标比例：
                    - `linear`: 线性比例
                    - `log`: 对数比例
            </instruction>

            <example>
                ## 问题
                查询数据库中的数据，并绘制堆叠柱状图。

                ## 思考
                让我们一步步思考。用户要求绘制堆叠柱状图，因此图表类型应为 `bar`，即柱状图；图表样式\
应为 `stacked`，即堆叠形式。

                ## 答案
                {
                    "chart_type": "bar",
                    "additional_style": "stacked",
                    "scale_type": "linear"
                }
            </example>
        </instructions>

        ## 问题
        {{question}}

        ## 思考
        让我们一步步思考。
    """,
    LanguageType.ENGLISH: r"""
        <instructions>
            <instruction>
                Your mission is: help the user make style choices when drawing a chart.
                Please output your choices in JSON format.

                Chart types:
                    - `bar`: Bar chart
                    - `pie`: Pie chart
                    - `line`: Line chart
                    - `scatter`: Scatter chart

                Bar chart additional styles:
                    - `normal`: Normal bar chart
                    - `stacked`: Stacked bar chart

                Pie chart additional styles:
                    - `normal`: Normal pie chart
                    - `ring`: Ring pie chart

                Axis scaling:
                - `linear`: Linear scaling
                - `log`: Logarithmic scaling
            </instruction>

            <example>
                ## Question
                Query the data from the database and draw a stacked bar chart.

                ## Thought
                Let's think step by step. The user requires drawing a stacked bar chart, so the chart type \
should be `bar`, i.e. a bar chart; the chart style should be `stacked`, i.e. a stacked form.

                ## Answer
                {
                    "chart_type": "bar",
                    "additional_style": "stacked",
                    "scale_type": "linear"
                }
            </example>
        </instructions>

        ## Question

        {{question}}

        ## Thought

        Let's think step by step.
    """,
}
