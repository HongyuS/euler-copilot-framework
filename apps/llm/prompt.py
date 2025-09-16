# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""系统提示词模板"""

from textwrap import dedent

JSON_GEN_BASIC = dedent(r"""
    Respond to the query according to the background information provided.

    # User query

    User query is given in <query></query> XML tags.

    <query>
    {{ query }}
    </query>

    {% if previous_trial %}
    # Previous Trial
    You tried to answer the query with one function, but the arguments are incorrect.

    The arguments you provided are:

    ```json
    {{ previous_trial }}
    ```

    And the error information is:

    ```
    {{ err_info }}
    ```
    {% endif %}

    # Tools
    You have access to a set of tools. You can use one tool and will receive the result of \
that tool use in the user's response. You use tools step-by-step to respond to the user's \
query, with each tool use informed by the result of the previous tool use.
""")


JSON_NO_FUNCTION_CALL = dedent(r"""
    **Tool Use Formatting:**
    Tool uses are formatted using XML-style tags. The tool name itself becomes the XML tag name. Each \
parameter is enclosed within its own set of tags. Here's the structure:

    <actual_tool_name>
    <parameter1_name>value1</parameter1_name>
    <parameter2_name>value2</parameter2_name>
    ...
    </actual_tool_name>

    Always use the actual tool name as the XML tag name for proper parsing and execution.
""")

