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
