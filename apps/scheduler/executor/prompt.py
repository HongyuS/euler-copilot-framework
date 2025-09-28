"""Executor相关大模型提示词"""

from textwrap import dedent

from apps.models import LanguageType

EXECUTOR_REASONING: dict[LanguageType, str] = {
    LanguageType.CHINESE: dedent(r"""
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
            <name>{{tool_name}}</name>
            <description>{{tool_description}}</description>
            <output>{{tool_output}}</output>
        </tool>

        <thought>
            {{last_thought}}
        </thought>

        <question>
            你当前需要解决的问题是：
            {{user_question}}
        </question>

        请综合以上信息，再次一步一步地进行思考，并给出见解和行动：
    """),
    LanguageType.ENGLISH: dedent(r"""
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
            <name>{{tool_name}}</name>
            <description>{{tool_description}}</description>
            <output>{{tool_output}}</output>
        </tool>

        <thought>
            {{last_thought}}
        </thought>

        <question>
            The question you need to solve is:
            {{user_question}}
        </question>

        Please integrate the above information, think step by step again, provide insights, and give actions:
    """),
}

FLOW_ERROR_PROMPT: dict[LanguageType, str] = {
    LanguageType.CHINESE: dedent(
        r"""
            <instructions>
                你是一位智能助手，能够根据用户的问题，使用Python工具获取信息，并作出回答。你在使用工具解决回答用户的问题时，发生了错误。
                你的任务是：分析工具（Python程序）的异常信息，分析造成该异常可能的原因，并以通俗易懂的方式，将原因告知用户。

                当前时间：{{ time }}，可以作为时间参照。
                发生错误的程序异常信息将在<error_info>中给出，用户的问题将在<user_question>中给出，上下文背景信息将在<context>中给出。
                注意：输出不要包含任何XML标签，不要编造任何信息。若你认为用户提问与背景信息无关，请忽略背景信息。
            </instructions>

            <error_info>
                {{ error_info }}
            </error_info>

            <user_question>
                {{ question }}
            </user_question>

            <context>
                {{ context }}
            </context>

            现在，输出你的回答：
        """,
    ).strip("\n"),
    LanguageType.ENGLISH: dedent(
        r"""
            <instructions>
                You are an intelligent assistant. When using Python tools to answer user questions, an error occurred.
                Your task is: Analyze the exception information of the tool (Python program), analyze the possible \
causes of the error, and inform the user in an easy-to-understand way.

                Current time: {{ time }}, which can be used as a reference.
                The program exception information that occurred will be given in <error_info>, the user's question \
will be given in <user_question>, and the context background information will be given in <context>.
                Note: Do not include any XML tags in the output. Do not make up any information. If you think the \
user's question is unrelated to the background information, please ignore the background information.
            </instructions>

            <error_info>
                {{ error_info }}
            </error_info>

            <user_question>
                {{ question }}
            </user_question>

            <context>
                {{ context }}
            </context>

            Now, please output your answer:
        """,
    ).strip("\n"),
}

