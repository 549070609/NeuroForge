# Service API 全量总览（单文件）

生成时间: 2026-02-21 23:09:45
来源目录: main/Service/docs

## 目录

1. README.md
2. 00-common\api-conventions.md
3. 00-common\llm-adapter.md
4. 01-health\health-root.md
5. 02-tools\tools.md
6. 03-agents\agents.md
7. 04-plans\plans.md
8. 05-proxy\workspaces.md
9. 05-proxy\sessions.md
10. 05-proxy\execution.md
11. 99-llm\endpoint-catalog.md

---

## README.md

# Service API 文档（按类型分类）

本文档基于 `main/Service/gateway/routes`、`main/Service/schemas`、`main/Service/services` 当前实现整理。

## 目录结构

```text
docs/
├─ 00-common/
│  ├─ api-conventions.md
│  └─ llm-adapter.md
├─ 01-health/
│  └─ health-root.md
├─ 02-tools/
│  └─ tools.md
├─ 03-agents/
│  └─ agents.md
├─ 04-plans/
│  └─ plans.md
├─ 05-proxy/
│  ├─ workspaces.md
│  ├─ sessions.md
│  └─ execution.md
└─ 99-llm/
   └─ endpoint-catalog.md
```

## API 类型分类

1. 基础与健康类: `/`、`/health`
2. 工具管理类: `/api/v1/tools*`
3. Agent 管理与执行类: `/api/v1/agents*`
4. Plan 管理类: `/api/v1/plans*`
5. Proxy 工作空间类: `/api/v1/proxy/workspaces*`
6. Proxy 会话类: `/api/v1/proxy/sessions*`
7. Proxy 执行与流式类: `/api/v1/proxy/execute*`
8. 统计类: `/api/v1/agents/stats`、`/api/v1/plans/stats`、`/api/v1/proxy/stats`

## 快速开始

```bash
export BASE_URL="http://localhost:8000"
curl "$BASE_URL/health"
```

Windows PowerShell:

```powershell
$env:BASE_URL = "http://localhost:8000"
curl "$env:BASE_URL/health"
```

## LLM 适配入口

- 通用规范: `00-common/llm-adapter.md`
- 机读端点目录: `99-llm/endpoint-catalog.md`

---

## 00-common\api-conventions.md

# 通用约定

## 基础信息

- Base URL: `http://{host}:{port}`
- 默认端口: `8000`
- API 前缀: `/api/v1`（健康检查和根路径除外）
- Content-Type: `application/json`（SSE 接口除外）

## 鉴权与限流

- 代码中存在鉴权中间件与限流中间件配置项:
  - API Key Header: `X-API-Key`
  - 环境变量: `SERVICE_API_KEY`
  - 限流配置: `SERVICE_RATE_LIMIT_*`
- 当前 `create_app()` 默认仅挂载 CORS 中间件，未默认挂载鉴权/限流中间件。
- 如果后续挂载鉴权中间件，请在请求头中传入:

```http
X-API-Key: <your-api-key>
```

## 通用错误返回

大多数业务错误由 `HTTPException` 返回，格式通常为:

```json
{
  "detail": "error message"
}
```

常见状态码:

- `200` 请求成功
- `201` 资源创建成功
- `400` 业务参数错误（如工作区不存在）
- `404` 资源不存在
- `422` 请求体验证失败（字段缺失或类型错误）
- `429` 限流（启用限流中间件后）
- `501` 接口未实现
- `503` 服务未可用（如 Proxy 服务未初始化）

## 请求示例模板

```bash
curl -X POST "$BASE_URL/api/v1/xxx" \
  -H "Content-Type: application/json" \
  -d '{"key":"value"}'
```

## 响应时间字段

- 多数时间字段为 ISO-8601 字符串，例如:
  - `"2026-02-21T14:00:00.123456"`
  - `"2026-02-21T14:00:00.123456Z"`

---

## 00-common\llm-adapter.md

# LLM 阅读适配规范

## 目标

让大模型在最少上下文下完成:

1. 快速定位接口
2. 生成正确请求体
3. 解析关键响应字段
4. 处理常见错误分支

## 推荐读取顺序

1. `99-llm/endpoint-catalog.md` 获取路由全量映射
2. 再跳转到对应分类文档查看字段级说明和 cURL
3. 优先读取每个接口的 `入参`、`出参`、`错误码`

