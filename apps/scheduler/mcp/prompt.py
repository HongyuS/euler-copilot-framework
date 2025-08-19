# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP相关的大模型Prompt"""

from textwrap import dedent

from apps.schemas.enum_var import LanguageType

MCP_SELECT: dict[LanguageType, str] = {
    LanguageType.CHINESE: dedent(
        r"""
            你是一个计划生成器。
            请分析用户的目标，并生成一个计划。你后续将根据这个计划，一步一步地完成用户的目标。

            # 一个好的计划应该：

            1. 能够成功完成用户的目标
            2. 计划中的每一个步骤必须且只能使用一个工具。
            3. 计划中的步骤必须具有清晰和逻辑的步骤，没有冗余或不必要的步骤。
            4. 计划中的最后一步必须是Final工具，以确保计划执行结束。
            5.生成的计划必须要覆盖用户的目标，不能遗漏任何用户目标中的内容。

            # 生成计划时的注意事项：

            - 每一条计划包含3个部分：
                - 计划内容：描述单个计划步骤的大致内容
                - 工具ID：必须从下文的工具列表中选择
                - 工具指令：改写用户的目标，使其更符合工具的输入要求
            - 必须按照如下格式生成计划，不要输出任何额外数据：

            ```json
            {
                "plans": [
                    {
                        "content": "计划内容",
                        "tool": "工具ID",
                        "instruction": "工具指令"
                    }
                ]
            }
            ```

            - 在生成计划之前，请一步一步思考，解析用户的目标，并指导你接下来的生成。\
        思考过程应放置在<thinking></thinking> XML标签中。
            - 计划内容中，可以使用"Result[]"来引用之前计划步骤的结果。例如："Result[3]"表示引用第三条计划执行后的结果。
            - 计划不得多于{{ max_num }}条，且每条计划内容应少于150字。

            # 工具

            你可以访问并使用一些工具，这些工具将在<tools></tools> XML标签中给出。

            <tools>
                {% for tool in tools %}
                - <id>{{ tool.id }}</id><description>{{tool.name}}；{{ tool.description }}</description>
                {% endfor %}
                - <id>Final</id><description>结束步骤，当执行到这一步时，\
        表示计划执行结束，所得到的结果将作为最终结果。</description>
            </tools>

            # 样例

            ## 目标

            在后台运行一个新的alpine:latest容器，将主机/root文件夹挂载至/data，并执行top命令。

            ## 计划

            <thinking>
            1. 这个目标需要使用Docker来完成,首先需要选择合适的MCP Server
            2. 目标可以拆解为以下几个部分:
               - 运行alpine:latest容器
               - 挂载主机目录
               - 在后台运行
               - 执行top命令
            3. 需要先选择MCP Server,然后生成Docker命令,最后执行命令
            </thinking>

            ```json
            {
                "plans": [
                    {
                        "content": "选择一个支持Docker的MCP Server",
                        "tool": "mcp_selector",
                        "instruction": "需要一个支持Docker容器运行的MCP Server"
                    },
                    {
                        "content": "使用Result[0]中选择的MCP Server，生成Docker命令",
                        "tool": "command_generator",
                        "instruction": "生成Docker命令：在后台运行alpine:latest容器，挂载/root到/data，执行top命令"
                    },
                    {
                        "content": "在Result[0]的MCP Server上执行Result[1]生成的命令",
                        "tool": "command_executor",
                        "instruction": "执行Docker命令"
                    },
                    {
                        "content": "任务执行完成，容器已在后台运行，结果为Result[2]",
                        "tool": "Final",
                        "instruction": ""
                    }
                ]
            }
            ```

            # 现在开始生成计划：

            ## 目标

            {{goal}}

            # 计划
        """,
    ),
    LanguageType.ENGLISH: dedent(
        r"""
            You are a helpful intelligent assistant.
            Your task is to select the most appropriate MCP server based on your current goals.

            ## Things to note when selecting an MCP server:

            1. Ensure you fully understand your current goals and select the most appropriate MCP server.
            2. Please select from the provided list of MCP servers; do not generate your own.
            3. Please provide the rationale for your choice before making your selection.
            4. Your current goals will be listed below, along with the list of MCP servers.
               Please include your thought process in the "Thought Process" section and your selection in the \
"Selection Results" section.
            5. Your selection must be in JSON format, strictly following the template below. Do not output any \
additional content:

            ```json
            {
                "mcp": "The name of your selected MCP server"
            }
            ```

            6. The following example is for reference only. Do not use it as a basis for selecting an MCP server.

            ## Example

            ### Goal

            I need an MCP server to complete a task.

            ### MCP Server List

            - **mcp_1**: "MCP Server 1"; Description of MCP Server 1
            - **mcp_2**: "MCP Server 2"; Description of MCP Server 2

            ### Think step by step:

            Because the current goal requires an MCP server to complete a task, select mcp_1.

            ### Select Result

            ```json
            {
                "mcp": "mcp_1"
            }
            ```

            ## Let's get started!

            ### Goal

            {{goal}}

            ### MCP Server List

            {% for mcp in mcp_list %}
            - **{{mcp.id}}**: "{{mcp.name}}"; {{mcp.description}}
            {% endfor %}

            ### Think step by step:

        """,
    ),
}

