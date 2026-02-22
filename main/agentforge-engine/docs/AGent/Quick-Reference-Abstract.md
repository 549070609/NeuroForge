# Agent 构建抽象指南 - 快速参考

> Agent 构建核心模式速查表

---

## 1. Agent 核心公式

```
Agent = LLM + Context + Tools + Loop
```

---

## 2. Agent 类型

| 类型 | 特征 | 工具集 | 适用场景 |
|------|------|--------|---------|
| **单一职责** | 单角色，独立完成 | 特定领域工具 | 简单任务 |
| **协调者** | 管理子Agent | Task, ParallelTask | 复杂多步骤 |
| **层级** | 树状结构 | Task + 领域工具 | 大型项目 |

---

## 3. Anthropic vs OpenAI 关键差异

| 特性 | Anthropic | OpenAI |
|------|-----------|--------|
| **System Prompt** | 独立参数 `system=` | 在 messages 中 `role: system` |
| **Tool Schema** | `input_schema` | `parameters` |
| **Tool Format** | 直接列表 | 包装在 `function` 中 |
| **Tool Input** | dict | JSON字符串 |
| **Response Content** | 数组（多个block） | 单一 content 字段 |
| **Tool Calls** | 在 content 数组中 | 独立 tool_calls 字段 |
| **Stop Reason** | `"tool_use"` | `"tool_calls"` |
| **Tool Result Role** | `"user"` | `"tool"` |
| **Tool Result Type** | `tool_result` | 无类型标记 |

---

## 4. 构建流程（9步）

### 定义阶段
```
1. 明确角色     → name, description, category
2. 设计Prompt  → 结构化：角色/职责/流程/格式/限制
3. 选择工具     → 最小权限原则
4. 配置参数     → temperature, max_tokens, timeout
```

### 实现阶段
```
5. 实现配置     → Builder API / YAML / Python
6. 实现循环     → ReAct Loop
7. 子Agent调用  → TaskTool（可选）
```

### 测试阶段
```
8. 单元测试     → 创建/对话/工具/上下文/错误
9. 集成测试     → 多Agent协作
```

---

## 4. System Prompt 模板

```markdown
# [角色名称]

## 角色定义
你是 [角色]，负责 [核心职责]。

## 核心职责
1. [职责1]
2. [职责2]

## 工作流程
1. [步骤1]
2. [步骤2]
3. [步骤3]

## 输出格式
### [章节1]
[说明]

### [章节2]
[说明]

## 工作原则
- [原则1]
- [原则2]

## 限制
- [限制1]
- [限制2]
```

---

## 5. ReAct Loop 伪代码

```python
def run_agent(prompt, context, tools):
    context.add_user_message(prompt)

    iteration = 0
    while iteration < MAX_ITERATIONS:
        iteration += 1

        # 1. 调用LLM
        response = llm_call(
            messages=context.get_messages(),
            tools=tools.get_schemas()
        )

        # 2. 记录usage
        track_usage(response.usage)

        # 3. 判断结束
        if response.stop_reason != "tool_use":
            context.add_assistant_text(response.text)
            return response.text

        # 4. 添加助手消息
        context.add_assistant_message(response.content)

        # 5. 执行工具
        for tool_call in response.tool_calls:
            result = execute_tool(tool_call)
            context.add_tool_result(tool_call.id, result)

        # 6. 上下文管理
        if context.is_near_limit():
            context.compress()

    return "Error: Maximum iterations reached"
```

---

## 6. 子Agent调用模式

### TaskTool 核心逻辑

