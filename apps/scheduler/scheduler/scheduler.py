# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""调度器；负责任务的分发与执行"""

import asyncio
import logging
import uuid
from datetime import UTC, datetime

from jinja2 import BaseLoader
from jinja2.sandbox import SandboxedEnvironment

from apps.common.queue import MessageQueue
from apps.llm import Embedding, FunctionLLM, JsonGenerator, ReasoningLLM
from apps.models import AppType, Conversation, ExecutorStatus, Task, TaskRuntime, User
from apps.scheduler.executor import FlowExecutor, MCPAgentExecutor, QAExecutor
from apps.scheduler.pool.pool import Pool
from apps.schemas.enum_var import EventType
from apps.schemas.message import (
    InitContent,
    InitContentFeature,
)
from apps.schemas.request_data import RequestData
from apps.schemas.scheduler import LLMConfig, TopFlow
from apps.schemas.task import TaskData
from apps.services import (
    Activity,
    AppCenterManager,
    ConversationManager,
    KnowledgeBaseManager,
    LLMManager,
    TaskManager,
    UserManager,
)

from .prompt import FLOW_SELECT

_logger = logging.getLogger(__name__)


class Scheduler:
    """
    “调度器”，是最顶层的、控制Executor执行顺序和状态的逻辑。

    Scheduler包含一个“SchedulerContext”，作用为多个Executor的“聊天会话”
    """

    task: TaskData
    llm: LLMConfig
    queue: MessageQueue
    post_body: RequestData
    user: User


    async def init(
            self,
            task_id: uuid.UUID,
            queue: MessageQueue,
            post_body: RequestData,
            user_sub: str,
    ) -> None:
        """初始化"""
        self.queue = queue
        self.post_body = post_body
        # 获取用户
        user = await UserManager.get_user(user_sub)
        if not user:
            err = f"[Scheduler] 用户 {user_sub} 不存在"
            _logger.error(err)
            raise RuntimeError(err)
        self.user = user

        # 获取Task
        task = await TaskManager.get_task_data_by_task_id(task_id)
        if not task:
            _logger.info("[Scheduler] 新建任务")
            task = TaskData(
                metadata=Task(
                    id=task_id,
                    userSub=user_sub,
                    conversationId=self.post_body.conversation_id,
                ),
                runtime=TaskRuntime(
                    taskId=task_id,
                ),
                state=None,
                context=[],
            )
        self.task = task

        # Jinja2
        self._env = SandboxedEnvironment(
            loader=BaseLoader(),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
            extensions=["jinja2.ext.loopcontrols"],
        )

        # LLM
        await self._get_scheduler_llm(post_body.llm_id)


    async def _push_init_message(
        self, context_num: int, *, is_flow: bool = False,
    ) -> None:
        """推送初始化消息"""
        # 组装feature
        if is_flow:
            feature = InitContentFeature(
                maxTokens=self.llm.reasoning.config.maxToken or 0,
                contextNum=context_num,
                enableFeedback=False,
                enableRegenerate=False,
            )
        else:
            feature = InitContentFeature(
                maxTokens=self.llm.reasoning.config.maxToken or 0,
                contextNum=context_num,
                enableFeedback=True,
                enableRegenerate=True,
            )

        # 保存必要信息到Task
        created_at = round(datetime.now(UTC).timestamp(), 3)
        self.task.runtime.time = created_at

        # 推送初始化消息
        await self.queue.push_output(
            self.task,
            self.llm,
            event_type=EventType.INIT.value,
            data=InitContent(feature=feature, createdAt=created_at).model_dump(exclude_none=True, by_alias=True),
        )

    async def _monitor_activity(self, kill_event: asyncio.Event, user_sub: str) -> None:
        """监控用户活动状态，不活跃时终止工作流"""
        try:
            check_interval = 0.5  # 每0.5秒检查一次

            while not kill_event.is_set():
                # 检查用户活动状态
                is_active = await Activity.is_active(user_sub)

                if not is_active:
                    _logger.warning("[Scheduler] 用户 %s 不活跃，终止工作流", user_sub)
                    kill_event.set()
                    break

                # 控制检查频率
                await asyncio.sleep(check_interval)
        except asyncio.CancelledError:
            _logger.info("[Scheduler] 活动监控任务已取消")
        except Exception:
            _logger.exception("[Scheduler] 活动监控过程中发生错误")
            kill_event.set()


    async def _get_scheduler_llm(self, reasoning_llm_id: str) -> LLMConfig:
        """获取RAG大模型"""
        # 获取当前会话使用的大模型
        reasoning_llm = await LLMManager.get_llm(reasoning_llm_id)
        if not reasoning_llm:
            err = "[Scheduler] 获取问答用大模型ID失败"
            _logger.error(err)
            raise ValueError(err)
        reasoning_llm = ReasoningLLM(reasoning_llm)

        # 获取功能性的大模型信息
        function_llm = None
        if not self.user.functionLLM:
            _logger.error("[Scheduler] 用户 %s 没有设置函数调用大模型，相关功能将被禁用", self.user.userSub)
        else:
            function_llm = await LLMManager.get_llm(self.user.functionLLM)
            if not function_llm:
                _logger.error(
                    "[Scheduler] 用户 %s 设置的函数调用大模型ID %s 不存在，相关功能将被禁用",
                    self.user.userSub, self.user.functionLLM,
                )
            else:
                function_llm = FunctionLLM(function_llm)

        embedding_llm = None
        if not self.user.embeddingLLM:
            _logger.error("[Scheduler] 用户 %s 没有设置向量模型，相关功能将被禁用", self.user.userSub)
        else:
            embedding_llm = await LLMManager.get_llm(self.user.embeddingLLM)
            if not embedding_llm:
                _logger.error(
                    "[Scheduler] 用户 %s 设置的向量模型ID %s 不存在，相关功能将被禁用",
                    self.user.userSub, self.user.embeddingLLM,
                )
            else:
                embedding_llm = Embedding(embedding_llm)

        return LLMConfig(
            reasoning=reasoning_llm,
            function=function_llm,
            embedding=embedding_llm,
        )


    async def get_top_flow(self) -> str:
        """获取Top1 Flow"""
        if not self.llm.function:
            err = "[Scheduler] 未设置Function模型"
            _logger.error(err)
            raise RuntimeError(err)

        # 获取所选应用的所有Flow
        if not self.post_body.app or not self.post_body.app.app_id:
            err = "[Scheduler] 未选择应用"
            _logger.error(err)
            raise RuntimeError(err)

        flow_list = await Pool().get_flow_metadata(self.post_body.app.app_id)
        if not flow_list:
            err = "[Scheduler] 未找到应用中合法的Flow"
            _logger.error(err)
            raise RuntimeError(err)

        _logger.info("[Scheduler] 选择应用 %s 最合适的Flow", self.post_body.app.app_id)
        choices = [{
            "name": flow.id,
            "description": f"{flow.name}, {flow.description}",
        } for flow in flow_list]

        # 根据用户语言选择模板
        template = self._env.from_string(FLOW_SELECT[self.task.runtime.language])
        # 渲染模板
        prompt = template.render(
            template,
            question=self.post_body.question,
            choice_list=choices,
        )
        schema = TopFlow.model_json_schema()
        schema["properties"]["choice"]["enum"] = [choice["name"] for choice in choices]
        result_str = await JsonGenerator(self.llm.function, self.post_body.question, [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ], schema).generate()
        result = TopFlow.model_validate(result_str)
        return result.choice


    async def create_new_conversation(
        self, title: str, user_sub: str, app_id: uuid.UUID | None = None,
        *,
        debug: bool = False,
    ) -> Conversation:
        """判断并创建新对话"""
        # 新建对话
        if app_id and not await AppCenterManager.validate_user_app_access(user_sub, app_id):
            err = "Invalid app_id."
            raise RuntimeError(err)
        new_conv = await ConversationManager.add_conversation_by_user_sub(
            title=title,
            user_sub=user_sub,
            app_id=app_id,
            debug=debug,
        )
        if not new_conv:
            err = "Create new conversation failed."
            raise RuntimeError(err)
        return new_conv


    async def _init_task(self) -> None:
        """初始化Task"""
        self.task = await TaskManager.get_task_data_by_task_id(self.post_body.task_id)
        if not self.task:
            self.task = await TaskManager.init_new_task(self.post_body.task_id, self.post_body.conversation_id, self.post_body.language, self.post_body.app.app_id)
        self.task.runtime.question = self.post_body.question
        self.task.state.app_id = self.post_body.app.app_id if self.post_body.app else None


    async def run(self) -> None:
        """运行调度器"""
        # 如果是智能问答，直接执行
        _logger.info("[Scheduler] 开始执行")
        # 创建用于通信的事件
        kill_event = asyncio.Event()
        monitor = asyncio.create_task(self._monitor_activity(kill_event, self.task.metadata.userSub))

        rag_method = True
        if self.post_body.app and self.post_body.app.app_id:
            rag_method = False

        if rag_method:
            kb_ids = await KnowledgeBaseManager.get_selected_kb(self.task.metadata.userSub)
            await self._push_init_message(3, is_flow=False)
            # 启动监控任务和主任务
            main_task = asyncio.create_task(self._run_qa(
                self.task, self.queue, self.task.ids.user_sub, llm, history, doc_ids, rag_data))
        else:
            # 查找对应的App元数据
            app_data = await AppCenterManager.fetch_app_data_by_id(self.post_body.app.app_id)
            if not app_data:
                _logger.error("[Scheduler] App %s 不存在", self.post_body.app.app_id)
                await self.queue.close()
                return

            # 获取上下文
            if app_data.app_type == AppType.FLOW:
                # 需要执行Flow
                is_flow = True
            else:
                # Agent 应用
                is_flow = False
            # 启动监控任务和主任务
            main_task = asyncio.create_task(self._run_agent(self.queue, self.post_body, executor_background))
        # 等待任一任务完成
        done, pending = await asyncio.wait(
            [main_task, monitor],
            return_when=asyncio.FIRST_COMPLETED,
        )

        # 如果用户手动终止，则cancel主任务
        if kill_event.is_set():
            _logger.warning("[Scheduler] 用户取消执行，正在终止...")
            main_task.cancel()
            if self.task.state.executorStatus in [ExecutorStatus.RUNNING, ExecutorStatus.WAITING]:
                self.task.state.executorStatus = ExecutorStatus.CANCELLED
            try:
                await main_task
                _logger.info("[Scheduler] 工作流执行已被终止")
            except Exception:
                _logger.exception("[Scheduler] 终止工作流时发生错误")

        # 更新Task，发送结束消息
        _logger.info("[Scheduler] 发送结束消息")
        await self.queue.push_output(self.task, event_type=EventType.DONE.value, data={})
        # 关闭Queue
        await self.queue.close()

        return


    async def _run_qa(self) -> None:
        qa_executor = QAExecutor(
            task=self.task,
            msg_queue=self.queue,
            question=self.post_body.question,
            llm=self.llm,
        )
        _logger.info("[Scheduler] 开始智能问答")
        await qa_executor.init()
        await qa_executor.run()
        self.task = qa_executor.task


    async def _run_flow(self) -> None:
        # 获取应用信息
        if not self.post_body.app or not self.post_body.app.app_id:
            _logger.error("[Scheduler] 未选择应用")
            return

        _logger.info("[Scheduler] 获取工作流元数据")
        flow_info = await Pool().get_flow_metadata(self.post_body.app.app_id)

        # 如果flow_info为空，则直接返回
        if not flow_info:
            _logger.error("[Scheduler] 未找到工作流元数据")
            return

        # 如果用户选了特定的Flow
        if not self.post_body.app.flow_id:
            _logger.info("[Scheduler] 选择最合适的流")
            flow_id = await self.get_top_flow()
        else:
            # 如果用户没有选特定的Flow，则根据语义选择一个Flow
            flow_id = self.post_body.app.flow_id
        _logger.info("[Scheduler] 获取工作流定义")
        flow_data = await Pool().get_flow(self.post_body.app.app_id, flow_id)

        # 如果flow_data为空，则直接返回
        if not flow_data:
            _logger.error("[Scheduler] 未找到工作流定义")
            return

        # 初始化Executor
        flow_exec = FlowExecutor(
            flow_id=flow_id,
            flow=flow_data,
            task=self.task,
            msg_queue=self.queue,
            question=self.post_body.question,
            post_body_app=self.post_body.app,
            llm=self.llm,
        )

        # 开始运行
        _logger.info("[Scheduler] 运行工作流执行器")
        await flow_exec.init()
        await flow_exec.run()
        self.task = flow_exec.task


    async def _run_agent(self) -> None:
        """构造Executor并执行"""
        # 获取应用信息
        if not self.post_body.app or not self.post_body.app.app_id:
            _logger.error("[Scheduler] 未选择MCP应用")
            return

        # 初始化Executor
        agent_exec = MCPAgentExecutor(
            task=self.task,
            msg_queue=self.queue,
            question=self.post_body.question,
            agent_id=self.post_body.app.app_id,
            params=self.post_body.app.params,
            llm=self.llm,
        )
        # 开始运行
        _logger.info("[Scheduler] 运行MCP执行器")
        await agent_exec.init()
        await agent_exec.run()
        self.task = agent_exec.task


    async def _save_task(self) -> None:
        """保存Task"""
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
