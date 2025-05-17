"""问题改写"""

import logging

from pydantic import BaseModel, Field

from apps.llm.function import JsonGenerator
from apps.llm.patterns.core import CorePattern
from apps.llm.reasoning import ReasoningLLM

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
            <input>openEuler的特点？</input>
            <output>
              {{
                "question": "openEuler相较于其他操作系统，其特点是什么？"
              }}
            </output>
          </example>
        </instructions>

        <input>{question}</input>
        <output>
    """
    """用户提示词"""

    async def generate(self, **kwargs) -> str:  # noqa: ANN003
        """问题补全与重写"""
        history = kwargs.get("history", [])
        question = kwargs["question"]

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.user_prompt.format(question=question)},
        ]
        messages = history+messages
        result = ""
        llm = ReasoningLLM()
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