```python
class TaskTool:
    def __init__(self, depth=0, max_depth=2):
        self.depth = depth
        self.max_depth = max_depth

    async def execute(self, subagent_type, prompt):
        # 1. 深度检查
        if self.depth >= self.max_depth:
            return "Error: Max depth reached"

        # 2. 获取配置
        config = SUBAGENT_TYPES[subagent_type]

        # 3. 创建隔离上下文
        sub_context = ContextManager(
            system_prompt=config["system_prompt"]
        )

        # 4. 过滤工具
        sub_tools = filter_tools(
            allowed=config["allowed_tools"]
        )

        # 5. 递归注册Task（深度+1）
        if self.depth + 1 < self.max_depth:
            sub_tools.register(TaskTool(
                depth=self.depth + 1,
                max_depth=self.max_depth
            ))

        # 6. 创建子引擎
        sub_engine = AgentEngine(
            context=sub_context,
            tools=sub_tools
        )

        # 7. 执行
        result = await sub_engine.run(prompt)

        # 8. 返回格式化结果
        return f"<{subagent_type}结果>\n{result}\n</{subagent_type}结果>"
```

### 子Agent类型定义

```python
SUBAGENT_TYPES = {
    "agent-name": {
        "description": "简短描述",
        "allowed_tools": ["read", "write"],
        "system_prompt": "你是...",
    }
}
```

---

## 7. 输出格式规范

### 标准输出

```markdown
# [标题]

## 摘要
[一句话总结]

## 详细内容
[主要内容]

## 下一步建议
[行动建议]
```

### 工具结果

```xml
<工具名称-结果>
[结果内容]
</工具名称-结果>
```

### 错误输出

```xml
<错误>
工具：[名称]
错误类型：[类型]
错误信息：[详情]
建议：[修复建议]
</错误>
```

### 子Agent结果

```xml
<子Agent类型-结果>
[完整输出]
</子Agent类型-结果>
```

---

## 8. 工具选择矩阵

| Agent类型 | read | write | edit | bash | web | task |
|-----------|:----:|:-----:|:----:|:----:|:---:|:----:|
| 只读分析 | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ |
| 内容创作 | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ |
| 代码执行 | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| 协调者 | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |

**原则：** 最小权限 + 职责匹配

---

## 9. 7大陷阱速查

| 陷阱 | 症状 | 原因 | 解决 |
|------|------|------|------|
| **上下文污染** | Token爆炸 | 共享context | 独立ContextManager |
| **工具泄露** | 越权调用 | 传递全部tools | filter_tools(allowed) |
| **无限递归** | 死循环 | 无深度检查 | depth >= max_depth检查 |
| **结果未回传** | 重复调用 | 忘记add_tool_result | 必须回传结果 |
| **迭代无上限** | 无限循环 | while True | MAX_ITERATIONS限制 |
| **Token未统计** | 成本失控 | 无usage跟踪 | UsageStats记录 |
| **错误未处理** | 崩溃 | 无try-catch | 完整错误处理 |

---

## 10. 关键设计模式

### 上下文隔离

```python
# ❌ 错误
sub_engine = AgentEngine(context=parent_context)

# ✅ 正确
sub_context = ContextManager(system_prompt=config["system_prompt"])
sub_engine = AgentEngine(context=sub_context)
```

### 工具过滤

```python
def filter_tools(parent_registry, allowed_list):
    filtered = ToolRegistry()
    for name in allowed_list:
        tool = parent_registry.get(name)
        if tool:
            filtered.register(tool)
    return filtered
```

### 深度控制

```python
if current_depth < max_depth:
    sub_tools.register(TaskTool(
        current_depth=current_depth + 1,
        max_depth=max_depth
    ))
```

### 并行调用

```python
results = await asyncio.gather(
    *[execute_task(task) for task in tasks]
)
```

---

## 11. 参数配置指南

### Temperature

| 值 | 用途 | Agent类型 |
|----|------|-----------|
| 0.0-0.3 | 确定性 | 代码、逻辑 |
| 0.4-0.7 | 平衡 | 分析、规划 |
| 0.8-1.0 | 创意 | 写作、头脑风暴 |

### Max Tokens

| 值 | 用途 |
|----|------|
| 1024-2048 | 短输出（摘要、回答） |
| 4096-8192 | 中等（分析报告） |
| 8192+ | 长输出（长文创作） |

---

## 12. 上下文管理策略

