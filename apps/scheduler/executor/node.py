"""Node相关的函数，含Node转换为Call"""

import inspect
from typing import Any

from apps.scheduler.call.core import CoreCall
from apps.scheduler.call.empty import Empty
from apps.scheduler.call.facts.facts import FactsCall
from apps.scheduler.call.slot.slot import Slot
from apps.scheduler.call.summary.summary import Summary
from apps.scheduler.pool.pool import Pool


class StepNode:
    """Executor的Node相关逻辑"""

    @staticmethod
    async def check_cls(call_cls: Any) -> bool:
        """检查Call是否符合标准要求"""
        flag = True
        if not hasattr(call_cls, "name") or not isinstance(call_cls.name, str):
            flag = False
        if not hasattr(call_cls, "description") or not isinstance(call_cls.description, str):
            flag = False
        if not hasattr(call_cls, "exec") or not inspect.isasyncgenfunction(call_cls.exec):
            flag = False
        return flag

    @staticmethod
    async def get_call_cls(call_id: str) -> type[CoreCall]:
        """获取并验证Call类"""
        # 特判，用于处理隐藏节点
        if call_id == "Empty":
            return Empty
        if call_id == "Summary":
            return Summary
        if call_id == "Facts":
            return FactsCall
        if call_id == "Slot":
            return Slot

        # 从Pool中获取对应的Call
        call_cls: type[CoreCall] = await Pool().get_call(call_id)

        # 检查Call合法性
        if not await StepNode.check_cls(call_cls):
            err = f"[FlowExecutor] 工具 {call_id} 不符合Call标准要求"
            raise ValueError(err)

        return call_cls
