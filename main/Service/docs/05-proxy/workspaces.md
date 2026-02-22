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
