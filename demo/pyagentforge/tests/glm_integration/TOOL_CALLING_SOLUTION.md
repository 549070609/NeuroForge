# GLM 工具调用问题 - 根因分析与解决方案

## 🔍 问题根因

通过对比 OpenCode Server 的工具调用实现，发现 GLM API 端点工具调用失败的**根本原因**：

### 不是格式问题，而是 API 能力问题

**错误代码 1210** 表示：
> "API 调用参数错误，请参考文档"

这意味着 GLM 的 **Coding Plan OpenAI 兼容端点** 根本**不支持 `tools` 参数**。

---

## 📊 对比分析

### OpenCode Server 的工具调用架构

```
┌─────────────────────────────────────────────────────────────┐
│                     AI SDK Provider Layer                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ Anthropic   │  │   OpenAI    │  │   Other Providers   │  │
│  │ Provider    │  │   Provider  │  │                     │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
│         │                │                    │              │
│         ▼                ▼                    ▼              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │            统一工具格式 (LanguageModelV2FunctionTool)  │  │
│  │  { type: 'function', name, description, inputSchema }  │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### GLM API 端点对比

| 端点 | 协议 | 基础对话 | 工具调用 | 说明 |
|------|------|:--------:|:--------:|------|
| `open.bigmodel.cn/api/paas/v4` | OpenAI | ✅ | ❌ | 通用 API，不支持工具 |
| `open.bigmodel.cn/api/coding/paas/v4` | OpenAI | ✅ | ❌ | Coding Plan，但工具格式不同 |
| `api.z.ai/api/anthropic` | Anthropic | ❌ | ❌ | 需要不同认证 |

---

## 💡 解决方案

### 方案 1: 使用 GLM 原生工具调用格式 ⭐ 推荐

GLM API 可能使用 **`functions`** 而不是 **`tools`** 参数。

**修改 `glm_provider.py`**:

```python
def _convert_tools_to_glm(
    self,
    tools: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """将工具格式转换为 GLM 原生格式 (使用 functions 而非 tools)"""
    glm_functions = []
    for tool in tools:
        glm_functions.append({
            "name": tool.get("name", ""),
            "description": tool.get("description", ""),
            "parameters": tool.get("input_schema", {}),
        })
    return glm_functions

async def create_message(
    self,
    system: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    **kwargs: Any,
) -> ProviderResponse:
    """创建消息 - 使用 GLM 原生格式"""
    openai_messages = self._convert_messages_to_openai(system, messages)

    params: dict[str, Any] = {
        "model": self.model,
        "messages": openai_messages,
        "max_tokens": kwargs.get("max_tokens", self.max_tokens),
        "temperature": kwargs.get("temperature", self.temperature),
    }

    # 关键修改: 使用 functions 而不是 tools
    if tools:
        params["functions"] = self._convert_tools_to_glm(tools)
        # 或者尝试: params["function_call"] = "auto"

    # ... 其余代码
```

---

### 方案 2: 查阅 GLM 官方文档确认格式

**GLM 工具调用文档**: https://open.bigmodel.cn/dev/api#tool

可能的格式选项：
1. `tools` (OpenAI 新格式)
2. `functions` (OpenAI 旧格式)
3. `plugins` (GLM 特有格式)

---

### 方案 3: 使用支持工具调用的模型

**切换到 Anthropic Claude**:

```python
# 使用 Anthropic Provider (完全支持工具调用)
from pyagentforge.providers.anthropic_provider import AnthropicProvider

provider = AnthropicProvider(
    api_key="your-anthropic-api-key",
    model="claude-3-5-sonnet-20241022"
)
```

---

### 方案 4: 实现 ReAct 模式的工具调用

**不依赖 API 原生工具调用**，使用 ReAct (Reasoning + Acting) 模式：

```python
class ReActAgent:
    """基于 ReAct 模式的 Agent，不依赖 API 工具调用"""

    TOOL_PROMPT = """
你是一个智能助手。你可以使用以下工具：

{tool_descriptions}

当你需要使用工具时，请按以下格式回复：
Thought: [思考过程]
Action: [工具名称]
Action Input: {"param": "value"}

当不需要工具时，直接回复用户。

用户问题：{question}
"""

    async def run(self, prompt: str) -> str:
        # 1. 生成工具描述
        tool_desc = self._generate_tool_descriptions()

        # 2. 构造提示词
        full_prompt = self.TOOL_PROMPT.format(
            tool_descriptions=tool_desc,
            question=prompt
        )

        # 3. 调用 LLM
        response = await self.provider.create_message(
            system="你是一个智能助手",
            messages=[{"role": "user", "content": full_prompt}],
            tools=[],  # 不使用 API 工具调用
        )

        # 4. 解析响应，检测是否需要工具
        if "Action:" in response.text:
            tool_name, tool_input = self._parse_action(response.text)
            tool_result = await self.execute_tool(tool_name, tool_input)

            # 5. 将工具结果加入上下文，继续对话
            return await self.run(f"工具结果：{tool_result}\n请继续回答：{prompt}")

        return response.text
```

---

## 🎯 推荐实施方案

### 立即尝试 (5分钟)

**测试 GLM 的 functions 参数**:

```bash
# 修改 glm_provider.py 的 create_message 方法
# 将 params["tools"] 改为 params["functions"]
```

### 如果方案 1 失败 (10分钟)

**查阅官方文档**:
1. 访问 https://open.bigmodel.cn/dev/api
2. 搜索 "工具调用" 或 "Function Calling"
3. 确认正确的参数格式

### 备选方案 (30分钟)

**实现 ReAct 模式**:
- 不依赖 API 原生工具调用
- 通过 Prompt 引导模型输出工具调用格式
- 在应用层解析和执行工具

---

## 📋 待验证事项

1. **GLM 是否支持 `functions` 参数？**
2. **GLM-4-plus 是否支持工具调用而 GLM-4-flash 不支持？**
3. **Coding Plan 是否需要单独的 API Key？**
4. **GLM 原生工具调用格式是什么？**

---

## 🔗 相关资源

- [GLM API 官方文档](https://open.bigmodel.cn/dev/api)
- [OpenAI Function Calling](https://platform.openai.com/docs/guides/function-calling)
- [Anthropic Tool Use](https://docs.anthropic.com/claude/docs/tool-use)
- [ReAct 论文](https://arxiv.org/abs/2210.03629)

---

**结论**: 问题很可能不是代码格式问题，而是 GLM API 端点本身不支持 OpenAI 格式的工具调用。需要：
1. 尝试 GLM 原生格式 (`functions`)
2. 或查阅官方文档确认正确格式
3. 或切换到支持工具调用的模型
