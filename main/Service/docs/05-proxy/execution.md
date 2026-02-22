# Proxy 执行与流式类 API

前缀: `/api/v1/proxy`

## 数据模型

### ProxyExecuteRequest

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `session_id` | string | 是 | 会话 ID |
| `prompt` | string | 是 | 用户输入 |
| `context` | object/null | 否 | 执行上下文 |

### ProxyExecuteResponse

| 字段 | 类型 | 说明 |
|---|---|---|
| `session_id` | string | 会话 ID |
| `success` | bool | 是否成功 |
| `output` | string | 输出文本 |
| `error` | string/null | 错误信息 |
| `iterations` | int | 迭代次数 |
| `metadata` | object | 扩展信息 |

### ProxyStreamEvent

| 字段 | 类型 | 说明 |
|---|---|---|
| `type` | enum | `stream`/`tool_start`/`tool_result`/`complete`/`error` |
| `event` | any/null | 流事件数据 |
| `tool_name` | string/null | 工具名（tool_start） |
| `tool_id` | string/null | 工具调用 ID（tool_start） |
| `result` | string/null | 工具结果（tool_result） |
| `text` | string/null | 最终文本（complete） |
| `message` | string/null | 错误信息（error） |

## POST `/api/v1/proxy/execute`

用途: 同步执行 Agent。

### Body 示例

```json
{
  "session_id": "sess-1234567890ab",
  "prompt": "请总结最近一次发布变更",
  "context": {
    "repo": "main/service"
  }
}
```

### 出参

`ProxyExecuteResponse` 示例:

```json
{
  "session_id": "sess-1234567890ab",
  "success": true,
  "output": "已完成总结...",
  "error": null,
  "iterations": 3,
  "metadata": {
    "model": "claude-sonnet-4-20250514"
  }
}
```

### 状态码

- `200` 成功返回
- `400` 会话不存在或参数错误
- `422` 请求体验证失败

### cURL

```bash
curl -X POST "$BASE_URL/api/v1/proxy/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id":"sess-1234567890ab",
    "prompt":"分析当前接口错误率升高原因"
  }'
```

## POST `/api/v1/proxy/execute/stream`

用途: 流式执行 Agent，返回 SSE。

### 请求体

同 `ProxyExecuteRequest`。

### 响应格式

- `Content-Type`: `text/event-stream`
- 每个事件一行 `data: <json>`

示例事件:

```text
data: {"type":"stream","event":{"delta":"正在分析..."}}

data: {"type":"tool_start","tool_name":"read","tool_id":"tool-1"}

data: {"type":"tool_result","result":"读取成功"}

data: {"type":"complete","text":"最终结果"}
```

### cURL

```bash
curl -N -X POST "$BASE_URL/api/v1/proxy/execute/stream" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id":"sess-1234567890ab",
    "prompt":"实时输出分析过程"
  }'
```

## GET `/api/v1/proxy/stats`

用途: 查询 Proxy 服务统计。

### 出参

`ProxyStatsResponse`

| 字段 | 类型 | 说明 |
|---|---|---|
| `workspaces` | object | 工作空间统计 |
| `sessions` | object | 会话统计 |
| `executor_cache_size` | int | 执行器缓存数量 |

示例:

```json
{
  "workspaces": {
    "total_workspaces": 1
  },
  "sessions": {
    "total_sessions": 2,
    "by_status": {
      "active": 2
    }
  },
  "executor_cache_size": 2
}
```

### cURL

```bash
curl "$BASE_URL/api/v1/proxy/stats"
```

## LLM 速读块

```yaml
- id: proxy_execute
  method: POST
  path: /api/v1/proxy/execute
  request: ProxyExecuteRequest
  response: ProxyExecuteResponse
- id: proxy_execute_stream
  method: POST
  path: /api/v1/proxy/execute/stream
  request: ProxyExecuteRequest
  response: text/event-stream(ProxyStreamEvent)
- id: proxy_stats
  method: GET
  path: /api/v1/proxy/stats
  response: ProxyStatsResponse
```
