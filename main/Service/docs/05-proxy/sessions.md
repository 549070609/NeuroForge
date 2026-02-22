# Proxy 会话类 API

前缀: `/api/v1/proxy`

## 数据模型

### SessionCreate

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `workspace_id` | string | 是 | 绑定工作空间 |
| `agent_id` | string | 是 | 会话使用的 Agent |
| `metadata` | object/null | 否 | 业务元数据 |

### SessionResponse

| 字段 | 类型 | 说明 |
|---|---|---|
| `session_id` | string | 会话 ID（典型 `sess-xxxxxxxxxxxx`） |
| `workspace_id` | string | 工作空间 ID |
| `agent_id` | string | Agent ID |
| `status` | string | 会话状态 |
| `message_count` | int | 消息条数 |
| `created_at` | string | 创建时间 |
| `updated_at` | string | 更新时间 |
| `metadata` | object | 元数据 |

## POST `/api/v1/proxy/sessions`

用途: 在指定工作空间创建会话。

### Body 示例

```json
{
  "workspace_id": "ws-payment",
  "agent_id": "plan",
  "metadata": {
    "ticket": "PAY-1024"
  }
}
```

### 出参

- `201`: `SessionResponse`
- `400`: 工作空间不存在或参数错误

### cURL

```bash
curl -X POST "$BASE_URL/api/v1/proxy/sessions" \
  -H "Content-Type: application/json" \
  -d '{
    "workspace_id":"ws-payment",
    "agent_id":"plan"
  }'
```

## GET `/api/v1/proxy/sessions`

用途: 列出会话，支持过滤。

### Query 参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `workspace_id` | string | 否 | 按工作空间过滤 |
| `agent_id` | string | 否 | 按 Agent 过滤 |

### 出参

`SessionListResponse`

| 字段 | 类型 | 说明 |
|---|---|---|
| `sessions` | SessionResponse[] | 会话列表 |
| `total` | int | 总数 |

### cURL

```bash
curl "$BASE_URL/api/v1/proxy/sessions?workspace_id=ws-payment&agent_id=plan"
```

## GET `/api/v1/proxy/sessions/{session_id}`

用途: 查询会话详情。

### Path 参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `session_id` | string | 是 | 会话 ID |

### 出参

- `200`: `SessionResponse`
- `404`: `{"detail":"Session not found: <session_id>"}`

### cURL

```bash
curl "$BASE_URL/api/v1/proxy/sessions/sess-1234567890ab"
```

## DELETE `/api/v1/proxy/sessions/{session_id}`

用途: 删除会话。

### 出参

成功:

```json
{
  "status": "ok",
  "message": "Session sess-1234567890ab deleted"
}
```

失败:

```json
{
  "detail": "Session not found: sess-1234567890ab"
}
```

### 状态码

- `200` 删除成功
- `404` 会话不存在

### cURL

```bash
curl -X DELETE "$BASE_URL/api/v1/proxy/sessions/sess-1234567890ab"
```

## LLM 速读块

```yaml
- id: create_session
  method: POST
  path: /api/v1/proxy/sessions
  request: SessionCreate
  response: SessionResponse
  status_code: 201
- id: list_sessions
  method: GET
  path: /api/v1/proxy/sessions
  query: [workspace_id?, agent_id?]
  response: SessionListResponse
```
