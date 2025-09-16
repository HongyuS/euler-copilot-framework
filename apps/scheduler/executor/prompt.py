"""Executor相关大模型提示词"""

from textwrap import dedent

from apps.schemas.enum_var import LanguageType

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
                你是openEuler社区的智能助手。请结合给出的文档内容, 回答用户的提问，并且基于给出的文档内容在相关句子后\
进行脚注标注。
                一个例子将在<example>中给出。
                文档内容将在<docs>中给出。
                用户的提问将在<user_question>中给出。
                注意：
                1.输出不要包含任何XML标签，不要编造任何信息。若你认为用户提问与文档内容无关，请忽略文档内容直接作答。
                2.脚注的格式为[[1]]，[[2]]，[[3]]等，脚注的内容为对应的文档ID。
                3.脚注只出现在回答的句子的末尾，例如句号、问号等标点符号后面。
                4.不要对脚注本身进行解释或说明。
                5.请不要使用<example></example>中的文档ID作为脚注。
                6.请仔细识别文档中的关键信息并准确标注来源。
        </instructions>
        <example>
            <docs>
                <document id="1" name="example_doc">
                    <chunk>openEuler社区是一个开源操作系统社区，致力于推动Linux操作系统的发展。</chunk>
                    <chunk>openEuler社区的目标是为用户提供一个稳定、安全、高效的操作系统平台，并且支持多种硬件架构。</chunk>
                </document>
                <document id="2" name="another_example_doc">
                    <chunk>openEuler社区的成员来自世界各地，包括开发者、用户和企业。</chunk>
                    <chunk>openEuler社区的成员共同努力，推动开源操作系统的发展，并且为用户提供支持和帮助。</chunk>
                </document>
            </docs>
            <user_question>
                openEuler社区的目标是什么？
            </user_question>
            <answer>
                openEuler社区是一个开源操作系统社区，致力于推动Linux操作系统的发展。[[1]] openEuler社区的目标是为\
用户提供一个稳定、安全、高效的操作系统平台，并且支持多种硬件架构。[[1]]
            </answer>
        </example>

        <docs>
                {{docs}}
        </docs>
        <user_question>
                {{user_question}}
        </user_question>
        """,
    LanguageType.ENGLISH: r"""
        <instructions>
                You are a helpful assistant of openEuler community. Please answer the user's question based on the \
given document contents and add footnote markers after the related sentences.
                An example will be given in <example>.
                The document contents will be given in <docs>.
                The user's question will be given in <user_question>.
                Note:
                1. Do not include any XML tags in the output, and do not make up any information. If you think the \
user's question is unrelated to the document contents, please ignore the document contents and directly \
answer.
                2. Your response should not exceed 250 words.
                3. Clearly identify and cite the source documents for key information in your answer.
                4. Use footnote format [[1]], [[2]], [[3]], etc., where the number corresponds to the document ID.
        </instructions>
        <example>
            <docs>
                <document id="1" name="example_doc">
                    <chunk>openEuler community is an open source operating system community, committed to promoting \
the development of the Linux operating system.</chunk>
                    <chunk>openEuler community aims to provide users with a stable, secure, and efficient operating \
system platform, and support multiple hardware architectures.</chunk>
                </document>
                <document id="2" name="another_example_doc">
                    <chunk>Members of the openEuler community come from all over the world, including developers, \
users, and enterprises.</chunk>
                    <chunk>Members of the openEuler community work together to promote the development of open \
source operating systems, and provide support and assistance to users.</chunk>
                </document>
            </docs>
            <user_question>
                What is the goal of openEuler community?
            </user_question>
            <answer>
                openEuler community is an open source operating system community, committed to promoting the \
development of the Linux operating system. [[1]] openEuler community aims to provide users with a \
stable, secure, and efficient operating system platform, and support multiple hardware architectures. [[1]]
            </answer>
        </example>

        <docs>
                {docs}
        </docs>
        <user_question>
                {user_question}
        </user_question>
        """,
    }
