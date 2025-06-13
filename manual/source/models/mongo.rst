##############
MongoDB 数据库
##############

MongoDB是一个NoSQL数据库，以集合（``collection``）和文档（``document``）的形式存储和查询数据。

MongoDB有诸多优秀的特性，例如：

- 轻量化，占用系统资源较少
- 文档实际上就是JSON，可以动态增删字段
- 对文档的读写等操作始终原子化
- 支持丰富多样的查询方式
- 支持像Redis一样设置数据的过期时间
- 支持 ``replicaSet`` 模式，可以实现高可用，有一定的事务能力


**************
MongoDB 连接器
**************

.. autoclass:: apps.models.mongo.MongoDB
   :members:
   :undoc-members:
   :private-members:
   :inherited-members:
