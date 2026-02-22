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
