# Service Docs

本目录文档已切换到新版接入方式：

- 统一使用 `LLMClient` + 模型级配置
- 通过模型配置声明 `provider`、`api_type`、`base_url`、`model_name`
- 通过 `api_key` 或 `api_key_env` 解析认证信息

模型级配置仅保留：
- `api_type`
- `base_url`
- `model_name`
- `api_key` / `api_key_env`
- `headers`
- `timeout`
