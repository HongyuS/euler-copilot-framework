"""用于执行智能问答的Executor"""
from .base import BaseExecutor


class QAExecutor(BaseExecutor):
    """用于执行智能问答的Executor"""

    question: str


    async def run(self) -> None:
        """运行QA"""
        pass

