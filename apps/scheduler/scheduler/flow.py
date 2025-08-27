# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""Scheduler中，关于Flow的逻辑"""

import logging
import uuid

from apps.llm.patterns import Select
from apps.scheduler.pool.pool import Pool
from apps.schemas.request_data import RequestDataApp
from apps.services.task import TaskManager

logger = logging.getLogger(__name__)


class FlowChooser:
    """Flow选择器"""

    def __init__(self, task_id: uuid.UUID, question: str, user_selected: RequestDataApp | None = None) -> None:
        """初始化Flow选择器"""
        self.task_id = task_id
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

        logger.info("[FlowChooser] 选择任务 %s 最合适的Flow", self.task_id)
        choices = [{
            "name": flow.id,
            "description": f"{flow.name}, {flow.description}",
        } for flow in flow_list]
        select_obj = Select()
        top_flow = await select_obj.generate(question=self._question, choices=choices)

        await TaskManager.update_task_token(self.task_id, select_obj.input_tokens, select_obj.output_tokens)
        return top_flow
