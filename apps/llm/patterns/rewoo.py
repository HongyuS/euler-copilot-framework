# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""规划生成命令行"""

from apps.llm.patterns.core import CorePattern
from apps.llm.reasoning import ReasoningLLM


class InitPlan(CorePattern):
    """规划生成命令行"""

    system_prompt: str = r"""
        你是一个计划生成器。对于给定的目标，**制定一个简单的计划**，该计划可以逐步生成合适的命令行参数和标志。

        你会收到一个"命令前缀"，这是已经确定和生成的命令部分。你需要基于这个前缀使用标志和参数来完成命令。

        在每一步中，指明使用哪个外部工具以及工具输入来获取证据。

        工具可以是以下之一：
        (1) Option["指令"]：查询最相似的命令行标志。只接受一个输入参数，"指令"必须是搜索字符串。搜索字符串应该详细且包含必要的数据。
        (2) Argument[名称]<值>：将任务中的数据放置到命令行的特定位置。接受两个输入参数。

        所有步骤必须以"Plan: "开头，且少于150个单词。
        不要添加任何多余的步骤。
        确保每个步骤都包含所需的所有信息 - 不要跳过步骤。
        不要在证据后面添加任何额外数据。

        开始示例

        任务：在后台运行一个新的alpine:latest容器，将主机/root文件夹挂载至/data，并执行top命令。
        前缀：`docker run`
        用法：`docker run ${OPTS} ${image} ${command}`。这是一个Python模板字符串。OPTS是所有标志的占位符。参数必须是 \
        ["image", "command"] 其中之一。
        前缀描述：二进制程序`docker`的描述为"Docker容器平台"，`run`子命令的描述为"从镜像创建并运行一个新的容器"。

        Plan: 我需要一个标志使容器在后台运行。 #E1 = Option[在后台运行单个容器]
        Plan: 我需要一个标志，将主机/root目录挂载至容器内/data目录。 #E2 = Option[挂载主机/root目录至/data目录]
        Plan: 我需要从任务中解析出镜像名称。 #E3 = Argument[image]<alpine:latest>
        Plan: 我需要指定容器中运行的命令。 #E4 = Argument[command]<top>
        Final: 组装上述线索，生成最终命令。 #F

        示例结束

        让我们开始！
    """
    """系统提示词"""

    user_prompt: str = r"""
        任务：{instruction}
        前缀：`{binary_name} {subcmd_name}`
        用法：`{subcmd_usage}`。这是一个Python模板字符串。OPTS是所有标志的占位符。参数必须是 {argument_list} 其中之一。
        前缀描述：二进制程序`{binary_name}`的描述为"{binary_description}"，`{subcmd_name}`子命令的描述为\
        "{subcmd_description}"。

        请生成相应的计划。
    """
    """用户提示词"""

    def __init__(self, system_prompt: str | None = None, user_prompt: str | None = None) -> None:
        """处理Prompt"""
        super().__init__(system_prompt, user_prompt)

    async def generate(self, **kwargs) -> str:  # noqa: ANN003
        """生成命令行evidence"""
        spec = kwargs["spec"]
        binary_name = kwargs["binary_name"]
        subcmd_name = kwargs["subcmd_name"]
        binary_description = spec[binary_name][0]
        subcmd_usage = spec[binary_name][2][subcmd_name][1]
        subcmd_description = spec[binary_name][2][subcmd_name][0]

        argument_list = []
        for key in spec[binary_name][2][subcmd_name][3]:
            argument_list += [key]

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.user_prompt.format(
                instruction=kwargs["instruction"],
                binary_name=binary_name,
                subcmd_name=subcmd_name,
                binary_description=binary_description,
                subcmd_description=subcmd_description,
                subcmd_usage=subcmd_usage,
                argument_list=argument_list,
            )},
        ]

        result = ""
        llm = ReasoningLLM()
        async for chunk in llm.call(messages, streaming=False):
            result += chunk
        self.input_tokens = llm.input_tokens
        self.output_tokens = llm.output_tokens

        return result


class PlanEvaluator(CorePattern):
    """计划评估器"""

    system_prompt: str = r"""
        你是一个计划评估器。你的任务是评估给定的计划是否合理和完整。

        一个好的计划应该：
        1. 涵盖原始任务的所有要求
        2. 使用适当的工具收集必要的信息
        3. 具有清晰和逻辑的步骤
        4. 没有冗余或不必要的步骤

        对于计划中的每个步骤，评估：
        1. 工具选择是否适当
        2. 输入参数是否清晰和充分
        3. 该步骤是否有助于实现最终目标

        请回复：
        "VALID" - 如果计划良好且完整
        "INVALID: <原因>" - 如果计划有问题，请解释原因
    """
    """系统提示词"""

    user_prompt: str = r"""
        任务：{instruction}
        计划：{plan}

        评估计划并回复"VALID"或"INVALID: <原因>"。
    """
    """用户提示词"""

    def __init__(self, system_prompt: str | None = None, user_prompt: str | None = None) -> None:
        """初始化Prompt"""
        super().__init__(system_prompt, user_prompt)

    async def generate(self, **kwargs) -> str:
        """生成计划评估结果"""
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.user_prompt.format(
                instruction=kwargs["instruction"],
                plan=kwargs["plan"],
            )},
        ]

        result = ""
        llm = ReasoningLLM()
        async for chunk in llm.call(messages, streaming=False):
            result += chunk
        self.input_tokens = llm.input_tokens
        self.output_tokens = llm.output_tokens

        return result


class RePlanner(CorePattern):
    """重新规划器"""

    system_prompt: str = r"""
        你是一个计划重新规划器。当计划被评估为无效时，你需要生成一个新的、改进的计划。

        新计划应该：
        1. 解决评估中提到的所有问题
        2. 保持与原始计划相同的格式
        3. 更加精确和完整
        4. 为每个步骤使用适当的工具

        遵循与原始计划相同的格式：
        - 每个步骤应以"Plan: "开头
        - 包含带有适当参数的工具使用
        - 保持步骤简洁和重点突出
        - 以"Final"步骤结束
    """
    """系统提示词"""

    user_prompt: str = r"""
        任务：{instruction}
        原始计划：{plan}
        评估：{evaluation}

        生成一个新的、改进的计划，解决评估中提到的所有问题。
    """
    """用户提示词"""

    def __init__(self, system_prompt: str | None = None, user_prompt: str | None = None) -> None:
        """初始化Prompt"""
        super().__init__(system_prompt, user_prompt)

    async def generate(self, **kwargs) -> str:
        """生成重新规划结果"""
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.user_prompt.format(
                instruction=kwargs["instruction"],
                plan=kwargs["plan"],
                evaluation=kwargs["evaluation"],
            )},
        ]

        result = ""
        llm = ReasoningLLM()
        async for chunk in llm.call(messages, streaming=False):
            result += chunk
        self.input_tokens = llm.input_tokens
        self.output_tokens = llm.output_tokens

        return result