GEN_RAG_ANSWER: dict[LanguageType, str] = {
    LanguageType.CHINESE: r"""
        <instructions>
        你是一个专业的智能助手，擅长基于提供的文档内容回答用户问题。

        <task>
        任务：结合背景信息全面回答用户提问，并为关键信息添加脚注引用。
        </task>

        <input_format>
        - 背景信息：<bac_info> 标签中提供相关文档内容
        - 用户问题：<user_question> 标签中提供具体问题
        - 参考示例：<example> 标签中展示期望的输出格式
        </input_format>

        <output_requirements>
        1. 格式要求：
           - 纯文本输出，不使用任何格式标记（标题、加粗、列表等）
           - 脚注格式：[[1]]、[[2]]、[[3]]，数字对应文档ID
           - 脚注紧跟相关句子的标点符号后

        2. 内容要求：
           - 基于文档内容回答，不编造信息
           - 如问题与文档无关，直接回答而不使用文档
           - 回答应结构清晰：背景→核心→扩展→总结
           - 充分引用文档内容，提供详细信息

        3. 引用规范：
           - 文档ID从1开始按顺序递增
           - 不得使用示例中的文档序号
           - 关键信息必须添加脚注
        </output_requirements>
    </instructions>

    <example>
        <bac_info>
            <document>
                <doc_id>1</doc_id>
                <doc_name>openEuler介绍文档</doc_name>
                <chunk>
                openEuler社区是一个开源操作系统社区，致力于推动Linux操作系统的发展。该社区由华为公司于2019年发起，旨在构建一个开放、协作的操作系统生态系统。
                </chunk>
                <chunk>
                openEuler社区的核心目标是面向服务器、云、边缘计算等场景，为用户提供一个稳定、安全、高效的操作系统平台，并且支持x86、ARM等多种硬件架构。
                </chunk>
            </document>
            <document>
                <doc_id>2</doc_id>
                <doc_name>社区发展报告</doc_name>
                <chunk>
                openEuler社区的成员来自世界各地，包括开发者、用户、企业合作伙伴和学术机构。截至2023年，社区已有超过300家企业和组织参与贡献。
                </chunk>
                <chunk>
                社区成员通过技术贡献、代码提交、文档编写、测试验证等多种方式，共同推动开源操作系统的发展，并为用户提供技术支持和社区服务。
                </chunk>
            </document>
        </bac_info>
        <user_question>
        openEuler社区的目标是什么？有哪些特色？
        </user_question>

        请基于上述背景信息和用户问题，按照指令要求生成详细、结构清晰的回答：

        openEuler社区是一个由华为公司发起的开源操作系统社区，自2019年成立以来，一直致力于推动Linux操作系统的发展。[[1]]

        该社区的核心目标是面向服务器、云、边缘计算等多种应用场景，为用户提供一个稳定、安全、高效的操作系统平台。[[1]]
        同时，openEuler支持x86、ARM等多种硬件架构，具有良好的跨平台兼容性。[[1]]

        在社区建设方面，openEuler汇聚了来自全球的开发者、用户、企业合作伙伴和学术机构。[[2]]
        目前已有超过300家企业和组织参与社区贡献，[[2]] 通过技术贡献、代码提交、文档编写、测试验证等多种方式，
        共同推动开源操作系统的发展。[[2]]

        这种开放协作的模式不仅促进了技术创新，也为用户提供了全面的技术支持和社区服务，
        形成了良性的开源生态系统。[[2]]
    </example>

    <bac_info>
    {bac_info}
    </bac_info>

    <user_question>
    {user_question}
    </user_question>

    请基于上述背景信息和用户问题，按照指令要求生成详细、结构清晰的回答：
    """,
    LanguageType.ENGLISH: r"""
        <instructions>
        You are a professional assistant who specializes in answering user questions based on provided document content.

        <task>
        Task: Answer user questions comprehensively based on background information and add footnote references to \
key information.
        </task>

        <input_format>
        - Background information: Provided in <bac_info> tags with relevant document content
        - User question: Provided in <user_question> tags with specific questions
        - Reference example: Shown in <example> tags with expected output format
        </input_format>

        <output_requirements>
        1. Format requirements:
           - Plain text output, no formatting marks (headings, bold, lists, etc.)
           - Footnote format: [[1]], [[2]], [[3]], with numbers corresponding to document IDs
           - Footnotes placed right after punctuation of related sentences

        2. Content requirements:
           - Answer based on document content, do not fabricate information
           - If the question is unrelated to the document, answer directly without using the document
           - Answers should be well-structured: background → core → expansion → summary
           - Fully cite document content with detailed information

        3. Citation specifications:
           - Document IDs start from 1 and increase sequentially
           - Do not use document numbers from examples
           - Key information must have footnotes
        </output_requirements>
    </instructions>

    <example>
        <bac_info>
            <document>
                <doc_id>1</doc_id>
                <doc_name>openEuler Introduction Document</doc_name>
                <chunk>
                The openEuler community is an open-source operating system community dedicated to promoting the \
development of Linux operating systems. The community was initiated by Huawei in 2019, aiming to build an open \
and collaborative operating system ecosystem.
                </chunk>
                <chunk>
                The core goal of the openEuler community is to provide users with a stable, secure, and efficient \
operating system platform for scenarios such as servers, clouds, and edge computing, supporting multiple hardware \
architectures such as x86 and ARM.
                </chunk>
            </document>
            <document>
                <doc_id>2</doc_id>
                <doc_name>Community Development Report</doc_name>
                <chunk>
                Members of the openEuler community come from all over the world, including developers, users, \
enterprise partners, and academic institutions. As of 2023, the community has over 300 enterprises and \
organizations participating in contributions.
                </chunk>
                <chunk>
                Community members contribute through various ways such as technical contributions, code \
submissions, documentation writing, and testing verification, jointly promoting the development of \
open-source operating systems and providing technical support and community services to users.
                </chunk>
            </document>
        </bac_info>
        <user_question>
        What are the goals and characteristics of the openEuler community?
        </user_question>

        Please generate a detailed and well-structured answer based on the background information and user \
question according to the instructions:

        The openEuler community is an open-source operating system community initiated by Huawei, dedicated \
to promoting the development of Linux operating systems since its establishment in 2019. [[1]]

        The core goal of the community is to provide users with a stable, secure, and efficient operating \
system platform for various application scenarios such as servers, clouds, and edge computing. [[1]]
        At the same time, openEuler supports multiple hardware architectures such as x86 and ARM, offering \
excellent cross-platform compatibility. [[1]]

        In terms of community building, openEuler gathers developers, users, enterprise partners, and \
academic institutions from around the world. [[2]]
        Currently, over 300 enterprises and organizations have participated in community contributions, \
[[2]] jointly promoting the development of open-source operating systems through technical contributions, \
code submissions, documentation writing, and testing verification. [[2]]

        This open collaboration model not only promotes technological innovation but also provides \
comprehensive technical support and community services to users, forming a positive open-source ecosystem. [[2]]
    </example>

    <bac_info>
    {bac_info}
    </bac_info>

    <user_question>
    {user_question}
    </user_question>

    Please generate a detailed and well-structured answer based on the background information and user question \
according to the instructions:
    """,
}
