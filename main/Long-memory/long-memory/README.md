# Long Memory

基于 ChromaDB 的长记忆系统插件，为 pyagentforge 提供语义搜索和持久化存储能力。

## 功能特性

- **语义搜索**: 基于向量相似度搜索记忆，而非关键词匹配
- **持久化存储**: 使用 ChromaDB 本地持久化，重启不丢失
- **重要性评分**: 为记忆设置重要性，支持按重要性过滤
- **多维度分类**: 支持消息类型、标签、会话等多维度分类
- **统计信息**: 提供记忆系统统计和概览

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
```

## 提供的工具

### 1. memory_store

存储记忆到向量数据库。

```python
# 参数
{
    "content": "要存储的内容",
    "importance": 0.8,  # 可选，0.0-1.0，默认 0.5
    "tags": ["偏好", "设置"],  # 可选
    "message_type": "knowledge"  # 可选，默认 knowledge
}

# 返回
"已存储记忆 (ID: mem_xxx)\n内容: ...\n重要性: 0.80"
```

### 2. memory_search

语义搜索记忆。

```python
# 参数
{
    "query": "用户偏好的回复风格",
    "limit": 5,  # 可选，默认 5
    "session_filter": "session_xxx",  # 可选
    "type_filter": "knowledge",  # 可选
    "min_importance": 0.5  # 可选
}

# 返回
"找到 3 条相关记忆:\n
1. [相似度: 89.23%] 用户偏好使用中文回答...
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

列出记忆或获取统计。

```python
# 列出记忆
{
    "action": "list",
    "limit": 10,
    "offset": 0
}

# 获取统计
{
    "action": "stats"
}

# 返回
"长记忆系统统计信息
========================================
总记忆数: 25
唯一会话数: 5
平均重要性: 0.625
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
| message_type | enum | user/assistant/tool/summary/knowledge |
| source | enum | manual/auto/session |
| importance | float | 重要性 0.0-1.0 |
| tags | list | 分类标签 |
| metadata | dict | 额外信息 |

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
