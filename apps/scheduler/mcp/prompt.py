# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""MCP相关的大模型Prompt"""

MCP_SELECT_REASON = r"""
# 指令

你是一个乐于助人的智能助手。
你的任务是：根据当前目标，选择最合适的MCP Server。

## 选择MCP Server时的注意事项：
1. 确保充分理解当前目标，选择最合适的MCP Server。
2. 请在给定的MCP Server列表中选择，不要自己生成MCP Server。
3. 请先给出你选择的理由，再给出你的选择。
4. 当前目标将在下面给出，MCP Server列表也会在下面给出。
   请将你的思考过程放在"思考过程"部分，将你的选择放在"选择结果"部分。
5. 选择必须是JSON格式，严格按照下面的模板，不要输出任何其他内容：

```json
{
    "mcp": "你选择的MCP Server的名称"
}
```

6. 下面的示例仅供参考，不要将示例中的内容作为选择MCP Server的依据。

## 示例

### 目标
我需要一个MCP Server来完成一个任务。

### MCP Server列表
- **mcp_1**: "MCP Server 1"；MCP Server 1的描述
- **mcp_2**: "MCP Server 2"；MCP Server 2的描述

### 思考过程
因为当前目标需要一个MCP Server来完成一个任务，所以选择mcp_1。

### 选择结果
```json
{
    "mcp": "mcp_1"
}
```

## 当前任务

### 目标
{{goal}}

### MCP Server列表
{% for mcp in mcp_list %}
- **{{mcp.id}}**: "{{mcp.name}}"；{{mcp.description}}
{% endfor %}

### 思考过程
"""
MCP_SELECT_FUNCTION = r"""

"""
SELECT_TOOL_REASON = r"""

"""
