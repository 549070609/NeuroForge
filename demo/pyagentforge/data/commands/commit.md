---
name: commit
description: Git 提交 - 自动分析更改并生成 commit message
alias:
  - git-commit
  - ci
category: git
tools:
  - bash
  - read
  - glob
  - grep
---

# Git Commit 命令

请帮我完成 Git 提交。以下是当前仓库的状态：

## 当前 Git 状态
!`git status --short`

## 未暂存的更改
!`git diff`

## 已暂存的更改
!`git diff --cached`

## 最近提交记录
!`git log --oneline -5`

## 当前分支
!`git branch --show-current`

---

请根据以上信息：
1. 分析更改的内容和目的
2. 生成符合 Conventional Commits 规范的 commit message
3. 执行 `git add` 和 `git commit` 命令

Commit message 格式要求：
- 使用中文描述
- 格式：`<type>(<scope>): <description>`
- type: feat/fix/docs/style/refactor/test/chore
