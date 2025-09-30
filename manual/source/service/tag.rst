########################
Tag 模块（用户标签）
########################

.. currentmodule:: apps.services.tag

概述
====

``Tag`` 模块提供用户标签的增删改查能力，统一通过数据库会话访问 ``Tag`` 与 ``UserTag`` 两类模型，实现：

- 获取全部标签
- 按名称查询标签
- 按用户 ``sub`` 查询其拥有的标签集合
- 新增标签（若存在则合并）
- 按名称更新标签定义
- 删除标签

依赖
====

- 数据库会话：``apps.common.postgres.postgres.session`` （异步上下文）
- 数据模型：``apps.models.Tag``、``apps.models.UserTag``
- 入参模型：``apps.schemas.request_data.PostTagData`` （字段：``tag``、``description``）

API 参考
========

TagManager 类
--------------

.. autoclass:: TagManager
   :members:
   :undoc-members:
   :show-inheritance:

设计说明
========

- 读取路径：查询 ``Tag`` 表，或先查 ``UserTag`` 再关联回 ``Tag`` 表。
- 写入路径：采用 ``session.merge`` 以便在新增/幂等更新间取得平衡。
- 时间戳：更新时写入 ``updatedAt = datetime.now(tz=UTC)``。
- 异常处理：更新/删除时若目标标签不存在，记录错误并抛出 ``ValueError``。

流程图（get_tag_by_user_sub）
=============================

.. uml::

   @startuml
   title 通过 user_sub 查询用户标签流程
   start
   :传入 user_sub;
   :开启数据库会话;
   :查询 UserTag where userSub = user_sub;
   if (是否存在 user_tags?) then (是)
     :遍历 user_tags;
     :按 tag id 逐个查询 Tag;
     :若 Tag 存在则加入结果列表;
   else (否)
     :返回空列表;
     stop
   endif
   :返回标签结果列表;
   stop
   @enduml

流程图（add/update/delete）
============================

.. uml::

   @startuml
   title 标签写操作流程（add / update / delete）
   start
   :开启数据库会话;
   partition add_tag {
     :构造 Tag(name=data.tag, definition=data.description);
     :session.merge(tag);
     :commit;
   }
   partition update_tag_by_name {
     :按名称查询 Tag;
     if (是否存在?) then (否)
       :logger.error 并抛出 ValueError;
       stop
     else (是)
       :更新 definition, updatedAt;
       :session.merge(tag);
       :commit 并返回 tag;
     endif
   }
   partition delete_tag {
     :按名称查询 Tag;
     if (是否存在?) then (否)
       :logger.error 并抛出 ValueError;
       stop
     else (是)
       :session.delete(tag);
       :commit;
     endif
   }
   stop
   @enduml

时序图（get_tag_by_name / add_tag）
===================================

.. uml::

   @startuml
   title 查询与新增标签时序
   actor Client
   participant "TagManager" as TM
   database "PostgreSQL" as PG

   == get_tag_by_name ==
   Client -> TM: get_tag_by_name(name)
   TM -> PG: SELECT Tag WHERE name = :name LIMIT 1
   PG --> TM: Tag | None
   TM -> Client: 返回 Tag | None

   == add_tag ==
   Client -> TM: add_tag(PostTagData)
   TM -> PG: MERGE Tag(name, definition)
   TM -> PG: COMMIT
   TM -> Client: 完成
   @enduml


