# JSON 配置说明（main 目录）

本项目的 LLM 相关 JSON 配置已统一放在 `main/` 下集中管理。

## 1. 文件说明

- `main/llm_config.json`
  - 运行时主配置，优先编辑此文件。
- `main/default_llm_config.json`
  - 当主配置缺失时的默认回退配置。
- `main/llm_config.template.json`
  - 完整模板，包含更多 provider/model 示例。
- `main/llm_config_schema.json`
  - JSON Schema，可用于结构校验。

## 2. 配置加载优先级

运行时按以下顺序查找配置：

1. 环境变量 `LLM_CONFIG_PATH`
2. `main/llm_config.json`
3. `{当前工作目录}/llm_config.json`（兼容旧路径）
4. `main/default_llm_config.json`
5. 包内回退：`pyagentforge/config/default_llm_config.json`

## 3. 最小可用结构

```json
{
  "default_model": "claude-sonnet-4-20250514",
  "max_tokens": 4096,
  "temperature": 1.0,
  "providers": {},
  "models": {}
}
```

## 4. 关键字段

- `default_model`：默认模型 ID。
- `max_tokens`：默认输出 token 上限。
- `temperature`：默认采样温度。
- `providers`：Provider 级配置（密钥、base_url、timeout、重试等）。
- `models`：模型级配置（provider、api_type、上下文窗口、输出上限等）。

## 5. API Key 读取规则

当前实现的读取逻辑：

1. 优先读取环境变量（模型级/Provider 级）。
2. 若环境变量缺失，则回退读取 JSON 内 `api_key`。

建议：

- 生产环境优先使用 `api_key_env`。
- 本地快速调试可临时写 `api_key`。

## 6. 示例

### 6.1 推荐：环境变量方式

```json
{
  "providers": {
    "anthropic": {
      "enabled": true,
      "api_key_env": "ANTHROPIC_API_KEY"
    }
  }
}
```

### 6.2 本地调试：直填 key

```json
{
  "providers": {
    "anthropic": {
      "enabled": true,
      "api_key": "YOUR_KEY_HERE"
    }
  }
}
```

### 6.3 本地 Ollama 示例

```json
{
  "providers": {
    "ollama": {
      "enabled": true,
      "base_url": "http://localhost:11434/v1"
    }
  },
  "models": {
    "llama3.1": {
      "id": "llama3.1",
      "name": "Llama 3.1",
      "provider": "ollama",
      "api_type": "openai-completions",
      "context_window": 128000
    }
  }
}
```

## 7. 快速验证

```bash
cd main/Service
uvicorn Service.gateway.app:create_app --factory --reload --port 8000
```

若进入真实 provider 调用并出现鉴权报错，通常说明配置路径已正确生效。
