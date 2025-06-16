# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""上下文管理"""

import logging
from datetime import UTC, datetime

from apps.common.security import Security
from apps.entities.collection import Document
from apps.entities.enum_var import StepStatus
from apps.entities.record import (
    Record,
    RecordContent,
    RecordDocument,
    RecordMetadata,
)
from apps.entities.request_data import RequestData
from apps.entities.task import Task
from apps.llm.patterns.facts import Facts
from apps.manager.appcenter import AppCenterManager
from apps.manager.document import DocumentManager
from apps.manager.record import RecordManager
from apps.manager.task import TaskManager

logger = logging.getLogger(__name__)


async def get_docs(user_sub: str, post_body: RequestData) -> tuple[list[RecordDocument] | list[Document], list[str]]:
    """获取当前问答可供关联的文档"""
    if not post_body.group_id:
        err = "[Scheduler] 问答组ID不能为空！"
        logger.error(err)
        raise ValueError(err)

    doc_ids = []

    docs = await DocumentManager.get_used_docs_by_record_group(user_sub, post_body.group_id)
    if not docs:
        # 是新提问
        # 从Conversation中获取刚上传的文档
        docs = await DocumentManager.get_unused_docs(user_sub, post_body.conversation_id)
        # 从最近10条Record中获取文档
        docs += await DocumentManager.get_used_docs(user_sub, post_body.conversation_id, 10)
        doc_ids += [doc.id for doc in docs]
    else:
        # 是重新生成
        doc_ids += [doc.id for doc in docs]

    return docs, doc_ids


async def assemble_history(history: list[dict[str, str]]) -> str:
    """
    组装历史问题

    :param history: 历史问题列表
    :return: 组装后的字符串
    """
    history_str = ""
    for item in history:
        role = item.get("role")
        content = item.get("content")
        if role and content:
            history_str += f"{role}: {content}\n"
    return history_str.strip()


async def get_context(user_sub: str, post_body: RequestData, n: int) -> tuple[list[dict[str, str]], list[str]]:
    """
    获取当前问答的上下文信息

    注意：这里的n要比用户选择的多，因为要考虑事实信息和历史问题
    """
    # 最多15轮
    n = min(n, 15)

    # 获取最后n+5条Record
    records = await RecordManager.query_record_by_conversation_id(user_sub, post_body.conversation_id, n + 5)

    # 组装问答
    context = []
    facts = []
    for record in records:
        record_data = RecordContent.model_validate_json(Security.decrypt(record.content, record.key))
        context.append({"role": "user", "content": record_data.question})
        context.append({"role": "assistant", "content": record_data.answer})
        facts.extend(record_data.facts)

    return context, facts


async def generate_facts(task: Task, question: str) -> tuple[Task, list[str]]:
    """生成Facts"""
    message = [
        {"role": "user", "content": question},
        {"role": "assistant", "content": task.runtime.answer},
    ]

    facts = await Facts().generate(conversation=message)
    task.runtime.facts = facts
    await TaskManager.save_task(task.id, task)

    return task, facts


async def save_data(task: Task, user_sub: str, post_body: RequestData, used_docs: list[str]) -> None:
    """保存当前Executor、Task、Record等的数据"""
    # 构造RecordContent
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
        groupId=task.ids.group_id,
        conversationId=task.ids.conversation_id,
        taskId=task.id,
        user_sub=user_sub,
        content=encrypt_data,
        key=encrypt_config,
        metadata=RecordMetadata(
            timeCost=task.tokens.full_time,
            inputTokens=task.tokens.input_tokens,
            outputTokens=task.tokens.output_tokens,
            feature={},
        ),
        createdAt=current_time,
        flow=[i["_id"] for i in task.context],
    )

    # 检查是否存在group_id
    if not await RecordManager.check_group_id(task.ids.group_id, user_sub):
        record_group = await RecordManager.create_record_group(
            task.ids.group_id, user_sub, post_body.conversation_id, task.id,
        )
        if not record_group:
            logger.error("[Scheduler] 创建问答组失败")
            return
    else:
        record_group = task.ids.group_id

    # 修改文件状态
    await DocumentManager.change_doc_status(user_sub, post_body.conversation_id, record_group)
    # 保存Record
    await RecordManager.insert_record_data_into_record_group(user_sub, record_group, record)
    # 保存与答案关联的文件
    await DocumentManager.save_answer_doc(user_sub, record_group, used_docs)

    if post_body.app and post_body.app.app_id:
        # 更新最近使用的应用
        await AppCenterManager.update_recent_app(user_sub, post_body.app.app_id)

    # 若状态为成功，删除Task
    if not task.state or task.state.status == StepStatus.SUCCESS:
        await TaskManager.delete_task_by_task_id(task.id)
    else:
        # 更新Task
        await TaskManager.save_task(task.id, task)
