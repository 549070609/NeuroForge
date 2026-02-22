# Agent 构建抽象指南

> 通用的 Agent 系统设计模式与实现要点

---

## 目录

- [1. Agent 核心抽象模型](#1-agent-核心抽象模型)
- [2. Agent 构建流程](#2-agent-构建流程)
- [3. 关键设计模式](#3-关键设计模式)
- [4. 输出格式规范](#4-输出格式规范)
- [5. 构建注意事项](#5-构建注意事项)
- [6. LLM Provider 适配](#6-llm-provider-适配)
- [7. 常见陷阱与解决方案](#7-常见陷阱与解决方案)

---

## 1. Agent 核心抽象模型

### 1.1 Agent 的本质定义

**Agent = LLM + 上下文 + 工具集 + 执行循环**

```
┌─────────────────────────────────────┐
│              Agent                   │
│                                      │
│  ┌──────────────────────────────┐   │
│  │     System Prompt            │   │
│  │  (角色定义、职责、行为规范)   │   │
│  └──────────────────────────────┘   │
│                                      │
│  ┌──────────────────────────────┐   │
│  │     Context (上下文)          │   │
│  │  - 用户消息历史               │   │
│  │  - 助手回复历史               │   │
│  │  - 工具调用记录               │   │
│  │  - 工具执行结果               │   │
│  └──────────────────────────────┘   │
│                                      │
│  ┌──────────────────────────────┐   │
│  │     Tool Registry (工具集)    │   │
│  │  - 可用工具列表               │   │
│  │  - 工具 Schema                │   │
│  │  - 工具执行器                 │   │
│  └──────────────────────────────┘   │
│                                      │
│  ┌──────────────────────────────┐   │
│  │     Execution Loop            │   │
│  │  while not done:              │   │
│  │    1. 调用 LLM                │   │
│  │    2. 判断停止条件            │   │
│  │    3. 执行工具（如果有）      │   │
│  │    4. 回传结果                │   │
│  └──────────────────────────────┘   │
└─────────────────────────────────────┘
```

### 1.2 Agent 类型分类

#### 单一职责 Agent

**特征：**
- 单个角色定义
- 专注于特定领域
- 独立完成任务

**适用场景：**
- 简单任务处理
- 单领域专家
- 一次交互完成

**示例：**
```yaml
name: code-reviewer
role: 代码审查专家
tools: [read, grep]
focus: 检查代码质量和最佳实践
```

#### 协调者 Agent

**特征：**
- 管理多个子 Agent
- 分配任务和整合结果
- 不直接执行具体工作

**适用场景：**
- 复杂多步骤任务
- 需要多个专业领域
- 任务分解和编排

**示例：**
```yaml
name: project-manager
role: 项目协调者
tools: [Task, ParallelTask]  # 子Agent调用工具
subagents:
  - frontend-specialist
  - backend-specialist
  - database-specialist
```

#### 层级 Agent

**特征：**
- 树状组织结构
- 上层 Agent 调用下层 Agent
- 递归嵌套

**适用场景：**
- 大型复杂项目
- 清晰的责任分工
- 多级管理

**示例：**
```
CTO Agent (战略层)
  ├─ Frontend Lead Agent (管理层)
  │   ├─ UI Developer Agent (执行层)
  │   └─ UX Designer Agent (执行层)
  └─ Backend Lead Agent (管理层)
      ├─ API Developer Agent (执行层)
      └─ Database Architect Agent (执行层)
```

---

## 2. Agent 构建流程

### 2.1 定义阶段

#### Step 1: 明确 Agent 角色

**核心问题：**
1. Agent 的职责是什么？
2. Agent 需要什么能力？
3. Agent 的边界在哪里？

**定义模板：**

```yaml
identity:
  name: agent-name
  description: 一句话描述Agent职责
  category: planning | execution | coordination | analysis

responsibilities:
  - 职责1
  - 职责2

capabilities:
  - 能力1
  - 能力2

limitations:
  - 不做的事1
  - 不做的事2
```

**示例：**

```yaml
identity:
  name: data-analyst
  description: 分析数据并提供洞察
  category: analysis

responsibilities:
  - 数据清洗和预处理
  - 统计分析
  - 生成可视化报告

capabilities:
  - 处理CSV、JSON数据
  - 执行SQL查询
  - 生成图表

limitations:
  - 不修改原始数据
  - 不执行危险操作
```

#### Step 2: 设计 System Prompt

**结构化模板：**

```markdown
# 角色定义
你是 [Agent角色]，负责 [核心职责]。

# 核心职责
1. [职责1]
2. [职责2]
3. [职责3]

# 工作流程
1. [步骤1]
2. [步骤2]
3. [步骤3]

# 输出格式
[具体的输出格式要求]

# 工作原则
- [原则1]
- [原则2]

# 限制
- [限制1]
- [限制2]

# 可用工具
- read: [用途]
- write: [用途]
```

**System Prompt 优化原则：**

| 原则 | 说明 | 示例 |
|------|------|------|
| **结构化** | 使用标题、列表、代码块 | `# 职责\n1. ...\n2. ...` |
| **具体化** | 避免模糊表述 | ❌ "分析数据"<br>✅ "执行统计计算：均值、中位数、标准差" |
| **示例化** | 提供输出示例 | `输出格式：\n## 摘要\n...\n## 详细分析\n...` |
| **边界化** | 明确说明不做的事 | `限制：不修改原始数据` |

#### Step 3: 选择工具集

**工具选择原则：**

1. **最小权限原则**：只给必需的工具
2. **职责匹配原则**：工具要匹配Agent职责
3. **风险控制原则**：高风险工具需要额外审批

**工具分类：**

| 类别 | 工具示例 | 风险等级 | 适用Agent |
|------|---------|---------|----------|
| **只读** | read, grep, glob | 低 | 分析类Agent |
| **写入** | write, edit | 中 | 创作类Agent |
| **执行** | bash, python | 高 | 执行类Agent |
| **网络** | web_search, fetch | 中 | 研究类Agent |
| **协调** | task, parallel_task | 中 | 协调者Agent |

**工具配置示例：**

```yaml
tools:
  required:
    - read      # 必需工具
    - write     # 必需工具

  optional:
    - grep      # 可选工具
    - glob      # 可选工具

  denied:
    - bash      # 禁止工具
    - delete    # 禁止工具
```

#### Step 4: 配置模型参数

**关键参数：**

```yaml
model:
  provider: anthropic | openai | google | custom
  model: claude-sonnet-4-6 | gpt-4 | gemini-pro

  # 温度（0.0-1.0）
  temperature: 0.7
  # - 0.0-0.3: 确定性任务（代码、逻辑）
  # - 0.4-0.7: 平衡任务（分析、规划）
  # - 0.8-1.0: 创意任务（写作、头脑风暴）

  # 最大Token
  max_tokens: 4096
  # - 短输出：1024-2048（摘要、回答）
  # - 中等输出：4096-8192（分析报告）
  # - 长输出：8192+（长文创作）

  # 停止序列
  stop_sequences:
    - "###"
    - "---"

  # 超时（秒）
  timeout: 120
```

**参数选择指南：**

| Agent类型 | Temperature | Max Tokens | 说明 |
|-----------|-------------|------------|------|
| 代码生成 | 0.2 | 4096 | 低温度确保代码正确 |
| 数据分析 | 0.5 | 4096 | 平衡准确性和洞察 |
| 内容创作 | 0.8 | 8192 | 高温度激发创意 |
| 规划决策 | 0.6 | 2048 | 结构化思维 |

### 2.2 实现阶段

#### Step 5: 实现 Agent 配置

**方式1: 使用 Builder API**

```python
schema = (
    AgentBuilder()
    # 身份
    .with_name("data-analyst")
    .with_description("数据分析专家")

    # 模型
    .with_model("claude-sonnet-4-6")
    .with_temperature(0.5)

    # 工具
    .add_tools(["read", "write", "execute"])

    # 行为
    .with_prompt("你是数据分析专家...")

    # 限制
    .max_iterations(20)
    .timeout(300)

    # 构建
    .build()
)
```

**方式2: 使用配置文件（YAML）**

```yaml
# agents/data-analyst.yaml

identity:
  name: data-analyst
  version: "1.0.0"
  description: "数据分析专家"

model:
  provider: anthropic
  model: claude-sonnet-4-6
  temperature: 0.5
  max_tokens: 4096

capabilities:
  tools:
    - read
    - write
    - execute-python

behavior:
  system_prompt: |
    你是数据分析专家，负责...

limits:
  max_iterations: 20
  timeout: 300
```

**方式3: 使用 Python Schema**

```python
from pyagentforge.building.schema import (
    AgentSchema,
    AgentIdentity,
    ModelConfiguration,
)

def create_schema() -> AgentSchema:
    identity = AgentIdentity(
        name="data-analyst",
        version="1.0.0",
        description="数据分析专家",
    )

    model = ModelConfiguration(
        provider="anthropic",
        model="claude-sonnet-4-6",
        temperature=0.5,
        max_tokens=4096,
    )

    # ... 更多配置

    return AgentSchema(
        identity=identity,
        model=model,
        # ...
    )

AGENT_SCHEMA = create_schema()
```

#### Step 6: 实现执行循环

**核心循环伪代码：**

```python
def run_agent(prompt: str, context: Context, tools: ToolRegistry) -> str:
    # 1. 添加用户消息
    context.add_user_message(prompt)

    # 2. 执行循环
    iteration = 0
    while iteration < MAX_ITERATIONS:
        iteration += 1

        # 2.1 获取上下文
        messages = context.get_messages_for_api()

        # 2.2 调用 LLM
        response = llm_call(
            system_prompt=SYSTEM_PROMPT,
            messages=messages,
            tools=tools.get_schemas(),
        )

        # 2.3 记录使用量
        track_usage(response.usage)

        # 2.4 判断是否结束
        if response.stop_reason != "tool_use":
            # 返回文本响应
            context.add_assistant_text(response.text)
            return response.text

        # 2.5 添加助手消息（含工具调用）
        context.add_assistant_message(response.content)

        # 2.6 执行工具
        for tool_call in response.tool_calls:
            result = execute_tool(tool_call, tools)
            context.add_tool_result(tool_call.id, result)

        # 2.7 上下文管理
        if context.is_near_limit():
            context.compress_or_truncate()

    # 3. 达到迭代上限
    return "Error: Maximum iterations reached"
```

**关键实现细节：**

| 组件 | 实现 | 注意事项 |
|------|------|---------|
| 消息添加 | `context.add_user_message()` | 区分用户和系统消息 |
| LLM调用 | 传入 messages + tools | 正确格式化工具schema |
| 停止判断 | `stop_reason != "tool_use"` | 也可能是 "end_turn" |
| 工具执行 | `execute_tool()` | 异步执行，错误处理 |
| 结果回传 | `add_tool_result(id, result)` | 必须关联 tool_call.id |

#### Step 7: 实现子Agent调用（可选）

**如果Agent需要调用其他Agent：**

```python
class TaskTool(BaseTool):
    """子Agent调用工具"""

    name = "Task"
    description = "调用子Agent执行特定任务"

    def __init__(
        self,
        provider,
        tool_registry,
        current_depth=0,
        max_depth=2,
    ):
        self.provider = provider
        self.tool_registry = tool_registry
        self.current_depth = current_depth
        self.max_depth = max_depth

    async def execute(self, **kwargs):
        # 1. 提取参数
        subagent_type = kwargs.get("subagent_type")
        prompt = kwargs.get("prompt")

        # 2. 深度检查（防止无限递归）
        if self.current_depth >= self.max_depth:
            return "Error: Maximum subagent depth reached"

        # 3. 获取子Agent配置
        subagent_config = SUBAGENT_TYPES[subagent_type]

        # 4. 创建隔离上下文
        sub_context = ContextManager(
            system_prompt=subagent_config["system_prompt"]
        )

        # 5. 过滤工具
        sub_tools = filter_tools(
            self.tool_registry,
            subagent_config["allowed_tools"]
        )

        # 6. 递归注册Task工具（深度+1）
        if self.current_depth + 1 < self.max_depth:
            sub_tools.register(TaskTool(
                provider=self.provider,
                tool_registry=sub_tools,
                current_depth=self.current_depth + 1,
                max_depth=self.max_depth,
            ))

        # 7. 创建子Agent引擎
        sub_engine = AgentEngine(
            provider=self.provider,
            tool_registry=sub_tools,
            context=sub_context,
        )

        # 8. 执行子Agent
        result = await sub_engine.run(prompt)

        # 9. 返回格式化结果
        return f"<{subagent_type}结果>\n{result}\n</{subagent_type}结果>"

    @classmethod
    def get_schema(cls):
        return {
            "name": cls.name,
            "description": cls.description,
            "input_schema": {
                "type": "object",
                "properties": {
                    "subagent_type": {
                        "type": "string",
                        "description": "子Agent类型",
                        "enum": list(SUBAGENT_TYPES.keys()),
                    },
                    "prompt": {
                        "type": "string",
                        "description": "具体任务描述",
                    }
                },
                "required": ["subagent_type", "prompt"],
            }
        }
```

**子Agent类型定义：**

```python
SUBAGENT_TYPES = {
    "subagent-name": {
        "description": "子Agent简短描述",
        "allowed_tools": ["read", "write"],  # 工具白名单
        "system_prompt": "你是...",           # System Prompt
    },
}
```

### 2.3 测试阶段

#### Step 8: 单元测试

**测试检查清单：**

```python
def test_agent():
    # ✅ 1. Agent创建测试
    agent = create_agent()
    assert agent is not None

    # ✅ 2. 基本对话测试
    response = agent.run("你好")
    assert response is not None
    assert len(response) > 0

    # ✅ 3. 工具调用测试
    response = agent.run("读取文件 test.txt")
    assert "read" in get_tool_calls(response)

    # ✅ 4. 上下文管理测试
    for i in range(10):
        agent.run(f"消息{i}")
    assert len(agent.context) < agent.context.max_messages

    # ✅ 5. 迭代上限测试
    with pytest.raises(MaxIterationsError):
        agent.run(infinite_loop_prompt)

    # ✅ 6. 错误处理测试
    response = agent.run("执行不存在的工具")
    assert "Error" in response or "error" in response.lower()
```

#### Step 9: 集成测试

**多Agent协作测试：**

```python
def test_multi_agent_workflow():
    # 1. 创建协调者
    coordinator = create_coordinator_agent()

    # 2. 注册子Agent
    register_subagent("worker-a", worker_a_config)
    register_subagent("worker-b", worker_b_config)

    # 3. 执行工作流
    result = coordinator.run("完成任务X")

    # 4. 验证结果
    assert result is not None
    assert "worker-a" in result or "worker-b" in result

    # 5. 验证调用链
    calls = get_tool_call_history(coordinator)
    assert any(call.name == "Task" for call in calls)
```

---

## 3. 关键设计模式

### 3.1 上下文隔离模式

**问题：** 子Agent不应该看到父Agent的完整历史

**解决方案：**

```python
# ❌ 错误：共享上下文
sub_engine = AgentEngine(
    context=parent_context,  # 污染！
)

# ✅ 正确：隔离上下文
sub_context = ContextManager(
    system_prompt=subagent_config["system_prompt"]
)
sub_engine = AgentEngine(
    context=sub_context,  # 独立！
)
```

**好处：**
- 防止信息泄露
- 控制Token消耗
- 保持上下文清晰

### 3.2 工具过滤模式

**问题：** 子Agent不应该拥有所有工具权限

**解决方案：**

```python
def filter_tools(parent_registry, allowed_list):
    """只保留允许的工具"""
    filtered = ToolRegistry()
    for tool_name in allowed_list:
        tool = parent_registry.get(tool_name)
        if tool:
            filtered.register(tool)
    return filtered

# 使用
sub_tools = filter_tools(
    parent_tools,
    subagent_config["allowed_tools"]  # ["read", "write"]
)
```

### 3.3 递归深度控制模式

**问题：** 防止无限递归（A调B，B调A）

**解决方案：**

```python
class TaskTool:
    def __init__(self, current_depth=0, max_depth=2):
        self.current_depth = current_depth
        self.max_depth = max_depth

    def execute(self, **kwargs):
        # 深度检查
        if self.current_depth >= self.max_depth:
            return "Error: Maximum depth reached"

        # 递归创建时，深度+1
        sub_task_tool = TaskTool(
            current_depth=self.current_depth + 1,
            max_depth=self.max_depth,
        )
```

**深度示例：**
```
深度 0: 主Agent
深度 1: 子Agent A
深度 2: 子子Agent B
深度 3: ❌ 达到上限
```

### 3.4 并行调用模式

**问题：** 多个子Agent可以并行执行以提高效率

**解决方案：**

```python
class ParallelTaskTool(BaseTool):
    name = "ParallelTask"

    async def execute(self, **kwargs):
        tasks = kwargs.get("tasks", [])

        async def run_single(task):
            tool = TaskTool(...)
            return await tool.execute(**task)

        # 并行执行
        results = await asyncio.gather(
            *[run_single(task) for task in tasks]
        )

        return "\n\n---\n\n".join(results)
```

**Schema:**

```python
{
    "name": "ParallelTask",
    "input_schema": {
        "type": "object",
        "properties": {
            "tasks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "subagent_type": {"type": "string"},
                        "prompt": {"type": "string"}
                    }
                }
            }
        }
    }
}
```

---

## 4. 输出格式规范

### 4.1 标准输出格式

**Agent 应该输出结构化内容：**

```markdown
# [标题]

## 摘要
[一句话总结]

## 详细内容
[主要内容]

### 要点1
[细节]

### 要点2
[细节]

## 下一步建议
[行动建议]
```

### 4.2 工具结果格式

**统一格式：**

```xml
<工具名称-结果>
[结果内容]
</工具名称-结果>
```

**示例：**

```xml
<read-结果>
文件内容：
```python
def hello():
    print("Hello, World!")
```
文件大小：89 字节
</read-结果>
```

### 4.3 错误输出格式

**统一格式：**

```xml
<错误>
工具：[工具名称]
错误类型：[错误类型]
错误信息：[错误详情]
建议：[修复建议]
</错误>
```

**示例：**

```xml
<错误>
工具：write
错误类型：PermissionDenied
错误信息：无法写入文件 /root/protected.txt
建议：请使用有写入权限的目录，或联系管理员
</错误>
```

### 4.4 子Agent结果格式

**格式：**

```xml
<子Agent类型-结果>
[子Agent的完整输出]
</子Agent类型-结果>
```

**示例：**

```xml
<data-analyst-结果>
## 数据摘要
- 总记录数：1000
- 缺失值：50 (5%)

## 统计分析
- 均值：45.3
- 中位数：42.0
- 标准差：12.5

## 洞察
数据呈正态分布，建议进一步分析...
</data-analyst-结果>
```

### 4.5 进度报告格式

**长时间任务的进度报告：**

```markdown
## 执行进度

**当前阶段：** 阶段 2/5
**任务：** 处理数据文件
**进度：** ████████░░ 80%

**已完成：**
- ✅ 读取数据
- ✅ 数据清洗
- ✅ 基础统计

**进行中：**
- 🔄 生成可视化

**待完成：**
- ⏳ 编写报告
- ⏳ 提供建议

**预计剩余时间：** 约 2 分钟
```

---

## 5. 构建注意事项

### 5.1 System Prompt 设计

**✅ 好的实践：**

```markdown
# 数据分析专家

## 角色定义
你是数据分析专家，负责分析数据并提供洞察。

## 核心职责
1. 数据清洗和预处理
2. 统计分析（均值、中位数、标准差）
3. 生成可视化图表
4. 提供数据驱动的建议

## 工作流程
1. 读取和验证数据
2. 清洗异常值和缺失值
3. 执行统计分析
4. 生成可视化
5. 编写分析报告

## 输出格式
### 数据摘要
[基本信息]

### 统计分析
[统计结果]

### 可视化
[图表描述]

### 洞察与建议
[分析洞察]

## 工作原则
- 数据驱动：所有结论基于数据
- 清晰表达：避免专业术语
- 可操作性：提供具体建议

## 限制
- 不修改原始数据文件
- 不执行危险操作（删除、格式化）
- 不访问外部网络

## 可用工具
- read: 读取数据文件
- write: 保存分析报告
- execute-python: 执行Python代码进行统计
```

**❌ 不好的实践：**

```markdown
你是一个AI助手，可以帮助用户做数据分析。
```

### 5.2 工具选择原则

| 原则 | 说明 | 示例 |
|------|------|------|
| **最小权限** | 只给必需的工具 | 只读Agent不给write工具 |
| **职责匹配** | 工具要匹配职责 | 分析Agent给统计工具，不给创作工具 |
| **风险分级** | 高风险工具需审批 | bash工具需明确授权 |
| **工具隔离** | 子Agent限制工具集 | 子Agent不能调用Task工具 |

**工具配置矩阵：**

| Agent类型 | read | write | edit | bash | web | task |
|-----------|------|-------|------|------|-----|------|
| 只读分析 | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ |
| 内容创作 | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ |
| 代码执行 | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| 协调者 | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |

### 5.3 上下文管理策略

**Token 限制策略：**

```python
# 1. 设置合理的上限
context.max_messages = 100  # 最大消息数

# 2. 接近上限时截断
if len(context) > max_messages * 0.8:
    # 策略1：删除最早的对话（保留system prompt）
    context.truncate(keep_first=1)

    # 策略2：压缩旧消息
    context.compress()

    # 策略3：摘要化
    summary = summarize_old_messages(context)
    context.replace_with_summary(summary)
```

**上下文优化技巧：**

1. **工具结果压缩**
   ```python
   if len(result) > MAX_RESULT_LENGTH:
       result = result[:MAX_RESULT_LENGTH] + f"\n... (截断，共 {len(result)} 字符)"
   ```

2. **选择性保留**
   ```python
   # 只保留最近N轮对话
   context.keep_recent(n=10)
   ```

3. **摘要替换**
   ```python
   # 将长对话替换为摘要
   old_messages = context.get_old_messages(threshold=20)
   summary = llm_summarize(old_messages)
   context.replace_with_summary(summary)
   ```

### 5.4 错误处理机制

**工具执行错误：**

```python
async def execute_tool(tool_call, tools):
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

**LLM调用错误：**

```python
async def call_llm(messages, tools):
    try:
        response = await provider.chat(messages, tools)
        return response

    except RateLimitError:
        # 限流，等待后重试
        await asyncio.sleep(RETRY_DELAY)
        return await call_llm(messages, tools)

    except APIConnectionError:
        # 连接失败
        return "Error: 无法连接到AI服务，请检查网络"

    except InvalidRequestError as e:
        # 请求无效
        return f"Error: 请求无效 - {e}"
```

### 5.5 性能优化要点

**1. 并行工具调用**

```python
# 如果LLM返回多个工具调用，并行执行
if len(tool_calls) > 1:
    results = await asyncio.gather(
        *[execute_tool(tc) for tc in tool_calls]
    )
else:
    results = [await execute_tool(tool_calls[0])]
```

**2. 缓存机制**

```python
# 缓存文件读取结果
@lru_cache(maxsize=100)
def read_file(filepath):
    with open(filepath, 'r') as f:
        return f.read()
```

**3. 流式输出**

```python
async def stream_response(prompt):
    async for chunk in llm_stream(prompt):
        yield chunk  # 实时输出
```

**4. 懒加载工具**

```python
# 只在需要时加载大型工具
class LazyTool:
    def __init__(self, tool_loader):
        self.loader = tool_loader
        self._tool = None

    @property
    def tool(self):
        if self._tool is None:
            self._tool = self.loader()
        return self._tool
```

---

## 6. LLM Provider 适配

### 6.1 Anthropic API 特性与适配

**Anthropic Claude API 的关键特性：**

#### 1. 消息格式差异

**Anthropic 格式：**
```python
{
    "model": "claude-sonnet-4-6",
    "max_tokens": 4096,
    "system": "You are a helpful assistant.",  # 独立的system字段
    "messages": [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there"}
    ]
}
```

**OpenAI 格式：**
```python
{
    "model": "gpt-4",
    "messages": [
        {"role": "system", "content": "You are a helpful assistant."},  # system在messages中
        {"role": "user", "content": "Hello"}
    ]
}
```

**适配要点：**
```python
# ❌ 错误：将system放入messages
messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": user_message}
]

# ✅ 正确：Anthropic需要分离system
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=4096,
    system=system_prompt,  # 独立参数
    messages=[             # 只有user/assistant
        {"role": "user", "content": user_message}
    ]
)
```

#### 2. 工具调用格式

**Anthropic Tool Schema：**
```python
{
    "name": "read_file",
    "description": "Read a file from disk",
    "input_schema": {  # 注意：input_schema 不是 parameters
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the file"
            }
        },
        "required": ["file_path"]
    }
}
```

**OpenAI Tool Schema：**
```python
{
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read a file from disk",
        "parameters": {  # 注意：parameters 不是 input_schema
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string"
                }
            },
            "required": ["file_path"]
        }
    }
}
```

**适配要点：**
```python
# ✅ Anthropic 工具注册
tools = [
    {
        "name": "read_file",
        "description": "Read a file",
        "input_schema": {  # ← 关键差异
            "type": "object",
            "properties": {...}
        }
    }
]

