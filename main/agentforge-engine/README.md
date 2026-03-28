# PyAgentForge

PyAgentForge 已移除内置厂商 Provider 与供应商 SDK 封装。

## 当前接入方式

统一通过 `LLMClient` + 模型级配置使用远端模型：
- `api_type`
- `base_url`
- `model_name`
- `api_key` / `api_key_env`
- `headers`
- `timeout`

## 最小示例

```python
from pyagentforge import LLMClient

client = LLMClient()
response = await client.create_message(
    model_id="your-model-id",
    messages=[{"role": "user", "content": "你好"}],
)
```

## 配置示例

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

## 说明

- SDK 不再内置 `AnthropicProvider`、`OpenAIProvider`、`GoogleProvider` 等类
- 旧的 `providers` 配置段已删除
- 供应商接入统一由宿主应用以自定义参数方式完成
