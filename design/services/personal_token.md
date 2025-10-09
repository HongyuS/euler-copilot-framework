# 个人令牌（API Key）服务设计

本文档描述 Euler Copilot Framework 中与账号 API Key（Personal Token）相关的鉴权策略、核心流程、接口规范以及错误返回约定。实现参考：

- `apps/services/personal_token.py`：个人令牌生成、校验
- `apps/dependency/user.py`：请求依赖校验（`verify_personal_token`、`verify_session`）
- `apps/routers/auth.py`：重置个人令牌接口 `/api/auth/key`
- 使用举例：`apps/routers/user.py` 等路由均依赖 `verify_personal_token`

## 架构与职责

- 个人令牌用于对用户调用进行鉴权，是接口级依赖；受保护路由在鉴权通过后再处理请求。
- 生效范围与优先级约定：
  - 会话（Session）：仅在浏览器场景生效（前端 Web 应用）。
  - 个人令牌（API Key）：在客户端与 Shell 场景生效（CLI、Agent、集成脚本等）。
  - 二者不能组合使用；若请求同时携带，会优先以 API Key 进行鉴权并忽略会话态。
- 个人令牌的生成与更新由 `PersonalTokenManager.update_personal_token` 负责；校验由 `verify_personal_token` 委托 `PersonalTokenManager.get_user_by_personal_token` 完成。

## 流程图（重置 API Key）

```mermaid
flowchart TD
    A[客户端: POST /api/auth/key] --> B[依赖注入: verify_session]
    B --> C[依赖注入: verify_personal_token]
    C --> D[AuthRouter.change_personal_token]
    D --> E[PersonalTokenManager.update_personal_token]
    E -->|成功| F[DB: 更新 User.personalToken]
    F --> G[返回新 api_key]
    E -->|失败| H[记录异常并返回 500]
```

## 时序图（受保护资源访问）

```mermaid
sequenceDiagram
    participant Client
    participant Router as FastAPI Router
    participant Dep as Dependencies
    participant PTM as PersonalTokenManager
    participant DB

    Client->>Router: 调用受保护接口（携带 Authorization ）
    Router->>Dep: verify_session
    Dep-->>Router: 注入 request.state.session_id / user_sub（可选）
    Router->>Dep: verify_personal_token
    Dep->>PTM: get_user_by_personal_token(token)
    PTM->>DB: SELECT userSub WHERE personalToken == token
    DB-->>PTM: userSub 或 None
    PTM-->>Dep: userSub 或 None
    alt token 有效
        Dep-->>Router: 注入 request.state.user_sub
        Router-->>Client: 200 成功响应
    else token 无效
        Dep-->>Router: 抛出 401 Personal Token 无效
        Router-->>Client: 401 错误响应
    end
```

## 数据模型摘要

- 用户表 `User` 至少包含：`userSub`（用户唯一标识）、`personalToken`（个人令牌）。
- 个人令牌生成逻辑：`sha256(uuid4().hex)[:16]`（16 位十六进制字符串）。

## 接口规范

### 1) 重置个人令牌

- 路径：`POST /api/auth/key`
- 认证：依赖 `verify_session` 与 `verify_personal_token`
- 作用：为当前用户生成新的 API Key，并写入数据库，返回给客户端。

请求示例（当前实现中 Authorization 仅用于携带个人令牌；会话头可不传）：

```bash
curl -X POST \
  -H "Authorization: <Personal-Token>" \
  https://your-host/api/auth/key
```

成功响应（200）：

```json
{
  "code": 200,
  "message": "success",
  "result": {
    "api_key": "9f1a2b3c4d5e6f70"
  }
}
```

失败响应（500，示例）：

```json
{
  "code": 500,
  "message": "failed to update personal token",
  "result": {}
}
```

错误场景（401 未通过鉴权，示例）：

```json
{
  "detail": "Personal Token 无效"
}
```

### 2) 受保护资源的通用调用方式

- 多数路由（如 `GET /api/user`、`PUT /api/user/llm` 等）要求通过任一鉴权方式方可访问。
- 使用与优先级：
  - 客户端/Shell：仅携带 API Key；`Authorization: <Personal-Token>`。
  - 浏览器：由会话完成鉴权；`Authorization: Bearer <Session-ID>` 由前端/网关注入。
  - 若两者同时出现，以 API Key 优先，忽略会话态。

请求示例（以 `GET /api/user` 为例，客户端/Shell）：

```bash
curl -X GET \
  -H "Authorization: <Personal-Token>" \
  "https://your-host/api/user?page_size=10&page_num=1"
```

成功响应（节选）：

```json
{
  "code": 200,
  "message": "用户数据详细信息获取成功",
  "result": {
    "userInfoList": [
      { "userName": "alice", "userSub": "alice" }
    ],
    "total": 42
  }
}
```

## 安全与最佳实践

- 会话仅在浏览器场景生效，API Key 仅在客户端与 Shell 场景生效；不要同时携带，若同时携带则以 API Key 为准。
- 后端不回显旧密钥，仅在重置操作时返回新密钥一次；客户端需妥善保存。
- 个人令牌长度固定 16 位，可按需在前后端增加强度与轮换策略。
- 服务侧可结合访问频率限制与审计日志，及时发现异常使用。

## 关键实现参考

为避免直接引用代码，这里以自然语言描述关键逻辑：

- 个人令牌校验（路由依赖）
  - 从请求头读取 `Authorization`，将其作为个人令牌使用；若缺失则返回未授权错误。
  - 通过个人令牌查询对应的用户唯一标识；若查无此人则返回未授权错误。
  - 校验通过后，将用户唯一标识写入请求上下文，供后续处理使用。

- 重置个人令牌（POST /api/auth/key）
  - 在受保护路由中，由会话与个人令牌依赖共同保护；请求到达后，为当前用户生成新令牌。
- 生成方式为对随机 UUID 进行哈希处理并截取固定长度（16 位十六进制字符串）。
  - 将新令牌写入数据库并作为响应返回；若数据库更新失败，返回服务器错误。

- 令牌-用户映射与更新
  - “令牌查用户”：按“令牌等于用户表中的个人令牌字段”的条件检索，返回匹配到的用户标识；异常会被记录并视为查找失败。
  - “更新令牌”：按用户标识定位记录并写入新生成的令牌；更新异常会被记录并返回失败。
