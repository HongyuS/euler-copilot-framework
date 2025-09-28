# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""使用大模型或使用程序做出判断"""

import ast
import copy
import logging
from collections.abc import AsyncGenerator
from typing import Any

from pydantic import Field

from apps.models import LanguageType
from apps.scheduler.call.choice.condition_handler import ConditionHandler
from apps.scheduler.call.choice.schema import (
    ChoiceBranch,
    ChoiceInput,
    ChoiceOutput,
    Condition,
    Logic,
)
from apps.scheduler.call.core import CoreCall
from apps.schemas.enum_var import CallOutputType
from apps.schemas.scheduler import (
    CallError,
    CallInfo,
    CallOutputChunk,
    CallVars,
)

logger = logging.getLogger(__name__)


class Choice(CoreCall, input_model=ChoiceInput, output_model=ChoiceOutput):
    """Choice工具"""

    to_user: bool = Field(default=False)
    choices: list[ChoiceBranch] = Field(
        description="分支", default=[
            ChoiceBranch(),
            ChoiceBranch(conditions=[Condition()], is_default=False),
        ],
    )

    @classmethod
    def info(cls, language: LanguageType = LanguageType.CHINESE) -> CallInfo:
        """返回Call的名称和描述"""
        i18n_info = {
            LanguageType.CHINESE: CallInfo(name="选择器", description="使用大模型或使用程序做出判断"),
            LanguageType.ENGLISH: CallInfo(name="Choice", description="Use LLM or code to make a decision"),
        }
        return i18n_info[language]

    async def _prepare_message(self, call_vars: CallVars) -> list[ChoiceBranch]:  # noqa: C901, PLR0912, PLR0915
        """替换choices中的系统变量"""
        valid_choices = []

        for choice in self.choices:
            try:
                # 验证逻辑运算符
                if choice.logic not in [Logic.AND, Logic.OR]:
                    msg = f"[Choice] 分支 {choice.branch_id} 条件处理失败：无效的逻辑运算符：{choice.logic}"
                    logger.warning(msg)
                    continue

                valid_conditions = []
                for i in range(len(choice.conditions)):
                    condition = copy.deepcopy(choice.conditions[i])
                    # 处理左值
                    if condition.left.step_id is not None:
                        condition.left.value = self._extract_history_variables(
                            f"{condition.left.step_id}/{condition.left.value}", call_vars.step_data)
                        # 检查历史变量是否成功提取
                        if condition.left.value is None:
                            msg = (f"[Choice] 分支 {choice.branch_id} 条件处理失败："
                                   f"步骤 {condition.left.step_id} 的历史变量不存在")
                            logger.warning(msg)
                            continue
                        if not ConditionHandler.check_value_type(condition.left, condition.left.type):
                            msg = (f"[Choice] 分支 {choice.branch_id} 条件处理失败："
                                   f"左值类型不匹配：{condition.left.value}"
                                   f"应为 {condition.left.type.value if condition.left.type else 'None'}")
                            logger.warning(msg)
                            continue
                    else:
                        msg = f"[Choice] 分支 {choice.branch_id} 条件处理失败：左侧变量缺少step_id"
                        logger.warning(msg)
                        continue
                    # 处理右值
                    if condition.right.step_id is not None:
                        condition.right.value = self._extract_history_variables(
                            f"{condition.right.step_id}/{condition.right.value}", call_vars.step_data,
                        )
                        # 检查历史变量是否成功提取
                        if condition.right.value is None:
                            msg = (f"[Choice] 分支 {choice.branch_id} 条件处理失败："
                                   f"步骤 {condition.right.step_id} 的历史变量不存在")
                            logger.warning(msg)
                            continue
                        if not ConditionHandler.check_value_type(
                                condition.right, condition.right.type,
                            ):
                            msg = (f"[Choice] 分支 {choice.branch_id} 条件处理失败："
                                   f"右值类型不匹配：{condition.right.value}"
                                   f"应为 {condition.right.type.value if condition.right.type else 'None'}")
                            logger.warning(msg)
                            continue
                    else:
                        # 如果右值没有step_id，尝试从call_vars中获取
                        right_value_type = await ConditionHandler.get_value_type_from_operate(
                            condition.operate,
                        )
                        if right_value_type is None:
                            msg = f"[Choice] 分支 {choice.branch_id} 条件处理失败：不支持的运算符：{condition.operate}"
                            logger.warning(msg)
                            continue
                        if condition.right.type != right_value_type:
                            msg = (f"[Choice] 分支 {choice.branch_id} 条件处理失败："
                                   f"右值类型不匹配：{condition.right.value} 应为 {right_value_type.value}")
                            logger.warning(msg)
                            continue
                        condition.right.value = ast.literal_eval(str(condition.right.value))
                        if not ConditionHandler.check_value_type(
                                condition.right, condition.right.type,
                            ):
                            msg = (f"[Choice] 分支 {choice.branch_id} 条件处理失败："
                                   f"右值类型不匹配：{condition.right.value}"
                                   f"应为 {condition.right.type.value if condition.right.type else 'None'}")
                            logger.warning(msg)
                            continue
                    valid_conditions.append(condition)

                # 如果所有条件都无效，抛出异常
                if not valid_conditions and not choice.is_default:
                    msg = f"[Choice] 分支 {choice.branch_id} 条件处理失败：没有有效条件"
                    logger.warning(msg)
                    continue

                # 更新有效条件
                choice.conditions = valid_conditions
                valid_choices.append(choice)

            except ValueError as e:
                msg = f"[Choice] 分支 {choice.branch_id} 处理失败：{e!s}，已跳过"
                logger.warning(msg)
                continue

        return valid_choices

    async def _init(self, call_vars: CallVars) -> ChoiceInput:
        """初始化Choice工具"""
        return ChoiceInput(
            choices=await self._prepare_message(call_vars),
        )

    async def _exec(
        self, input_data: dict[str, Any],
    ) -> AsyncGenerator[CallOutputChunk, None]:
        """执行Choice工具"""
        # 解析输入数据
        data = ChoiceInput(**input_data)
        try:
            branch_id = ConditionHandler.handler(data.choices)
            yield CallOutputChunk(
                type=CallOutputType.DATA,
                content=ChoiceOutput(branch_id=branch_id).model_dump(exclude_none=True, by_alias=True),
            )
        except Exception as e:
            raise CallError(message=f"选择工具调用失败：{e!s}", data={}) from e