response = client.messages.create(
    model="claude-sonnet-4-6",
    system=system_prompt,
    messages=messages,
    tools=tools  # 直接传入列表
)
```

#### 3. 响应结构

**Anthropic 响应：**
```python
{
    "id": "msg_xxx",
    "type": "message",
    "role": "assistant",
    "content": [  # content是数组
        {
            "type": "text",
            "text": "Let me help you with that."
        },
        {
            "type": "tool_use",  # 工具调用
            "id": "toolu_xxx",
            "name": "read_file",
            "input": {"file_path": "/path/to/file"}
        }
    ],
    "stop_reason": "tool_use",  # 停止原因
    "usage": {
        "input_tokens": 100,
        "output_tokens": 50
    }
}
```

**OpenAI 响应：**
```python
{
    "id": "chatcmpl-xxx",
    "choices": [{
        "message": {
            "role": "assistant",
            "content": "Let me help you.",
            "tool_calls": [  # 独立的tool_calls字段
                {
                    "id": "call_xxx",
                    "type": "function",
                    "function": {
                        "name": "read_file",
                        "arguments": "{\"file_path\": \"/path/to/file\"}"  # JSON字符串
                    }
                }
            ]
        },
        "finish_reason": "tool_calls"
    }],
    "usage": {...}
}
```

**适配要点：**
```python
# ✅ 解析Anthropic响应
def parse_anthropic_response(response):
    # 提取文本
    text_content = ""
    tool_calls = []

    for block in response.content:
        if block.type == "text":
            text_content += block.text
        elif block.type == "tool_use":
            tool_calls.append({
                "id": block.id,
                "name": block.name,
                "input": block.input  # 已经是dict，不需要JSON解析
            })

    has_tool_calls = response.stop_reason == "tool_use"

    return {
        "text": text_content,
        "tool_calls": tool_calls,
        "has_tool_calls": has_tool_calls,
        "usage": response.usage
    }
