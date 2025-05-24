# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""进程处理器"""

import logging
import os
import signal
import multiprocessing
import uuid
import asyncio


logger = logging.getLogger(__name__)
multiprocessing = multiprocessing.get_context('spawn')


class ProcessHandler:
    """ 进程处理器类"""
    tasks = {}  # 存储进程的字典
    lock = multiprocessing.Lock()  # 创建一个锁对象
    max_processes = max((os.cpu_count() or 1) // 2, 1)  # 获取CPU核心数作为最大进程数，默认为1

    @staticmethod
    def subprocess_target(target, *args, **kwargs):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(target(*args, **kwargs))
        except Exception as e:
            logger.exception(e)
            raise e

    @staticmethod
    def add_task(task_id: str, target, *args, **kwargs):
        ProcessHandler._check_task()
        with ProcessHandler.lock:
            if len(ProcessHandler.tasks) >= ProcessHandler.max_processes:
                warning = f"任务数量已达上限({ProcessHandler.max_processes})，请稍后再试。"
                logging.warning(f"[ProcessHandler] %s", warning)
                return False

            if task_id not in ProcessHandler.tasks:
                process = multiprocessing.Process(target=ProcessHandler.subprocess_target,
                                                  args=(target,) + args, kwargs=kwargs)
                ProcessHandler.tasks[task_id] = process
                process.start()
            else:
                info = f"任务ID {task_id} 已存在，无法添加。"
                logging.info(f"[ProcessHandler] %s", info)
        return True


    @staticmethod
    def remove_task(task_id: uuid.UUID):
        with ProcessHandler.lock:
            if task_id in ProcessHandler.tasks.keys():
                process = ProcessHandler.tasks[task_id]
                try:
                    if process.is_alive():
                        pid = process.pid
                        os.kill(pid, signal.SIGKILL)
                        info = f"进程 {task_id} ({pid}) 被杀死。"
                        logging.info(f"[ProcessHandler] %s", info)
                    else:
                        process.close()
                except Exception as e:
                    warning = f"杀死进程 {task_id} 失败: {e}"
                    logging.warning(f"[ProcessHandler] %s", warning)
                del ProcessHandler.tasks[task_id]
                info = f"任务ID {task_id} 被删除。"
                logging.info(f"[ProcessHandler] %s", info)
            else:
                waring = f"任务ID {task_id} 不存在，无法删除。"
                logging.warning(f"[ProcessHandler] %s", waring)

    @staticmethod
    def _check_task():
        task_list = []
        with ProcessHandler.lock:
            for task_id, process in ProcessHandler.tasks.items():
                if not process.is_alive():
                    task_list.append(task_id)
        for task_id in task_list:
            logger.info(f"[ProcessHandler] remove task {task_id}")
            ProcessHandler.remove_task(task_id)
