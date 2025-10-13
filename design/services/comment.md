# Comment Module Documentation

## 模块概述

评论模块（Comment Module）负责处理用户对问答记录（Record）的反馈功能，包括点赞（Like）、点踩（Dislike）以及详细的反馈意见收集。该模块是系统用户体验反馈机制的核心组件。

## 目录结构

```text
apps/
├── routers/
│   └── comment.py          # FastAPI路由层，处理HTTP请求
├── services/
│   └── comment.py          # 业务逻辑层，评论管理器
├── models/
│   └── comment.py          # 数据库模型定义
└── schemas/
    ├── comment.py          # 请求数据模型
    └── record.py           # 记录相关数据模型（包含评论）
```

## 核心组件

### 1. 数据模型层 (models/comment.py)

#### Comment Table Schema

| 字段名 | 类型 | 说明 | 约束 |
|--------|------|------|------|
| id | BigInteger | 主键ID | Primary Key, Auto Increment |
| recordId | UUID | 问答对ID | Foreign Key → framework_record.id, Indexed |
| userSub | String(50) | 用户标识 | Foreign Key → framework_user.userSub |
| commentType | Enum(CommentType) | 评论类型 | Not Null |
| feedbackType | ARRAY(String) | 投诉类别列表 | Not Null |
| feedbackLink | String(1000) | 投诉相关链接 | Not Null |
| feedbackContent | String(1000) | 投诉详细内容 | Not Null |
| createdAt | DateTime(TZ) | 创建时间 | Not Null, Default: UTC Now |

#### CommentType Enum

```python
class CommentType(str, PyEnum):
    LIKE = "liked"      # 点赞
    DISLIKE = "disliked"  # 点踩
    NONE = "none"       # 无评论
```

### 2. 业务逻辑层 (services/comment.py)

#### CommentManager

提供评论的核心业务逻辑操作：

- **query_comment(record_id: str)**: 根据问答ID查询评论
- **update_comment(record_id: str, data: RecordComment, user_sub: str)**: 创建或更新评论

### 3. 路由层 (routers/comment.py)

#### API Endpoint

- **POST /api/comment**: 添加或更新评论
  - 认证要求: Session验证 + Personal Token验证
  - 请求体: AddCommentData
  - 响应: ResponseData

### 4. 数据传输对象 (schemas)

#### AddCommentData (请求模型)

```python
{
    "record_id": str,                    # 问答记录ID
    "comment": CommentType,              # 评论类型 (liked/disliked/none)
    "dislike_reason": str,               # 点踩原因 (分号分隔, max 200字符)
    "reason_link": str,                  # 相关链接 (max 200字符)
    "reason_description": str            # 详细描述 (max 500字符)
}
```

#### RecordComment (内部数据模型)

```python
{
    "comment": CommentType,              # 评论类型
    "feedback_type": list[str],          # 反馈类型列表 (别名: dislike_reason)
    "feedback_link": str,                # 反馈链接 (别名: reason_link)
    "feedback_content": str,             # 反馈内容 (别名: reason_description)
    "feedback_time": float               # 反馈时间戳
}
```

## 架构设计

### 系统架构图

```mermaid
graph TB
    subgraph "Client Layer"
        Client[前端客户端]
    end

    subgraph "API Layer"
        Router[FastAPI Router<br/>routers/comment.py]
        Auth1[Session验证]
        Auth2[Token验证]
    end

    subgraph "Service Layer"
        Manager[CommentManager<br/>services/comment.py]
    end

    subgraph "Data Layer"
        Model[Comment Model<br/>models/comment.py]
        DB[(PostgreSQL Database)]
    end

    subgraph "Schema Layer"
        Schema1[AddCommentData]
        Schema2[RecordComment]
    end

    Client -->|HTTP POST| Router
    Router -->|依赖注入| Auth1
    Router -->|依赖注入| Auth2
    Router -->|数据验证| Schema1
    Router -->|调用业务逻辑| Manager
    Manager -->|数据转换| Schema2
    Manager -->|ORM操作| Model
    Model -->|SQLAlchemy| DB
```

### 数据流程图

