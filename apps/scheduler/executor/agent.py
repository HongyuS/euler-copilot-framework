# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP Agent执行器"""

import logging
import uuid

import anyio
from mcp.types import TextContent
from pydantic import Field

from apps.constants import AGENT_FINAL_STEP_NAME, AGENT_MAX_RETRY_TIMES, AGENT_MAX_STEPS
from apps.models.mcp import MCPTools
from apps.models.task import ExecutorHistory
from apps.scheduler.call.slot.slot import Slot
from apps.scheduler.executor.base import BaseExecutor
from apps.scheduler.mcp_agent.host import MCPHost
from apps.scheduler.mcp_agent.plan import MCPPlanner
from apps.scheduler.pool.mcp.pool import MCPPool
from apps.schemas.enum_var import EventType, ExecutorStatus, LanguageType, StepStatus
from apps.schemas.mcp import Step
from apps.schemas.message import FlowParams
from apps.services.appcenter import AppCenterManager
from apps.services.mcp_service import MCPServiceManager
from apps.services.user import UserManager

_logger = logging.getLogger(__name__)

class MCPAgentExecutor(BaseExecutor):
    """MCP Agent执行器"""

    agent_id: uuid.UUID = Field(default=uuid.uuid4(), description="App ID作为Agent ID")
    agent_description: str = Field(default="", description="Agent描述")
    tools: dict[str, MCPTools] = Field(
        description="MCP工具列表，key为tool_id",
        default={},
    )
    params: FlowParams | bool | None = Field(
        default=None,
        description="流执行过程中的参数补充",
        alias="params",
    )

    async def init(self) -> None:
        """初始化MCP Agent"""
        # 初始化必要变量
        self._step_cnt = 0
        self._retry_times = 0
        self._mcp_pool = MCPPool()
        self._mcp_list = []
        self._current_input = {}
        # 初始化MCP Host相关对象
        self._planner = MCPPlanner(self.task.runtime.userInput, self.llm, self.task.runtime.language)
        self._host = MCPHost(self.task.metadata.userSub, self.llm)
        user = await UserManager.get_user(self.task.metadata.userSub)
        if not user:
            err = "[MCPAgentExecutor] 用户不存在: %s"
            _logger.error(err)
            raise RuntimeError(err)
        self._user = user

    async def load_mcp(self) -> None:
        """加载MCP服务器列表"""
        _logger.info("[MCPAgentExecutor] 加载MCP服务器列表")
        # 获取MCP服务器列表
        app = await AppCenterManager.fetch_app_data_by_id(self.agent_id)
        mcp_ids = app.mcp_service
        for mcp_id in mcp_ids:
            if not await MCPServiceManager.is_user_actived(self.task.metadata.userSub, mcp_id):
                _logger.warning(
                    "[MCPAgentExecutor] 用户 %s 未启用MCP %s",
                    self.task.metadata.userSub,
                    mcp_id,
                )
                continue

            mcp_service = await MCPServiceManager.get_mcp_service(mcp_id)
            if mcp_service:
                self._mcp_list.append(mcp_service)

                for tool in await MCPServiceManager.get_mcp_tools(mcp_id):
                    self.tools[tool.id] = tool

        self.tools[AGENT_FINAL_STEP_NAME] = MCPTools(
            id=AGENT_FINAL_STEP_NAME, mcpId="", toolName="Final Tool", description="结束流程的工具",
            inputSchema={}, outputSchema={},
        )

    async def get_tool_input_param(self, *, is_first: bool) -> None:
        """获取工具输入参数"""
        if not self.task.state:
            err = "[MCPAgentExecutor] 任务状态不存在"
            _logger.error(err)
            raise RuntimeError(err)

        if is_first:
            # 获取第一个输入参数
            mcp_tool = self.tools[self.task.state.stepName]
            self._current_input = await self._host.get_first_input_params(
                mcp_tool, self.task.runtime.userInput, self.task,
            )
        else:
            # 获取后续输入参数
            if isinstance(self.params, FlowParams):
                params = self.params.content
                params_description = self.params.description
            else:
                params = {}
                params_description = ""
            mcp_tool = self.tools[self.task.state.stepName]
            self.task.state.currentInput = await self._host.fill_params(
                mcp_tool,
                self.task.runtime.userInput,
                self.task.state.currentInput,
                self.task.state.errorMessage,
                params,
                params_description,
                self.task.runtime.language,
            )

    async def confirm_before_step(self) -> None:
        """确认前步骤"""
        if not self.task.state:
            err = "[MCPAgentExecutor] 任务状态不存在"
            _logger.error(err)
            raise RuntimeError(err)

        # 发送确认消息
        mcp_tool = self.tools[self.task.state.stepName]
        confirm_message = await self._planner.get_tool_risk(
            mcp_tool, self._current_input, "", self.llm, self.task.runtime.language,
        )
        await self._push_message(
            EventType.STEP_WAITING_FOR_START, confirm_message.model_dump(exclude_none=True, by_alias=True),
        )
        await self._push_message(EventType.FLOW_STOP, {})
        self.task.state.executorStatus = ExecutorStatus.WAITING
        self.task.state.stepStatus = StepStatus.WAITING
        self.task.context.append(
            ExecutorHistory(
                taskId=self.task.metadata.id,
                stepId=self.task.state.stepId,
                stepName=self.task.state.stepName,
                stepDescription=self.task.state.stepDescription,
                stepStatus=self.task.state.stepStatus,
                executorId=self.task.state.executorId,
                executorName=self.task.state.executorName,
                executorStatus=self.task.state.executorStatus,
                inputData={},
                outputData={},
                extraData=confirm_message.model_dump(exclude_none=True, by_alias=True),
            ),
        )

    async def run_step(self) -> None:
        """执行步骤"""
        if not self.task.state:
            err = "[MCPAgentExecutor] 任务状态不存在"
            _logger.error(err)
            raise RuntimeError(err)

        self.task.state.executorStatus = ExecutorStatus.RUNNING
        self.task.state.stepStatus = StepStatus.RUNNING
        mcp_tool = self.tools[self.task.state.stepName]
        mcp_client = await self._mcp_pool.get(mcp_tool.mcpId, self.task.metadata.userSub)
        if not mcp_client:
            _logger.exception("[MCPAgentExecutor] MCP客户端不存在: %s", mcp_tool.mcpId)
            self.task.state.stepStatus = StepStatus.ERROR
            self.task.state.errorMessage = {
                "err_msg": f"MCP客户端不存在: {mcp_tool.mcpId}",
                "data": self._current_input,
            }
            return

        try:
            output_data = await mcp_client.call_tool(mcp_tool.name, self._current_input)
        except anyio.ClosedResourceError as e:
            _logger.exception("[MCPAgentExecutor] MCP客户端连接已关闭: %s", mcp_tool.mcpId)
            # 停止当前用户MCP进程
            await self._mcp_pool.stop(mcp_tool.mcpId, self.task.metadata.userSub)
            self.task.state.stepStatus = StepStatus.ERROR
            self.task.state.errorMessage = {
                "err_msg": str(e),
                "data": self._current_input,
            }
            return
        except Exception as e:
            _logger.exception("[MCPAgentExecutor] 执行步骤 %s 时发生错误", self.task.state.stepName)
            self.task.state.stepStatus = StepStatus.ERROR
            self.task.state.errorMessage = {
                "err_msg": str(e),
                "data": self._current_input,
            }
            return

        _logger.error("当前工具名称: %s, 输出参数: %s", self.task.state.stepName, output_data)
        if output_data.isError:
            err = ""
            for output in output_data.content:
                if isinstance(output, TextContent):
                    err += output.text
            self.task.state.stepStatus = StepStatus.ERROR
            self.task.state.errorMessage = {
                "err_msg": err,
                "data": {},
            }
            return

        message = ""
        for output in output_data.content:
            if isinstance(output, TextContent):
                message += output.text
        output_data = {
            "message": message,
        }

        await self._push_message(EventType.STEP_INPUT, self._current_input)
        await self._push_message(EventType.STEP_OUTPUT, output_data)
        self.task.context.append(
            ExecutorHistory(
                taskId=self.task.metadata.id,
                stepId=self.task.state.stepId,
                stepName=self.task.state.stepName,
                stepDescription=self.task.state.stepDescription,
                stepStatus=StepStatus.SUCCESS,
                executorId=self.task.state.executorId,
                executorName=self.task.state.executorName,
                executorStatus=self.task.state.executorStatus,
                inputData=self._current_input,
                outputData=output_data,
            ),
        )
        self.task.state.stepStatus = StepStatus.SUCCESS

    async def generate_params_with_null(self) -> None:
        """生成参数补充"""
        if not self.task.state:
            err = "[MCPAgentExecutor] 任务状态不存在"
            _logger.error(err)
            raise RuntimeError(err)

        mcp_tool = self.tools[self.task.state.stepName]
        params_with_null = await self._planner.get_missing_param(
            mcp_tool,
            self._current_input,
            self.task.state.errorMessage,
        )
        error_message = await self._planner.change_err_message_to_description(
            error_message=self.task.state.errorMessage,
            tool=mcp_tool,
            input_params=self._current_input,
        )
        await self._push_message(
            EventType.STEP_WAITING_FOR_PARAM, data={"message": error_message, "params": params_with_null},
        )
        await self._push_message(EventType.FLOW_STOP, data={})
        self.task.state.executorStatus = ExecutorStatus.WAITING
        self.task.state.stepStatus = StepStatus.PARAM
        self.task.context.append(
            ExecutorHistory(
                taskId=self.task.metadata.id,
                stepId=self.task.state.stepId,
                stepName=self.task.state.stepName,
                stepDescription=self.task.state.stepDescription,
                stepStatus=self.task.state.stepStatus,
                executorId=self.task.state.executorId,
                executorName=self.task.state.executorName,
                executorStatus=self.task.state.executorStatus,
                inputData={},
                outputData={},
                extraData={
                    "message": error_message,
                    "params": params_with_null,
                },
            ),
        )

    async def get_next_step(self) -> None:
        """获取下一步"""
        if not self.task.state:
            err = "[MCPAgentExecutor] 任务状态不存在"
            _logger.error(err)
            raise RuntimeError(err)

        if self._step_cnt < AGENT_MAX_STEPS:
            self._step_cnt += 1
            history = await self._host.assemble_memory(self.task.runtime, self.task.context)
            max_retry = 3
            step = None
            for _ in range(max_retry):
                try:
                    step = await self._planner.create_next_step(history, self.tool_list)
                    if step.tool_id in self.tools:
                        break
                except Exception:
                    _logger.exception("[MCPAgentExecutor] 获取下一步失败，重试中...")
            if step is None or step.tool_id not in self.tools:
                step = Step(
                    tool_id=AGENT_FINAL_STEP_NAME,
                    description=AGENT_FINAL_STEP_NAME,
                )
            step_description = step.description
            self.task.state.stepId = uuid.uuid4()
            self.task.state.stepName = step.tool_id
            self.task.state.stepDescription = step_description
            self.task.state.stepStatus = StepStatus.INIT
        else:
            # 没有下一步了，结束流程
            self.task.state.toolId = AGENT_FINAL_STEP_NAME

    async def error_handle_after_step(self) -> None:
        """步骤执行失败后的错误处理"""
        if not self.task.state:
            err = "[MCPAgentExecutor] 任务状态不存在"
            _logger.error(err)
            raise RuntimeError(err)

        self.task.state.stepStatus = StepStatus.ERROR
        self.task.state.executorStatus = ExecutorStatus.ERROR
        await self._push_message(
            EventType.FLOW_FAILED,
            data={},
        )
        if len(self.task.context) and self.task.context[-1].stepId == self.task.state.stepId:
            del self.task.context[-1]
        self.task.context.append(
            ExecutorHistory(
                taskId=self.task.metadata.id,
                stepId=self.task.state.stepId,
                stepName=self.task.state.stepName,
                stepDescription=self.task.state.stepDescription,
                stepStatus=self.task.state.stepStatus,
                executorId=self.task.state.executorId,
                executorName=self.task.state.executorName,
                executorStatus=self.task.state.executorStatus,
                inputData={},
                outputData={},
            ),
        )

    async def work(self) -> None:  # noqa: C901, PLR0912, PLR0915
        """执行当前步骤"""
        if not self.task.state:
            err = "[MCPAgentExecutor] 任务状态不存在"
            _logger.error(err)
            raise RuntimeError(err)

        if self.task.state.stepStatus == StepStatus.INIT:
            await self._push_message(
                EventType.STEP_INIT,
                data={},
            )
            await self.get_tool_input_param(is_first=True)
            if not self._user.autoExecute:
                # 等待用户确认
                await self.confirm_before_step()
                return
            self.task.state.stepStatus = StepStatus.RUNNING
        elif self.task.state.stepStatus in [StepStatus.PARAM, StepStatus.WAITING, StepStatus.RUNNING]:
            if self.task.state.stepStatus == StepStatus.PARAM:
                if len(self.task.context) and self.task.context[-1].stepId == self.task.state.stepId:
                    del self.task.context[-1]
            elif self.task.state.stepStatus == StepStatus.WAITING:
                if self.params:
                    if len(self.task.context) and self.task.context[-1].stepId == self.task.state.stepId:
                        del self.task.context[-1]
                else:
                    self.task.state.executorStatus = ExecutorStatus.CANCELLED
                    self.task.state.stepStatus = StepStatus.CANCELLED
                    await self._push_message(
                        EventType.STEP_CANCEL,
                        data={},
                    )
                    await self._push_message(
                        EventType.FLOW_CANCEL,
                        data={},
                    )
                    if len(self.task.context) and self.task.context[-1].stepId == self.task.state.stepId:
                        self.task.context[-1].stepStatus = StepStatus.CANCELLED
                    return
            max_retry = 5
            for i in range(max_retry):
                if i != 0:
                    await self.get_tool_input_param(is_first=True)
                await self.run_step()
                if self.task.state.stepStatus == StepStatus.SUCCESS:
                    break
        elif self.task.state.stepStatus == StepStatus.ERROR:
            # 错误处理
            if self._retry_times >= AGENT_MAX_RETRY_TIMES:
                await self.error_handle_after_step()
            else:
                user_info = await UserManager.get_user(self.task.metadata.userSub)
                if user_info.auto_execute:
                    await self._push_message(
                        EventType.STEP_ERROR,
                        data={
                            "message": self.task.state.errorMessage,
                        }
                    )
                    if len(self.task.context) and self.task.context[-1].stepId == self.task.state.stepId:
                        self.task.context[-1].stepStatus = StepStatus.ERROR
                        self.task.context[-1].outputData = {
                            "message": self.task.state.errorMessage,
                        }
                    else:
                        self.task.context.append(
                            ExecutorHistory(
                                taskId=self.task.metadata.id,
                                stepId=self.task.state.stepId,
                                stepName=self.task.state.stepName,
                                stepDescription=self.task.state.stepDescription,
                                stepStatus=StepStatus.ERROR,
                                executorId=self.task.state.executorId,
                                executorName=self.task.state.executorName,
                                executorStatus=self.task.state.executorStatus,
                                inputData=self.task.state.currentInput,
                                outputData={
                                    "message": self.task.state.errorMessage,
                                },
                            ),
                        )
                    await self.get_next_step()
                else:
                    mcp_tool = self.tools[self.task.state.toolId]
                    is_param_error = await self._planner.is_param_error(
                        self.task.runtime.userInput,
                        await self._host.assemble_memory(self.task.runtime, self.task.context),
                        self.task.state.errorMessage,
                        mcp_tool,
                        self.task.state.stepDescription,
                        self.task.state.currentInput,
                        language=self.task.runtime.language,
                    )
                    if is_param_error.is_param_error:
                        # 如果是参数错误，生成参数补充
                        await self.generate_params_with_null()
                    else:
                        await self._push_message(
                            EventType.STEP_ERROR,
                            data={
                                "message": self.task.state.errorMessage,
                            },
                        )
                        if len(self.task.context) and self.task.context[-1].stepId == self.task.state.stepId:
                            self.task.context[-1].stepStatus = StepStatus.ERROR
                            self.task.context[-1].outputData = {
                                "message": self.task.state.errorMessage,
                            }
                        else:
                            self.task.context.append(
                                ExecutorHistory(
                                    taskId=self.task.metadata.id,
                                    stepId=self.task.state.stepId,
                                    stepName=self.task.state.stepName,
                                    stepDescription=self.task.state.stepDescription,
                                    stepStatus=StepStatus.ERROR,
                                    executorId=self.task.state.executorId,
                                    executorName=self.task.state.executorName,
                                    executorStatus=self.task.state.executorStatus,
                                    inputData=self.task.state.currentInput,
                                    outputData={
                                        "message": self.task.state.errorMessage,
                                    },
                                ),
                            )
                        await self.get_next_step()
        elif self.task.state.stepStatus == StepStatus.SUCCESS:
            await self.get_next_step()

    async def summarize(self) -> None:
        """总结"""
        async for chunk in self._planner.generate_answer(
            self.task.runtime.userInput,
            (await self._host.assemble_memory(self.task.runtime, self.task.context)),
            self.llm,
            self.task.runtime.language,
        ):
            await self._push_message(
                EventType.TEXT_ADD,
                data=chunk,
            )
            self.task.runtime.fullAnswer += chunk

    async def run(self) -> None:  # noqa: C901
        """执行MCP Agent的主逻辑"""
        if not self.task.state:
            err = "[MCPAgentExecutor] 任务状态不存在"
            _logger.error(err)
            raise RuntimeError(err)

        # 初始化MCP服务
        await self.load_mcp()
        data = {}
        if self.task.state.executorStatus == ExecutorStatus.INIT:
            # 初始化状态
            self.task.state.executorId = str(uuid.uuid4())
            self.task.state.executorName = (await self._planner.get_flow_name()).flow_name
            flow_risk = await self._planner.get_flow_excute_risk(self.tool_list, self.task.language)
            if self._user.autoExecute:
                data = flow_risk.model_dump(exclude_none=True, by_alias=True)
            await self.get_next_step()

        self.task.state.executorStatus = ExecutorStatus.RUNNING
        await self._push_message(EventType.FLOW_START, data=data)

        if self.task.state.stepName == AGENT_FINAL_STEP_NAME:
            # 如果已经是最后一步，直接结束
            self.task.state.executorStatus = ExecutorStatus.SUCCESS
            await self._push_message(EventType.FLOW_SUCCESS, data={})
            await self.summarize()
            return

        try:
            while self.task.state.executorStatus == ExecutorStatus.RUNNING:
                await self.work()

            if self.task.state.stepName == AGENT_FINAL_STEP_NAME:
                # 如果已经是最后一步，直接结束
                self.task.state.executorStatus = ExecutorStatus.SUCCESS
                self.task.state.stepStatus = StepStatus.SUCCESS
                await self._push_message(EventType.FLOW_SUCCESS, data={})
                await self.summarize()
        except Exception as e:
            _logger.exception("[MCPAgentExecutor] 执行过程中发生错误")
            self.task.state.executorName = ExecutorStatus.ERROR
            self.task.state.errorMessage = {
                "err_msg": str(e),
                "data": {},
            }
            self.task.state.stepStatus = StepStatus.ERROR
            await self._push_message(EventType.STEP_ERROR, data={})
            await self._push_message(EventType.FLOW_FAILED, data={})

            if len(self.task.context) and self.task.context[-1].stepId == self.task.state.stepId:
                del self.task.context[-1]
            self.task.context.append(
                ExecutorHistory(
                    taskId=self.task.metadata.id,
                    stepId=self.task.state.stepId,
                    stepName=self.task.state.stepName,
                    stepDescription=self.task.state.stepDescription,
                    stepStatus=self.task.state.stepStatus,
                    executorId=self.task.state.executorId,
                    executorName=self.task.state.executorName,
                    executorStatus=self.task.state.executorStatus,
                    inputData={},
                    outputData={},
                ),
            )
        finally:
            for mcp_service in self._mcp_list:
                try:
                    await self._mcp_pool.stop(mcp_service.id, self.task.metadata.userSub)
                except Exception:
                    _logger.exception("[MCPAgentExecutor] 停止MCP客户端时发生错误")
