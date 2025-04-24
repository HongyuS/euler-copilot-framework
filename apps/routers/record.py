"""
FastAPI Record相关接口

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from apps.common.security import Security
from apps.dependency import get_user, verify_user
from apps.entities.record import (
    RecordContent,
    RecordData,
    RecordFlow,
    RecordFlowStep,
    RecordMetadata,
)
from apps.entities.response_data import (
    RecordListMsg,
    RecordListRsp,
    ResponseData,
)
from apps.entities.task import FlowStepHistory
from apps.manager.conversation import ConversationManager
from apps.manager.document import DocumentManager
from apps.manager.record import RecordManager
from apps.manager.task import TaskManager

router = APIRouter(
    prefix="/api/record",
    tags=["record"],
    dependencies=[
        Depends(verify_user),
    ],
)


@router.get(
    "/{conversation_id}",
    response_model=RecordListRsp,
    responses={status.HTTP_403_FORBIDDEN: {"model": ResponseData}},
)
async def get_record(conversation_id: str, user_sub: Annotated[str, Depends(get_user)]) -> JSONResponse:
    """获取某个对话的所有问答对"""
    cur_conv = await ConversationManager.get_conversation_by_conversation_id(user_sub, conversation_id)
    # 判断conversation是否合法
    if not cur_conv:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=ResponseData(
                code=status.HTTP_403_FORBIDDEN,
                message="Conversation invalid.",
                result={},
            ).model_dump(exclude_none=True),
        )

    record_group_list = await RecordManager.query_record_group_by_conversation_id(conversation_id)
    result = []
    for record_group in record_group_list:
        for record in record_group.records:
            record_data = Security.decrypt(record.content, record.key)
            record_data = RecordContent.model_validate(json.loads(record_data))

            tmp_record = RecordData(
                id=record.id,
                groupId=record_group.id,
                taskId=record_group.task_id,
                conversationId=conversation_id,
                content=record_data,
                metadata=record.metadata
                if record.metadata
                else RecordMetadata(
                    inputTokens=0,
                    outputTokens=0,
                    timeCost=0,
                ),
                comment=record.comment.comment,
                createdAt=record.created_at,
            )

            # 获得Record关联的文档
            tmp_record.document = await DocumentManager.get_used_docs_by_record_group(user_sub, record_group.id)

            # 获得Record关联的flow数据
            flow_list = await TaskManager.get_context_by_record_id(record_group.id, record.id)
            if flow_list:
                first_flow = FlowStepHistory.model_validate(flow_list[0])
                tmp_record.flow = RecordFlow(
                    id=first_flow.flow_name,  #TODO: 此处前端应该用name
                    recordId=record.id,
                    flowId=first_flow.id,
                    stepNum=len(flow_list),
                    steps=[],
                )
                for flow in flow_list:
                    flow_step = FlowStepHistory.model_validate(flow)
                    tmp_record.flow.steps.append(
                        RecordFlowStep(
                            stepId=flow_step.step_name,  #TODO: 此处前端应该用name
                            stepStatus=flow_step.status,
                            input=flow_step.input_data,
                            output=flow_step.output_data,
                        ),
                    )

            result.append(tmp_record)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=RecordListRsp(
            code=status.HTTP_200_OK,
            message="success",
            result=RecordListMsg(records=result),
        ).model_dump(exclude_none=True, by_alias=True),
    )
