# Local Embeddings - 快速启动指南

## 快速开始

### 1. 安装依赖

```bash
cd main/Long-memory/embeddings
pip install -r requirements.txt
```

### 2. 运行单元测试

```bash
python test_embeddings.py
```

**预期输出:**
```
==================================================
Local Embeddings 测试套件
==================================================

测试 1: 基本嵌入生成
  ✓ 生成了 3 个嵌入向量
  ✓ 每个向量维度: 384

测试 2: 空输入处理
  ✓ 空输入正确处理

...

总计: 7/7 测试通过
```

### 3. 运行插件测试

```bash
python test_plugin.py
```

**预期输出:**
```
============================================================
Local Embeddings 插件集成测试
============================================================

测试 1: 插件发现
  发现的插件目录: ['...']
  ✓ 插件发现成功

测试 2: 插件加载
  插件 ID: tool.embeddings
  ...
  ✓ 插件加载成功

...

总计: 5/5 测试通过
```

### 4. 运行示例

```bash
python examples.py
```

### 5. 在 pyagentforge 中使用

**方式一: 配置文件**

创建 `plugin_config.yaml`:
```yaml
preset: minimal
enabled:
  - tool.embeddings
plugin_dirs:
  - "../Long-memory/embeddings"
config:
  tool.embeddings:
    device: cpu
```

**方式二: 代码**

```python
from pyagentforge import create_engine, PluginConfig
from pyagentforge.providers import AnthropicProvider

plugin_config = PluginConfig(
    enabled=["tool.embeddings"],
    plugin_dirs=["../Long-memory/embeddings"],
)

engine = await create_engine(
    provider=AnthropicProvider(api_key="..."),
    plugin_config=plugin_config
)

# Agent 现在可以使用 embed_text 和 compute_similarity 工具
result = await engine.run("计算 '猫' 和 '狗' 的语义相似度")
```

## 文件说明

| 文件 | 说明 |
|------|------|
| `PLUGIN.py` | pyagentforge 插件入口 |
| `embeddings_provider.py` | 核心嵌入功能 |
| `config.py` | 配置管理 |
| `requirements.txt` | Python 依赖 |
| `test_embeddings.py` | 单元测试 |
| `test_plugin.py` | 插件集成测试 |
| `examples.py` | 使用示例 |
| `plugin_config.yaml` | 配置示例 |
| `models/` | 本地模型文件 |

## 提供的工具

### embed_text
将文本转换为 384 维向量

### compute_similarity
计算两个文本的语义相似度 (0-1)

## 常见问题

### Q: 首次运行很慢？
A: 首次加载模型需要几秒钟，之后会缓存在内存中。

### Q: 如何使用 GPU？
A: 安装 CUDA 版本的 PyTorch，然后在配置中设置 `device: cuda`。

### Q: 模型会自动下载吗？
A: 是的，如果本地没有模型，sentence-transformers 会自动从 Hugging Face 下载。

### Q: 向量维度可以改吗？
A: 维度由模型决定。all-MiniLM-L6-v2 固定输出 384 维。如需其他维度，需要换模型。

## 性能参考

- CPU (Intel i7): ~20 条文本/秒
- CPU (Apple M1): ~40 条文本/秒
- GPU (NVIDIA RTX 3080): ~200 条文本/秒

## 下一步

1. 查看 `examples.py` 了解更多用法
2. 阅读 `README.md` 获取完整文档
3. 在 pyagentforge 中实际使用插件