```mermaid
flowchart TD
    Start([用户提交评论]) --> Validate{数据验证}
    Validate -->|验证失败| Error1[返回400错误]
    Validate -->|验证成功| Auth{身份认证}

    Auth -->|认证失败| Error2[返回401错误]
    Auth -->|认证成功| ParseData[解析dislike_reason<br/>分号分隔转列表]

    ParseData --> CreateDTO[创建RecordComment对象]
    CreateDTO --> QueryDB{查询数据库<br/>记录是否存在?}

    QueryDB -->|存在| Update[更新现有记录<br/>commentType<br/>feedbackType<br/>feedbackLink<br/>feedbackContent]
    QueryDB -->|不存在| Create[创建新记录<br/>包含recordId<br/>userSub等字段]

    Update --> Commit[提交事务]
    Create --> Merge[Merge操作]
    Merge --> Commit

    Commit --> Success{提交成功?}
    Success -->|失败| Error3[返回400错误]
    Success -->|成功| Return[返回200 OK]

    Error1 --> End([结束])
    Error2 --> End
    Error3 --> End
    Return --> End
```

## 时序图

### 添加评论完整流程

```mermaid
sequenceDiagram
    actor User as 用户
    participant Client as 前端客户端
    participant Router as FastAPI Router
    participant AuthMiddleware as 认证中间件
    participant Manager as CommentManager
    participant Session as DB Session
    participant DB as PostgreSQL

    User->>Client: 点赞/点踩并提交反馈
    Client->>Router: POST /api/comment<br/>{record_id, comment, ...}

    activate Router
    Router->>AuthMiddleware: verify_session()
    activate AuthMiddleware
    AuthMiddleware-->>Router: session验证结果
    deactivate AuthMiddleware

    Router->>AuthMiddleware: verify_personal_token()
    activate AuthMiddleware
    AuthMiddleware-->>Router: token验证结果
    deactivate AuthMiddleware

    Router->>Router: 解析dislike_reason<br/>分号分隔 → list
    Router->>Router: 创建RecordComment对象<br/>设置feedback_time

    Router->>Manager: update_comment(record_id, data, user_sub)
    activate Manager

    Manager->>Session: 创建异步会话
    activate Session

    Manager->>DB: SELECT * FROM framework_comment<br/>WHERE recordId = ?
    activate DB
    DB-->>Manager: 查询结果
    deactivate DB

    alt 记录存在
        Manager->>Manager: 更新现有对象字段<br/>commentType, feedbackType等
    else 记录不存在
        Manager->>Manager: 创建新Comment对象
        Manager->>Session: merge(comment_info)
    end

    Manager->>Session: commit()
    Session->>DB: 提交事务
    activate DB
    DB-->>Session: 提交成功
    deactivate DB

    Session-->>Manager: 完成
    deactivate Session
    Manager-->>Router: None (成功)
    deactivate Manager

    Router->>Client: 200 OK<br/>{code: 200, message: "success"}
    deactivate Router
    Client->>User: 显示反馈成功
```

### 查询评论流程

```mermaid
sequenceDiagram
    participant Service as 业务服务
    participant Manager as CommentManager
    participant Session as DB Session
    participant DB as PostgreSQL

    Service->>Manager: query_comment(record_id)
    activate Manager

    Manager->>Session: 创建异步会话
    activate Session

    Manager->>DB: SELECT * FROM framework_comment<br/>WHERE recordId = UUID(record_id)
    activate DB
    DB-->>Manager: 查询结果
    deactivate DB

    alt 记录存在
        Manager->>Manager: 构建RecordComment对象<br/>映射字段名称<br/>转换时间戳
        Manager-->>Service: RecordComment对象
    else 记录不存在
        Manager-->>Service: None
    end

    deactivate Session
    deactivate Manager
```

## 状态图

### 评论状态转换

```mermaid
stateDiagram-v2
    [*] --> NONE: 创建问答记录

    NONE --> LIKE: 用户点赞
    NONE --> DISLIKE: 用户点踩

    LIKE --> DISLIKE: 改为点踩
    LIKE --> NONE: 取消点赞

    DISLIKE --> LIKE: 改为点赞
    DISLIKE --> NONE: 取消点踩

    NONE --> [*]
    LIKE --> [*]
    DISLIKE --> [*]

    note right of DISLIKE
        点踩时需要提供:
        - feedbackType (类别列表)
        - feedbackLink (相关链接)
        - feedbackContent (详细说明)
    end note
```

## 类图

```mermaid
classDiagram
    class Comment {
        +int id
        +UUID recordId
        +str userSub
        +CommentType commentType
        +list~str~ feedbackType
        +str feedbackLink
        +str feedbackContent
        +datetime createdAt
    }

    class CommentType {
        <<enumeration>>
        LIKE
        DISLIKE
        NONE
    }

    class AddCommentData {
        +str record_id
        +CommentType comment
        +str dislike_reason
        +str reason_link
        +str reason_description
        +model_validate()
    }

    class RecordComment {
        +CommentType comment
        +list~str~ feedback_type
        +str feedback_link
        +str feedback_content
        +float feedback_time
    }

    class CommentManager {
        +query_comment(record_id)$ RecordComment|None
        +update_comment(record_id, data, user_sub)$ None
    }

    class Router {
        +add_comment(request, post_body) JSONResponse
    }

    Comment --> CommentType : uses
    AddCommentData --> CommentType : uses
    RecordComment --> CommentType : uses
    Router --> AddCommentData : validates
    Router --> CommentManager : calls
    CommentManager --> RecordComment : transforms
    CommentManager --> Comment : operates
```

## 数据库ER图

```mermaid
erDiagram
    FRAMEWORK_USER ||--o{ FRAMEWORK_COMMENT : creates
    FRAMEWORK_RECORD ||--o| FRAMEWORK_COMMENT : has

    FRAMEWORK_USER {
        string userSub PK
        string userName
        datetime createdAt
    }

    FRAMEWORK_RECORD {
        uuid id PK
        uuid conversationId
        string userSub FK
        string content
        datetime createdAt
    }

    FRAMEWORK_COMMENT {
        bigint id PK
        uuid recordId FK
        string userSub FK
        enum commentType
        array feedbackType
        string feedbackLink
        string feedbackContent
        datetime createdAt
    }
```

## 核心业务逻辑

### 1. 评论创建/更新逻辑

评论模块采用幂等性设计，支持对同一问答记录进行多次评论更新。核心流程如下：

#### 步骤一：查询现有评论

系统首先根据问答记录ID查询数据库中是否已存在对应的评论记录。

#### 步骤二：判断操作类型

- 如果记录已存在，则执行更新操作，修改现有记录的评论类型、反馈类型、反馈链接和反馈内容
- 如果记录不存在，则创建新的评论记录，包含问答记录ID、用户标识、评论类型等完整信息

#### 步骤三：数据持久化

使用数据库事务确保数据一致性，通过SQLAlchemy的merge操作实现UPSERT语义，自动处理插入或更新逻辑。

### 2. 数据转换逻辑

#### API → Service 层转换

路由层接收到前端请求后，需要进行数据格式转换：

- 将分号分隔的字符串格式的点踩原因转换为数组格式
- 将API字段名映射为内部数据模型字段名
- 生成当前时间戳作为反馈时间

#### Service → Model 层映射

业务逻辑层将处理后的数据映射到数据库模型：

- 评论类型字段直接映射
- 反馈类型列表映射为PostgreSQL数组类型
- 反馈链接和反馈内容直接映射
- 用户标识和记录ID保持原有格式

#### Model → Schema 层查询映射

查询操作时将数据库模型数据转换为API响应格式：

- 数据库字段名转换为前端友好的字段名
- 时间戳格式转换，将数据库的datetime对象转换为Unix时间戳
- 数组类型数据保持原有格式返回给前端

## 接口文档

### POST /api/comment

添加或更新评论

#### 认证要求

- Session验证 (verify_session)
- Personal Token验证 (verify_personal_token)

#### 请求

**Headers:**

```http
Content-Type: application/json
Authorization: Bearer <token>
Cookie: session=<session_id>
```

**Body:**

```json
{
    "record_id": "550e8400-e29b-41d4-a716-446655440000",
    "comment": "disliked",
    "dislike_reason": "答非所问;信息不准确;",
    "reason_link": "https://example.com/issue/123",
    "reason_description": "回答内容与问题不符，建议补充相关文档引用。"
}
```

**字段说明:**

| 字段 | 类型 | 必填 | 说明 | 限制 |
|------|------|------|------|------|
| record_id | string | 是 | 问答记录UUID | UUID格式 |
| comment | string | 是 | 评论类型 | "liked", "disliked", "none" |
| dislike_reason | string | 否 | 点踩原因 | 分号分隔，最长200字符 |
| reason_link | string | 否 | 相关链接 | 最长200字符 |
| reason_description | string | 否 | 详细描述 | 最长500字符 |

#### 响应

**成功 (200 OK):**

```json
{
    "code": 200,
    "message": "success",
    "result": {}
}
```

**失败 (400 Bad Request):**

```json
{
    "code": 400,
    "message": "record_id not found",
    "result": {}
}
```

**失败 (401 Unauthorized):**

```json
{
    "code": 401,
    "message": "Authentication failed"
}
```

#### 示例

**cURL:**

```bash
curl -X POST "http://localhost:8000/api/comment" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGc..." \
  --cookie "session=abc123..." \
  -d '{
    "record_id": "550e8400-e29b-41d4-a716-446655440000",
    "comment": "liked",
    "dislike_reason": "",
    "reason_link": "",
    "reason_description": ""
  }'
```

**Python:**

```python
import requests

response = requests.post(
    "http://localhost:8000/api/comment",
    json={
        "record_id": "550e8400-e29b-41d4-a716-446655440000",
        "comment": "disliked",
        "dislike_reason": "答非所问;信息不准确;",
        "reason_link": "https://example.com/issue/123",
        "reason_description": "回答内容与问题不符"
    },
    headers={"Authorization": "Bearer <token>"},
    cookies={"session": "<session_id>"}
)
```

## 关键特性

### 1. 幂等性设计

- 同一个 record_id 的评论支持多次更新
- 使用 SQLAlchemy 的 `merge` 操作实现 UPSERT 语义
- 自动识别创建或更新操作

### 2. 数据完整性

- recordId 外键约束 → framework_record.id
- userSub 外键约束 → framework_user.userSub
- 索引优化：recordId 字段建立索引提高查询性能

### 3. 字段别名映射

使用 Pydantic 的 `Field(alias=...)` 实现前端友好的字段命名：

| 内部字段 | API别名 |
|----------|---------|
| feedback_type | dislike_reason |
| feedback_link | reason_link |
| feedback_content | reason_description |

### 4. 时间处理

- 数据库存储：`datetime` 对象，带时区（UTC）
- API传输：`float` 类型的 Unix 时间戳（秒，保留3位小数）

### 5. 数组字段处理

- API输入：分号分隔的字符串 `"reason1;reason2;"`
- 数据转换：`split(";")[:-1]` → `["reason1", "reason2"]`
- 数据库存储：PostgreSQL ARRAY 类型

## 错误处理

### 常见错误场景

| 错误场景 | HTTP状态码 | 处理方式 |
|----------|-----------|----------|
| Session验证失败 | 401 | 依赖注入层拦截 |
| Token验证失败 | 401 | 依赖注入层拦截 |
| record_id不存在 | 400 | 业务逻辑层返回None |
| UUID格式错误 | 400 | Pydantic验证失败 |
| 字段长度超限 | 422 | Pydantic验证失败 |
| 数据库连接失败 | 500 | 异常传播至错误处理中间件 |
| 外键约束违反 | 500 | 数据库异常 |

### 异常传播链

```mermaid
flowchart LR
    A[Router Layer] --> B{验证异常?}
    B -->|是| C[422 Unprocessable Entity]
    B -->|否| D[Service Layer]
    D --> E{业务异常?}
    E -->|是| F[400 Bad Request]
    E -->|否| G[Database Layer]
    G --> H{DB异常?}
    H -->|是| I[500 Internal Server Error]
    H -->|否| J[200 OK]
```

## 性能优化

### 1. 数据库索引

```sql
CREATE INDEX idx_comment_record_id ON framework_comment(recordId);
```

- 优化基于 recordId 的查询性能
- 支持快速定位单个记录的评论

### 2. 异步IO

- 使用 SQLAlchemy 异步会话：`async with postgres.session()`
- 非阻塞数据库操作
- 提高并发处理能力

### 3. 连接池管理

- PostgreSQL 连接池复用
- 避免频繁建立/关闭连接的开销

### 4. 查询优化

```python
# 使用 one_or_none() 替代 all()[0]
result = (await session.scalars(
    select(Comment).where(Comment.recordId == uuid.UUID(record_id))
)).one_or_none()
```

- 提前终止查询（最多返回1条）
- 减少数据传输量

## 安全考虑

### 1. 认证与授权

- **双重认证**：Session + Personal Token
- **用户隔离**：userSub 关联确保数据隔离
- **依赖注入**：在路由层统一进行身份验证

### 2. 输入验证

- **字段长度限制**：
  - dislike_reason: 200字符
  - reason_link: 200字符
  - reason_description: 500字符
- **类型校验**：Pydantic自动验证数据类型
- **枚举约束**：CommentType限定为三个固定值

### 3. SQL注入防护

- 使用 SQLAlchemy ORM
- 参数化查询
- 无原生SQL拼接

### 4. 数据完整性

- 外键约束防止孤立记录
- 事务保证原子性操作
- NOT NULL约束防止空值

## 扩展性设计

### 1. 评论类型扩展

当前支持三种类型，如需扩展：

```python
class CommentType(str, PyEnum):
    LIKE = "liked"
    DISLIKE = "disliked"
    NONE = "none"
    # 未来扩展
    REPORT = "reported"      # 举报
    FAVORITE = "favorited"   # 收藏
```

### 2. 反馈类型扩展

feedbackType 使用数组类型，支持多选和动态扩展：

```python
# 前端定义的反馈类型选项
FEEDBACK_OPTIONS = [
    "答非所问",
    "信息不准确",
    "内容不完整",
    "格式混乱",
    "其他问题"
]
```

### 3. 多语言支持

在 RecordComment 中添加语言字段：

```python
class RecordComment(BaseModel):
    comment: CommentType
    language: str = "zh-CN"  # 新增字段
    # ... 其他字段
```

### 4. 统计分析扩展

可基于现有数据进行扩展：

- 点赞率统计
- 点踩原因分布
- 时间趋势分析
- 用户反馈热点

## 部署注意事项

### 1. 数据库迁移

使用 Alembic 进行数据库版本管理：

```bash
# 生成迁移脚本
alembic revision --autogenerate -m "create comment table"

# 执行迁移
alembic upgrade head
```

### 2. 环境变量配置

```bash
# PostgreSQL 连接配置
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname

# 日志级别
LOG_LEVEL=INFO
```

### 3. 性能调优

```python
# 连接池配置
pool_size = 20          # 连接池大小
max_overflow = 10       # 最大溢出连接数
pool_timeout = 30       # 连接超时时间
pool_recycle = 3600     # 连接回收时间
```

## 未来优化方向

### 1. 缓存策略

- Redis 缓存热点评论数据
- 减少数据库查询压力
- 设置合理的缓存过期时间

### 2. 批量操作支持

- 支持批量查询评论
- 支持批量更新评论
- 减少网络往返次数

### 3. 评论审核机制

- 敏感词过滤
- 内容审核工作流
- 人工复审接口

### 4. 数据分析增强

- 实时统计面板
- 评论情感分析
- 用户行为画像

## 常见问题 (FAQ)

### Q1: 为什么使用 merge 而不是 add？

**A:** `merge` 操作实现了 UPSERT 语义，可以自动判断是插入还是更新，简化了业务逻辑。

### Q2: dislike_reason 为什么使用分号分隔？

**A:** 前端传递多个原因时使用分号分隔的字符串格式，后端进行split转换为数组存储到数据库。

### Q3: 为什么 update_comment 返回 None？

**A:** 当前设计中更新操作无需返回值，失败时通过异常处理。未来可以改为返回布尔值或更新后的对象。

### Q4: 如何防止恶意刷评论？

**A:**

- 身份认证确保用户真实性
- 可增加频率限制（Rate Limiting）
- 可增加同一用户对同一记录的评论次数限制

### Q5: 评论数据如何归档？

**A:**

- 可按时间分区存储历史数据
- 定期将旧数据迁移到冷存储
- 保留索引供查询分析使用

## 参考资料

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Async Documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Pydantic V2 Documentation](https://docs.pydantic.dev/latest/)
- [PostgreSQL ARRAY Types](https://www.postgresql.org/docs/current/arrays.html)

## 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| 1.0.0 | 2025-10-13 | 初始版本，完成基础评论功能 |

---

**文档维护者**: Euler Copilot Framework Team
**最后更新**: 2025-10-13
