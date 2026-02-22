---
name: search
description: 搜索代码库 - 查找文件、函数或文本
alias:
  - find
  - grep
category: code
tools:
  - glob
  - grep
  - read
---

# 搜索代码库

在代码库中搜索文件、代码片段或特定文本。

## 使用方式

用户输入格式：`/search [查询内容] [选项]`

示例：
- `/search TODO` - 搜索包含 TODO 的文件
- `/search def main` - 搜索 main 函数定义
- `/search *.py` - 查找所有 Python 文件

---

## 搜索任务

### 1. **理解查询意图**

分析用户输入：
- 文件名模式（包含通配符）
- 代码模式（函数名、类名）
- 文本内容（注释、字符串）

### 2. **选择搜索工具**

根据查询类型选择：
- **Glob**: 文件名模式匹配
  - `**/*.py` - 所有 Python 文件
  - `test_*.py` - 测试文件

- **Grep**: 内容搜索
  - 正则表达式支持
  - 多行匹配
  - 忽略大小写

### 3. **执行搜索**

显示搜索结果：
- 匹配的文件路径
- 匹配的行号和内容
- 上下文信息

### 4. **结果展示**

格式化输出：
```
找到 5 个匹配：

📄 src/main.py:42
  def main():
      ^^^^

📄 src/utils.py:15
  # main utility functions
```

---

## 搜索模式

### 文件搜索
```
/search *.md              # 所有 Markdown 文件
/search **/test_*.py      # 所有测试文件
/search src/**/*.py       # src 目录下的 Python 文件
```

### 代码搜索
```
/search class User        # 搜索 User 类
/search def process       # 搜索 process 函数
/search import pydantic   # 搜索导入语句
```

### 文本搜索
```
/search TODO              # 搜索 TODO 注释
/search FIXME             # 搜索 FIXME
/search ERROR             # 搜索错误信息
```

### 高级搜索
```
/search regex:TODO|FIXME  # 正则表达式
/search "exact match"     # 精确匹配
```

---

请等待用户提供搜索查询。
