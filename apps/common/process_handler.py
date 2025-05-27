# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""进程处理器"""

import asyncio
import logging
import multiprocessing
import multiprocessing.context
import os
import signal
from collections.abc import Callable
from typing import ClassVar

logger = logging.getLogger(__name__)
mp = multiprocessing.get_context("spawn")


class ProcessHandler:
    """进程处理器类"""

    tasks: ClassVar[dict[str, multiprocessing.context.SpawnProcess]] = {}
    """存储进程的字典"""
    lock = multiprocessing.Lock()
    """锁对象"""
    max_processes = max((os.cpu_count() or 1) // 2, 1)
    """最大进程数"""

    @staticmethod
    def subprocess_target(target: Callable, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        """子进程目标函数"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(target(*args, **kwargs))

    @staticmethod
    def add_task(task_id: str, target: Callable, *args, **kwargs) -> bool:  # noqa: ANN002, ANN003
        """添加任务"""
        logger.info("[ProcessHandler] 添加任务 %s", task_id)
        ProcessHandler._check_task()
        with ProcessHandler.lock:
            if len(ProcessHandler.tasks) >= ProcessHandler.max_processes:
                logger.warning("[ProcessHandler] 任务数量已达上限(%s)，请稍后再试。", ProcessHandler.max_processes)
                return False

            if task_id not in ProcessHandler.tasks:
                process = mp.Process(
                    target=ProcessHandler.subprocess_target,
                    args=(target, *args),
                    kwargs=kwargs,
                )
                ProcessHandler.tasks[task_id] = process
                process.start()
            else:
                logger.warning("[ProcessHandler] 任务ID %s 已存在，无法添加。", task_id)
        logger.info("[ProcessHandler] 添加任务成功 %s", task_id)
        return True


    @staticmethod
    def remove_task(task_id: str) -> None:
        """删除任务"""
        with ProcessHandler.lock:
            if task_id not in ProcessHandler.tasks:
                logger.warning("[ProcessHandler] 任务ID %s 不存在，无法删除。", task_id)
                return
            process = ProcessHandler.tasks[task_id]

            pid = process.pid if process.is_alive() else None
            if pid is not None:
                try:
                    os.kill(pid, signal.SIGKILL)  # type: ignore[arg-type]
                    logger.info("[ProcessHandler] 进程 %s (%s) 被杀死。", task_id, pid)
                except Exception:
                    logger.exception("[ProcessHandler] 进程 %s 可能已结束", task_id)
            else:
                process.close()
            del ProcessHandler.tasks[task_id]
            logger.info("[ProcessHandler] 任务ID %s 被删除。", task_id)

    @staticmethod
    def _check_task() -> None:
        """检查任务"""
        task_list: list[str] = []
        with ProcessHandler.lock:
            for task_id, process in ProcessHandler.tasks.items():
                if not process.is_alive():
                    task_list.append(task_id)
        for task_id in task_list:
            logger.info("[ProcessHandler] 删除任务 %s", task_id)
            ProcessHandler.remove_task(task_id)
