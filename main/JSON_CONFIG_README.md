# JSON 配置说明

本项目已经移除内置厂商配置与 Provider SDK 集成。

现在仅保留模型级参数：
- `api_type`
- `base_url`
- `model_name`
- `api_key` / `api_key_env`
- `headers`
- `timeout`
- `supports_*` 等能力描述

## 最小示例

```json
{
  "default_model": "demo-model",
  "models": {
    "demo-model": {
      "id": "demo-model",
      "name": "Demo Model",
      "provider": "demo-provider",
      "api_type": "openai-completions",
      "model_name": "demo-model-name",
      "base_url": "https://api.example.com/v1",
      "api_key_env": "DEMO_API_KEY"
    }
  }
}
```

## 说明

- `provider` 只作展示分组，不再驱动任何内置逻辑。
- `api_type` 表示要兼容的请求/响应格式。
- 每个模型都应自行声明连接参数，不再从全局 `providers` 段继承。
- 如果远端需要额外请求头，可放在 `headers` 中。
- 任意供应商都应通过自定义参数接入，而不是通过 SDK 内置厂商类接入。
