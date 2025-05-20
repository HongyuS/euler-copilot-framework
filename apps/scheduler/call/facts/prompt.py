# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""记忆提取工具的提示词"""

from textwrap import dedent

DOMAIN_PROMPT: str = dedent(r"""
    <instructions>
      <instruction>
        根据对话上文，提取推荐系统所需的关键词标签，要求：
        1. 实体名词、技术术语、时间范围、地点、产品等关键信息均可作为关键词标签
        2. 至少一个关键词与对话的话题有关
        3. 标签需精简，不得重复，不得超过10个字
        4. 使用JSON格式输出，不要包含XML标签，不要包含任何解释说明
      </instruction>

      <example>
        <conversation>
          <user>北京天气如何？</user>
          <assistant>北京今天晴。</assistant>
        </conversation>

        <output>
          {
            "keywords": ["北京", "天气"]
          }
        </output>
      </example>
    </instructions>

    <conversation>
    {% for item in conversation %}
      <{{item['role']}}>
        {{item['content']}}
      </{{item['role']}}>
    {% endfor %}
    </conversation>
    <output>
""")
FACTS_PROMPT: str = dedent(r"""
    <instructions>
        <instruction>
            从对话中提取关键信息，并将它们组织成独一无二的、易于理解的事实，包含用户偏好、关系、实体等有用信息。
            以下是需要关注的信息类型以及有关如何处理输入数据的详细说明。

            **你需要关注的信息类型**
            1. 实体：对话中涉及到的实体。例如：姓名、地点、组织、事件等。
            2. 偏好：对待实体的态度。例如喜欢、讨厌等。
            3. 关系：用户与实体之间，或两个实体之间的关系。例如包含、并列、互斥等。
            4. 动作：对实体产生影响的具体动作。例如查询、搜索、浏览、点击等。

            **要求**
            1. 事实必须准确，只能从对话中提取。不要将样例中的信息体现在输出中。
            2. 事实必须清晰、简洁、易于理解。必须少于30个字。
            3. 必须按照以下JSON格式输出：

            {
                "facts": ["事实1", "事实2", "事实3"]
            }
        </instruction>

        <example>
            <conversation>
                <user>杭州西湖有哪些景点？</user>
                <assistant>杭州西湖是中国浙江省杭州市的一个著名景点，以其美丽的自然风光和丰富的文化遗产而闻名。西湖周围有许多著名的景点，包括著名的苏堤、白堤、断桥、三潭印月等。西湖以其清澈的湖水和周围的山脉而著名，是中国最著名的湖泊之一。</assistant>
            </conversation>

            <output>
                {
                    "facts": ["杭州西湖有苏堤、白堤、断桥、三潭印月等景点"]
                }
            </output>
        </example>
    </instructions>

    <conversation>
    {% for item in conversation %}
      <{{item['role']}}>
        {{item['content']}}
      </{{item['role']}}>
    {% endfor %}
    </conversation>
    <output>
""")
