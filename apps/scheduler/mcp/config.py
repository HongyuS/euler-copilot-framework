"""MCP 配置文件的处理"""


DEFAULT_STDIO = {
    "mcpServers": {
        "server-name": {
            "iconPath": "icon.png",
            "command": "uv",
            "args": [
                "your_package",
            ],
            "env": {
                "EXAMPLE_ENV": "example_value",
            },
        },
    },
}
DEFAULT_SSE = {
    "mcpServers": {
        "server-name": {
            "iconPath": "icon.png",
            "url": "http://localhost:8000/sse",
            "env": {
                "EXAMPLE_HEADER": "example_value",
            },
        },
    },
}
