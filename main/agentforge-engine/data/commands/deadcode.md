---
name: deadcode
description: 使用 LSP 验证安全地移除未使用的代码
alias:
  - unused
  - remove-dead
category: code
tools:
  - read
  - edit
  - bash
  - grep
---

# 移除死代码

使用 LSP (Language Server Protocol) 验证安全地移除项目中未使用的代码。

## 用法

```
/deadcode              - 扫描整个项目
/deadcode src/         - 只扫描 src 目录
/deadcode --dry-run    - 只显示不执行
/deadcode --check      - 只检查，不移除
```

## 参数

$ARGUMENTS

---

## 安全规则

### ⛔ 永远不要

- ❌ 永不猜测，必须 LSP 验证
- ❌ 永不移除入口点文件（main.py, __init__.py 等）
- ❌ 永不移除公开 API（除非明确确认）
- ❌ 永不跳过测试验证

### ✅ 必须遵守

- ✅ 一次移除 = 一次提交
- ✅ 失败立即回滚
- ✅ 每次移除后运行测试
- ✅ 从依赖树底部开始（叶子优先）

---

## 工作流程

### PHASE 1: 扫描

使用并行探索代理扫描项目：

```bash
# 扫描未使用的导入
autoflake --remove-all-unused-imports --check --recursive .

# 扫描未使用的代码
vulture . --exclude "tests/,migrations/"

# 使用 pyflakes
pyflakes .
```

**输出**: 候选移除列表

---

### PHASE 2: LSP 验证

使用 LSP FindReferences 验证每个候选：

```python
# 伪代码
for symbol in candidates:
    references = lsp.find_references(symbol)
    if len(references) == 0:
        mark_as_safe_to_remove(symbol)
    else:
        investigate_references(references)
```

**关键**: LSP 验证确保零误报

---

### PHASE 3: 规划移除顺序

按依赖关系排序，从叶子节点开始：

```
移除顺序:
1. utils/deprecated.py:old_function()  (无依赖)
2. services/unused.py:UnusedClass      (只被 1 依赖)
3. helpers/deprecated.py:helper()      (已被移除的函数使用)
```

---

### PHASE 4: 迭代移除循环

对每个符号执行：

```
for symbol in sorted_symbols:
    1. 移除符号
    2. 更新相关导入
    3. 运行测试
    4. 如果失败: 回滚，跳过此符号
    5. 如果成功: 提交更改
```

**提交消息格式**:
```
refactor: remove unused <symbol_type> <symbol_name>

No references found via LSP.
Verified by: find_references, pytest
```

---

### PHASE 5: 最终验证

完成所有移除后：

```bash
# 1. 全量测试
pytest --cov=.

# 2. 类型检查
mypy .

# 3. 构建
python -m build

# 4. 代码质量检查
pylint pyagentforge/
```

---

## 检测类型

### 1. 未使用的导入

```python
# 清理前
import os
import sys
from typing import List, Dict, Optional  # Optional 未使用

def func(items: List[str]) -> Dict:
    ...

# 清理后
from typing import List, Dict

def func(items: List[str]) -> Dict:
    ...
```

### 2. 未使用的函数

```python
# 清理前
def used_function():
    pass

def unused_function():  # 无任何调用
    pass

# 清理后
def used_function():
    pass
```

### 3. 未使用的类

```python
# 清理前
class UsedClass:
    pass

class UnusedClass:  # 无实例化或继承
    pass

# 清理后
class UsedClass:
    pass
```

### 4. 未使用的变量

```python
# 清理前
def process():
    used = get_data()
    unused = calculate()  # 从未读取
    return used

# 清理后
def process():
    used = get_data()
    return used
```

---

## 保留规则

即使检测为未使用，也保留：

1. **公开 API**: 导出给外部使用的函数/类
2. **入口点**: main(), setup(), pytest fixtures
3. **特殊方法**: \_\_str\_\_, \_\_repr\_\_ 等
4. **测试代码**: tests/ 目录下的代码
5. **插件接口**: 预留给插件使用的接口
6. **文档示例**: 文档中引用的代码

---

## 工具集成

### pyflakes
```bash
pyflakes src/
```

### vulture
```bash
vulture src/ --exclude "tests/"
```

### autoflake
```bash
autoflake --remove-all-unused-imports --in-place --recursive src/
```

### pylint
```bash
pylint --disable=all --enable=unused-import,unused-variable src/
```

---

## 示例输出

```
🔍 Scanning for unused code...

📋 Found 5 candidates:

  1. src/utils/deprecated.py:legacy_function()
     Risk: LOW (no references)
     Action: Safe to remove

  2. src/services/old_api.py:OldAPI class
     Risk: MEDIUM (1 reference in comment)
     Action: Investigate reference

  3. src/helpers/formatters.py:unused_import
     Risk: LOW (unused import)
     Action: Safe to remove

🔄 Proceeding with removal...

✅ Removed: src/utils/deprecated.py:legacy_function()
   Commit: abc123

⚠️  Skipped: src/services/old_api.py:OldAPI
   Reason: Referenced in migration guide

✅ Removed: unused import in src/helpers/formatters.py
   Commit: abc124

📊 Summary:
   - 3 symbols removed
   - 15 lines of code reduced
   - All tests passing
```

---

## 注意事项

1. **备份重要**: 开始前确保代码已提交或备份
2. **渐进式**: 不要一次移除太多
3. **测试覆盖**: 确保有足够的测试
4. **团队沟通**: 移除公开 API 前与团队确认
5. **文档同步**: 移除功能时更新文档
