# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""选择图表样式"""

import logging
from typing import Any, Literal

from pydantic import BaseModel, Field

from apps.llm.function import JsonGenerator
from apps.llm.patterns.core import CorePattern
from apps.llm.reasoning import ReasoningLLM

logger = logging.getLogger(__name__)


class RenderStyleResult(BaseModel):
    """选择图表样式结果"""

    chart_type: Literal["bar", "pie", "line", "scatter"] = Field(description="图表类型")
    additional_style: Literal["normal", "stacked", "ring"] | None = Field(description="图表样式")
    scale_type: Literal["linear", "log"] = Field(description="图表比例")


class RenderStyle(CorePattern):
    """选择图表样式"""

    system_prompt = r"""
        You are a helpful assistant. Help the user make style choices when drawing a chart.
        Chart title should be short and less than 3 words.

        Available types:
        - `bar`: Bar graph
        - `pie`: Pie graph
        - `line`: Line graph
        - `scatter`: Scatter graph

        Available bar additional styles:
        - `normal`: Normal bar graph
        - `stacked`: Stacked bar graph

        Available pie additional styles:
        - `normal`: Normal pie graph
        - `ring`: Ring pie graph

        Available scales:
        - `linear`: Linear scale
        - `log`: Logarithmic scale

        EXAMPLE
        ## Question
        查询数据库中的数据，并绘制堆叠柱状图。

        ## Thought
        Let's think step by step. The user requires drawing a stacked bar chart, so the chart type should be `bar`, \
        i.e. a bar chart; the chart style should be `stacked`, i.e. a stacked form.

        ## Answer
        The chart type should be: bar
        The chart style should be: stacked
        The scale should be: linear

        END OF EXAMPLE

        Let's begin.
    """

    user_prompt = r"""
        ## Question
        {question}

        ## Thought
        Let's think step by step.
    """

    def __init__(self, system_prompt: str | None = None, user_prompt: str | None = None) -> None:
        """初始化RenderStyle Prompt"""
        super().__init__(system_prompt, user_prompt)

    async def generate(self, **kwargs) -> dict[str, Any]:  # noqa: ANN003
        """使用LLM选择图表样式"""
        question = kwargs["question"]

        # 使用Reasoning模型进行推理
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.user_prompt.format(question=question)},
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

        # 使用FunctionLLM模型进行提取参数
        json_gen = JsonGenerator(
            query="根据给定的背景信息，生成预测问题",
            conversation=messages,
            schema=RenderStyleResult.model_json_schema(),
        )
        try:
            result_dict = await json_gen.generate()
            RenderStyleResult.model_validate(result_dict)
        except Exception:
            logger.exception("[RenderStyle] 选择图表样式失败")
            return {}

        return result_dict