## 字段对齐策略

- 优先使用 `schemas/*.py` 中的字段名作为唯一真值
- `path` 参数与 `body` 同名字段同时存在时，优先使用 `path` 参数
- `optional` 字段仅在有值时传递，减少噪声

## 输出约束（给大模型）

- 生成请求时保持最小必要字段:
  - 只传 `required + 当前任务确实需要的 optional`
- 解析响应时优先提取:
  - 标识字段（`id`、`session_id`、`plan_id`）
  - 状态字段（`status`、`success`）
  - 错误字段（`error`、`detail`）

## SSE 解析规范

`/api/v1/proxy/execute/stream` 返回 `text/event-stream`，每条消息格式:

```text
data: {"type":"...","...":"..."}
```

建议按 `type` 分流处理:

- `stream`: 增量内容
- `tool_start`: 工具开始
- `tool_result`: 工具结果
- `complete`: 最终文本
- `error`: 错误消息

## 低歧义提示模板

```text
请按以下顺序输出：
1) 目标接口 method + path
2) 最小请求 JSON
3) 关键响应字段提取规则
4) 非 2xx 时处理策略
```

---

## 01-health\health-root.md

# 基础与健康类 API

## GET `/`

用途: 服务入口信息。

### 入参

- 无

### 出参

| 字段 | 类型 | 说明 |
|---|---|---|
| `message` | string | 固定为服务名 |
| `docs` | string | 文档地址，通常为 `/docs` |

示例响应:

```json
{
  "message": "Service Layer",
  "docs": "/docs"
}
```

### cURL

```bash
curl "$BASE_URL/"
```

## GET `/health`

用途: 健康检查。

### 入参

- 无

### 出参

| 字段 | 类型 | 说明 |
|---|---|---|
| `status` | string | 健康状态，默认 `healthy` |
| `version` | string | 服务版本，默认 `0.1.0` |
| `timestamp` | string(datetime) | 服务生成时间 |

示例响应:

```json
{
  "status": "healthy",
  "version": "0.1.0",
  "timestamp": "2026-02-21T15:00:00.000000"
}
```

### cURL

```bash
curl "$BASE_URL/health"
```

## LLM 速读块

```yaml
- id: root_info
  method: GET
  path: /
  request: none
  response_keys: [message, docs]
- id: health_check
  method: GET
  path: /health
  request: none
  response_keys: [status, version, timestamp]
```

---

## 02-tools\tools.md

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

---

## 03-agents\agents.md

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

---

## 04-plans\plans.md

# Plan 管理类 API

## 数据模型

### PlanCreate

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `title` | string | 是 | 计划标题 |
| `objective` | string | 是 | 计划目标 |
| `context` | string/null | 否 | 背景上下文 |
| `steps` | StepCreate[]/null | 否 | 初始步骤 |
| `priority` | enum | 否 | `high`/`medium`/`low`，默认 `medium` |
| `namespace` | string | 否 | 默认 `default` |
| `estimated_complexity` | enum | 否 | `high`/`medium`/`low`，默认 `medium` |
| `metadata` | object/null | 否 | 扩展元数据 |

### StepCreate / StepAddRequest

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `title` | string | 是 | 步骤标题 |
| `description` | string/null | 否 | 详细描述 |
| `dependencies` | string[]/null | 否 | 依赖步骤 ID |
| `estimated_time` | string/null | 否 | 预估耗时 |
| `acceptance_criteria` | string[]/null | 否 | 验收标准 |
| `files_affected` | string[]/null | 否 | 影响文件 |

### StepUpdateRequest

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `status` | enum/null | 否 | `pending`/`in_progress`/`completed`/`blocked`/`skipped` |
| `notes` | string/null | 否 | 步骤备注 |

### PlanResponse（核心字段）

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | 计划 ID |
| `title` | string | 标题 |
| `objective` | string | 目标 |
| `status` | string | 计划状态 |
| `priority` | string | 优先级 |
| `namespace` | string | 命名空间 |
| `estimated_complexity` | string | 复杂度 |
| `created` | string | 创建时间 |
| `updated` | string | 更新时间 |
| `context` | string/null | 上下文 |
| `steps` | StepResponse[] | 步骤列表 |
| `progress` | number | 进度百分比 |
| `change_log` | object[] | 变更日志 |

