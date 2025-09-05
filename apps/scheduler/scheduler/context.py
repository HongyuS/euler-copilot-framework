# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""上下文管理"""

import logging
import re
from datetime import UTC, datetime

from apps.common.security import Security
from apps.models.record import Record, RecordMetadata
from apps.schemas.enum_var import StepStatus
from apps.schemas.record import (
    FlowHistory,
    RecordContent,
)
from apps.services.appcenter import AppCenterManager
from apps.services.document import DocumentManager
from apps.services.record import RecordManager
from apps.services.task import TaskManager

logger = logging.getLogger(__name__)


async def save_data(scheduler: "Scheduler") -> None:
    """保存当前Executor、Task、Record等的数据"""
    # 构造RecordContent
    used_docs = []
    order_to_id = {}
    for docs in task.runtime.documents:
        used_docs.append(
            RecordGroupDocument(
                _id=docs["id"],
                author=docs.get("author", ""),
                order=docs.get("order", 0),
                name=docs["name"],
                abstract=docs.get("abstract", ""),
                extension=docs.get("extension", ""),
                size=docs.get("size", 0),
                associated="answer",
                created_at=docs.get("created_at", round(datetime.now(UTC).timestamp(), 3)),
            ),
        )
        if docs.get("order") is not None:
            order_to_id[docs["order"]] = docs["id"]

    foot_note_pattern = re.compile(r"\[\[(\d+)\]\]")
    footnote_list = []
    offset = 0
    for match in foot_note_pattern.finditer(task.runtime.answer):
        order = int(match.group(1))
        if order in order_to_id:
            # 计算移除脚注后的插入位置
            original_start = match.start()
            new_position = original_start - offset

            footnote_list.append(
                FootNoteMetaData(
                    releatedId=order_to_id[order],
                    insertPosition=new_position,
                    footSource="rag_search",
                    footType="document",
                ),
            )

            # 更新偏移量，因为脚注被移除会导致后续内容前移
            offset += len(match.group(0))

    # 最后统一移除所有脚注
    task.runtime.answer = foot_note_pattern.sub("", task.runtime.answer).strip()
    record_content = RecordContent(
        question=task.runtime.question,
        answer=task.runtime.answer,
        facts=task.runtime.facts,
        data={},
    )

    try:
        # 加密Record数据
        encrypt_data, encrypt_config = Security.encrypt(record_content.model_dump_json(by_alias=True))
    except Exception:
        logger.exception("[Scheduler] 问答对加密错误")
        return

    # 保存Flow信息
    if task.state:
        # 遍历查找数据，并添加
        await TaskManager.save_flow_context(task.id, task.context)

    # 整理Record数据
    current_time = round(datetime.now(UTC).timestamp(), 2)
    record = Record(
        id=task.ids.record_id,
        conversationId=task.ids.conversation_id,
        taskId=task.id,
        userSub=user_sub,
        content=encrypt_data,
        key=encrypt_config,
        metadata=RecordMetadata(
            timeCost=task.tokens.full_time,
            inputTokens=task.tokens.input_tokens,
            outputTokens=task.tokens.output_tokens,
            feature={},
            footNoteMetadataList=footnote_list,
        ),
        createdAt=current_time,
        flow=FlowHistory(
            flow_id=task.state.flow_id,
            flow_name=task.state.flow_name,
            flow_status=task.state.flow_status,
            history_ids=[context.id for context in task.context],
        ),
    )

    # 修改文件状态
    await DocumentManager.change_doc_status(user_sub, post_body.conversation_id, record_group)
    # 保存Record
    await RecordManager.insert_record_data(user_sub, post_body.conversation_id, record)
    # 保存与答案关联的文件
    await DocumentManager.save_answer_doc(user_sub, record_group, used_docs)

    if post_body.app and post_body.app.app_id:
        # 更新最近使用的应用
        await AppCenterManager.update_recent_app(user_sub, post_body.app.app_id)

    # 若状态为成功，删除Task
    if not task.state or task.state.flow_status == StepStatus.SUCCESS or task.state.flow_status == StepStatus.ERROR or task.state.flow_status == StepStatus.CANCELLED:
        await TaskManager.delete_task_by_task_id(task.id)
    else:
        # 更新Task
        await TaskManager.save_task(task.id, task)
