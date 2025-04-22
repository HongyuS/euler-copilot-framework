"""
Scheduler中，关于Flow的逻辑

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

import logging

from apps.entities.flow import Flow, FlowError, Step
from apps.entities.request_data import RequestDataApp
from apps.entities.task import Task
from apps.llm.patterns import Select
from apps.scheduler.call.llm.schema import RAG_ANSWER_PROMPT
from apps.scheduler.pool.pool import Pool

logger = logging.getLogger(__name__)


class PredifinedRAGFlow(Flow):
    """预定义的RAG Flow"""

    name: str = "KnowledgeBase"
    description: str = "当上述工具无法直接解决用户问题时，使用知识库进行回答。"
    on_error: FlowError = FlowError(use_llm=True)
    steps: dict[str, Step] = ({  # noqa: RUF012
        "start": Step(
            name="start",
            description="开始",
            type="Empty",
            node="Empty",
        ),
        "rag": Step(
            name="查询知识库",
            description="根据用户问题，查询知识库",
            type="RAG",
            node="RAG",
            params={
                "kb_sn": "default",
                "top_k": 5,
                "retrieval_mode": "chunk",
            },
        ),
        "llm": Step(
            name="使用大模型",
            description="调用大模型，生成答案",
            type="LLM",
            node="LLM",
            params={
                "temperature": 0.7,
                "enable_context": True,
                "system_prompt": "",
                "user_prompt": RAG_ANSWER_PROMPT,
            },
        ),
        "end": Step(
            name="end",
            description="结束",
            type="Empty",
            node="Empty",
        ),
    })


class FlowChooser:
    """Flow选择器"""

    def __init__(self, task: Task, question: str, user_selected: RequestDataApp | None = None) -> None:
        """初始化Flow选择器"""
        self.task = task
        self._question = question
        self._user_selected = user_selected


    async def get_top_flow(self) -> str:
        """获取Top1 Flow"""
        # 获取所选应用的所有Flow
        if not self._user_selected or not self._user_selected.app_id:
            return "KnowledgeBase"

        flow_list = await Pool().get_flow_metadata(self._user_selected.app_id)
        if not flow_list:
            return "KnowledgeBase"

        logger.info("[FlowChooser] 选择任务 %s 最合适的Flow", self.task.id)
        choices = [{
            "name": flow.id,
            "description": f"{flow.name}, {flow.description}",
        } for flow in flow_list]
        select_obj = Select()
        top_flow = await select_obj.generate(question=self._question, choices=choices)
        self.task.tokens.input_tokens += select_obj.input_tokens
        self.task.tokens.output_tokens += select_obj.output_tokens
        return top_flow


    async def choose_flow(self) -> RequestDataApp | None:
        """
        依据用户的输入和选择，构造对应的Flow。

        - 当用户没有选择任何app时，直接进行智能问答
        - 当用户选择了特定的app时，在plugin内挑选最适合的flow
        """
        if not self._user_selected or not self._user_selected.app_id:
            return None

        if self._user_selected.flow_id:
            return self._user_selected

        top_flow = await self.get_top_flow()
        if top_flow == "KnowledgeBase":
            return None

        return RequestDataApp(
            appId=self._user_selected.app_id,
            flowId=top_flow,
            params={},
        )
