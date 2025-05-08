######
载入器
######

载入器（即 ``apps.scheduler.pool.loader`` 模块）是用于从文件系统中加载资源，并将内存中的资源保存在文件系统中的模块。

载入器一般会在Framework启动时执行初始化动作。只有初始化全部结束后，Framework才会开始接受请求。


.. toctree::
   :maxdepth: 2

   mcp
   pool
