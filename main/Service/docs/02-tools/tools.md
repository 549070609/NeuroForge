# 工具管理类 API

## GET `/api/v1/tools`

用途: 获取当前可用工具列表。

### 入参

- 无

### 出参

响应为数组 `ToolInfo[]`。

| 字段 | 类型 | 说明 |
|---|---|---|
| `name` | string | 工具名 |
| `description` | string | 工具描述 |
| `parameters` | object | 工具参数定义 |

示例响应:

```json
[
  {
    "name": "bash",
    "description": "Execute bash commands",
    "parameters": {
      "command": {
        "type": "string",
        "description": "Command to execute"
      }
    }
  }
]
```

### 状态码

- `200` 成功

### cURL

```bash
curl "$BASE_URL/api/v1/tools"
```

## POST `/api/v1/tools/{tool_name}/execute`

用途: 直接执行工具（当前为占位接口，未实现）。

### Path 参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `tool_name` | string | 是 | 工具名，例如 `bash` |

### Body 参数

请求体模型: `ExecuteToolRequest`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `tool_name` | string | 是 | 工具名（与 path 字段语义重复） |
| `parameters` | object | 是 | 工具参数 |

示例请求:

```json
{
  "tool_name": "bash",
  "parameters": {
    "command": "echo hello"
  }
}
```

### 出参

理论模型为 `ExecuteToolResponse`:

| 字段 | 类型 | 说明 |
|---|---|---|
| `tool_name` | string | 工具名 |
| `result` | any | 工具执行结果 |
| `error` | string/null | 错误信息 |

当前实现固定抛出:

```json
{
  "detail": "Direct tool execution not yet implemented"
}
```

### 状态码

- `501` 未实现
- `422` 请求体不合法

### cURL

```bash
curl -X POST "$BASE_URL/api/v1/tools/bash/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "bash",
    "parameters": {
      "command": "echo hello"
    }
  }'
```

## LLM 速读块

```yaml
- id: list_tools
  method: GET
  path: /api/v1/tools
  request: none
  response: ToolInfo[]
- id: execute_tool
  method: POST
  path: /api/v1/tools/{tool_name}/execute
  request: ExecuteToolRequest
  current_behavior: always_501
```
