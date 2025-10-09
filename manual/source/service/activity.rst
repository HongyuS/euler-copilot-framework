############################
Activity 模块（限流与并发）
############################

.. currentmodule:: apps.services.activity

概述
====

``Activity`` 模块负责用户请求的限流与全局并发控制，提供以下能力：

- 单用户滑动窗口限流：限制单个用户在指定时间窗口内的请求数量
- 全局并发限制：控制系统同时执行的任务总数
- 活动状态管理：提供活跃任务的登记与释放
- 数据持久化：使用 PostgreSQL 持久化活动记录

核心常量
========

以下常量由 ``apps.constants`` 提供，可通过配置调整：

- ``MAX_CONCURRENT_TASKS``：全局同时运行任务上限（默认 30）
- ``SLIDE_WINDOW_QUESTION_COUNT``：滑动窗口内单用户最大请求数（默认 5）
- ``SLIDE_WINDOW_TIME``：滑动窗口时间（秒，默认 15）

数据模型
========

使用 ``SessionActivity`` 记录活跃行为：

- ``id``：主键 ID（自增）
- ``userSub``：用户实体 ID（外键关联）
- ``timestamp``：活动时间戳（UTC）

API 参考
========

Activity 类
-----------

.. autoclass:: Activity
   :members:
   :undoc-members:
   :show-inheritance:

设计说明
========

- 滑动窗口限流：统计用户在最近 ``SLIDE_WINDOW_TIME`` 秒内的请求数量，超过 ``SLIDE_WINDOW_QUESTION_COUNT`` 即判定限流。
- 全局并发控制：通过统计 ``SessionActivity`` 的记录数判断是否达到 ``MAX_CONCURRENT_TASKS`` 上限。
- 并发安全：依赖数据库事务保障登记与释放的原子性。
- 时间精度：所有时间戳使用 UTC。

注意事项
========

1. 在调用活跃登记前应先进行可用性检查。
2. 任务完成后需及时释放活跃记录以避免占用并发额度。
3. 合理调整常量以适配不同吞吐需求。



流程图（is_active）
===================

.. uml::

   @startuml
   title Activity.is_active 流程
   start
   :获取当前 UTC 时间;
   :开启数据库会话;
   :统计 userSub 在 [now - SLIDE_WINDOW_TIME, now] 的请求数;
   if (count >= SLIDE_WINDOW_QUESTION_COUNT?) then (是)
     :返回 True (达到限流);
     stop
   else (否)
     :统计当前活跃任务数量 current_active;
     if (current_active >= MAX_CONCURRENT_TASKS?) then (是)
       :返回 True (达到并发上限);
     else (否)
       :返回 False (可执行);
     endif
   endif
   stop
   @enduml


时序图（set_active/remove_active）
===================================

.. uml::

   @startuml
   title 活跃任务登记与释放时序
   actor Client
   participant "Activity" as Activity
   database "PostgreSQL" as PG

   == set_active ==
   Client -> Activity: set_active(user_sub)
   Activity -> PG: 查询当前活跃数量
   PG --> Activity: current_active
   alt 达到并发上限
     Activity -> Client: 抛出 ActivityError
   else 未达上限
     Activity -> PG: merge SessionActivity(userSub, timestamp)
     Activity -> PG: commit
     Activity -> Client: 完成
   end

   == remove_active ==
   Client -> Activity: remove_active(user_sub)
   Activity -> PG: delete SessionActivity where userSub=user_sub
   Activity -> PG: commit
   Activity -> Client: 完成

   @enduml
