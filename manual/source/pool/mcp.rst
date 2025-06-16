###########
MCP载入器
###########

MCP载入器（Loader）根据MCP配置文件（一般为 ``.json`` 格式），自动（或手动）创建MCP Server的运行环境，并启动MCP进程。

********
数据结构
********

.. automodule:: apps.entities.mcp
   :members:
   :undoc-members:
   :show-inheritance:


******
客户端
******

客户端是直接与MCP Server进行交互的模块，负责发送请求和接收响应。


客户端类
========

.. automodule:: apps.scheduler.pool.mcp.client
   :members:
   :private-members:
   :undoc-members:
   :show-inheritance:


客户端默认值
============

.. automodule:: apps.scheduler.pool.mcp.default
   :members:
   :private-members:
   :undoc-members:
   :show-inheritance:


客户端自动安装
==============

目前仅支持自动安装使用 ``uvx`` 和 ``npx`` 启动的MCP Server。

.. automodule:: apps.scheduler.pool.mcp.install
   :members:
   :private-members:
   :undoc-members:
   :show-inheritance:


******
加载器
******

加载器是负责加载MCP配置文件并更新数据库条目的模块。

.. autoclass:: apps.scheduler.pool.loader.mcp.MCPLoader
   :members:
   :undoc-members:
   :private-members:
   :show-inheritance:
