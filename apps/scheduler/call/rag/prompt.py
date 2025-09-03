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
              <qa>
                <question>
                  openEuler的优势有哪些？
                </question>
                <answer>
                  openEuler的优势包括开源、社区支持、以及对云计算和边缘计算的优化。
                </answer>
              </qa>
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
          {{history}}
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
                <qa>
                  <question>
                    What are the features of openEuler?
                  </question>
                  <answer>
                    Compared to other operating systems, openEuler's features include support for multiple \
hardware architectures and providing a stable, secure, and efficient operating system platform.
                  </answer>
                </qa>
                <qa>
                  <question>
                    What are the advantages of openEuler?
                  </question>
                  <answer>
                    The advantages of openEuler include being open-source, having community support, \
and optimizations for cloud and edge computing.
                  </answer>
                </qa>
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
                {{history}}
            </history>
        <question>
            {{question}}
        </question>
    """).strip("\n"),
}

GEN_RAG_ANSWER: dict[LanguageType, str] = {
    LanguageType.CHINESE: r"""
        <instructions>
                你是openEuler社区的智能助手。请结合给出的背景信息, 回答用户的提问，并且基于给出的背景信息在相关句子后\
进行脚注。
                一个例子将在<example>中给出。
                上下文背景信息将在<bac_info>中给出。
                用户的提问将在<user_question>中给出。
                注意：
                1.输出不要包含任何XML标签，不要编造任何信息。若你认为用户提问与背景信息无关，请忽略背景信息直接作答。
                2.脚注的格式为[[1]]，[[2]]，[[3]]等，脚注的内容为提供的文档的id。
                3.脚注只出现在回答的句子的末尾，例如句号、问号等标点符号后面。
                4.不要对脚注本身进行解释或说明。
                5.请不要使用<example></example>中的文档的id作为脚注。
        </instructions>
        <example>
            <bac_info>
                    <document id = 1 name = example_doc>
                        <chunk>
                            openEuler社区是一个开源操作系统社区，致力于推动Linux操作系统的发展。
                        </chunk>
                        <chunk>
                            openEuler社区的目标是为用户提供一个稳定、安全、高效的操作系统平台，并且支持多种硬件架构。
                        </chunk>
                    </document>
                    <document id = 2 name = another_example_doc>
                        <chunk>
                            openEuler社区的成员来自世界各地，包括开发者、用户和企业。
                        </chunk>
                        <chunk>
                            openEuler社区的成员共同努力，推动开源操作系统的发展，并且为用户提供支持和帮助。
                        </chunk>
                    </document>
            </bac_info>
            <user_question>
                    openEuler社区的目标是什么？
            </user_question>
            <answer>
                    openEuler社区是一个开源操作系统社区，致力于推动Linux操作系统的发展。[[1]] openEuler社区的目标是为\
用户提供一个稳定、安全、高效的操作系统平台，并且支持多种硬件架构。[[1]]
            </answer>
        </example>

        <bac_info>
                {bac_info}
        </bac_info>
        <user_question>
                {user_question}
        </user_question>
        """,
    LanguageType.ENGLISH: r"""
        <instructions>
                You are a helpful assistant of openEuler community. Please answer the user's question based on the \
given background information and add footnotes after the related sentences.
                An example will be given in <example>.
                The background information will be given in <bac_info>.
                The user's question will be given in <user_question>.
                Note:
                1. Do not include any XML tags in the output, and do not make up any information. If you think the \
user's question is unrelated to the background information, please ignore the background information and directly \
answer.
                2. Your response should not exceed 250 words.
        </instructions>
        <example>
            <bac_info>
                    <document id = 1 name = example_doc>
                        <chunk>
                            openEuler community is an open source operating system community, committed to promoting \
the development of the Linux operating system.
                        </chunk>
                        <chunk>
                            openEuler community aims to provide users with a stable, secure, and efficient operating \
system platform, and support multiple hardware architectures.
                        </chunk>
                    </document>
                    <document id = 2 name = another_example_doc>
                        <chunk>
                            Members of the openEuler community come from all over the world, including developers, \
users, and enterprises.
                        </chunk>
                        <chunk>
                            Members of the openEuler community work together to promote the development of open \
source operating systems, and provide support and assistance to users.
                        </chunk>
                    </document>
            </bac_info>
            <user_question>
                    What is the goal of openEuler community?
            </user_question>
            <answer>
                    openEuler community is an open source operating system community, committed to promoting the \
development of the Linux operating system. [[1]] openEuler community aims to provide users with a stable, secure, \
and efficient operating system platform, and support multiple hardware architectures. [[1]]
            </answer>
        </example>

        <bac_info>
                {bac_info}
        </bac_info>
        <user_question>
                {user_question}
        </user_question>
        """,
    }
