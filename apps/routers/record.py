# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""FastAPI Record相关接口"""

import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request, status
from fastapi.responses import JSONResponse

from apps.common.security import Security
from apps.dependency import verify_personal_token, verify_session
from apps.schemas.record import (
    RecordContent,
    RecordData,
    RecordFlow,
    RecordFlowStep,
    RecordMetadata,
)
from apps.schemas.response_data import (
    RecordListMsg,
    RecordListRsp,
    ResponseData,
)
from apps.schemas.task import FlowStepHistory
from apps.services.conversation import ConversationManager
from apps.services.document import DocumentManager
from apps.services.record import RecordManager
from apps.services.task import TaskManager

router = APIRouter(
    prefix="/api/record",
    tags=["record"],
    dependencies=[
        Depends(verify_session),
        Depends(verify_personal_token),
    ],
)


@router.get("/{conversationId}", response_model=RecordListRsp, responses={
        status.HTTP_403_FORBIDDEN: {"model": ResponseData},
    },
)
async def get_record(request: Request, conversationId: Annotated[uuid.UUID, Path()]) -> JSONResponse:  # noqa: N803
    """获取某个对话的所有问答对"""
    cur_conv = await ConversationManager.get_conversation_by_conversation_id(
        request.state.user_sub, conversationId,
    )
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

    record_group_list = await RecordManager.query_record_group_by_conversation_id(conversationId)
    result = []
    for record_group in record_group_list:
        for record in record_group.records:
            record_data = Security.decrypt(record.content, record.key)
            record_data = RecordContent.model_validate(json.loads(record_data))

            tmp_record = RecordData(
                id=record.id,
                groupId=record_group.id,
                taskId=record_group.task_id,
                conversationId=conversationId,
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
            tmp_record.document = await DocumentManager.get_used_docs_by_record(user_sub, record_group.id)
            # 获得Record关联的flow数据
            flow_step_list = await TaskManager.get_context_by_record_id(record_group.id, record.id)
            if flow_step_list:
                tmp_record.flow = RecordFlow(
                    id=record.flow.flow_id,  # TODO: 此处前端应该用name
                    recordId=record.id,
                    flowStatus=record.flow.flow_staus,
                    flowId=record.flow.flow_id,
                    stepNum=len(flow_step_list),
                    steps=[],
                )
                for flow_step in flow_step_list:
                    flow_step = FlowStepHistory.model_validate(flow_step)
                    tmp_record.flow.steps.append(
                        RecordFlowStep(
                            stepId=flow_step.step_name,  # TODO: 此处前端应该用name
                            stepStatus=flow_step.step_status,
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
