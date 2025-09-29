"""RAG工具的提示词"""

from textwrap import dedent

from apps.models import LanguageType

QUESTION_REWRITE: dict[LanguageType, str] = {
    LanguageType.CHINESE: dedent(r"""
        <instructions>
            <instruction>
                根据用户当前的提问，推断用户的实际意图并补全用户的提问内容。要求：
                    1. 请使用JSON格式输出，参考下面给出的样例；不要包含任何XML标签，不要包含任何解释说明；
                    2. 若用户当前提问内容已足够完整，请直接输出用户的提问内容。
                    3. 补全内容必须精准、恰当，不要编造任何内容。
                    4. 请参考上下文理解用户的真实意图，确保补全后的问题与上下文保持一致。
                    5. 请输出补全后的问题，不要输出其他内容。
                    输出格式样例：
                    ```json
                        {
                            "question": "补全后的问题"
                        }
                    ```
            </instruction>

            <example>
                <question>
                    openEuler的优势有哪些？
                </question>
                <output>
                    ```json
                        {
                            "question": "openEuler操作系统的优势和应用场景是什么？"
                        }
                    ```
                </output>
            </example>
        </instructions>

        <question>
            {{question}}
        </question>

        现在，请输出补全后的问题：
        <output>
    """).strip("\n"),
    LanguageType.ENGLISH: dedent(r"""
        <instructions>
            <instruction>
                Based on the user's current question, infer the user's actual intent and complete the user's question. \
Requirements:
                    1. Please output in JSON format, referring to the example provided below; do not include any XML \
tags or any explanatory notes;
                    2. If the user's current question is already complete enough, directly output the user's question.
                    3. The completed content must be precise and appropriate; do not fabricate any content.
                    4. Please refer to the context to understand the user's true intent, ensuring that the \
completed question is consistent with the context.
                    5. Output only the completed question; do not include any other content.
                    Example output format:
                    ```json
                        {
                            "question": "The completed question"
                        }
                    ```
            </instruction>

            <example>
                <question>
                    What are the features of openEuler?
                </question>
                <output>
                    ```json
                        {
                            "question": "What are the features and application scenarios of openEuler?"
                        }
                    ```
                </output>
            </example>
        </instructions>
        <question>
            {{question}}
        </question>
    """).strip("\n"),
}