```

#### 4. 工具结果回传

**Anthropic 工具结果格式：**
```python
# 工具调用后，回传结果
{
    "role": "user",
    "content": [
        {
            "type": "tool_result",  # ← 关键类型
            "tool_use_id": "toolu_xxx",  # 对应工具调用的ID
            "content": "File content here..."
        }
    ]
}
```

**OpenAI 工具结果格式：**
```python
{
    "role": "tool",  # ← 独立role
    "tool_call_id": "call_xxx",
    "content": "File content here..."
}
```

**适配要点：**
```python
# ✅ Anthropic 工具结果回传
def add_tool_result_anthropic(messages, tool_call_id, result):
    messages.append({
        "role": "user",  # 注意：是user，不是tool
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": tool_call_id,
                "content": result
            }
        ]
    })

# ✅ OpenAI 工具结果回传
def add_tool_result_openai(messages, tool_call_id, result):
    messages.append({
        "role": "tool",  # 独立role
        "tool_call_id": tool_call_id,
        "content": result
    })
```

#### 5. 停止原因

**Anthropic stop_reason：**
- `"end_turn"` - 正常结束（文本响应）
- `"tool_use"` - 需要调用工具
- `"max_tokens"` - 达到最大token限制
- `"stop_sequence"` - 遇到停止序列

**OpenAI finish_reason：**
- `"stop"` - 正常结束
- `"tool_calls"` - 需要调用工具
- `"length"` - 达到最大token限制
- `"content_filter"` - 内容过滤

**适配要点：**
```python
# ✅ 判断是否需要工具调用
# Anthropic
if response.stop_reason == "tool_use":
    # 执行工具

