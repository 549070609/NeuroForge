# LLM 配置说明

本框架支持通过 JSON 配置文件管理大模型连接参数。

## 快速开始

### 1. 设置配置文件路径

通过环境变量 `LLM_CONFIG_PATH` 指定配置文件路径：

```bash
# Linux/macOS
export LLM_CONFIG_PATH=/path/to/llm_config.json

# Windows CMD
set LLM_CONFIG_PATH=C:\path\to\llm_config.json

# Windows PowerShell
$env:LLM_CONFIG_PATH = "C:\path\to\llm_config.json"
```

### 2. 创建配置文件

复制模板文件并根据需要修改：

```bash
cp llm_config.example.json llm_config.json
```

### 3. 设置 API Keys

有两种方式设置 API Keys：

#### 方式一：环境变量（推荐）

```bash
export ANTHROPIC_API_KEY=your-anthropic-key
export OPENAI_API_KEY=your-openai-key
export GLM_API_KEY=your-glm-key
export DEEPSEEK_API_KEY=your-deepseek-key
```

#### 方式二：配置文件

直接在配置文件中设置（不推荐用于生产环境）：

```json
{
  "providers": {
    "anthropic": {
      "api_key": "your-anthropic-key"
    }
  }
}
```

#### 方式三：环境变量引用

在配置文件中使用 `${VAR_NAME}` 语法引用环境变量：

```json
{
  "providers": {
    "anthropic": {
      "api_key": "${ANTHROPIC_API_KEY}"
    }
  }
}
```

支持默认值语法 `${VAR_NAME:-default}`：

```json
{
  "providers": {
    "anthropic": {
      "timeout": "${ANTHROPIC_TIMEOUT:-120}"
    }
  }
}
```

## 配置文件结构

```json
{
  "default_model": "claude-sonnet-4-20250514",
  "max_tokens": 4096,
  "temperature": 1.0,

  "providers": {
    "anthropic": {
      "enabled": true,
      "api_key_env": "ANTHROPIC_API_KEY",
      "base_url": null,
      "timeout": 120,
      "max_retries": 3
    }
  },

  "models": {
    "claude-sonnet-4-20250514": {
      "id": "claude-sonnet-4-20250514",
      "name": "Claude Sonnet 4",
      "provider": "anthropic",
      "api_type": "anthropic-messages",
      "supports_vision": true,
      "context_window": 200000,
      "max_output_tokens": 16384
    }
  }
}
```

## 支持的 Provider

| Provider | api_key_env | base_url |
|----------|-------------|----------|
| anthropic | ANTHROPIC_API_KEY | https://api.anthropic.com |
| openai | OPENAI_API_KEY | https://api.openai.com/v1 |
| google | GOOGLE_API_KEY | - |
| zhipu | GLM_API_KEY | https://open.bigmodel.cn/api/paas/v4 |
| deepseek | DEEPSEEK_API_KEY | https://api.deepseek.com/v1 |
| alibaba | DASHSCOPE_API_KEY | https://dashscope.aliyuncs.com/compatible-mode/v1 |
| moonshot | MOONSHOT_API_KEY | https://api.moonshot.cn/v1 |
| yi | YI_API_KEY | https://api.lingyiwanwu.com/v1 |
| ollama | - | http://localhost:11434/v1 |
| custom | CUSTOM_API_KEY | 自定义 |

## API 优先级

获取 API Key 的优先级：

1. 模型级配置 `models[id].api_key`
2. 模型级环境变量 `models[id].api_key_env`
3. Provider 级配置 `providers[name].api_key`
4. Provider 级环境变量 `providers[name].api_key_env`
5. 默认环境变量（如 `ANTHROPIC_API_KEY`）

获取 Base URL 的优先级：

1. 模型级配置 `models[id].base_url`
2. Provider 级配置 `providers[name].base_url`
3. 默认值

## 在代码中使用

```python
from pyagentforge.config import get_llm_config, get_llm_config_manager

# 获取配置
config = get_llm_config()
print(f"Default model: {config.default_model}")

# 获取 API Key
manager = get_llm_config_manager()
api_key = manager.get_api_key("anthropic", "claude-sonnet-4-20250514")
base_url = manager.get_base_url("zhipu")

# 重新加载配置
manager.reload_config()
```

## 配置验证

配置文件支持 JSON Schema 验证，在 IDE 中可通过 `$schema` 字段启用自动补全：

```json
{
  "$schema": "./pyagentforge/config/llm_config_schema.json",
  ...
}
```

## 完整模板

参见：
- `llm_config.example.json` - 简洁示例
- `pyagentforge/config/llm_config.template.json` - 完整模板（包含所有模型）
- `pyagentforge/config/llm_config_schema.json` - JSON Schema
