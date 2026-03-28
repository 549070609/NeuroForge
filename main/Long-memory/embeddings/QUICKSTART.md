# Local Embeddings - 快速启动指南

## 快速开始

```bash
cd main/Long-memory/embeddings
pip install -r requirements.txt
python test_embeddings.py
python test_plugin.py
```

## 接入说明

本插件不再附带任何内置厂商 Provider 示例。
如需结合远端大模型使用，请在宿主应用中使用 `LLMClient` 和模型级配置接入。