EVALUATE_PLAN: dict[LanguageType, str] = {
    LanguageType.CHINESE: dedent(
        r"""
            你是一个计划评估器。
            请根据给定的计划，和当前计划执行的实际情况，分析当前计划是否合理和完整，并生成改进后的计划。

            # 一个好的计划应该：

            1. 能够成功完成用户的目标
            2. 计划中的每一个步骤必须且只能使用一个工具。
            3. 计划中的步骤必须具有清晰和逻辑的步骤，没有冗余或不必要的步骤。
            4. 计划中的最后一步必须是Final工具，以确保计划执行结束。

            # 你此前的计划是：

            {{ plan }}

            # 这个计划的执行情况是：

            计划的执行情况将放置在<status></status> XML标签中。

            <status>
            {{ memory }}
            </status>

            # 进行评估时的注意事项：

            - 请一步一步思考，解析用户的目标，并指导你接下来的生成。思考过程应放置在<thinking></thinking> XML标签中。
            - 评估结果分为两个部分：
                - 计划评估的结论
                - 改进后的计划
            - 请按照以下JSON格式输出评估结果：

            ```json
            {
                "evaluation": "评估结果",
                "plans": [
                    {
                        "content": "改进后的计划内容",
                        "tool": "工具ID",
                        "instruction": "工具指令"
                    }
                ]
            }
            ```

            # 现在开始评估计划：
        """,
    ),
    LanguageType.ENGLISH: dedent(
        r"""
            You are a plan evaluator.
            Based on the given plan and the actual execution of the current plan, analyze whether the current plan is \
reasonable and complete, and generate an improved plan.

            # A good plan should:

            1. Be able to successfully achieve the user's goal.
            2. Each step in the plan must use only one tool.
            3. The steps in the plan must have clear and logical steps, without redundant or unnecessary steps.
            4. The last step in the plan must be a Final tool to ensure the completion of the plan execution.

            # Your previous plan was:

            {{ plan }}

            # The execution status of this plan is:

            The execution status of the plan will be placed in the <status></status> XML tags.

            <status>
            {{ memory }}
            </status>

            # Notes when conducting the evaluation:

            - Please think step by step, analyze the user's goal, and guide your subsequent generation. The thinking \
process should be placed in the <thinking></thinking> XML tags.
            - The evaluation results are divided into two parts:
                - Conclusion of the plan evaluation
                - Improved plan
            - Please output the evaluation results in the following JSON format:

            ```json
            {
                "evaluation": "Evaluation results",
                "plans": [
                    {
                        "content": "Improved plan content",
                        "tool": "Tool ID",
                        "instruction": "Tool instructions"
                    }
                ]
            }
            ```

            # Start evaluating the plan now:

        """,
    ),
}
FINAL_ANSWER: dict[str, str] = {
    LanguageType.CHINESE: dedent(
        r"""
            综合理解计划执行结果和背景信息，向用户报告目标的完成情况。

            # 用户目标

            {{ goal }}

            # 计划执行情况

            为了完成上述目标，你实施了以下计划：

            {{ memory }}

            # 其他背景信息：

            {{ status }}

            # 现在，请根据以上信息，向用户报告目标的完成情况：

        """,
    ),
    LanguageType.ENGLISH: dedent(
        r"""
            Based on the understanding of the plan execution results and background information, report to the user \
the completion status of the goal.

            # User goal

            {{ goal }}

            # Plan execution status

            To achieve the above goal, you implemented the following plan:

            {{ memory }}

            # Other background information:

            {{ status }}

            # Now, based on the above information, please report to the user the completion status of the goal:

        """,
    ),
}
MEMORY_TEMPLATE: dict[str, str] = {
    LanguageType.CHINESE: dedent(
        r"""
            {% for ctx in context_list %}
            - 第{{ loop.index }}步：{{ ctx.step_description }}
              - 调用工具 `{{ ctx.step_name }}`，并提供参数 `{{ ctx.input_data | tojson }}`。
              - 执行状态：{{ ctx.step_status }}
              - 得到数据：`{{ ctx.output_data | tojson }}`
            {% endfor %}
        """,
    ),
    LanguageType.ENGLISH: dedent(
        r"""
            {% for ctx in context_list %}
            - Step {{ loop.index }}: {{ ctx.step_description }}
              - Called tool `{{ ctx.step_id }}` and provided parameters `{{ ctx.input_data }}`
              - Execution status: {{ ctx.status }}
              - Got data: `{{ ctx.output_data }}`
            {% endfor %}
        """,
    ),
}
