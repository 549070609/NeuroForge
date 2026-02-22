---
name: pr
description: 管理 GitHub PR 完整工作流 (review, prepare, merge)
alias:
  - pull-request
  - review-pr
category: git
tools:
  - bash
  - read
  - edit
  - grep
---

# PR 工作流管理

管理 GitHub Pull Request 的完整生命周期。

## 用法

```
/pr review <PR号>     - 审查 PR 代码质量、测试、文档
/pr prepare <PR号>    - 准备 PR (rebase, 修复问题, 运行测试)
/pr merge <PR号>      - 安全合并 PR
```

## 当前项目

!`git remote get-url origin 2>/dev/null || echo "No remote configured"`

## 参数

$ARGUMENTS

---

## Review 阶段

当用户使用 `/pr review <PR号>` 时执行：

### 1. 获取 PR 信息
```bash
gh pr view $ARGUMENTS --json title,body,author,headRefName,baseRefName,files,additions,deletions
```

### 2. 审查清单

- [ ] **代码质量**: 检查代码风格、命名规范、注释质量
- [ ] **测试覆盖**: 是否有足够的测试用例
- [ ] **文档更新**: 相关文档是否已更新
- [ ] **Breaking Changes**: 是否有破坏性变更，是否在文档中说明
- [ ] **安全性**: 检查是否有潜在安全问题（SQL注入、XSS等）
- [ ] **性能**: 是否有明显的性能问题

### 3. 输出审查报告

生成结构化的审查报告，包含：
- PR 基本信息
- 变更文件列表
- 发现的问题（按严重程度分类）
- 改进建议
- 是否推荐合并

---

## Prepare 阶段

当用户使用 `/pr prepare <PR号>` 时执行：

### 1. 检出 PR 分支
```bash
gh pr checkout $ARGUMENTS
```

### 2. Rebase 到最新主干
```bash
git fetch origin main
git rebase origin/main
```

### 3. 运行测试
```bash
# 检测并运行测试
if [ -f "pytest.ini" ] || [ -f "pyproject.toml" ]; then
    pytest
elif [ -f "package.json" ]; then
    npm test
fi
```

### 4. 修复发现的问题
- 解决合并冲突
- 修复测试失败
- 更新过时的依赖

### 5. 推送更新
```bash
git push --force-with-lease
```

---

## Merge 阶段

当用户使用 `/pr merge <PR号>` 时执行：

### 1. 最终检查
- 确认所有 CI 检查通过
- 确认有足够的审核批准
- 确认没有合并冲突

### 2. Squash Merge
```bash
gh pr merge $ARGUMENTS --squash --delete-branch
```

### 3. 添加 Co-author (如适用)
在 commit message 中添加协作者信息：
```
Co-authored-by: Author Name <author@email.com>
```

### 4. 验证合并
```bash
gh pr view $ARGUMENTS --json state,mergedAt
```

### 5. 后续清理
- 删除功能分支
- 更新本地分支
- 通知相关人员

---

## 注意事项

1. **人工判断优先**: 技能执行前，询问用户确认关键决策
2. **安全第一**: 有疑问时，选择更安全的操作
3. **保持沟通**: 在每个阶段向用户报告进度
4. **回滚准备**: 遇到问题时，提供回滚方案