# OpenAI
if response.choices[0].finish_reason == "tool_calls":
    # 执行工具
```

### 6.2 Anthropic 特有问题与解决方案

#### 问题1: Content Block 顺序

**问题：** Anthropic 返回的 content 数组中，text 和 tool_use 的顺序不固定

**症状：**
```python
# 有时text在前
content = [
    {"type": "text", "text": "Let me check..."},
    {"type": "tool_use", "name": "read", ...}
]

# 有时tool_use在前
content = [
    {"type": "tool_use", "name": "read", ...},
    {"type": "text", "text": "Done."}
]
```

**解决：**
```python
# ✅ 正确处理：遍历所有block
def process_response(response):
    text_parts = []
    tool_calls = []

    for block in response.content:
        if block.type == "text":
            text_parts.append(block.text)
        elif block.type == "tool_use":
            tool_calls.append(block)

    return "".join(text_parts), tool_calls
```

#### 问题2: System Prompt 长度限制

**问题：** Anthropic 对 system prompt 有长度限制（约 10K tokens）

**症状：**
```python
APIStatusError: system prompt is too long
```

**解决：**
```python
# ❌ 错误：超长system prompt
system_prompt = load_large_document()  # 100K+ tokens

# ✅ 方案1：摘要化
system_prompt = summarize(system_prompt, max_tokens=9000)

