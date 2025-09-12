"""RAG工具的提示词"""

from textwrap import dedent

from apps.schemas.enum_var import LanguageType

QUESTION_REWRITE: dict[LanguageType, str] = {
    LanguageType.CHINESE: dedent(r"""
        <instructions>
            <instruction>
                根据历史对话，推断用户的实际意图并补全用户的提问内容,历史对话被包含在<history>标签中，用户意图被包含在<question>标签中。
                要求：
                    1. 请使用JSON格式输出，参考下面给出的样例；不要包含任何XML标签，不要包含任何解释说明；
                    2. 若用户当前提问内容与对话上文不相关，或你认为用户的提问内容已足够完整，请直接输出用户的提问内容。
                    3. 补全内容必须精准、恰当，不要编造任何内容。
                    4. 请输出补全后的问题，不要输出其他内容。
                    输出格式样例：
                    ```json
                        {
                            "question": "补全后的问题"
                        }
                    ```
            </instruction>

            <example>
                <history>
                    <item>
                        <question>
                            openEuler的优势有哪些？
                        </question>
                        <answer>
                            openEuler的优势包括开源、社区支持、以及对云计算和边缘计算的优化。
                        </answer>
                    </item>
                </history>

                <question>
                    详细点？
                </question>
                <output>
                    ```json
                        {
                            "question": "详细说明openEuler操作系统的优势和应用场景"
                        }
                    ```
                </output>
            </example>
        </instructions>

        <history>
            {% for item in history %}
            <item>
                <question>{{ item.question }}</question>
                <answer>{{ item.answer }}</answer>
            </item>
            {% endfor %}
        </history>
        <question>
            {{question}}
        </question>

        现在，请输出补全后的问题：
        <output>
    """).strip("\n"),
    LanguageType.ENGLISH: dedent(r"""
        <instructions>
            <instruction>
                Based on the historical dialogue, infer the user's actual intent and complete the user's question. \
The historical dialogue is contained within the <history> tags, and the user's intent is contained within the \
<question> tags.
                Requirements:
                    1. Please output in JSON format, referring to the example provided below; do not include any XML \
tags or any explanatory notes;
                    2. If the user's current question is unrelated to the previous dialogue or you believe the \
user's question is already complete enough, directly output the user's question.
                    3. The completed content must be precise and appropriate; do not fabricate any content.
                    4. Output only the completed question; do not include any other content.
                    Example output format:
                    ```json
                        {
                            "question": "The completed question"
                        }
                    ```
            </instruction>

            <example>
                <history>
                    <item>
                        <question>
                            What are the features of openEuler?
                        </question>
                        <answer>
                            Compared to other operating systems, openEuler's features include support for multiple \
hardware architectures and providing a stable, secure, and efficient operating system platform.
                        </answer>
                    </item>
                </history>

                <question>
                    More details?
                </question>
                <output>
                    ```json
                        {
                            "question":  "What are the features of openEuler? Please elaborate on its advantages and \
application scenarios."
                        }
                    ```
                </output>
            </example>

        </instructions>
        <history>
            {% for item in history %}
            <item>
                <question>{{ item.question }}</question>
                <answer>{{ item.answer }}</answer>
            </item>
            {% endfor %}
        </history>
        <question>
            {{question}}
        </question>
    """).strip("\n"),
}