## GET `/api/v1/plans`

用途: 列出计划。

### Query 参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `namespace` | string | 否 | 按命名空间过滤 |
| `status` | string | 否 | 按状态过滤 |

### 出参

`PlanListResponse`

| 字段 | 类型 | 说明 |
|---|---|---|
| `plans` | PlanResponse[] | 计划列表 |
| `total` | int | 总数 |

### cURL

```bash
curl "$BASE_URL/api/v1/plans?namespace=default&status=active"
```

## GET `/api/v1/plans/stats`

用途: 计划统计。

### 出参

`PlanStatsResponse`

| 字段 | 类型 | 说明 |
|---|---|---|
| `total_plans` | int | 计划总数 |
| `by_status` | object | 按状态统计 |

### cURL

```bash
curl "$BASE_URL/api/v1/plans/stats"
```

## POST `/api/v1/plans`

用途: 创建计划。

### Body 参数

`PlanCreate`，示例:

```json
{
  "title": "支付重构计划",
  "objective": "降低支付超时失败率",
  "priority": "high",
  "namespace": "payment",
  "estimated_complexity": "medium",
  "steps": [
    {
      "title": "梳理失败日志",
      "estimated_time": "2h"
    }
  ]
}
```

### 出参

- `201`: `PlanResponse`
- `500`: `{"detail":"Failed to create plan"}`

### cURL

```bash
curl -X POST "$BASE_URL/api/v1/plans" \
  -H "Content-Type: application/json" \
  -d '{
    "title":"支付重构计划",
    "objective":"降低失败率",
    "priority":"high",
    "namespace":"payment"
  }'
```

## GET `/api/v1/plans/{plan_id}`

用途: 查询计划详情。

### Path 参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `plan_id` | string | 是 | 计划 ID |

### 出参

- `200`: `PlanResponse`
- `404`: `{"detail":"Plan not found: <plan_id>"}`

### cURL

```bash
curl "$BASE_URL/api/v1/plans/plan-20260221-abc123"
```

## DELETE `/api/v1/plans/{plan_id}`

用途: 删除计划。

### 出参

成功:

```json
{
  "status": "ok",
  "message": "Plan <plan_id> deleted"
}
```

失败:

```json
{
  "detail": "Plan not found: <plan_id>"
}
```

### 状态码

- `200` 删除成功
- `404` 计划不存在

### cURL

```bash
curl -X DELETE "$BASE_URL/api/v1/plans/plan-20260221-abc123"
```

## PATCH `/api/v1/plans/{plan_id}/steps/{step_id}`

用途: 更新步骤状态或备注。

### Path 参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `plan_id` | string | 是 | 计划 ID |
| `step_id` | string | 是 | 步骤 ID |

### Body 参数

`StepUpdateRequest`，示例:

```json
{
  "status": "in_progress",
  "notes": "已开始编码"
}
```

### 出参

- `200`: 更新后的 `PlanResponse`
- `404`: `{"detail":"Plan or step not found: <plan_id>/<step_id>"}`

### cURL

```bash
curl -X PATCH "$BASE_URL/api/v1/plans/plan-20260221-abc123/steps/step-1" \
  -H "Content-Type: application/json" \
  -d '{
    "status":"completed",
    "notes":"已完成并通过自测"
  }'
```

## POST `/api/v1/plans/{plan_id}/steps`

用途: 向计划追加步骤。

### Path 参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `plan_id` | string | 是 | 计划 ID |

### Body 参数

`StepAddRequest`，示例:

```json
{
  "title": "新增监控告警",
  "description": "覆盖核心支付链路",
  "dependencies": ["step-1"],
  "estimated_time": "1d"
}
```

### 出参

- `200`: 更新后的 `PlanResponse`
- `404`: `{"detail":"Plan not found: <plan_id>"}`

### cURL

```bash
curl -X POST "$BASE_URL/api/v1/plans/plan-20260221-abc123/steps" \
  -H "Content-Type: application/json" \
  -d '{
    "title":"补充回归测试",
    "estimated_time":"4h"
  }'
```

## LLM 速读块