# ✅ 方案2：分段，放到user消息中
system_prompt = "核心指令..."
reference_docs = "参考资料..."  # 在第一次user消息中提供
```

#### 问题3: Tool Result 过长

**问题：** 工具结果过长导致上下文超出限制

**症状：**
```python
APIStatusError: messages result in too many tokens
```

**解决：**
```python
# ✅ 截断或压缩工具结果
def add_tool_result_safe(messages, tool_call_id, result, max_length=5000):
    if len(result) > max_length:
        result = result[:max_length] + f"\n... (截断，共 {len(result)} 字符)"

    messages.append({
        "role": "user",
        "content": [{
            "type": "tool_result",
            "tool_use_id": tool_call_id,
            "content": result
        }]
    })
```

#### 问题4: 流式响应解析

**问题：** Anthropic 流式响应的 content_block_delta 结构复杂

**症状：**
```python
# 流式事件类型多样
event.type == "content_block_start"
event.type == "content_block_delta"
event.type == "content_block_stop"
event.type == "message_delta"
event.type == "message_stop"
```

**解决：**
```python
# ✅ 正确处理流式响应
async def stream_anthropic_response(prompt):
    text_buffer = ""
    tool_calls_buffer = {}

    async with client.messages.stream(...) as stream:
        async for event in stream:
            if event.type == "content_block_start":
                block = event.content_block
                if block.type == "tool_use":
                    tool_calls_buffer[block.id] = {
                        "name": block.name,
                        "input": ""
                    }

            elif event.type == "content_block_delta":
                delta = event.delta
                if delta.type == "text_delta":
                    text_buffer += delta.text
                    yield delta.text  # 实时输出
                elif delta.type == "input_json_delta":
                    # 工具输入是JSON流
                    tool_calls_buffer[event.index]["input"] += delta.partial_json

            elif event.type == "message_stop":
                # 解析完整的工具输入
                for tool_call in tool_calls_buffer.values():
                    tool_call["input"] = json.loads(tool_call["input"])

                return text_buffer, list(tool_calls_buffer.values())
