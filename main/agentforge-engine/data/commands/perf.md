---
name: perf
description: 性能分析和优化建议
alias:
  - performance
  - profile
category: optimization
tools:
  - bash
  - read
  - grep
---

# 性能分析

分析代码性能瓶颈，提供优化建议。

## 用法

```
/perf analyze              - 分析整体性能
/perf profile script.py    - 性能分析特定脚本
/perf memory               - 内存使用分析
/perf suggest              - 优化建议
/perf benchmark            - 运行基准测试
```

## 参数

$ARGUMENTS

---

## 分析维度

### 1. 时间分析

识别执行时间的瓶颈。

#### 使用 cProfile

```bash
python -m cProfile -o output.prof script.py
```

#### 分析结果

```python
import pstats

stats = pstats.Stats("output.prof")
stats.sort_stats("cumulative")
stats.print_stats(20)  # Top 20 functions
```

#### 输出示例

```
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
      100    0.050    0.001    2.500    0.025 agent.py:45(run)
     1000    0.030    0.000    1.200    0.001 tool.py:78(execute)
      500    0.020    0.000    0.800    0.002 api.py:120(call)
```

### 2. 内存分析

识别内存使用和泄漏。

#### 使用 memory_profiler

```bash
pip install memory-profiler
python -m memory_profiler script.py
```

#### 输出示例

```
Line #    Mem usage    Increment  Occurrences   Line Contents
=============================================================
    45   125.3 MiB   125.3 MiB           1   def process_data():
    46   130.5 MiB     5.2 MiB           1       data = load_large_file()
    47   135.8 MiB     5.3 MiB           1       result = transform(data)
    48   125.4 MiB   -10.4 MiB           1       del data
```

### 3. I/O 分析

识别 I/O 瓶颈。

#### 使用 trace 模块

```bash
python -m trace --count script.py
```

#### 关注点

- 文件读写频率
- 网络请求延迟
- 数据库查询次数

---

## /perf analyze

分析整体性能：

### 1. 代码静态分析

扫描可能的性能问题：

```python
# 检测 O(n²) 复杂度
for item in items:
    if item in other_items:  # O(n) for list
        ...

# 建议优化
other_set = set(other_items)  # O(n) once
for item in items:
    if item in other_set:  # O(1) lookup
        ...
```

### 2. 热点识别

识别执行频率高的代码：

- 循环中的计算
- 频繁调用的函数
- 重复的 I/O 操作

### 3. 资源使用

分析资源使用模式：

- CPU 使用率
- 内存峰值
- I/O 等待时间

---

## /perf profile script.py

对特定脚本进行性能分析：

### 1. 运行分析器

```bash
python -m cProfile -s cumulative script.py
```

### 2. 生成火焰图（可选）

```bash
pip install py-spy
py-spy record -o flamegraph.svg -- python script.py
```

### 3. 分析输出

```markdown
## Performance Profile: script.py

### Top Time Consumers

| Function | Calls | Total Time | % |
|----------|-------|------------|---|
| `agent.run()` | 100 | 5.2s | 45% |
| `tool.execute()` | 500 | 3.1s | 27% |
| `api.call()` | 200 | 1.8s | 16% |

### Hotspots

1. **agent.py:78** - `process_response()`
   - Called 500 times
   - Average: 10ms per call
   - Optimization potential: High

2. **tool.py:120** - `validate_input()`
   - Called 1000 times
   - Average: 2ms per call
   - Could be cached

### Recommendations

1. Cache `validate_input()` results
2. Batch API calls
3. Use async for I/O operations
```

---

## /perf memory

内存使用分析：

### 1. 内存快照

```python
import tracemalloc

tracemalloc.start()

# ... your code ...

snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics("lineno")

for stat in top_stats[:10]:
    print(stat)
```

### 2. 内存泄漏检测

```python
# 比较两个快照
snapshot1 = tracemalloc.take_snapshot()
# ... operations ...
snapshot2 = tracemalloc.take_snapshot()

diff = snapshot2.compare_to(snapshot1, "lineno")
for stat in diff[:10]:
    print(stat)
```

### 3. 输出示例

```markdown
## Memory Analysis

### Top Memory Consumers

| Location | Size | Count |
|----------|------|-------|
| agent.py:45 | 15.2 MB | 1000 |
| tool.py:78 | 8.5 MB | 500 |
| cache.py:30 | 5.3 MB | 200 |

### Memory Growth

- Initial: 50 MB
- Peak: 180 MB
- Final: 85 MB
- Potential leak: 35 MB growth

### Recommendations

1. Clear cache periodically
2. Use generators instead of lists
3. Release large objects explicitly
```

---

## /perf suggest

生成优化建议：

### 1. 算法优化

```python
# Before: O(n²)
result = []
for item in items:
    for other in others:
        if item.id == other.id:
            result.append(item)

# After: O(n)
item_map = {item.id: item for item in items}
result = [item_map[other.id] for other in others if other.id in item_map]
```

### 2. 缓存策略

```python
from functools import lru_cache

@lru_cache(maxsize=128)
def expensive_computation(param):
    # This will be cached
    return result
```

### 3. 并行化

```python
from concurrent.futures import ThreadPoolExecutor

with ThreadPoolExecutor(max_workers=4) as executor:
    results = list(executor.map(process, items))
```

### 4. 懒加载

```python
# Before
class DataProcessor:
    def __init__(self):
        self.data = load_all_data()  # Expensive!

# After
class DataProcessor:
    def __init__(self):
        self._data = None

    @property
    def data(self):
        if self._data is None:
            self._data = load_all_data()
        return self._data
```

### 5. I/O 优化

```python
# Before: Multiple reads
for file in files:
    with open(file) as f:
        data = f.read()

# After: Batch reads
import aiofiles
import asyncio

async def read_all(files):
    tasks = [read_file(f) for f in files]
    return await asyncio.gather(*tasks)
```

---

## /perf benchmark

运行基准测试：

### 1. 使用 timeit

```bash
python -m timeit "from module import func; func()"
```

### 2. 自定义基准

```python
import time

def benchmark(func, iterations=1000):
    start = time.perf_counter()
    for _ in range(iterations):
        func()
    end = time.perf_counter()
    return (end - start) / iterations
```

### 3. 输出报告

```markdown
## Benchmark Results

| Operation | Average Time | Std Dev | Improvement |
|-----------|-------------|---------|-------------|
| Baseline | 15.2 ms | 0.8 ms | - |
| Optimized | 8.5 ms | 0.3 ms | 44% faster |

### Configurations Tested

1. **Baseline**: Original implementation
2. **Cached**: Added LRU cache
3. **Parallel**: Used ThreadPoolExecutor
4. **Optimized**: Final version

### Best Configuration

Use **Optimized** for best results:
- 44% faster than baseline
- Same memory usage
- Stable performance
```

---

## 性能优化检查清单

- [ ] 识别热点（profile）
- [ ] 检查算法复杂度
- [ ] 添加缓存（适当位置）
- [ ] 考虑并行化
- [ ] 优化 I/O 操作
- [ ] 检查内存使用
- [ ] 运行基准测试
- [ ] 监控生产环境

---

## 注意事项

1. **过早优化**: 不要过早优化，先保证正确性
2. **测量驱动**: 基于测量结果优化，不要猜测
3. **权衡**: 考虑可读性与性能的平衡
4. **持续监控**: 性能随时间可能退化
5. **测试覆盖**: 优化后确保测试仍然通过
