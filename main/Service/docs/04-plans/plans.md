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
