# Service API Full

本文档已更新为新版架构说明。

## 架构说明

- 采用协议驱动与模型级配置
- 通过 `LLMClient` 统一调用
- 不依赖内置厂商 SDK

## 当前推荐用法

```python
from pyagentforge import LLMClient

client = LLMClient()
response = await client.create_message(
    model_id="your-model-id",
    messages=[{"role": "user", "content": "你好"}],
)
```

## 当前配置方式

```json
{
  "default_model": "your-model-id",
  "models": {
    "your-model-id": {
      "id": "your-model-id",
      "name": "Your Model",
      "provider": "your-provider-name",
      "api_type": "openai-completions",
      "model_name": "your-remote-model-name",
      "base_url": "https://api.example.com/v1",
      "api_key_env": "YOUR_LLM_API_KEY"
    }
  }
}
```
