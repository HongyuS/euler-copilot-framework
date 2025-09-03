"""Executor相关大模型提示词"""

from apps.schemas.enum_var import LanguageType

EXECUTOR_REASONING: dict[LanguageType, str] = {
    LanguageType.CHINESE: r"""
        <instructions>
            <instruction>
                你是一个可以使用工具的智能助手。
                在回答用户的问题时，你为了获取更多的信息，使用了一个工具。
                请简明扼要地总结工具的使用过程，提供你的见解，并给出下一步的行动。

                注意：
                工具的相关信息在<tool></tool>标签中给出。
                为了使你更好的理解发生了什么，你之前的思考过程在<thought></thought>标签中给出。
                输出时请不要包含XML标签，输出时请保持简明和清晰。
            </instruction>
        </instructions>

        <tool>
            <name>{tool_name}</name>
            <description>{tool_description}</description>
            <output>{tool_output}</output>
        </tool>

        <thought>
            {last_thought}
        </thought>

        <question>
            你当前需要解决的问题是：
            {user_question}
        </question>

        请综合以上信息，再次一步一步地进行思考，并给出见解和行动：
    """,
    LanguageType.ENGLISH: r"""
        <instructions>
            <instruction>
                You are an intelligent assistant who can use tools.
                When answering user questions, you use a tool to get more information.
                Please summarize the process of using the tool briefly, provide your insights, \
and give the next action.

                Note:
                The information about the tool is given in the <tool></tool> tag.
                To help you better understand what happened, your previous thought process is given in the \
<thought></thought> tag.
                Do not include XML tags in the output, and keep the output brief and clear.
            </instruction>
        </instructions>

        <tool>
            <name>{tool_name}</name>
            <description>{tool_description}</description>
            <output>{tool_output}</output>
        </tool>

        <thought>
            {last_thought}
        </thought>

        <question>
            The question you need to solve is:
            {user_question}
        </question>

        Please integrate the above information, think step by step again, provide insights, and give actions:
    """,
}
