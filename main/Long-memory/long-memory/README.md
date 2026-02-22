# Long Memory

基于 ChromaDB 的长记忆系统插件，为 pyagentforge 提供语义搜索和持久化存储能力。

## 功能特性

- **双模式搜索**: 支持精准匹配和模糊语义搜索两种模式
- **持久化存储**: 使用 ChromaDB 本地持久化，重启不丢失
- **重要性评分**: 为记忆设置重要性，支持按重要性过滤
- **多维度分类**: 支持消息类型、标签、会话等多维度分类
- **统计信息**: 提供记忆系统统计和概览

## 搜索模式

### 模糊模式 (fuzzy) - 默认
基于语义相似度的向量搜索，理解查询的含义而非字面匹配。

```python
# 查询 "用户喜欢什么" 能匹配 "我爱吃苹果"
{
    "query": "用户喜欢什么",
    "mode": "fuzzy"  # 或省略，默认为 fuzzy
}
```

**适用场景:**
- 查找相关主题的记忆
- 理解性查询
- 不确定具体关键词时

### 精准模式 (exact)
关键词/文本精确匹配，文档必须包含查询词。

```python
# 查询 "API_KEY" 只匹配包含 "API_KEY" 的记忆
{
    "query": "API_KEY",
    "mode": "exact"
}
```

**适用场景:**
- 查找特定代码片段
- 查找配置值、密钥名
- 精确词句查找

## 依赖

- `tool.local-embeddings` 插件（提供嵌入向量生成）
- `chromadb>=0.4.22`

## 安装

```bash
# 安装依赖
pip install chromadb>=0.4.22

# 确保 local-embeddings 插件已安装
```

## 配置

```yaml
# plugin_config.yaml
enabled:
  - tool.local-embeddings
  - tool.long-memory

plugin_dirs:
  - "./main/Long-memory/embeddings"
  - "./main/Long-memory/long-memory"

config:
  tool.local-embeddings:
    device: cpu

  tool.long-memory:
    persist_directory: "./data/chroma"
    collection_name: "long_memory"
    default_search_limit: 5
    max_search_limit: 50
    default_search_mode: "fuzzy"  # 或 "exact"
    exact_match_threshold: 0.95   # 精准模式的基础匹配分数
```

## 提供的工具

### 1. memory_store

存储记忆到向量数据库，支持设置主题和标签。

```python
# 参数
{
    "content": "要存储的内容",
    "topic": "用户偏好",         # 可选，记忆主题
    "importance": 0.8,          # 可选，0.0-1.0，默认 0.5
    "tags": ["偏好", "设置"],    # 可选，分类标签
    "message_type": "knowledge" # 可选，默认 knowledge
}

# 返回
"已存储记忆 (ID: mem_xxx)
主题: 用户偏好
内容: ...
重要性: 0.80
标签: 偏好, 设置"
```

### 2. memory_search

搜索记忆，支持精准和模糊两种模式。

```python
# 模糊搜索（语义相似度）
{
    "query": "用户偏好的回复风格",
    "mode": "fuzzy",  # 可选，默认 fuzzy
    "limit": 5,
    "min_importance": 0.5
}

# 精准搜索（关键词匹配）
{
    "query": "API_KEY",
    "mode": "exact",
    "limit": 10
}

# 返回
"找到 3 条相关记忆 (语义相似):

1. [匹配度: 89.23%] 用户偏好使用中文回答...
   ID: mem_xxx | 类型: knowledge | 重要性: 0.80
..."
```

### 3. memory_delete

删除记忆。

```python
# 参数
{
    "memory_ids": ["mem_xxx"],  # 按ID删除
    # 或
    "session_filter": "session_xxx",  # 按会话删除
    "confirm": true  # 必须为 true
}
```

### 4. memory_list

列出记忆、获取统计、或按条件组合召回。

