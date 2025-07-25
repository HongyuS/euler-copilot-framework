# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""问题改写"""

import logging

from pydantic import BaseModel, Field

from apps.llm.function import JsonGenerator
from apps.llm.reasoning import ReasoningLLM
from apps.llm.token import TokenCalculator

from .core import CorePattern

logger = logging.getLogger(__name__)


class QuestionRewriteResult(BaseModel):
    """问题补全与重写结果"""

    question: str = Field(description="补全后的问题")


class QuestionRewrite(CorePattern):
    """问题补全与重写"""

    system_prompt: str = "You are a helpful assistant."
    """系统提示词"""

    user_prompt: str = r"""
        <instructions>
          <instruction>
            根据上面的对话，推断用户的实际意图并补全用户的提问内容。
            要求：
              1. 请使用JSON格式输出，参考下面给出的样例；不要包含任何XML标签，不要包含任何解释说明；
              2. 若用户当前提问内容与对话上文不相关，或你认为用户的提问内容已足够完整，请直接输出用户的提问内容。
              3. 补全内容必须精准、恰当，不要编造任何内容。
              4. 请输出补全后的问题，不要输出其他内容。
              输出格式样例：
              {{
                "question": "补全后的问题"
              }}
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
              {{
                "question": "详细说明openEuler操作系统的优势和应用场景"
              }}
            </output>
          </example>
        </instructions>

        <history>
          {history}
        </history>
        <question>
          {question}
        </question>

        现在，请输出补全后的问题：
        <output>
    """
    """用户提示词"""

    async def generate(self, **kwargs) -> str:  # noqa: ANN003
        """问题补全与重写"""
        history = kwargs.get("history", [])
        question = kwargs["question"]

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.user_prompt.format(history="", question=question)},
        ]
        llm = kwargs.get("llm")
        if not llm:
            llm = ReasoningLLM()
        leave_tokens = llm._config.max_tokens
        leave_tokens -= TokenCalculator().calculate_token_length(messages)
        if leave_tokens <= 0:
            logger.error("[QuestionRewrite] 大模型上下文窗口不足，无法进行问题补全与重写")
            return question
        index = 0
        qa = ""
        while index < len(history)-1 and leave_tokens > 0:
            q = history[index-1].get("content", "")
            a = history[index].get("content", "")
            sub_qa = f"<qa>\n<question>\n{q}\n</question>\n<answer>\n{a}\n</answer>\n</qa>"
            leave_tokens -= TokenCalculator().calculate_token_length(
                messages=[
                    {"role": "user", "content": sub_qa},
                ],
                pure_text=True,
            )
            if leave_tokens >= 0:
                qa = sub_qa + qa
            index += 2

        messages[1]["content"] = self.user_prompt.format(history=qa, question=question)
        result = ""
        async for chunk in llm.call(messages, streaming=False):
            result += chunk
        self.input_tokens = llm.input_tokens
        self.output_tokens = llm.output_tokens

        messages += [{"role": "assistant", "content": result}]
        json_gen = JsonGenerator(
            query="根据给定的背景信息，生成预测问题",
            conversation=messages,
            schema=QuestionRewriteResult.model_json_schema(),
        )
        try:
            question_dict = QuestionRewriteResult.model_validate(await json_gen.generate())
        except Exception:
            logger.exception("[QuestionRewrite] 问题补全与重写失败")
            return question

        return question_dict.question
