# 记忆加工插件 (Memory Processor)

## 概述

记忆加工插件是一个自动化的记忆元数据增强系统。当用户存储新记忆时，它会自动分析内容并生成：

- **标签 (tags)**: 从预定义标签池中选择相关标签
- **主题 (topic)**: 3-5 个字的简短概括
- **摘要 (summary)**: 1-2 句话的内容摘要

## 提供的工具

### 1. memory_store（来自 long-memory 插件）

存储记忆到向量数据库。存储完成后会自动触发加工。

```
参数:
  content (required): 要存储的记忆内容
  topic (optional): 记忆主题
  importance (optional): 重要性 0.0-1.0，默认 0.5
  tags (optional): 分类标签列表
  message_type (optional): 消息类型，默认 'knowledge'

返回:
  已存储记忆 (ID: mem_xxx)
  主题: xxx
  内容: xxx...
  重要性: x.xx
  标签: xxx, xxx

自动加工后会附加:
  [自动加工完成] 标签: xxx | 主题: xxx
```

### 2. memory_process

手动加工指定的记忆。

```
参数:
  memory_id (required): 要加工的记忆 ID（格式: mem_xxx）
  force (optional): 是否强制重新加工，默认 false

返回:
  记忆加工完成 (ID: mem_xxx)
  分析方法: llm/rule
  置信度: x.xx
  标签: xxx, xxx
  主题: xxx
  摘要: xxx
```

### 3. memory_reprocess

批量重加工历史记忆。

```
参数:
  limit (optional): 最大处理数量，默认 10，最大 100
  filter_tags (optional): 只处理包含这些标签的记忆
  filter_topic (optional): 只处理主题匹配的记忆

返回:
  批量加工完成: x 成功, x 失败
  --- 处理详情 ---
  ✓ mem_xxx: [标签] 主题: xxx
  ✓ mem_xxx: [标签] 主题: xxx
  ...
  分析方法统计:
    - rule: x 条
    - llm: x 条
```

## 标签池

插件内置 8 个分类的标签池：

| 分类 | 标签 |
|------|------|
| work | 工作, 项目, 任务, 计划, 会议, 进度 |
| technical | 代码, 技术, Bug, 功能, 架构, API, 框架 |
| learning | 学习, 笔记, 教程, 文档, 课程, 研究 |
| personal | 偏好, 设置, 个人信息, 习惯, 风格 |
| ideas | 想法, 创意, 待办, 目标, 规划, 灵感 |
| reference | 资料, 链接, 命令, 配置, 参数, 环境 |
| communication | 沟通, 反馈, 问题, 决策, 讨论 |
| important | 重要, 紧急, 关键, 核心, 必要 |

## 工作流程

```
用户请求存储记忆
       ↓
  memory_store 工具
       ↓
   存储到 ChromaDB
       ↓
  [Hook: on_after_tool_call]
       ↓
  MemoryProcessorPlugin 检测到存储
       ↓
  LLMAnalyzer 分析内容
       ↓
  ┌─────────────────┐
  │ LLM 可用?       │
  │  Yes → LLM 分析 │
  │  No  → 规则分析 │
  └─────────────────┘
       ↓
  生成 tags, topic, summary
       ↓
  更新记忆条目
       ↓
  返回加工结果
```

## 分析方法

### LLM 分析（优先）

当 LLM 客户端可用时，使用智能分析：

1. 发送内容和标签池给 LLM
2. LLM 返回 JSON 格式的分析结果
3. 验证标签在标签池中
4. 计算置信度

### 规则分析（回退）

当 LLM 不可用或分析失败时，使用关键词匹配：

1. 扫描内容中的关键词
2. 根据关键词匹配度选择标签
3. 提取前几句作为摘要
4. 置信度固定为 0.3-0.5

## 使用场景

### 场景 1: 自动存储 + 自动加工

```
用户: 请记住，项目使用 Python 3.11，主要框架是 FastAPI

Agent 调用:
  memory_store(
    content="项目使用 Python 3.11，主要框架是 FastAPI",
    importance=0.7
  )

自动加工结果:
  标签: [技术, 代码, 项目]
  主题: 项目技术栈
  摘要: 项目使用 Python 3.11 和 FastAPI 框架。
```

