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
