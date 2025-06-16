# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""图表工具的输入输出"""

from typing import Any

from pydantic import BaseModel, Field

from apps.scheduler.call.core import DataBase


class RenderAxis(BaseModel):
    """ECharts图表的轴配置"""

    type: str = Field(description="轴的类型")
    axisTick: dict = Field(description="轴刻度配置")  # noqa: N815


class RenderFormat(BaseModel):
    """ECharts图表配置"""

    tooltip: dict[str, Any] = Field(description="ECharts图表的提示框配置")
    legend: dict[str, Any] = Field(description="ECharts图表的图例配置")
    dataset: dict[str, Any] = Field(description="ECharts图表的数据集配置")
    xAxis: RenderAxis = Field(description="ECharts图表的X轴配置")  # noqa: N815
    yAxis: RenderAxis = Field(description="ECharts图表的Y轴配置")  # noqa: N815
    series: list[dict[str, Any]] = Field(description="ECharts图表的数据列配置")


class RenderInput(DataBase):
    """图表工具的输入"""

    question: str = Field(description="用户输入")
    data: list[dict[str, Any]] = Field(description="图表数据")


class RenderOutput(DataBase):
    """Render工具的输出"""

    output: RenderFormat = Field(description="ECharts图表配置")