### 场景 2: 手动加工

```
用户: 帮我优化一下 mem_abc123 这条记忆的分类

Agent 调用:
  memory_process(memory_id="mem_abc123", force=true)

结果:
  记忆加工完成 (ID: mem_abc123)
  分析方法: rule
  置信度: 0.50
  标签: 代码, 技术架构
  主题: API 设计规范
  摘要: 定义了 RESTful API 的设计规范和命名约定。
```

### 场景 3: 批量处理历史记忆

```
用户: 帮我处理一下之前存储的没有分类的记忆

Agent 调用:
  memory_reprocess(limit=20)

结果:
  批量加工完成: 18 成功, 2 失败
  --- 处理详情 ---
  ✓ mem_xxx1: [工作, 项目] 主题: 项目进度
  ✓ mem_xxx2: [学习, 笔记] 主题: Python 教程
  ...
```

## 配置选项

```yaml
tool.memory-processor:
  # 基本配置
  enabled: true              # 是否启用插件
  auto_trigger: true         # 存储后自动触发加工

  # 模型配置
  model: "default"           # LLM 模型标识

  # 输出限制
  max_summary_length: 200    # 摘要最大长度（字符）
  max_topic_length: 50       # 主题最大长度（字符）
  max_tags: 5                # 最多标签数

  # 性能配置
  timeout: 30                # LLM 调用超时（秒）

  # 回退策略
  fallback_to_rules: true    # LLM 失败时回退到规则分析

  # 自定义标签池（可选）
  tag_pool:
    - "工作"
    - "项目"
    - "代码"
    - "学习"
```

## 依赖关系

```
tool.local-embeddings (嵌入插件)
        ↓
tool.long-memory (长记忆插件)
        ↓
tool.memory-processor (记忆加工插件) ← 本插件
```

## 注意事项

1. **自动触发**: 默认在每次 `memory_store` 后自动触发加工，可通过 `auto_trigger: false` 关闭

2. **性能考虑**: LLM 分析会增加约 1-3 秒延迟；规则分析几乎即时完成

3. **标签限制**: 生成的标签必须来自标签池，确保一致性

4. **重新加工**: 使用 `force=true` 可以重新加工已有标签的记忆

5. **批量限制**: 单次批量处理最多 100 条，避免超时

## 目录结构

```
long-memory/
├── models.py                      # 数据模型（含 summary 字段）
├── vector_store.py                # 向量存储（含 update 方法）
└── memory_processor/              # 记忆加工插件
    ├── __init__.py
    ├── config.py                  # 配置和标签池
    ├── llm_analyzer.py            # LLM/规则分析器
    ├── processor_engine.py        # 加工引擎
    ├── PLUGIN.py                  # 插件入口
    ├── tools/
    │   ├── __init__.py
    │   ├── process_tool.py        # 手动加工工具
    │   └── reprocess_tool.py      # 批量重加工工具
    └── tests/
        ├── __init__.py
        └── test_processor.py      # 单元测试
```

## API 参考

### ProcessorConfig

```python
@dataclass
class ProcessorConfig:
    enabled: bool = True
    auto_trigger: bool = True
    model: str = "default"
    max_summary_length: int = 200
    max_topic_length: int = 50
    max_tags: int = 5
    tag_pool: Dict[str, List[str]] = DEFAULT_TAG_POOL
    timeout: int = 30
    fallback_to_rules: bool = True
```

### AnalysisResult

```python
@dataclass
class AnalysisResult:
    tags: List[str]          # 生成的标签
    topic: str               # 生成的主题
    summary: str             # 生成的摘要
    confidence: float        # 置信度 0.0-1.0
    method: str              # 分析方法: "llm" | "rule" | "none"
```

### ProcessResult

```python
@dataclass
class ProcessResult:
    memory_id: str                  # 记忆 ID
    success: bool                   # 是否成功
    analysis: AnalysisResult        # 分析结果
    error: str                      # 错误信息
    original_entry: MemoryEntry     # 原始条目
    updated_entry: MemoryEntry      # 更新后条目
```
