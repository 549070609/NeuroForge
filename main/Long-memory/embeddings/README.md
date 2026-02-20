# Local Embeddings

基于 sentence-transformers 的本地文本嵌入模块，作为 pyagentforge 插件使用。

## 特性

- 使用 `all-MiniLM-L6-v2` 模型进行文本嵌入
- 输出 384 维向量
- 支持批量处理 (默认 batch size: 4)
- 支持语义相似度计算
- 可使用本地模型或自动下载

## 安装

### 1. 安装依赖

```bash
cd main/Long-memory/embeddings
pip install -r requirements.txt
```

### 2. 模型准备

**方式一：使用在线模型（推荐）**

首次运行时，`sentence-transformers` 会自动从 Hugging Face 下载模型。

**方式二：使用本地模型**

将模型文件复制到 `models/all-MiniLM-L6-v2/` 目录：

```bash
# 从原 TypeScript 项目复制
cp -r ../embeddings/embeddings/models/all-MiniLM-L6-v2 ./models/
```

## 在 pyagentforge 中使用

### 方式一：通过配置文件

在 `plugin_config.yaml` 中添加：

```yaml
preset: standard
enabled:
  - tool.embeddings
plugin_dirs:
  - "../Long-memory/embeddings"
config:
  tool.embeddings:
    model_path: null  # 使用默认路径或在线下载
    device: cpu       # cpu, cuda, mps
```

### 方式二：通过代码

```python
from pyagentforge import create_engine, PluginConfig
from pyagentforge.providers import AnthropicProvider
import os

plugin_config = PluginConfig(
    preset="minimal",
    enabled=["tool.embeddings"],
    plugin_dirs=["../Long-memory/embeddings"],
    config={
        "tool.embeddings": {
            "device": "cpu"
        }
    }
)

engine = await create_engine(
    provider=AnthropicProvider(api_key=os.getenv("ANTHROPIC_API_KEY")),
    plugin_config=plugin_config
)

# 使用嵌入功能
result = await engine.run("请计算 'Hello world' 和 '你好世界' 的语义相似度")
print(result)
```

## 提供的工具

### 1. embed_text

将文本转换为 384 维向量嵌入。

**参数：**
- `texts` (array): 要嵌入的文本列表
- `return_vectors` (boolean, 可选): 是否返回完整向量（默认只返回统计信息）

**示例：**
```python
# Agent 可以通过工具调用
result = await engine.run("请将 '机器学习很有趣' 这段文本转换为向量")
```

### 2. compute_similarity

计算两个文本之间的语义相似度。

**参数：**
- `text1` (string): 第一个文本
- `text2` (string): 第二个文本

**返回：**
- 0-1 之间的相似度分数（余弦相似度）

**示例：**
```python
result = await engine.run("比较 '猫是宠物' 和 '狗是家养动物' 的语义相似度")
```

## 独立使用

```python
import asyncio
from embeddings_provider import EmbeddingsProvider

async def main():
    # 创建提供者
    provider = EmbeddingsProvider(
        model_name="all-MiniLM-L6-v2",
        device="cpu"
    )

    # 生成嵌入
    texts = ["Hello world", "你好世界", "Machine learning is fascinating"]
    embeddings = await provider.embed(texts)

    print(f"生成了 {len(embeddings)} 个向量")
    print(f"每个向量维度: {len(embeddings[0])}")

    # 计算相似度
    import numpy as np
    vec1 = np.array(embeddings[0])
    vec2 = np.array(embeddings[1])
    similarity = np.dot(vec1, vec2)
    print(f"'Hello world' 和 '你好世界' 的相似度: {similarity:.4f}")

asyncio.run(main())
```

## 配置选项

| 选项 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `model_path` | string | null | 本地模型路径 |
| `model_name` | string | "all-MiniLM-L6-v2" | 模型名称 |
| `device` | string | "cpu" | 运行设备 (cpu/cuda/mps) |
| `max_batch_size` | int | 4 | 批处理大小 |

## 性能说明

- 首次加载模型可能需要几秒钟
- CPU 模式下每秒可处理约 10-50 条文本（取决于长度）
- GPU 模式可显著提升处理速度
- 建议单次处理不超过 100 条文本

## 与 TypeScript 版本的兼容性

本 Python 版本与原 TypeScript 版本完全兼容：

| 特性 | TypeScript | Python |
|------|-----------|--------|
| 模型 | all-MiniLM-L6-v2 | all-MiniLM-L6-v2 |
| 输出维度 | 384 | 384 |
| 批处理大小 | 4 | 4 |
| 归一化 | L2 归一化 | L2 归一化 |
| 向量兼容性 | ✅ 完全兼容 | ✅ 完全兼容 |

相同文本在两个版本中生成的向量完全一致，可以互操作。

## 故障排除

### 模型下载失败

如果自动下载失败，可以手动下载模型：

```bash
# 使用 huggingface-cli
pip install huggingface-hub
huggingface-cli download sentence-transformers/all-MiniLM-L6-v2 --local-dir ./models/all-MiniLM-L6-v2
```

### GPU 加速

确保安装了正确的 PyTorch CUDA 版本：

```bash
# CUDA 11.8
pip install torch --index-url https://download.pytorch.org/whl/cu118

# CUDA 12.1
pip install torch --index-url https://download.pytorch.org/whl/cu121
```

然后在配置中设置 `"device": "cuda"`。

## 许可证

MIT License
