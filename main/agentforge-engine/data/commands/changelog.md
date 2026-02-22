---
name: changelog
description: 分析变更并生成 CHANGELOG
alias:
  - changes
  - release-notes
category: git
tools:
  - bash
  - read
  - write
---

# 变更日志生成

分析未发布的代码变更，生成结构化的变更日志。

## 用法

```
/changelog               - 显示未发布变更摘要
/changelog patch         - 生成 patch 版本日志 (1.0.0 → 1.0.1)
/changelog minor         - 生成 minor 版本日志 (1.0.0 → 1.1.0)
/changelog major         - 生成 major 版本日志 (1.0.0 → 2.0.0)
/changelog --safe        - 评估部署安全性 (Oracle 模式)
```

## 参数

$ARGUMENTS

---

## 当前版本

!`git describe --tags --abbrev=0 2>/dev/null || echo "No tags found"`

## 最新提交

!`git log -1 --oneline`

---

## 执行步骤

### 1. 确定版本范围

```bash
# 获取最新 tag
LAST_TAG=$(git describe --tags --abbrev=0)

# 获取该 tag 以来的所有 commits
git log $LAST_TAG..HEAD --oneline

# 获取该 tag 以来的所有变更文件
git diff $LAST_TAG..HEAD --stat
```

### 2. 分析变更内容

不只是分析 commit message，还要深入分析代码变更：

```bash
# 获取详细 diff
git diff $LAST_TAG..HEAD

# 分析变更类型
- 新增功能 (feat)
- Bug 修复 (fix)
- 重构 (refactor)
- 文档更新 (docs)
- 测试变更 (test)
- 依赖更新 (deps)
- 配置变更 (config)
```

### 3. 分类变更

将变更按类型分组：

#### feat (新功能)
- 新增的 API 端点
- 新增的命令
- 新增的配置选项

#### fix (Bug 修复)
- 修复的问题
- 修复的方式
- 影响范围

#### refactor (重构)
- 代码重组
- 性能优化
- 架构改进

#### docs (文档)
- 新增的文档
- 更新的说明
- 修正的错误

#### Breaking Changes (破坏性变更)
- 不兼容的 API 变更
- 配置格式变更
- 行为变更

### 4. 推荐版本号

根据变更类型推荐版本升级：

```python
if has_breaking_changes:
    return "major"
elif has_new_features:
    return "minor"
else:
    return "patch"
```

---

## 输出格式

```markdown
## Unpublished Changes (v1.0.0 → HEAD)

### 🚀 Features

| Scope | What Changed |
|-------|--------------|
| Agent | Added support for parallel subagent execution |
| Tools | New `search` tool for code search |
| Config | Added `model.temperature` configuration |

### 🐛 Bug Fixes

| Scope | What Changed |
|-------|--------------|
| API | Fixed race condition in concurrent tool calls |
| Auth | Corrected token refresh timing |
| CLI | Fixed argument parsing for nested commands |

### 🔧 Refactoring

| Scope | What Changed |
|-------|--------------|
| Core | Migrated from callbacks to async/await |
| Utils | Consolidated duplicate utility functions |

### 📚 Documentation

| Scope | What Changed |
|-------|--------------|
| Guide | Added getting started tutorial |
| API | Updated endpoint documentation |

### ⚠️ Breaking Changes

- **Agent**: Changed `run()` signature, now returns `Result` object instead of string
- **Config**: Removed deprecated `model.name` field, use `model.model_id`

### 📦 Dependencies

- Updated `anthropic` from 0.18.0 to 0.20.0
- Added `tiktoken` for token counting

### Suggested Version Bump

- **Recommendation**: `minor`
- **Reason**: New features added, backward compatible (no breaking changes in public API)

### Stats

- **Commits**: 23
- **Files changed**: 45
- **Additions**: +1,234
- **Deletions**: -567
```

---

## Oracle 安全审查 (可选)

当用户请求 `--safe` 或 "safe to deploy" 时：

### 1. 预验证

```bash
# 运行类型检查
mypy .

# 运行测试
pytest --cov=.

# 运行 lint
pylint pyagentforge/
```

### 2. 深度分析

调用 Oracle 深度分析：
- 回归风险评估
- 副作用分析
- 边界情况
- 安全隐患

### 3. 部署建议

```markdown
## Deployment Safety Assessment

### ✅ Safe to Deploy

- All tests passing
- No type errors
- No breaking changes in public API
- Security scan clean

### ⚠️ Considerations

- New feature `parallel_subagent` needs monitoring
- Token usage may increase with new features
- Consider gradual rollout

### 📋 Pre-deployment Checklist

- [ ] Update documentation
- [ ] Notify users of new features
- [ ] Prepare rollback plan
- [ ] Monitor error rates after deploy

### Recommendation: **PROCEED WITH CONFIDENCE**
```

---

## CHANGELOG 文件更新

如果确认生成，更新 CHANGELOG.md：

```markdown
# Changelog

All notable changes to this project will be documented in this file.

## [1.1.0] - 2026-02-21

### Added
- Agent: Support for parallel subagent execution
- Tools: New `search` tool for code search
- Config: `model.temperature` configuration option

### Fixed
- API: Race condition in concurrent tool calls
- Auth: Token refresh timing
- CLI: Argument parsing for nested commands

### Changed
- Core: Migrated from callbacks to async/await
- Utils: Consolidated duplicate utility functions

### Breaking Changes
- Agent: `run()` now returns `Result` object instead of string
  - Migration: Use `result.text` to get the text output
```

---

## 注意事项

1. **准确性**: 基于 diff 分析，不只是 commit message
2. **完整性**: 包含所有重要变更
3. **可读性**: 使用清晰的表格格式
4. **实用性**: 提供版本号建议
5. **安全性**: 评估部署风险
