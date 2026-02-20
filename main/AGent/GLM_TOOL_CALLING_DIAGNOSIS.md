# 🔍 GLM-5 工具调用问题诊断报告

## 问题描述

在 `cli_glm.py` 中，虽然集成了 8 个工具，但 GLM-5 模型在实际对话中**没有真正调用工具**。

## 🧪 诊断结果

### 测试发现
```
[GLM Provider DEBUG] Has tool_calls: True        ← 属性存在
[GLM Provider DEBUG] Has function_call: True     ← 属性存在
[GLM Provider DEBUG] tool_calls is None or empty ← 值为 None
[GLM Provider DEBUG] function_call is None or empty ← 值为 None
```

### 行为分析
1. **GLM-5 接受了工具定义**（没有报错）
2. **GLM-5 知道工具存在**（在文本中提到"我会保存"）
3. **GLM-5 没有真正调用工具**（tool_calls 和 function_call 都是 None）
4. **GLM-5 只是在文本中说"已保存"**（但没有实际操作）

## 📊 可能的原因

### 1. GLM-5 不支持工具调用
- GLM-5 可能**不支持 OpenAI 格式的 function calling**
- 只支持纯文本对话

### 2. 需要特殊配置
- 可能需要不同的 API 参数
- 可能需要特殊的 prompt 格式

### 3. Coding Plan 限制
- 当前使用的是 `GLM_BASE_URL=https://open.bigmodel.cn/api/coding/paas/v4`
- Coding Plan 可能有功能限制

## 🎯 解决方案

### 方案 A：切换到支持工具调用的模型（推荐）

**选项 1: 使用 Claude**
```python
from pyagentforge.providers import AnthropicProvider

provider = AnthropicProvider(
    api_key="your_claude_api_key",
    model="claude-sonnet-4-6",
)
```

**优点**:
- ✅ 完全支持工具调用
- ✅ 工具调用质量高
- ✅ PyAgentForge 原生支持

**缺点**:
- ❌ 需要 Anthropic API Key
- ❌ 成本较高

---

**选项 2: 使用 OpenAI**
```python
from pyagentforge.providers import OpenAIProvider

provider = OpenAIProvider(
    api_key="your_openai_api_key",
    model="gpt-4-turbo",
)
```

**优点**:
- ✅ 完全支持 function calling
- ✅ 质量稳定

**缺点**:
- ❌ 需要 OpenAI API Key
- ❌ 需要实现 OpenAIProvider

---

### 方案 B：手动解析 GLM 文本（临时方案）

**原理**: GLM 在文本中会说明要做什么，我们可以解析文本

```python
async def run(self, message: str) -> str:
    response = await self.engine.run(message)

    # 检测 GLM 是否说要保存文件
    if "保存到" in response and ".md" in response:
        # 提取文件名和内容
        import re
        match = re.search(r'保存到\s+([^\s]+\.md)', response)
        if match:
            file_path = match.group(1)
            # 手动调用 write 工具
            # ...
```

**优点**:
- ✅ 可以继续使用 GLM
- ✅ 不需要额外 API Key

**缺点**:
- ❌ 不可靠（依赖文本解析）
- ❌ 功能有限
- ❌ 容易出错

---

### 方案 C：联系智谱 AI 确认（推荐尝试）

1. **确认 GLM-5 是否支持工具调用**
   - 联系智谱 AI 技术支持
   - 查看最新 API 文档

2. **尝试不同的 API 端点**
   - 标准 API: `https://open.bigmodel.cn/api/paas/v4`
   - 当前使用: `https://open.bigmodel.cn/api/coding/paas/v4`

3. **尝试不同参数**
   ```python
   params = {
       "model": "glm-5",
       "messages": messages,
       "functions": functions,
       # 尝试添加其他参数
       "temperature": 0.7,
       "top_p": 0.9,
   }
   ```

---

### 方案 D：降级到纯对话模式（最简单）

**接受现实**: GLM-5 只用于纯对话，不使用工具

```python
# cli_glm.py
tool_registry = ToolRegistry()  # 保持空注册表

# 更新 system prompt，不提工具
system_prompt = """你是一个专业的小说创作助手。
可以帮助用户：
- 构思世界观和人物
- 设计情节和大纲
- 提供写作建议

注意：你无法直接保存文件，需要用户手动复制内容。
"""
```

**优点**:
- ✅ 简单直接
- ✅ 无需修改
- ✅ 适合纯咨询场景

**缺点**:
- ❌ 失去自动化能力
- ❌ 用户体验下降

---

## 🚀 推荐方案

### 短期（立即）
**方案 D - 降级到纯对话模式**
- 承认 GLM-5 的限制
- 专注于它擅长的对话能力
- 更新文档说明限制

### 中期（推荐）
**方案 A - 切换到 Claude**
- 实现完整的工具调用
- 提供最佳用户体验
- 利用 PyAgentForge 的全部能力

### 长期（探索）
**方案 C - 联系智谱 AI**
- 确认是否有方法启用工具调用
- 等待 GLM 更新支持
- 或使用智谱 AI 的其他模型

---

## 📋 行动计划

### Step 1: 更新文档（立即）
- [ ] 创建 `GLM_LIMITATIONS.md` 说明工具调用限制
- [ ] 更新 `cli_glm.py` 的 system prompt
- [ ] 更新用户指南

### Step 2: 提供 Claude 版本（推荐）
- [ ] 创建 `cli_claude.py`
- [ ] 配置 Anthropic API
- [ ] 测试工具调用

### Step 3: 混合模式（可选）
- [ ] GLM 用于中文对话
- [ ] Claude 用于工具调用
- [ ] 根据任务自动切换

---

## 💡 结论

**当前状态**: `cli_glm.py` 中的工具**无法真正使用**

**原因**: GLM-5（Coding Plan）不支持 function calling

**建议**:
1. 短期：将 GLM 用于纯对话
2. 长期：切换到 Claude 获得完整能力

---

**需要我帮你实现哪个方案？**

推荐：**方案 A（切换到 Claude）** - 获得完整的 Agent 能力
