# 配置指南

## 设计原则

- 不再内置任何厂商 Provider
- 所有连接参数均在模型级声明
- 仅保留兼容协议格式与必要请求参数
- 通过 `api_type` 完成格式兼容

## 支持的协议格式

- `anthropic-messages`
- `openai-completions`
- `openai-responses`
- `google-generative-ai`
- `bedrock-converse-stream`
- `custom`

## 推荐配置结构

```json
{
  "default_model": "your-model-id",
  "max_tokens": 4096,
  "temperature": 1.0,
  "models": {
    "your-model-id": {
      "id": "your-model-id",
      "name": "Your Model",
      "provider": "your-provider-name",
      "api_type": "openai-completions",
      "model_name": "your-remote-model-name",
      "base_url": "https://api.example.com/v1",
      "api_key_env": "YOUR_LLM_API_KEY",
      "headers": {},
      "timeout": 120
    }
  }
}
```

## 字段说明

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `id` | string | 是 | 本地模型唯一标识 |
| `name` | string | 是 | 展示名称 |
| `provider` | string | 是 | 展示用供应商标识 |
| `api_type` | string | 是 | 兼容协议格式 |
| `model_name` | string | 否 | 实际发送到远端的模型名 |
| `base_url` | string | 否 | 远端接口基础地址 |
| `api_key` | string | 否 | 直接传入密钥 |
| `api_key_env` | string | 否 | 从环境变量读取密钥 |
| `headers` | object | 否 | 附加请求头 |
| `timeout` | int | 否 | 请求超时秒数 |
| `extra` | object | 否 | 额外透传配置 |

## 迁移说明

旧版 `providers` 配置段已废弃并删除。
请将所有公共配置下沉到各个模型节点中。
