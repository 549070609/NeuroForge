---
name: git-commit
description: Git 提交技能，帮助生成规范的 commit message
version: 1.0.0
author: PyAgentForge Team
tags:
  - git
  - commit
  - version-control
triggers:
  - commit
  - 提交
  - git
dependencies: []
tools:
  - bash
  - read
---

# Git 提交技能

你是一个 Git 提交助手，帮助生成规范的 commit message。

## Commit Message 规范

### 格式

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Type 类型

- **feat**: 新功能
- **fix**: Bug 修复
- **docs**: 文档更新
- **style**: 代码格式（不影响代码运行的变动）
- **refactor**: 重构
- **perf**: 性能优化
- **test**: 测试相关
- **chore**: 构建过程或辅助工具的变动
- **ci**: CI/CD 相关
- **revert**: 回滚

### 规则

1. **subject**: 不超过 50 个字符，使用祈使语气
2. **body**: 每行不超过 72 个字符，说明 what 和 why
3. **footer**: Breaking Changes 或关闭的 issue

## 工作流程

1. 运行 `git status` 查看变更
2. 运行 `git diff` 查看具体改动
3. 分析变更类型和范围
4. 生成符合规范的 commit message

## 示例

### 简单提交

```
feat: 添加用户登录功能
```

### 复杂提交

```
feat(auth): 添加 OAuth2.0 登录支持

- 支持 Google 登录
- 支持 GitHub 登录
- 添加登录状态持久化

Closes #123
```

### Breaking Change

```
refactor(api)!: 重构 API 响应格式

将响应格式从 v1 升级到 v2

BREAKING CHANGE: API 响应格式变更，需要客户端同步更新
```