```

### 6.3 Provider 抽象层设计

**最佳实践：实现 Provider 抽象层**

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any

class LLMProvider(ABC):
    """LLM Provider 抽象基类"""

    @abstractmethod
    async def chat(
        self,
        system_prompt: str,
        messages: List[Dict],
        tools: List[Dict]
    ) -> Dict:
        """调用LLM"""
        pass

    @abstractmethod
    def add_tool_result(
        self,
        messages: List[Dict],
        tool_call_id: str,
        result: str
    ) -> None:
        """添加工具结果"""
        pass

    @abstractmethod
    def parse_response(self, response: Any) -> Dict:
        """解析响应"""
        pass

class AnthropicProvider(LLMProvider):
    """Anthropic 实现"""

    def __init__(self, api_key: str, model: str):
        from anthropic import AsyncAnthropic
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model

    async def chat(self, system_prompt, messages, tools):
        # Anthropic 格式
        return await self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system_prompt,  # 独立字段
            messages=messages,
            tools=[{"name": t["name"],
                    "description": t["description"],
                    "input_schema": t["input_schema"]}
                   for t in tools]
        )

    def add_tool_result(self, messages, tool_call_id, result):
        # Anthropic 格式
        messages.append({
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": tool_call_id,
                "content": result
            }]
        })

    def parse_response(self, response):
        # Anthropic 解析
        text = ""
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                text += block.text
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "input": block.input
                })

        return {
            "text": text,
            "tool_calls": tool_calls,
            "has_tool_calls": response.stop_reason == "tool_use",
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens
            }
        }

class OpenAIProvider(LLMProvider):
    """OpenAI 实现"""

    def __init__(self, api_key: str, model: str):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def chat(self, system_prompt, messages, tools):
        # OpenAI 格式
        full_messages = [
            {"role": "system", "content": system_prompt},  # system在messages中
            *messages
        ]

        return await self.client.chat.completions.create(
            model=self.model,
            messages=full_messages,
            tools=[{"type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t["description"],
                        "parameters": t["input_schema"]
                    }}
                   for t in tools]
        )

    def add_tool_result(self, messages, tool_call_id, result):
        # OpenAI 格式
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": result
        })

    def parse_response(self, response):
        # OpenAI 解析
        choice = response.choices[0]

        tool_calls = []
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                tool_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "input": json.loads(tc.function.arguments)
                })

        return {
            "text": choice.message.content or "",
            "tool_calls": tool_calls,
            "has_tool_calls": choice.finish_reason == "tool_calls",
            "usage": {
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens
            }
        }
```

