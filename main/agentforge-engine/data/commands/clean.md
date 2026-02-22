---
name: clean
description: 清理 AI 生成的代码痕迹和风格不一致
alias:
  - cleanup
  - deslop
category: code
tools:
  - read
  - edit
  - grep
---

# 清理 AI 代码痕迹

检测并移除 AI 生成的代码中常见的"痕迹"，使代码更符合人类编写习惯。

## 用法

```
/clean              - 清理当前分支相对于 main 的所有更改
/clean src/         - 只清理 src 目录
/clean --dry-run    - 只显示将要清理的内容，不实际执行
```

## 参数

$ARGUMENTS

---

## 清理内容类型

### 1. 多余注释

**问题**: AI 经常添加人类不会写的注释

**清理前**:
```python
# This function processes user input
def process_data(input: str) -> str:
    # Validate the input
    if not input:
        return ""
    # Return the processed result
    return input.strip()
```

**清理后**:
```python
def process_data(input: str) -> str:
    if not input:
        return ""
    return input.strip()
```

### 2. 过度防御

**问题**: 对可信代码路径的异常防御性检查

**清理前**:
```python
def get_config(key: str) -> Any:
    try:
        config = load_config()
        if config is None:
            raise ValueError("Config is None")
        if key not in config:
            return None
        return config[key]
    except Exception as e:
        print(f"Error getting config: {e}")
        return None
```

**清理后**:
```python
def get_config(key: str) -> Any:
    config = load_config()
    return config.get(key)
```

### 3. 不必要的类型转换

**问题**: 使用 `any` 绕过类型问题

**清理前**:
```python
def process(data: any) -> any:
    result: any = transform(data)
    return result
```

**清理后**:
```python
def process(data: dict) -> dict:
    return transform(data)
```

### 4. 风格不一致

**问题**: 与文件其余部分不一致的代码风格

检查并统一：
- 命名约定（snake_case vs camelCase）
- 引号使用（单引号 vs 双引号）
- 缩进风格
- 导入顺序

### 5. 不必要的 Emoji

**问题**: 在不适合的地方使用 emoji

**清理前**:
```python
def success():
    print("✅ Operation completed successfully! 🎉")
```

**清理后**:
```python
def success():
    print("Operation completed successfully")
```

---

## 执行步骤

### 1. 确定清理范围

```bash
# 如果没有指定目录，使用 git diff 确定更改的文件
if [ -z "$ARGUMENTS" ]; then
    git diff --name-only main
else
    find $ARGUMENTS -name "*.py" -type f
fi
```

### 2. 逐文件检查

对每个文件执行：
1. 读取文件内容
2. 识别 AI 生成模式的痕迹
3. 检查与现有代码风格的一致性
4. 标记需要清理的位置

### 3. 清理并保持功能

- 移除多余注释
- 简化过度防御的代码
- 统一代码风格
- **确保功能不变**

### 4. 验证更改

```bash
# 运行测试确保功能正常
pytest
```

### 5. 总结更改

用 1-3 句话总结所有更改。

---

## 清理原则

1. **保持功能**: 清理不能改变代码行为
2. **尊重现有风格**: 与文件其余部分保持一致
3. **渐进式清理**: 不要一次性大规模重写
4. **可读性优先**: 清理后代码应该更易读

---

## 检查清单

- [ ] 移除解释显而易见逻辑的注释
- [ ] 移除与文件风格不一致的注释
- [ ] 简化不必要的 try/catch 块
- [ ] 移除对可信代码的防御性检查
- [ ] 修复使用 `any` 的类型标注
- [ ] 统一命名约定
- [ ] 统一引号风格
- [ ] 移除不合适的 emoji（除非项目风格要求）
- [ ] 运行测试确保功能正常
