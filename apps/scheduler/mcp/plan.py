# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP 用户目标拆解与规划"""

class MCPPlanner:
    """MCP 用户目标拆解与规划"""

    def __init__(self, user_goal: str) -> None:
        """初始化MCP规划器"""
        self.user_goal = user_goal


    def create_plan(self) -> list[str]:
        """规划下一步的执行流程，并输出"""
        pass


    def evaluate_plan(self) -> bool:
        """评估MCP"""
        pass