```python
# 列出记忆（简单分页）
{
    "action": "list",
    "limit": 10,
    "offset": 0
}

# 获取统计（包含主题和标签统计）
{
    "action": "stats"
}

# 按条件组合召回（核心功能）
# 支持标签、主题、时间的任意组合
{
    "action": "recall",
    "tags": ["代码", "Python"],           # 匹配任意一个标签
    "topic": "项目配置",                  # 精确匹配主题
    "time_range": "最近7天",              # 时间范围
    "limit": 10
}

# 时间范围支持格式：
# - 相对时间: "今天", "昨天", "最近7天", "最近30天", "本周", "本月"
# - 日期范围: "2024-01-01~2024-12-31"
# - 单个日期: "2024-01-15"

# 返回示例
"召回记忆 (共 5 条，显示 5 条)
过滤条件: 标签: 代码, Python | 主题: 项目配置 | 时间: 最近7天

1. 项目使用 Python 3.11，主要依赖是...
   ID: mem_xxx | 主题: 项目配置 | 重要性: 0.80 | 2024-02-15
   标签: 代码, Python, 配置
..."
```

## 数据模型

### MemoryEntry

| 字段 | 类型 | 描述 |
|------|------|------|
| id | string | 唯一标识 `mem_xxx` |
| content | string | 记忆内容 |
| timestamp | ISO8601 | 存储时间 |
| session_id | string | 会话 ID |
| topic | string | 记忆主题（用于分类和召回） |
| message_type | enum | user/assistant/tool/summary/knowledge |
| source | enum | manual/auto/session |
| importance | float | 重要性 0.0-1.0 |
| tags | list | 分类标签 |
| metadata | dict | 额外信息 |

### MemoryStats

| 字段 | 类型 | 描述 |
|------|------|------|
| total_count | int | 总记忆数 |
| by_type | dict | 按类型统计 |
| by_source | dict | 按来源统计 |
| by_topic | dict | 按主题统计 |
| by_tag | dict | 按标签统计 |
| avg_importance | float | 平均重要性 |
| oldest_timestamp | string | 最早记忆时间 |
| newest_timestamp | string | 最新记忆时间 |
| unique_sessions | int | 唯一会话数 |

## 使用示例

### Python API

```python
from pyagentforge import create_engine, PluginConfig

config = PluginConfig(
    enabled=["tool.local-embeddings", "tool.long-memory"],
    plugin_dirs=[
        "../Long-memory/embeddings",
        "../Long-memory/long-memory"
    ]
)

engine = await create_engine(provider=..., plugin_config=config)

# 存储记忆
result = await engine.run("""
请记住：用户偏好使用中文回答，喜欢简洁的回复风格，并且不喜欢太长的解释。
""")

# 搜索记忆
result = await engine.run("搜索关于用户偏好的记忆")
```

### Agent 使用

Agent 可以通过工具调用来使用长记忆：

```
用户: 请记住，我的项目路径是 /home/user/projects

Agent: [调用 memory_store 工具]
已存储记忆。您的项目路径设置已保存到长记忆中。

用户: 我的项目路径是什么？

Agent: [调用 memory_search 工具]
根据记忆，您的项目路径是 /home/user/projects。
```

## 架构

```
+------------------------------------------+
|            pyagentforge                   |
+------------------------------------------+
        |                    |
        v                    v
+----------------+    +---------------------+
| local-embeddings|    |  long-memory   |
| (嵌入插件)      |    |    (本插件)          |
+----------------+    +---------------------+
        |                    |
        v                    v
+----------------+    +---------------------+
|EmbeddingsProvider   |  ChromaVectorStore  |
| all-MiniLM-L6-v2    |  (ChromaDB)         |
+----------------+    +---------------------+
                              |
                              v
                      +---------------------+
                      |  Persistent Storage |
                      |  ./data/chroma/     |
                      +---------------------+
```

## 注意事项

1. **嵌入插件依赖**: 必须先加载 `tool.local-embeddings` 插件
2. **存储空间**: ChromaDB 会在本地创建持久化存储，注意磁盘空间
3. **删除不可逆**: 删除操作无法恢复，请谨慎使用
4. **性能**: 大量记忆可能影响搜索性能，建议定期清理

## License

MIT
