# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP Agent执行器"""

import logging
import uuid

import anyio
from mcp.types import TextContent
from pydantic import Field

from apps.llm.reasoning import ReasoningLLM
from apps.models.mcp import MCPInfo, MCPTools
from apps.models.task import ExecutorHistory
from apps.scheduler.executor.base import BaseExecutor
from apps.scheduler.mcp_agent.host import MCPHost
from apps.scheduler.mcp_agent.plan import MCPPlanner
from apps.scheduler.pool.mcp.pool import MCPPool
from apps.schemas.enum_var import EventType, ExecutorStatus, LanguageType, StepStatus
from apps.schemas.mcp import Step
from apps.schemas.message import FlowParams
from apps.services.appcenter import AppCenterManager
from apps.services.mcp_service import MCPServiceManager
from apps.services.task import TaskManager
from apps.services.user import UserManager

logger = logging.getLogger(__name__)
FINAL_TOOL_ID = "FIANL"

class MCPAgentExecutor(BaseExecutor):
    """MCP Agent执行器"""

    max_steps: int = Field(default=40, description="最大步数")
    servers_id: list[str] = Field(description="MCP server id")
    agent_id: uuid.UUID = Field(default=uuid.uuid4(), description="App ID作为Agent ID")
    agent_description: str = Field(default="", description="Agent描述")
    mcp_list: list[MCPInfo] = Field(description="MCP服务器列表", default=[])
    mcp_pool: MCPPool = Field(description="MCP池", default=MCPPool())
    tools: dict[str, MCPTools] = Field(
        description="MCP工具列表，key为tool_id",
        default={},
    )
    tool_list: list[MCPTools] = Field(
        description="MCP工具列表，包含所有MCP工具",
        default=[],
    )
    params: FlowParams | bool | None = Field(
        default=None,
        description="流执行过程中的参数补充",
        alias="params",
    )
    resoning_llm: ReasoningLLM = Field(
        default=ReasoningLLM(),
        description="推理大模型",
    )
    step_cnt: int = Field(default=0, description="当前已执行步骤数")

    async def init(self) -> None:
        """初始化MCP Agent"""
        self.planner = MCPPlanner(self.task.runtime.userInput, self.resoning_llm, self.task.runtime.language)
        self.host = MCPHost(self.task.metadata.userSub, self.resoning_llm)

    async def load_state(self) -> None:
        """从数据库中加载FlowExecutor的状态"""
        logger.info("[MCPAgentExecutor] 加载Executor状态")
        # 尝试恢复State
        if self.task.state and self.task.state.executorStatus != ExecutorStatus.INIT:
            self.task.context = await TaskManager.get_context_by_task_id(self.task.metadata.id)

    async def load_mcp(self) -> None:
        """加载MCP服务器列表"""
        logger.info("[MCPAgentExecutor] 加载MCP服务器列表")
        # 获取MCP服务器列表
        app = await AppCenterManager.fetch_app_data_by_id(self.agent_id)
        mcp_ids = app.mcp_service
        for mcp_id in mcp_ids:
            mcp_service = await MCPServiceManager.get_mcp_service(mcp_id)
            if self.task.metadata.userSub not in mcp_service.activated:
                logger.warning(
                    "[MCPAgentExecutor] 用户 %s 未启用MCP %s",
                    self.task.metadata.userSub,
                    mcp_id,
                )
                continue

            self.mcp_list.append(mcp_service)
            await self.mcp_pool.init_mcp(mcp_id, self.task.metadata.userSub)
            for tool in mcp_service.tools:
                self.tools[tool.id] = tool
            self.tool_list.extend(mcp_service.tools)
        self.tools[FINAL_TOOL_ID] = MCPTools(
            id=FINAL_TOOL_ID, mcpId="", toolName="Final Tool", description="结束流程的工具",
            inputSchema={}, outputSchema={},
        )
        self.tool_list.append(MCPTools(
            id=FINAL_TOOL_ID, mcpId="", toolName="Final Tool", description="结束流程的工具",
            inputSchema={}, outputSchema={}),
        )

    async def get_tool_input_param(self, *, is_first: bool) -> None:
        """获取工具输入参数"""
        if is_first:
            # 获取第一个输入参数
            mcp_tool = self.tools[self.task.state.toolId]
            self.task.state.currentInput = await self.host.get_first_input_params(
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
            mcp_tool = self.tools[self.task.state.tool_id]
            self.task.state.currentInput = await self.host.fill_params(
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
            logger.error(err)
            raise RuntimeError(err)

        # 发送确认消息
        mcp_tool = self.tools[self.task.state.tool_id]
        confirm_message = await self.planner.get_tool_risk(
            mcp_tool, self.task.state.currentInput, "", self.resoning_llm, self.task.runtime.language,
        )
        await self.update_tokens()
        await self.push_message(
            EventType.STEP_WAITING_FOR_START, confirm_message.model_dump(exclude_none=True, by_alias=True),
        )
        await self.push_message(EventType.FLOW_STOP, {})
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
            logger.error(err)
            raise RuntimeError(err)

        self.task.state.executorStatus = ExecutorStatus.RUNNING
        self.task.state.stepStatus = StepStatus.RUNNING
        mcp_tool = self.tools[self.task.state.toolId]
        mcp_client = (await self.mcp_pool.get(mcp_tool.mcp_id, self.task.metadata.userSub))
        try:
            output_params = await mcp_client.call_tool(mcp_tool.name, self.task.state.currentInput)
        except anyio.ClosedResourceError:
            logger.exception("[MCPAgentExecutor] MCP客户端连接已关闭: %s", mcp_tool.mcp_id)
            await self.mcp_pool.stop(mcp_tool.mcp_id, self.task.metadata.userSub)
            await self.mcp_pool.init_mcp(mcp_tool.mcp_id, self.task.metadata.userSub)
            self.task.state.stepStatus = StepStatus.ERROR
            return
        except Exception as e:
            logger.exception("[MCPAgentExecutor] 执行步骤 %s 时发生错误", mcp_tool.name)
            self.task.state.stepStatus = StepStatus.ERROR
            self.task.state.errorMessage = str(e)
            return
        logger.error(f"当前工具名称: {mcp_tool.name}, 输出参数: {output_params}")
        if output_params.isError:
            err = ""
            for output in output_params.content:
                if isinstance(output, TextContent):
                    err += output.text
            self.task.state.stepStatus = StepStatus.ERROR
            self.task.state.errorMessage = {
                "err_msg": err,
                "data": {},
            }
            return
        message = ""
        for output in output_params.content:
            if isinstance(output, TextContent):
                message += output.text
        output_params = {
            "message": message,
        }

        await self.update_tokens()
        await self.push_message(EventType.STEP_INPUT, self.task.state.currentInput)
        await self.push_message(EventType.STEP_OUTPUT, output_params)
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
                inputData=self.task.state.currentInput,
                outputData=output_params,
            ),
        )
        self.task.state.stepStatus = StepStatus.SUCCESS

    async def generate_params_with_null(self) -> None:
        """生成参数补充"""
        if not self.task.state:
            err = "[MCPAgentExecutor] 任务状态不存在"
            logger.error(err)
            raise RuntimeError(err)

        mcp_tool = self.tools[self.task.state.toolId]
        params_with_null = await self.planner.get_missing_param(
            mcp_tool,
            self.task.state.currentInput,
            self.task.state.errorMessage,
        )
        await self.update_tokens()
        error_message = await self.planner.change_err_message_to_description(
            error_message=self.task.state.errorMessage,
            tool=mcp_tool,
            input_params=self.task.state.currentInput,
        )
        await self.push_message(
            EventType.STEP_WAITING_FOR_PARAM, data={"message": error_message, "params": params_with_null},
        )
        await self.push_message(EventType.FLOW_STOP, data={})
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
            logger.error(err)
            raise RuntimeError(err)

        if self.step_cnt < self.max_steps:
            self.step_cnt += 1
            history = await self.host.assemble_memory(self.task.runtime, self.task.context)
            max_retry = 3
            step = None
            for _ in range(max_retry):
                try:
                    step = await self.planner.create_next_step(history, self.tool_list)
                    if step.tool_id in self.tools:
                        break
                except Exception:
                    logger.exception("[MCPAgentExecutor] 获取下一步失败，重试中...")
            if step is None or step.tool_id not in self.tools:
                step = Step(
                    tool_id=FINAL_TOOL_ID,
                    description=FINAL_TOOL_ID,
                )
            tool_id = step.tool_id
            step_name = FINAL_TOOL_ID if tool_id == FINAL_TOOL_ID else self.tools[tool_id].name
            step_description = step.description
            self.task.state.stepId = uuid.uuid4()
            self.task.state.toolId = tool_id
            self.task.state.stepName = step_name
            self.task.state.stepDescription = step_description
            self.task.state.stepStatus = StepStatus.INIT
            self.task.state.currentInput = {}
        else:
            # 没有下一步了，结束流程
            self.task.state.toolId = FINAL_TOOL_ID

    async def error_handle_after_step(self) -> None:
        """步骤执行失败后的错误处理"""
        if not self.task.state:
            err = "[MCPAgentExecutor] 任务状态不存在"
            logger.error(err)
            raise RuntimeError(err)

        self.task.state.stepStatus = StepStatus.ERROR
        self.task.state.executorStatus = ExecutorStatus.ERROR
        await self.push_message(
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

    async def work(self) -> None:
        """执行当前步骤"""
        if self.state.stepStatus == StepStatus.INIT:
            await self.push_message(
                EventType.STEP_INIT,
                data={},
            )
            await self.get_tool_input_param(is_first=True)
            user_info = await UserManager.get_userinfo_by_user_sub(self.task.userSub)
            if not user_info.auto_execute:
                # 等待用户确认
                await self.confirm_before_step()
                return
            self.state.stepStatus = StepStatus.RUNNING
        elif self.state.stepStatus in [StepStatus.PARAM, StepStatus.WAITING, StepStatus.RUNNING]:
            if self.state.stepStatus == StepStatus.PARAM:
                if len(self.context) and self.context[-1].stepId == self.state.stepId:
                    del self.context[-1]
            elif self.state.stepStatus == StepStatus.WAITING:
                if self.params:
                    if len(self.context) and self.context[-1].stepId == self.state.stepId:
                        del self.context[-1]
                else:
                    self.state.executorStatus = ExecutorStatus.CANCELLED
                    self.state.stepStatus = StepStatus.CANCELLED
                    await self.push_message(
                        EventType.STEP_CANCEL,
                        data={},
                    )
                    await self.push_message(
                        EventType.FLOW_CANCEL,
                        data={},
                    )
                    if len(self.context) and self.context[-1].stepId == self.state.stepId:
                        self.context[-1].stepStatus = StepStatus.CANCELLED
                    return
            max_retry = 5
            for i in range(max_retry):
                if i != 0:
                    await self.get_tool_input_param(is_first=True)
                await self.run_step()
                if self.state.stepStatus == StepStatus.SUCCESS:
                    break
        elif self.state.stepStatus == StepStatus.ERROR:
            # 错误处理
            if self.task.state.retry_times >= 3:
                await self.error_handle_after_step()
            else:
                user_info = await UserManager.get_userinfo_by_user_sub(self.task.ids.user_sub)
                if user_info.auto_execute:
                    await self.push_message(
                        EventType.STEP_ERROR,
                        data={
                            "message": self.state.errorMessage,
                        }
                    )
                    if len(self.context) and self.context[-1].stepId == self.state.stepId:
                        self.context[-1].stepStatus = StepStatus.ERROR
                        self.context[-1].outputData = {
                            "message": self.state.errorMessage,
                        }
                    else:
                        self.context.append(
                            ExecutorHistory(
                                task_id=self.task.id,
                                step_id=self.task.state.step_id,
                                step_name=self.task.state.step_name,
                                step_description=self.task.state.step_description,
                                step_status=StepStatus.ERROR,
                                flow_id=self.task.state.flow_id,
                                flow_name=self.task.state.flow_name,
                                flow_status=self.task.state.flow_status,
                                input_data=self.task.state.current_input,
                                output_data={
                                    "message": self.task.state.error_message,
                                },
                            )
                        )
                    await self.get_next_step()
                else:
                    mcp_tool = self.tools[self.state.toolId]
                    is_param_error = await MCPPlanner.is_param_error(
                        self.runtime.question,
                        await MCPHost.assemble_memory(self.task),
                        self.state.errorMessage,
                        mcp_tool,
                        self.state.stepDescription,
                        self.state.currentInput,
                        language=self.runtime.language,
                    )
                    if is_param_error.is_param_error:
                        # 如果是参数错误，生成参数补充
                        await self.generate_params_with_null()
                    else:
                        await self.push_message(
                            EventType.STEP_ERROR,
                            data={
                                "message": self.state.errorMessage,
                            }
                        )
                        if len(self.context) and self.context[-1].stepId == self.state.stepId:
                            self.context[-1].stepStatus = StepStatus.ERROR
                            self.context[-1].outputData = {
                                "message": self.state.errorMessage,
                            }
                        else:
                            self.task.context.append(
                                FlowStepHistory(
                                    task_id=self.task.id,
                                    step_id=self.task.state.step_id,
                                    step_name=self.task.state.step_name,
                                    step_description=self.task.state.step_description,
                                    step_status=StepStatus.ERROR,
                                    flow_id=self.task.state.flow_id,
                                    flow_name=self.task.state.flow_name,
                                    flow_status=self.task.state.flow_status,
                                    input_data=self.task.state.current_input,
                                    output_data={
                                        "message": self.task.state.error_message,
                                    },
                                ),
                            )
                        await self.get_next_step()
        elif self.state.stepStatus == StepStatus.SUCCESS:
            await self.get_next_step()

    async def summarize(self) -> None:
        """总结"""
        async for chunk in MCPPlanner.generate_answer(
            self.runtime.userInput,
            (await MCPHost.assemble_memory(self.task)),
            self.resoning_llm,
            self.runtime.language,
        ):
            await self.push_message(
                EventType.TEXT_ADD,
                data=chunk,
            )
            self.runtime.fullAnswer += chunk

    async def run(self) -> None:
        """执行MCP Agent的主逻辑"""
        # 初始化MCP服务
        await self.load_state()
        await self.load_mcp()
        if self.state.executorStatus == ExecutorStatus.INIT:
            # 初始化状态
            try:
                self.state.executorId = str(uuid.uuid4())
                self.state.executorName = (await MCPPlanner.get_flow_name(
                    self.task.runtime.question, self.resoning_llm, self.task.language
                )).flow_name
                await TaskManager.save_task(self.task.id, self.task)
                await self.get_next_step()
            except Exception as e:
                logger.exception("[MCPAgentExecutor] 初始化失败")
                self.task.state.flow_status = FlowStatus.ERROR
                self.task.state.error_message = str(e)
                await self.push_message(
                    EventType.FLOW_FAILED,
                    data={},
                )
                return
        self.state.executorStatus = ExecutorStatus.RUNNING
        await self.push_message(
            EventType.FLOW_START,
            data={},
        )
        if self.state.toolId == FINAL_TOOL_ID:
            # 如果已经是最后一步，直接结束
            self.state.executorStatus = ExecutorStatus.SUCCESS
            await self.push_message(
                EventType.FLOW_SUCCESS,
                data={},
            )
            await self.summarize()
            return
        try:
            while self.state.executorStatus == ExecutorStatus.RUNNING:
                if self.state.toolId == FINAL_TOOL_ID:
                    break
                await self.work()
                await TaskManager.save_task(self.task.id, self.task)
            if self.state.toolId == FINAL_TOOL_ID:
                # 如果已经是最后一步，直接结束
                self.state.executorStatus = ExecutorStatus.SUCCESS
                self.state.stepStatus = StepStatus.SUCCESS
                await self.push_message(
                    EventType.FLOW_SUCCESS,
                    data={},
                )
                await self.summarize()
        except Exception as e:
            logger.exception("[MCPAgentExecutor] 执行过程中发生错误")
            self.state.executorName = ExecutorStatus.ERROR
            self.state.errorMessage = str(e)
            self.state.stepStatus = StepStatus.ERROR
            await self.push_message(
                EventType.STEP_ERROR,
                data={},
            )
            await self.push_message(
                EventType.FLOW_FAILED,
                data={},
            )
            if len(self.context) and self.context[-1].stepId == self.state.stepId:
                del self.context[-1]
            self.context.append(
                ExecutorHistory(
                    task_id=self.task.id,
                    step_id=self.task.state.step_id,
                    step_name=self.task.state.step_name,
                    step_description=self.task.state.step_description,
                    step_status=self.task.state.step_status,
                    flow_id=self.task.state.flow_id,
                    flow_name=self.task.state.flow_name,
                    flow_status=self.task.state.flow_status,
                    input_data={},
                    output_data={},
                ),
            )
        finally:
            for mcp_service in self.mcp_list:
                try:
                    await self.mcp_pool.stop(mcp_service.id, self.task.ids.user_sub)
                except Exception as e:
                    logger.error("[MCPAgentExecutor] 停止MCP客户端时发生错误: %s", traceback.format_exc())