```yaml
- id: list_plans
  method: GET
  path: /api/v1/plans
  query: [namespace?, status?]
  response: PlanListResponse
- id: create_plan
  method: POST
  path: /api/v1/plans
  request: PlanCreate
  response: PlanResponse
  status_code: 201
- id: update_plan_step
  method: PATCH
  path: /api/v1/plans/{plan_id}/steps/{step_id}
  request: StepUpdateRequest
  response: PlanResponse
```

---

## 05-proxy\workspaces.md

# Proxy 工作空间类 API

前缀: `/api/v1/proxy`

## 数据模型

### WorkspaceCreate

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `workspace_id` | string | 是 | - | 工作空间 ID |
| `root_path` | string | 是 | - | 工作空间根路径 |
| `namespace` | string | 否 | `default` | 命名空间 |
| `allowed_tools` | string[] | 否 | `["*"]` | 允许工具列表 |
| `denied_tools` | string[] | 否 | `[]` | 禁止工具列表 |
| `is_readonly` | bool | 否 | `false` | 是否只读 |
| `denied_paths` | string[] | 否 | `[]` | 禁止访问路径模式 |
| `max_file_size` | int | 否 | `10485760` | 最大文件大小（字节） |
| `enable_symlinks` | bool | 否 | `false` | 是否允许符号链接 |

### WorkspaceResponse

| 字段 | 类型 | 说明 |
|---|---|---|
| `workspace_id` | string | 工作空间 ID |
| `root_path` | string | 解析后的根路径 |
| `namespace` | string | 命名空间 |
| `is_readonly` | bool | 是否只读 |
| `allowed_tools` | string[] | 允许工具 |
| `denied_tools` | string[] | 禁止工具 |

## POST `/api/v1/proxy/workspaces`

用途: 创建工作空间。

### Body 示例

```json
{
  "workspace_id": "ws-payment",
  "root_path": "E:/projects/payment",
  "namespace": "payment",
  "allowed_tools": ["read", "write", "bash"],
  "denied_tools": ["rm"],
  "is_readonly": false,
  "denied_paths": [".env", ".git"],
  "max_file_size": 10485760,
  "enable_symlinks": false
}
```

### 出参

- `201`: `WorkspaceResponse`
- `400`: 参数非法或路径创建失败

### cURL

```bash
curl -X POST "$BASE_URL/api/v1/proxy/workspaces" \
  -H "Content-Type: application/json" \
  -d '{
    "workspace_id":"ws-payment",
    "root_path":"E:/projects/payment",
    "namespace":"payment",
    "is_readonly":false
  }'
```

## GET `/api/v1/proxy/workspaces`

用途: 获取工作空间 ID 列表。

### 出参

`WorkspaceListResponse`

| 字段 | 类型 | 说明 |
|---|---|---|
| `workspaces` | string[] | 工作空间 ID 列表 |
| `total` | int | 总数 |

### cURL

```bash
curl "$BASE_URL/api/v1/proxy/workspaces"
```

## GET `/api/v1/proxy/workspaces/{workspace_id}`

用途: 获取单个工作空间详情。

### Path 参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `workspace_id` | string | 是 | 工作空间 ID |

### 出参

- `200`: `WorkspaceResponse`
- `404`: `{"detail":"Workspace not found: <workspace_id>"}`

### cURL

```bash
curl "$BASE_URL/api/v1/proxy/workspaces/ws-payment"
```

## DELETE `/api/v1/proxy/workspaces/{workspace_id}`

用途: 从服务中移除工作空间（不删除磁盘目录）。

### 出参

成功:

```json
{
  "status": "ok",
  "message": "Workspace ws-payment removed"
}
```

失败:

```json
{
  "detail": "Workspace not found: ws-payment"
}
```

### 状态码

- `200` 移除成功
- `404` 工作空间不存在

### cURL

```bash
curl -X DELETE "$BASE_URL/api/v1/proxy/workspaces/ws-payment"
```

## LLM 速读块

```yaml
- id: create_workspace
  method: POST
  path: /api/v1/proxy/workspaces
  request: WorkspaceCreate
  response: WorkspaceResponse
  status_code: 201
- id: get_workspace
  method: GET
  path: /api/v1/proxy/workspaces/{workspace_id}
  response: WorkspaceResponse
  errors: [404]
```

---

## 05-proxy\sessions.md

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

---

## 05-proxy\execution.md

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

---

## 99-llm\endpoint-catalog.md

# LLM 机读端点目录

