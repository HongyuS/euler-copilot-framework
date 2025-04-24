"""消息队列模块"""
import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

from apps.entities.enum_var import EventType
from apps.entities.message import (
    HeartbeatData,
    MessageBase,
    MessageFlow,
    MessageMetadata,
)
from apps.entities.task import Task

logger = logging.getLogger(__name__)


class MessageQueue:
    """使用asyncio.Queue实现的消息队列"""

    _heartbeat_interval: float = 3.0

    async def init(self) -> None:
        """
        异步初始化消息队列

        :param task: 任务
        """
        self._queue = asyncio.Queue()
        self._close = False
        self._heartbeat_task = asyncio.get_event_loop().create_task(self._heartbeat())

    async def push_output(self, task: Task, event_type: str, data: dict[str, Any]) -> None:
        """组装用于向用户（前端/Shell端）输出的消息"""
        if event_type == EventType.DONE.value:
            await self._queue.put("[DONE]")
            return

        # 计算当前Step时间
        step_time = round((datetime.now(UTC).timestamp() - task.tokens.time), 3)
        step_time = max(step_time, 0)

        metadata = MessageMetadata(
            timeCost=step_time,
            inputTokens=task.tokens.input_tokens,
            outputTokens=task.tokens.output_tokens,
        )

        if task.state:
            # 如果使用了Flow
            flow = MessageFlow(
                appId=task.state.app_id,
                flowId=task.state.flow_id,
                stepId=task.state.step_id,
                stepName=task.state.step_name,
                stepStatus=task.state.status,
            )
        else:
            flow = None

        message = MessageBase(
            event=event_type,
            id=task.ids.record_id,
            groupId=task.ids.group_id,
            conversationId=task.ids.conversation_id,
            taskId=task.id,
            metadata=metadata,
            flow=flow,
            content=data,
        )

        await self._queue.put(json.dumps(message.model_dump(by_alias=True, exclude_none=True), ensure_ascii=False))

    async def get(self) -> AsyncGenerator[str, None]:
        """从Queue中获取消息；变为async generator"""
        while True:
            if self._close and self._queue.empty():
                break

            try:
                message = self._queue.get_nowait()
                yield message
            except asyncio.QueueEmpty:
                await asyncio.sleep(0.02)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("[Queue] 获取消息失败")
                break

    async def _heartbeat(self) -> None:
        """组装用于向用户（前端/Shell端）输出的心跳"""
        heartbeat_template = HeartbeatData()
        heartbeat_msg = json.dumps(heartbeat_template.model_dump(by_alias=True), ensure_ascii=False)

        while True:
            # 如果关闭，则停止心跳
            if self._close:
                break

            # 等待一个间隔
            await asyncio.sleep(self._heartbeat_interval)

            # 添加心跳消息
            await self._queue.put(heartbeat_msg)

    async def close(self) -> None:
        """关闭消息队列"""
        self._close = True
        self._heartbeat_task.cancel()
