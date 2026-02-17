---
name: debug
description: 调试助手 - 收集环境和错误信息
alias:
  - diagnose
category: debugging
tools:
  - bash
  - read
---

# 调试助手

收集项目环境和错误信息，帮助诊断问题。

## 环境信息
!`python --version 2>&1`
!`pip --version 2>&1`
!`which python 2>&1 || where python 2>&1`

## 项目结构
!`find . -type f -name "*.py" | head -30`

## 最近修改
!`git log --oneline -10 2>/dev/null || echo "Not a git repository"`

## 依赖检查
!`pip list 2>&1 | grep -E "(pydantic|anthropic|openai|fastapi)" || echo "No matching packages"`

---

请根据以上信息：
1. 分析可能的问题原因
2. 提供调试建议
3. 如有错误日志，分析错误信息