## 端点总表

| endpoint_id | method | path | request_model | response_model | type |
|---|---|---|---|---|---|
| root_info | GET | `/` | - | inline object | health |
| health_check | GET | `/health` | - | `HealthResponse` | health |
| list_tools | GET | `/api/v1/tools` | - | `ToolInfo[]` | tools |
| execute_tool | POST | `/api/v1/tools/{tool_name}/execute` | `ExecuteToolRequest` | `ExecuteToolResponse`(当前501) | tools |
| list_agents | GET | `/api/v1/agents` | query | `AgentListResponse` | agents |
| get_agent_stats | GET | `/api/v1/agents/stats` | - | `AgentStatsResponse` | agents |
| list_namespaces | GET | `/api/v1/agents/namespaces` | - | `NamespaceListResponse` | agents |
| refresh_agents | GET | `/api/v1/agents/refresh` | - | inline object | agents |
| get_agent | GET | `/api/v1/agents/{agent_id}` | path | `AgentInfoResponse` | agents |
| execute_agent | POST | `/api/v1/agents/{agent_id}/execute` | `AgentExecuteRequest` | `AgentExecuteResponse` | agents |
| list_plans | GET | `/api/v1/plans` | query | `PlanListResponse` | plans |
| get_plan_stats | GET | `/api/v1/plans/stats` | - | `PlanStatsResponse` | plans |
| create_plan | POST | `/api/v1/plans` | `PlanCreate` | `PlanResponse` | plans |
| get_plan | GET | `/api/v1/plans/{plan_id}` | path | `PlanResponse` | plans |
| delete_plan | DELETE | `/api/v1/plans/{plan_id}` | path | inline object | plans |
| update_step | PATCH | `/api/v1/plans/{plan_id}/steps/{step_id}` | `StepUpdateRequest` | `PlanResponse` | plans |
| add_step | POST | `/api/v1/plans/{plan_id}/steps` | `StepAddRequest` | `PlanResponse` | plans |
| create_workspace | POST | `/api/v1/proxy/workspaces` | `WorkspaceCreate` | `WorkspaceResponse` | proxy_workspace |
| list_workspaces | GET | `/api/v1/proxy/workspaces` | - | `WorkspaceListResponse` | proxy_workspace |
| get_workspace | GET | `/api/v1/proxy/workspaces/{workspace_id}` | path | `WorkspaceResponse` | proxy_workspace |
| remove_workspace | DELETE | `/api/v1/proxy/workspaces/{workspace_id}` | path | inline object | proxy_workspace |
| create_session | POST | `/api/v1/proxy/sessions` | `SessionCreate` | `SessionResponse` | proxy_session |
| list_sessions | GET | `/api/v1/proxy/sessions` | query | `SessionListResponse` | proxy_session |
| get_session | GET | `/api/v1/proxy/sessions/{session_id}` | path | `SessionResponse` | proxy_session |
| delete_session | DELETE | `/api/v1/proxy/sessions/{session_id}` | path | inline object | proxy_session |
| proxy_execute | POST | `/api/v1/proxy/execute` | `ProxyExecuteRequest` | `ProxyExecuteResponse` | proxy_exec |
| proxy_execute_stream | POST | `/api/v1/proxy/execute/stream` | `ProxyExecuteRequest` | `ProxyStreamEvent`(SSE) | proxy_exec |
| proxy_stats | GET | `/api/v1/proxy/stats` | - | `ProxyStatsResponse` | proxy_exec |

## 错误码映射

| code | 场景 |
|---|---|
| `400` | 业务参数错误（如 session/workspace 不存在） |
| `404` | 资源不存在 |
| `422` | 请求体验证失败 |
| `501` | 未实现接口（tool execute） |
| `503` | Proxy 服务不可用 |

## 机读 JSON（可直接喂给大模型）

```json
{
  "base_url": "http://localhost:8000",
  "prefix": "/api/v1",
  "sse_endpoint": "/api/v1/proxy/execute/stream",
  "key_models": [
    "AgentExecuteRequest",
    "AgentExecuteResponse",
    "PlanCreate",
    "PlanResponse",
    "WorkspaceCreate",
    "SessionCreate",
    "ProxyExecuteRequest",
    "ProxyExecuteResponse",
    "ProxyStreamEvent"
  ]
}
```

