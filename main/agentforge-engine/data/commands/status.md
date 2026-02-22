---
name: status
description: 显示当前项目状态和环境信息
alias:
  - info
  - env
category: basic
tools:
  - bash
  - read
---

# 显示项目状态

收集并显示当前项目的状态信息。

## 环境信息

操作系统: !`uname -s 2>/dev/null || echo "Windows"`
当前用户: !`whoami 2>/dev/null || echo "unknown"`
当前目录: !`pwd`

## Git 状态

!`git status --short 2>/dev/null || echo "Not a git repository"`
当前分支: !`git branch --show-current 2>/dev/null || echo "N/A"`
最近提交: !`git log --oneline -3 2>/dev/null || echo "No commits"`

## Python 环境

Python 版本: !`python --version 2>&1`
pip 版本: !`pip --version 2>&1`
虚拟环境: !`echo $VIRTUAL_ENV 2>/dev/null || echo "Not active"`

## 项目结构

!`ls -la | head -15`

## 依赖检查

!`test -f requirements.txt && echo "✓ requirements.txt found" || echo "✗ No requirements.txt"`
!`test -f pyproject.toml && echo "✓ pyproject.toml found" || echo "✗ No pyproject.toml"`
!`test -f setup.py && echo "✓ setup.py found" || echo "✗ No setup.py"`

---

请根据以上信息：

1. **汇总环境状态**
   - 操作系统和 Python 版本
   - Git 仓库状态
   - 项目类型识别

2. **识别潜在问题**
   - 未提交的更改
   - 缺失的配置文件
   - 环境配置问题

3. **提供状态总结**
   - 项目是否处于可工作状态
   - 是否需要执行特定操作
   - 下一步建议