**使用 Provider 抽象层：**

```python
# Agent 引擎不依赖具体Provider
class AgentEngine:
    def __init__(self, provider: LLMProvider, tools, context):
        self.provider = provider
        self.tools = tools
        self.context = context

    async def run(self, prompt: str) -> str:
        self.context.add_user_message(prompt)

        while True:
            # 统一接口，无需关心Provider差异
            response = await self.provider.chat(
                system_prompt=self.system_prompt,
                messages=self.context.get_messages(),
                tools=self.tools.get_schemas()
            )

            parsed = self.provider.parse_response(response)

            if not parsed["has_tool_calls"]:
                self.context.add_assistant_text(parsed["text"])
                return parsed["text"]

            self.context.add_assistant_message(parsed["tool_calls"])

            for tool_call in parsed["tool_calls"]:
                result = await self.execute_tool(tool_call)
                self.provider.add_tool_result(
                    self.context.messages,
                    tool_call["id"],
                    result
                )
```

### 6.4 Anthropic 适配检查清单

**消息格式：**
- [ ] System prompt 使用独立参数（不在 messages 中）
- [ ] Messages 只包含 user 和 assistant 角色
- [ ] Content 字段是数组，支持多个 block

**工具调用：**
- [ ] 工具 schema 使用 `input_schema`（不是 parameters）
- [ ] 工具列表直接传递（不包装在 function 中）
- [ ] 工具 input 是 dict（不是 JSON 字符串）

**响应解析：**
- [ ] Content 是数组，需要遍历处理
- [ ] 使用 `stop_reason` 判断是否工具调用
- [ ] Tool call id 使用 `tool_use_id`（不是 tool_call_id）

