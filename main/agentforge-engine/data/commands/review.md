---
name: review
description: 代码审查 - 审查当前更改
alias:
  - code-review
  - cr
category: code
tools:
  - read
  - glob
  - grep
---

# 代码审查

请对当前更改进行代码审查。

## Git 差异
!`git diff HEAD`

## 更改的文件
!`git diff HEAD --name-only`

---

请审查以上更改并提供：

1. **代码质量评估**
   - 代码可读性
   - 命名规范
   - 注释完整性

2. **潜在问题**
   - Bug 或逻辑错误
   - 性能问题
   - 安全隐患

3. **改进建议**
   - 重构建议
   - 最佳实践

4. **总体评分**
   - 给出 1-10 分的评分
