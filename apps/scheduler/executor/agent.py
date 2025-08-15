# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP Agent执行器"""

import logging
import uuid

import anyio
from mcp.types import TextContent
from pydantic import Field

from apps.llm.reasoning import ReasoningLLM
from apps.scheduler.executor.base import BaseExecutor
from apps.scheduler.mcp_agent.host import MCPHost
from apps.scheduler.mcp_agent.plan import MCPPlanner
from apps.scheduler.pool.mcp.pool import MCPPool
from apps.schemas.enum_var import EventType, ExecutorStatus, StepStatus
from apps.schemas.mcp import (
    MCPCollection,
    MCPTool,
    Step,
)
from apps.schemas.message import FlowParams
from apps.schemas.task import FlowStepHistory
from apps.services.appcenter import AppCenterManager
from apps.services.mcp_service import MCPServiceManager
from apps.services.task import TaskManager
from apps.services.user import UserManager

logger = logging.getLogger(__name__)
FINAL_TOOL_ID = "FIANL"


class MCPAgentExecutor(BaseExecutor):
    """MCP Agent执行器"""

    max_steps: int = Field(default=20, description="最大步数")
    agent_id: str = Field(default="", description="Agent ID")
    mcp_list: list[MCPCollection] = Field(description="MCP服务器列表", default=[])
    mcp_pool: MCPPool = Field(description="MCP池", default=MCPPool())
    tools: dict[str, MCPTool] = Field(
        description="MCP工具列表，key为tool_id",
        default={},
    )
    tool_list: list[MCPTool] = Field(
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

    async def init(self) -> None:
        """初始化Executor"""
        self.planner = MCPPlanner(self.task.runtime.question, self.resoning_llm)
        self.host = MCPHost(self.task.runtime.question)

    async def update_tokens(self) -> None:
        """更新令牌数"""
        self.task.tokens.input_tokens = self.resoning_llm.input_tokens
        self.task.tokens.output_tokens = self.resoning_llm.output_tokens
        await TaskManager.save_task(self.task.id, self.task)

    async def load_state(self) -> None:
        """从数据库中加载FlowExecutor的状态"""
        logger.info("[FlowExecutor] 加载Executor状态")
        # 尝试恢复State
        if self.task.state and self.task.state.flow_status != ExecutorStatus.INIT:
            self.task.context = await TaskManager.get_context_by_task_id(self.task.id)

    async def load_mcp(self) -> None:
        """加载MCP服务器列表"""
        logger.info("[MCPAgentExecutor] 加载MCP服务器列表")
        # 获取MCP服务器列表
        app = await AppCenterManager.fetch_app_data_by_id(self.agent_id)
        mcp_ids = app.mcp_service
        for mcp_id in mcp_ids:
            mcp_service = await MCPServiceManager.get_mcp_service(mcp_id)
            if self.task.ids.user_sub not in mcp_service.activated:
                logger.warning(
                    "[MCPAgentExecutor] 用户 %s 未启用MCP %s",
                    self.task.ids.user_sub,
                    mcp_id,
                )
                continue

            self.mcp_list.append(mcp_service)
            await self.mcp_pool.init_mcp(mcp_id, self.task.ids.user_sub)
            for tool in mcp_service.tools:
                self.tools[tool.id] = tool
            self.tool_list.extend(mcp_service.tools)
        self.tools[FINAL_TOOL_ID] = MCPTool(
            id=FINAL_TOOL_ID, name="Final Tool", description="结束流程的工具", mcp_id="", input_schema={},
        )
        self.tool_list.append(
            MCPTool(id=FINAL_TOOL_ID, name="Final Tool", description="结束流程的工具", mcp_id="", input_schema={}),
        )

    async def get_tool_input_param(self, *, is_first: bool) -> None:
        """获取工具输入参数"""
        if is_first:
            # 获取第一个输入参数
            mcp_tool = self.tools[self.task.state.tool_id]
            self.task.state.current_input = await self.host.get_first_input_params(
                mcp_tool, self.task.state.step_description, self.task,
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
            self.task.state.current_input = await self.host.fill_params(
                mcp_tool,
                self.task.state.step_description,
                self.task.state.current_input,
                self.task.state.error_message,
                params,
                params_description,
            )

    async def confirm_before_step(self) -> None:
        """确认前步骤"""
        # 发送确认消息
        mcp_tool = self.tools[self.task.state.tool_id]
        confirm_message = await self.planner.get_tool_risk(mcp_tool, self.task.state.current_input, "")
        await self.update_tokens()
        await self.push_message(
            EventType.STEP_WAITING_FOR_START, confirm_message.model_dump(exclude_none=True, by_alias=True),
        )
        await self.push_message(EventType.FLOW_STOP, {})
        self.task.state.flow_status = ExecutorStatus.WAITING
        self.task.state.step_status = StepStatus.WAITING
        self.task.context.append(
            FlowStepHistory(
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
                ex_data=confirm_message.model_dump(exclude_none=True, by_alias=True),
            ),
        )

    async def run_step(self) -> None:
        """执行步骤"""
        self.task.state.flow_status = ExecutorStatus.RUNNING
        self.task.state.step_status = StepStatus.RUNNING
        mcp_tool = self.tools[self.task.state.tool_id]
        mcp_client = await self.mcp_pool.get(mcp_tool.mcp_id, self.task.ids.user_sub)
        if mcp_client is None:
            logger.error("[MCPAgentExecutor] MCP客户端不存在: %s", mcp_tool.mcp_id)
            self.task.state.step_status = StepStatus.ERROR
            return
        try:
            output_params = await mcp_client.call_tool(mcp_tool.name, self.task.state.current_input)
        except anyio.ClosedResourceError:
            logger.exception("[MCPAgentExecutor] MCP客户端连接已关闭: %s", mcp_tool.mcp_id)
            await self.mcp_pool.stop(mcp_tool.mcp_id, self.task.ids.user_sub)
            await self.mcp_pool.init_mcp(mcp_tool.mcp_id, self.task.ids.user_sub)
            self.task.state.step_status = StepStatus.ERROR
            return
        except Exception as e:
            import traceback

            logger.exception("[MCPAgentExecutor] 执行步骤 %s 时发生错误: %s", mcp_tool.name, traceback.format_exc())
            self.task.state.step_status = StepStatus.ERROR
            self.task.state.error_message = str(e)
            return
        if output_params.isError:
            err = ""
            for output in output_params.content:
                if isinstance(output, TextContent):
                    err += output.text
            self.task.state.step_status = StepStatus.ERROR
            self.task.state.error_message = err
            return
        message = ""
        for output in output_params.content:
            if isinstance(output, TextContent):
                message += output.text
        output_params = {
            "message": message,
        }

        await self.update_tokens()
        await self.push_message(EventType.STEP_INPUT, self.task.state.current_input)
        await self.push_message(EventType.STEP_OUTPUT, output_params)
        self.task.context.append(
            FlowStepHistory(
                task_id=self.task.id,
                step_id=self.task.state.step_id,
                step_name=self.task.state.step_name,
                step_description=self.task.state.step_description,
                step_status=StepStatus.SUCCESS,
                flow_id=self.task.state.flow_id,
                flow_name=self.task.state.flow_name,
                flow_status=self.task.state.flow_status,
                input_data=self.task.state.current_input,
                output_data=output_params,
            ),
        )
        self.task.state.step_status = StepStatus.SUCCESS

    async def generate_params_with_null(self) -> None:
        """生成参数补充"""
        mcp_tool = self.tools[self.task.state.tool_id]
        params_with_null = await self.planner.get_missing_param(
            mcp_tool, self.task.state.current_input, self.task.state.error_message,
        )
        await self.update_tokens()
        error_message = await self.planner.change_err_message_to_description(
            error_message=self.task.state.error_message,
            tool=mcp_tool,
            input_params=self.task.state.current_input,
        )
        await self.push_message(
            EventType.STEP_WAITING_FOR_PARAM, data={"message": error_message, "params": params_with_null},
        )
        await self.push_message(EventType.FLOW_STOP, data={})
        self.task.state.flow_status = ExecutorStatus.WAITING
        self.task.state.step_status = StepStatus.PARAM
        self.task.context.append(
            FlowStepHistory(
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
                ex_data={"message": error_message, "params": params_with_null},
            ),
        )

    async def get_next_step(self) -> None:
        """获取下一步"""
        if self.task.state.step_cnt < self.max_steps:
            self.task.state.step_cnt += 1
            history = await MCPHost.assemble_memory(self.task)
            max_retry = 3
            step = None
            for _ in range(max_retry):
                try:
                    step = await self.planner.create_next_step(history, self.tool_list)
                    if step.tool_id in self.tools:
                        break
                except Exception as e:  # noqa: BLE001
                    logger.warning("[MCPAgentExecutor] 获取下一步失败，重试中: %s", str(e))
            if step is None or step.tool_id not in self.tools:
                step = Step(
                    tool_id=FINAL_TOOL_ID,
                    description=FINAL_TOOL_ID,
                )
            tool_id = step.tool_id
            step_name = FINAL_TOOL_ID if tool_id == FINAL_TOOL_ID else self.tools[tool_id].name
            step_description = step.description
            self.task.state.step_id = str(uuid.uuid4())
            self.task.state.tool_id = tool_id
            self.task.state.step_name = step_name
            self.task.state.step_description = step_description
            self.task.state.step_status = StepStatus.INIT
            self.task.state.current_input = {}
        else:
            # 没有下一步了，结束流程
            self.task.state.tool_id = FINAL_TOOL_ID

    async def error_handle_after_step(self) -> None:
        """步骤执行失败后的错误处理"""
        self.task.state.step_status = StepStatus.ERROR
        self.task.state.flow_status = ExecutorStatus.ERROR
        await self.push_message(EventType.FLOW_FAILED, data={})
        if len(self.task.context) and self.task.context[-1].step_id == self.task.state.step_id:
            del self.task.context[-1]
        self.task.context.append(
            FlowStepHistory(
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

    async def work(self) -> None:  # noqa: C901, PLR0912, PLR0915
        """执行当前步骤"""
        if self.task.state.step_status == StepStatus.INIT:
            await self.push_message(EventType.STEP_INIT, data={})
            await self.get_tool_input_param(is_first=True)
            user_info = await UserManager.get_userinfo_by_user_sub(self.task.ids.user_sub)
            if user_info is None:
                logger.error("[MCPAgentExecutor] 用户信息不存在: %s", self.task.ids.user_sub)
                return
            if not user_info.auto_execute:
                # 等待用户确认
                await self.confirm_before_step()
                return
            self.task.state.step_status = StepStatus.RUNNING
        elif self.task.state.step_status in [StepStatus.PARAM, StepStatus.WAITING, StepStatus.RUNNING]:
            if self.task.state.step_status == StepStatus.PARAM:
                if len(self.task.context) and self.task.context[-1].step_id == self.task.state.step_id:
                    del self.task.context[-1]
            elif self.task.state.step_status == StepStatus.WAITING:
                if self.params:
                    if len(self.task.context) and self.task.context[-1].step_id == self.task.state.step_id:
                        del self.task.context[-1]
                else:
                    self.task.state.flow_status = ExecutorStatus.CANCELLED
                    self.task.state.step_status = StepStatus.CANCELLED
                    await self.push_message(EventType.STEP_CANCEL, data={})
                    await self.push_message(EventType.FLOW_CANCEL, data={})
                    if len(self.task.context) and self.task.context[-1].step_id == self.task.state.step_id:
                        self.task.context[-1].step_status = StepStatus.CANCELLED
            if self.task.state.step_status == StepStatus.PARAM:
                await self.get_tool_input_param(is_first=False)
            max_retry = 5
            for i in range(max_retry):
                if i != 0:
                    await self.get_tool_input_param(is_first=True)
                await self.run_step()
                if self.task.state.step_status == StepStatus.SUCCESS:
                    break
        elif self.task.state.step_status == StepStatus.ERROR:
            # 错误处理
            if self.task.state.retry_times >= 3:
                await self.error_handle_after_step()
            else:
                user_info = await UserManager.get_userinfo_by_user_sub(self.task.ids.user_sub)
                if user_info is None:
                    logger.error("[MCPAgentExecutor] 用户信息不存在: %s", self.task.ids.user_sub)
                    return
                if user_info.auto_execute:
                    await self.push_message(
                        EventType.STEP_ERROR,
                        data={
                            "message": self.task.state.error_message,
                        },
                    )
                    if len(self.task.context) and self.task.context[-1].step_id == self.task.state.step_id:
                        self.task.context[-1].step_status = StepStatus.ERROR
                        self.task.context[-1].output_data = {
                            "message": self.task.state.error_message,
                        }
                    await self.get_next_step()
                else:
                    mcp_tool = self.tools[self.task.state.tool_id]
                    is_param_error = await self.planner.is_param_error(
                        await self.host.assemble_memory(self.task),
                        self.task.state.error_message,
                        mcp_tool,
                        self.task.state.step_description,
                        self.task.state.current_input,
                    )
                    if is_param_error.is_param_error:
                        # 如果是参数错误，生成参数补充
                        await self.generate_params_with_null()
                    else:
                        await self.push_message(
                            EventType.STEP_ERROR,
                            data={
                                "message": self.task.state.error_message,
                            },
                        )
                        if len(self.task.context) and self.task.context[-1].step_id == self.task.state.step_id:
                            self.task.context[-1].step_status = StepStatus.ERROR
                            self.task.context[-1].output_data = {
                                "message": self.task.state.error_message,
                            }
                        await self.get_next_step()
        elif self.task.state.step_status == StepStatus.SUCCESS:
            await self.get_next_step()

    async def summarize(self) -> None:
        """总结"""
        async for chunk in self.planner.generate_answer(await self.host.assemble_memory(self.task)):
            await self.push_message(EventType.TEXT_ADD, data=chunk)
            self.task.runtime.answer += chunk

    async def run(self) -> None:  # noqa: C901
        """执行MCP Agent的主逻辑"""
        # 初始化MCP服务
        await self.load_state()
        await self.load_mcp()
        if self.task.state.flow_status == ExecutorStatus.INIT:
            # 初始化状态
            try:
                self.task.state.flow_id = str(uuid.uuid4())
                self.task.state.flow_name = await self.planner.get_flow_name()
                await TaskManager.save_task(self.task.id, self.task)
                await self.get_next_step()
            except Exception as e:
                logger.exception("[MCPAgentExecutor] 初始化失败")
                self.task.state.flow_status = ExecutorStatus.ERROR
                self.task.state.error_message = str(e)
                await self.push_message(EventType.FLOW_FAILED, data={})
                return
        self.task.state.flow_status = ExecutorStatus.RUNNING
        await self.push_message(EventType.FLOW_START, data={})
        if self.task.state.tool_id == FINAL_TOOL_ID:
            # 如果已经是最后一步，直接结束
            self.task.state.flow_status = ExecutorStatus.SUCCESS
            await self.push_message(EventType.FLOW_SUCCESS, data={})
            await self.summarize()
            return
        try:
            while self.task.state.flow_status == ExecutorStatus.RUNNING:
                if self.task.state.tool_id == FINAL_TOOL_ID:
                    break
                await self.work()
                await TaskManager.save_task(self.task.id, self.task)
            tool_id = self.task.state.tool_id
            if tool_id == FINAL_TOOL_ID:
                # 如果已经是最后一步，直接结束
                self.task.state.flow_status = ExecutorStatus.SUCCESS
                self.task.state.step_status = StepStatus.SUCCESS
                await self.push_message(EventType.FLOW_SUCCESS, data={})
                await self.summarize()
        except Exception as e:
            logger.exception("[MCPAgentExecutor] 执行过程中发生错误")
            self.task.state.flow_status = ExecutorStatus.ERROR
            self.task.state.error_message = str(e)
            self.task.state.step_status = StepStatus.ERROR
            await self.push_message(EventType.STEP_ERROR, data={})
            await self.push_message(EventType.FLOW_FAILED, data={})
            if len(self.task.context) and self.task.context[-1].step_id == self.task.state.step_id:
                del self.task.context[-1]
            self.task.context.append(
                FlowStepHistory(
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
                except Exception:
                    logger.exception("[MCPAgentExecutor] 停止MCP客户端时发生错误")