**工具结果：**
- [ ] Role 使用 "user"（不是 "tool"）
- [ ] Content 使用 `tool_result` 类型
- [ ] 对应 id 使用 `tool_use_id`

**错误处理：**
- [ ] 处理 system prompt 过长错误
- [ ] 处理工具结果过长错误
- [ ] 正确处理流式响应的多种事件类型

---

## 7. 常见陷阱与解决方案

### 6.1 上下文污染

**症状：**
- Token消耗快速增长
- 子Agent看到不该看的信息
- 响应质量下降

**原因：**
```python
# ❌ 共享上下文
sub_engine = AgentEngine(context=parent_context)
```

**解决：**
```python
# ✅ 独立上下文
sub_context = ContextManager(system_prompt=subagent_config["system_prompt"])
sub_engine = AgentEngine(context=sub_context)
```

### 6.2 工具权限泄露

**症状：**
- 子Agent调用了不该有的工具
- 安全风险
- 意外的副作用

**原因：**
```python
# ❌ 传递整个工具注册表
sub_engine = AgentEngine(tool_registry=parent_tools)
```

**解决：**
```python
# ✅ 过滤工具
sub_tools = filter_tools(parent_tools, subagent_config["allowed_tools"])
sub_engine = AgentEngine(tool_registry=sub_tools)
```

### 6.3 无限递归

**症状：**
- Agent无限循环
- 资源耗尽
- 无响应

**原因：**
```python
# ❌ 无深度检查
sub_tools.register(TaskTool(...))  # 无限递归
```

**解决：**
```python
# ✅ 深度控制
if current_depth < max_depth:
    sub_tools.register(TaskTool(
        current_depth=current_depth + 1,
        max_depth=max_depth,
    ))
```

### 6.4 忘记回传工具结果

**症状：**
- LLM重复调用相同工具
- 上下文不完整
- 逻辑混乱

**原因：**
```python
# ❌ 执行但不回传
result = execute_tool(tool_call)
# 忘记添加到上下文
```

**解决：**
```python
# ✅ 回传结果
result = execute_tool(tool_call)
context.add_tool_result(tool_call.id, result)
```

### 6.5 迭代上限未设置

**症状：**
- Agent陷入死循环
- 长时间无响应
- 成本失控

**原因：**
```python
# ❌ 无迭代上限
while True:  # 危险！
    response = llm_call(messages)
```

**解决：**
```python
# ✅ 设置上限
MAX_ITERATIONS = 20
iteration = 0
while iteration < MAX_ITERATIONS:
    iteration += 1
    response = llm_call(messages)
```

### 6.6 Token 统计缺失

**症状：**
- 不知道成本
- 无法优化
- 预算超支

**解决：**
```python
# ✅ 统计使用量
@dataclass
class UsageStats:
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_requests: int = 0
    by_agent: dict = field(default_factory=dict)

    def add_usage(self, agent, input_t, output_t):
        self.total_input_tokens += input_t
        self.total_output_tokens += output_t
        self.total_requests += 1

        if agent not in self.by_agent:
            self.by_agent[agent] = {"input": 0, "output": 0}
        self.by_agent[agent]["input"] += input_t
        self.by_agent[agent]["output"] += output_t

# 使用
if response.usage:
    usage_stats.add_usage(
        agent=agent_name,
        input_t=response.usage.input_tokens,
        output_t=response.usage.output_tokens,
    )
```

### 6.7 错误处理缺失

**症状：**
- 异常崩溃
- 用户看到技术错误
- 无法恢复

**解决：**
```python
# ✅ 完整错误处理
async def run_agent(prompt):
    try:
        # Agent逻辑
        return await execute(prompt)

    except ValidationError as e:
        return format_user_error("输入验证失败", e)

    except ToolExecutionError as e:
        return format_user_error("工具执行失败", e)

    except LLMError as e:
        return format_user_error("AI服务错误", e)

    except Exception as e:
        log_error(e)  # 记录到日志
        return format_user_error("未知错误，请联系管理员")
```

---

## 总结

### Agent 构建检查清单

**定义阶段：**
- [ ] 明确Agent角色和职责
- [ ] 设计结构化System Prompt
- [ ] 选择合适的工具集
- [ ] 配置合理的模型参数

**实现阶段：**
- [ ] 实现Agent配置（Builder/YAML/Python）
- [ ] 实现执行循环（ReAct Loop）
- [ ] 实现上下文管理
- [ ] 实现工具注册和执行
- [ ] （可选）实现子Agent调用

**测试阶段：**
- [ ] 单元测试（基本功能）
- [ ] 集成测试（多Agent协作）
- [ ] 边界测试（迭代上限、Token限制）
- [ ] 错误测试（异常处理）

**优化阶段：**
- [ ] Token统计和优化
- [ ] 性能优化（并行、缓存）
- [ ] 输出格式优化
- [ ] 错误处理完善

### 核心原则

1. **单一职责**：每个Agent只做一件事
2. **最小权限**：只给必需的工具
3. **上下文隔离**：子Agent独立上下文
4. **深度控制**：防止无限递归
5. **结果回传**：工具结果必须回传
6. **错误处理**：优雅处理所有异常
7. **成本控制**：统计Token消耗

---

*最后更新：2026-02-21*
