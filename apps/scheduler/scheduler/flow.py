# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Scheduler中，关于Flow的逻辑"""

import logging

from apps.llm.patterns import Select
from apps.scheduler.pool.pool import Pool
from apps.schemas.request_data import RequestDataApp
from apps.schemas.task import Task

logger = logging.getLogger(__name__)


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
        # FIXME KnowledgeBase不是UUID，要改个值
        if top_flow == "KnowledgeBase":
            return None

        return RequestDataApp(
            appId=self._user_selected.app_id,
            flowId=top_flow,
            params={},
        )
