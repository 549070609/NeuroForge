# Local Embeddings

基于 `sentence-transformers` 的本地文本嵌入模块，作为插件使用。

## 说明

本目录只提供 embeddings 能力，不再包含任何内置厂商 LLM Provider 用法。
如需接入远端模型，请在上层应用使用 `LLMClient` 并通过模型级配置传入：
- `api_type`
- `base_url`
- `model_name`
- `api_key` / `api_key_env`
- `headers`
- `timeout`

## 通过配置文件加载插件

```yaml
preset: standard
enabled:
  - tool.embeddings
plugin_dirs:
  - "../Long-memory/embeddings"
config:
  tool.embeddings:
    model_path: null
    device: cpu
```
