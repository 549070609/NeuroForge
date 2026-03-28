# LLM Adapter

当前适配层只负责协议兼容，不再负责厂商注册。

## 使用方式

- 在配置中为每个模型单独声明连接参数与认证信息
- 通过 `api_type` 选择兼容协议
- 通过 `base_url`、`model_name`、`api_key` / `api_key_env` 发起请求
