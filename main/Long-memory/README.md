# Long Memory Plugins

基于 ChromaDB 的长记忆系统，为 pyagentforge 提供语义搜索和持久化存储能力。

## 插件列表

### 1. embeddings (本地嵌入插件)

基于 sentence-transformers 的本地文本嵌入工具，使用 all-MiniLM-L6-v2 模型。

**功能：**
- 文本向量化（384维）
- 语义相似度计算
- 本地运行，无需API

**插件ID：** `tool.local-embeddings`

### 2. long-memory (长记忆插件)

基于 ChromaDB 的长记忆系统，提供语义搜索和持久化存储。

**功能：**
- 语义搜索记忆
- 持久化存储（ChromaDB）
- 重要性评分
- 多维度分类（类型、标签、会话）
- 统计信息

**插件ID：** `tool.long-memory`

**依赖：** `tool.local-embeddings`

## 安装

```bash
# 安装依赖
pip install chromadb>=0.4.22 sentence-transformers
```

## 配置示例

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
```

## 使用示例

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
请记住：用户偏好使用中文回答，喜欢简洁的回复风格。
""")

# 搜索记忆
result = await engine.run("搜索关于用户偏好的记忆")
```

## 目录结构

```
Long-memory/
├── embeddings/              # 本地嵌入插件
│   ├── PLUGIN.py           # 插件入口
│   ├── embeddings_provider.py
│   ├── models/             # 本地模型
│   └── README.md
│
└── long-memory/            # 长记忆插件
    ├── PLUGIN.py           # 插件入口
    ├── vector_store.py     # ChromaDB 封装
    ├── tools/              # 工具类
    │   ├── memory_store.py
    │   ├── memory_search.py
    │   ├── memory_delete.py
    │   └── memory_list.py
    ├── middleware/         # 中间件
    └── README.md
```

## 提供的工具

| 工具名 | 功能 | 插件 |
|--------|------|------|
| `embed_text` | 文本向量化 | embeddings |
| `compute_similarity` | 语义相似度计算 | embeddings |
| `memory_store` | 存储记忆 | long-memory |
| `memory_search` | 语义搜索 | long-memory |
| `memory_delete` | 删除记忆 | long-memory |
| `memory_list` | 列出/统计记忆 | long-memory |

## 版本

- embeddings: v1.0.0
- long-memory: v1.0.0

---
*Updated: 2026-02-20*
