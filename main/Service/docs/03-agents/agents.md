# Agent 管理与执行类 API

## 数据模型

### AgentInfoResponse

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | Agent ID |
| `name` | string | Agent 名称 |
| `namespace` | string | 命名空间 |
| `origin` | string | 来源类型 |
| `description` | string | 描述 |
| `tags` | string[] | 标签 |
| `category` | string | 分类 |
| `is_readonly` | bool | 是否只读 |
| `max_concurrent` | int | 最大并发 |
| `tools` | string[] | 允许工具 |
| `denied_tools` | string[] | 禁止工具 |

### AgentExecuteRequest

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `task` | string | 是 | 任务描述 |
| `context` | object/null | 否 | 额外上下文 |
| `namespace` | string/null | 否 | 命名空间（当前实现未直接使用） |
| `options` | object/null | 否 | 执行选项 |

### AgentExecuteResponse

| 字段 | 类型 | 说明 |
|---|---|---|
| `agent_id` | string | 执行的 Agent ID |
| `status` | string | 执行状态 |
| `result` | string/null | 执行结果 |
| `plan_id` | string/null | 生成的计划 ID（若有） |
| `error` | string/null | 错误信息 |
| `started_at` | datetime | 开始时间 |
| `completed_at` | datetime/null | 完成时间 |

## GET `/api/v1/agents`

用途: 列出 Agent。

### Query 参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `namespace` | string | 否 | 按命名空间过滤 |
| `tags` | string | 否 | 标签过滤，逗号分隔，例如 `plan,code` |

### 出参

`AgentListResponse`

| 字段 | 类型 | 说明 |
|---|---|---|
| `agents` | AgentInfoResponse[] | Agent 列表 |
| `total` | int | 总数 |
| `namespaces` | string[] | 命名空间列表 |

### cURL

```bash
curl "$BASE_URL/api/v1/agents?namespace=default&tags=plan,code"
```

## GET `/api/v1/agents/stats`

用途: Agent 统计信息。

### 出参

`AgentStatsResponse`

| 字段 | 类型 | 说明 |
|---|---|---|
| `total_agents` | int | Agent 总数 |
| `total_namespaces` | int | 命名空间总数 |
| `by_origin` | object | 按来源统计 |
| `namespaces` | string[] | 命名空间列表 |

### cURL

```bash
curl "$BASE_URL/api/v1/agents/stats"
```

## GET `/api/v1/agents/namespaces`

用途: 命名空间列表及每个命名空间内 Agent。

### 出参

`NamespaceListResponse`

| 字段 | 类型 | 说明 |
|---|---|---|
| `namespaces` | NamespaceInfo[] | 命名空间详情 |
| `total` | int | 总数 |

`NamespaceInfo`:

| 字段 | 类型 | 说明 |
|---|---|---|
| `name` | string | 命名空间名称 |
| `agent_count` | int | Agent 数量 |
| `agents` | string[] | Agent ID 列表 |

### cURL

```bash
curl "$BASE_URL/api/v1/agents/namespaces"
```

## GET `/api/v1/agents/refresh`

用途: 刷新 Agent 目录缓存。

### 出参

```json
{
  "status": "ok",
  "message": "Agent directory refreshed"
}
```

### cURL

```bash
curl "$BASE_URL/api/v1/agents/refresh"
```

## GET `/api/v1/agents/{agent_id}`

用途: 查询单个 Agent 详情。

### Path 参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `agent_id` | string | 是 | Agent ID |

### 出参

- `200`: `AgentInfoResponse`
- `404`: `{"detail":"Agent not found: <agent_id>"}`

### cURL

```bash
curl "$BASE_URL/api/v1/agents/plan"
```

## POST `/api/v1/agents/{agent_id}/execute`

用途: 执行 Agent（当前为模拟执行逻辑，后续可接入真实执行引擎）。

### Path 参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `agent_id` | string | 是 | 要执行的 Agent ID |

### Body 参数

`AgentExecuteRequest`，示例:

```json
{
  "task": "为支付系统设计重试机制",
  "context": {
    "repo": "main/payment",
    "env": "staging"
  },
  "options": {
    "max_steps": 5
  }
}
```

### 出参

`AgentExecuteResponse`，示例:

```json
{
  "agent_id": "plan",
  "status": "completed",
  "result": "Plan created successfully with 3 steps",
  "plan_id": "plan-20260221-abc123",
  "error": null,
  "started_at": "2026-02-21T15:10:00.000000",
  "completed_at": "2026-02-21T15:10:01.000000"
}
```

### 状态码

- `200` 执行完成
- `404` Agent 不存在
- `422` 请求体验证失败

### cURL

```bash
curl -X POST "$BASE_URL/api/v1/agents/plan/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "生成一份 API 重构计划",
    "context": {"module":"gateway"},
    "options": {"format":"markdown"}
  }'
```

## LLM 速读块

```yaml
- id: list_agents
  method: GET
  path: /api/v1/agents
  query: [namespace?, tags?]
  response: AgentListResponse
- id: get_agent
  method: GET
  path: /api/v1/agents/{agent_id}
  response: AgentInfoResponse
  errors: [404]
- id: execute_agent
  method: POST
  path: /api/v1/agents/{agent_id}/execute
  request: AgentExecuteRequest
  response: AgentExecuteResponse
```
