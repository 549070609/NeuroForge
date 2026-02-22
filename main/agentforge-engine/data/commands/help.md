---
name: help
description: 显示帮助信息和可用命令列表
alias:
  - h
  - ?
  - commands
category: basic
tools:
  - bash
---

# 显示帮助信息

显示系统的帮助信息、可用命令列表和使用指南。

## 系统信息

Python 版本: !`python --version 2>&1`
当前目录: !`pwd`

---

## 帮助内容

请提供以下信息：

### 1. **可用命令列表**

显示所有已注册的命令，包括：
- 命令名称和别名
- 命令描述
- 使用示例

格式示例：
```
/commit (别名: git-commit, ci) - Git 提交，自动生成 commit message
/debug (别名: diagnose) - 调试助手，收集环境和错误信息
/review (别名: code-review, cr) - 代码审查
/test (别名: pytest, run-tests) - 运行测试
/new (别名: start, begin) - 开始新任务
/clear (别名: cls, reset) - 清空对话历史
/help (别名: h, ?) - 显示帮助信息
```

### 2. **基本用法**

说明如何使用命令：
- 命令格式：`/命令名 [参数]`
- 示例：`/commit`, `/test`, `/help`

### 3. **工具列表**

列出当前可用的工具（如 bash, read, write, edit 等）

### 4. **快捷提示**

提供一些使用技巧和最佳实践

---

请以清晰、结构化的方式显示帮助信息。
