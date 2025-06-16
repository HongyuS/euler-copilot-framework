from apps.scheduler.mcp_agent.tool.base import BaseTool


_TERMINATE_DESCRIPTION = """当请求得到满足或助理无法继续处理任务时，终止交互。
当您完成所有任务后，调用此工具结束工作。"""


class Terminate(BaseTool):
    name: str = "terminate"
    description: str = _TERMINATE_DESCRIPTION
    parameters: dict = {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "description": "交互的完成状态",
                "enum": ["success", "failure"],
            }
        },
        "required": ["status"],
    }

    async def execute(self, status: str) -> str:
        """Finish the current execution"""
        return f"交互已完成，状态为： {status}"
