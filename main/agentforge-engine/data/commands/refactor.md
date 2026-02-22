---
name: refactor
description: 智能重构代码助手
alias:
  - restructure
category: code
tools:
  - read
  - edit
  - bash
  - grep
  - glob
---

# 代码重构助手

智能识别重构机会，提供安全的重构方案。

## 用法

```
/refactor suggest              - 建议重构机会
/refactor rename Old New       - 重命名符号
/refactor extract-method file.py  - 提取方法
/refactor move file.py dest/   - 移动文件并更新引用
/refactor inline file.py       - 内联变量/方法
```

## 参数

$ARGUMENTS

---

## 重构类型

### 1. 提取重构 (Extract)

#### 提取方法

将代码片段提取为独立方法：

**重构前**:
```python
def process_order(order):
    # 验证逻辑
    if not order.items:
        raise ValueError("Empty order")
    if order.total < 0:
        raise ValueError("Invalid total")

    # 计算逻辑
    subtotal = sum(item.price * item.quantity for item in order.items)
    tax = subtotal * 0.1
    total = subtotal + tax

    return total
```

**重构后**:
```python
def process_order(order):
    validate_order(order)
    return calculate_total(order)

def validate_order(order):
    if not order.items:
        raise ValueError("Empty order")
    if order.total < 0:
        raise ValueError("Invalid total")

def calculate_total(order):
    subtotal = sum(item.price * item.quantity for item in order.items)
    tax = subtotal * 0.1
    return subtotal + tax
```

#### 提取变量

将复杂表达式提取为变量：

**重构前**:
```python
if platform.system() == "Windows" and sys.version_info >= (3, 8):
    # ...
```

**重构后**:
```python
is_windows = platform.system() == "Windows"
is_python_38_plus = sys.version_info >= (3, 8)

if is_windows and is_python_38_plus:
    # ...
```

#### 提取常量

将魔法数字提取为命名常量：

**重构前**:
```python
time.sleep(300)  # What does 300 mean?
```

**重构后**:
```python
RETRY_DELAY_SECONDS = 300  # 5 minutes

time.sleep(RETRY_DELAY_SECONDS)
```

---

### 2. 内联重构 (Inline)

#### 内联变量

将只使用一次的变量内联：

**重构前**:
```python
result = calculate()
return result
```

**重构后**:
```python
return calculate()
```

#### 内联方法

将简单方法内联到调用处：

**重构前**:
```python
def is_valid(value):
    return value is not None and value > 0

def process(data):
    if is_valid(data):
        ...
```

**重构后**:
```python
def process(data):
    if data is not None and data > 0:
        ...
```

---

### 3. 移动重构 (Move)

#### 移动文件

移动文件并更新所有引用：

```bash
/refactor move utils/old.py helpers/new.py
```

会自动：
1. 移动文件
2. 更新所有导入语句
3. 更新相对导入路径

#### 移动类/函数

将类或函数移动到更合适的模块：

**重构前** (`utils.py`):
```python
class DatabaseHelper:
    pass
```

**重构后** (`database.py`):
```python
class DatabaseHelper:
    pass
```

更新所有导入：
```python
# 旧的导入
from utils import DatabaseHelper

# 新的导入
from database import DatabaseHelper
```

---

### 4. 重命名重构 (Rename)

#### 重命名符号

全局重命名并更新所有引用：

```bash
/refactor rename old_function new_function
/refactor rename OldClass NewClass
/refactor rename OLD_CONSTANT NEW_CONSTANT
```

**执行步骤**:
1. 搜索所有引用
2. 确认每个引用
3. 批量替换
4. 运行测试验证

---

## /refactor suggest

自动识别重构机会：

### 1. 代码异味检测

检测常见的代码异味：

- **长方法**: 超过 50 行的方法
- **重复代码**: 相似的代码块
- **过大类**: 超过 500 行的类
- **过长参数列表**: 超过 4 个参数
- **魔法数字**: 未命名的常量
- **深层嵌套**: 超过 3 层的嵌套

### 2. 建议输出

```markdown
## Refactoring Opportunities

### High Priority

1. **Long Method**: `src/core/agent.py:run()` (127 lines)
   - Suggestion: Extract `plan()`, `execute()`, `verify()` methods
   - Benefit: Improved readability and testability

2. **Duplicated Code**: Similar validation logic in 3 places
   - Locations: `auth.py:15-25`, `user.py:30-40`, `admin.py:20-30`
   - Suggestion: Extract `validate_input()` method
   - Benefit: DRY principle, easier maintenance

### Medium Priority

3. **Large Class**: `src/models/agent.py:Agent` (520 lines)
   - Suggestion: Split into `Agent`, `AgentConfig`, `AgentState`
   - Benefit: Single responsibility principle

4. **Magic Numbers**: 5 occurrences
   - Example: `timeout = 300` → `timeout = DEFAULT_TIMEOUT_SECONDS`
   - Benefit: Self-documenting code

### Low Priority

5. **Deep Nesting**: `src/utils/parser.py:parse()` (4 levels)
   - Suggestion: Use early returns or guard clauses
   - Benefit: Improved readability
```

---

## 安全重构原则

### 1. 小步重构

- 一次只做一个小改动
- 每次改动后运行测试
- 频繁提交

### 2. 测试驱动

- 重构前确保有测试
- 重构后运行所有测试
- 使用覆盖率工具

### 3. 保持功能

- 重构不改变行为
- 只改变代码结构
- 不做功能变更

### 4. 工具辅助

- 使用 IDE 重构功能
- 使用 LSP 进行引用查找
- 使用版本控制便于回滚

---

## 重构工作流

```
1. 识别重构机会
   ↓
2. 确保测试覆盖
   ↓
3. 执行重构
   - 小步骤
   - 每步后测试
   ↓
4. 验证功能不变
   ↓
5. 提交更改
```

---

## 注意事项

1. **测试覆盖**: 重构前确保有足够的测试
2. **渐进式**: 不要一次性大规模重构
3. **可回滚**: 每个重构步骤都应该是可回滚的
4. **团队沟通**: 重大重构需要与团队沟通
5. **性能影响**: 某些重构可能影响性能，需要评估