```python
# 1. 设置上限
context.max_messages = 100

# 2. 接近上限时处理
if len(context) > max_messages * 0.8:
    # 策略1：截断
    context.truncate(keep_first=1)

    # 策略2：压缩
    context.compress()

    # 策略3：摘要
    summary = summarize(context)
    context.replace_with_summary(summary)

# 3. 工具结果压缩
if len(result) > MAX_LENGTH:
    result = result[:MAX_LENGTH] + f"... (截断，共{len(result)}字符)"
```

---

## 13. 错误处理模板

```python
async def execute_tool(tool_call):
    try:
        tool = tools.get(tool_call.name)
        if not tool:
            return f"<错误>工具 '{tool_call.name}' 不存在</错误>"

        result = await tool.execute(**tool_call.input)
        return result

    except ValidationError as e:
        return f"<错误>参数验证失败：{e}</错误>"

    except PermissionError as e:
        return f"<错误>权限不足：{e}</错误>"

    except TimeoutError as e:
        return f"<错误>执行超时：{e}</错误>"

    except Exception as e:
        return f"<错误>未知错误：{e}</错误>"
```

---

## 14. 性能优化要点

```python
# 1. 并行工具调用
results = await asyncio.gather(
    *[execute_tool(tc) for tc in tool_calls]
)

# 2. 缓存
@lru_cache(maxsize=100)
def read_file(filepath):
    return open(filepath).read()

# 3. 流式输出
async for chunk in llm_stream(prompt):
    yield chunk

# 4. 懒加载
class LazyTool:
    @property
    def tool(self):
        if self._tool is None:
            self._tool = load_tool()
        return self._tool
```

---

## 17. Anthropic 适配要点

### 消息格式

```python
# ✅ Anthropic
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=4096,
    system=system_prompt,  # ← 独立参数
    messages=[             # ← 只有user/assistant
        {"role": "user", "content": "Hello"}
    ],
    tools=[...]  # ← 直接列表
)
```

### 工具 Schema

```python
# ✅ Anthropic
{
    "name": "read_file",
    "description": "Read a file",
    "input_schema": {  # ← 不是 parameters
        "type": "object",
        "properties": {
            "file_path": {"type": "string"}
        }
    }
}
```

### 响应解析

```python
# ✅ Anthropic - content是数组
for block in response.content:
    if block.type == "text":
        text += block.text
    elif block.type == "tool_use":
        tool_calls.append({
            "id": block.id,
            "name": block.name,
            "input": block.input  # 已经是dict
        })

# 判断工具调用
has_tools = response.stop_reason == "tool_use"
```

### 工具结果回传

```python
# ✅ Anthropic
messages.append({
    "role": "user",  # ← 不是 "tool"
    "content": [{
        "type": "tool_result",  # ← 必需
        "tool_use_id": tool_call_id,  # ← 对应id
        "content": result
    }]
})
```

### 常见错误

| 错误 | 原因 | 解决 |
|------|------|------|
| `system prompt is too long` | System超10K tokens | 摘要或分段 |
| `messages result in too many tokens` | 工具结果过长 | 截断或压缩 |
| `invalid tool_use_id` | ID不匹配 | 检查tool_use_id |
| Content解析错误 | 期望string，实际array | 遍历content数组 |

---

## 18. 检查清单

**定义：**
- [ ] 角色/职责明确
- [ ] System Prompt结构化
- [ ] 工具最小权限
- [ ] 参数合理

**实现：**
- [ ] 配置完成
- [ ] 循环正确
- [ ] 上下文管理
- [ ] 工具执行
- [ ] （可选）子Agent

**测试：**
- [ ] 单元测试
- [ ] 集成测试
- [ ] 边界测试
- [ ] 错误测试

**优化：**
- [ ] Token统计
- [ ] 性能优化
- [ ] 格式优化
- [ ] 错误处理

---

## 19. 核心原则

1. **单一职责** - 每个Agent只做一件事
2. **最小权限** - 只给必需工具
3. **上下文隔离** - 子Agent独立上下文
4. **深度控制** - 防止无限递归
5. **结果回传** - 工具结果必须回传
6. **错误处理** - 优雅处理异常
7. **成本控制** - 统计Token消耗
8. **Provider抽象** - 统一接口，隔离差异

---

*最后更新：2026-02-21*
