---
name: issues
description: 搜索和查找 GitHub Issues
alias:
  - issue
  - find-issue
category: git
tools:
  - bash
---

# 搜索 GitHub Issues

使用 GitHub CLI 搜索项目中的 issues。

## 用法

```
/issues [查询内容]        - 搜索匹配的 issues
/issues "error message"   - 搜索包含错误信息的 issues
/issues --label bug       - 搜索标签为 bug 的 issues
/issues --similar         - 查找相似问题
```

## 当前项目

!`git remote get-url origin 2>/dev/null || echo "No remote configured"`

## 当前分支

!`git branch --show-current`

## 查询内容

$ARGUMENTS

---

## 执行搜索

### 基础搜索
```bash
gh issue list --search "$ARGUMENTS" --state open --limit 20 --json number,title,state,labels,url,createdAt,updatedAt
```

### 按标签搜索
如果参数中包含 `--label`，提取标签名并搜索：
```bash
gh issue list --label "<标签名>" --state open --limit 20 --json number,title,state,url
```

### 查找相似问题
如果参数中包含 `--similar`，基于当前分支名或最近 commit 搜索相关问题。

---

## 输出格式

将搜索结果格式化为表格：

| Issue # | 标题 | 标签 | 状态 | 创建时间 | 链接 |
|---------|------|------|------|----------|------|
| #123 | Bug: Login fails | bug, high-priority | open | 2026-02-15 | [查看](url) |

---

## 搜索技巧

1. **关键词搜索**: 使用引号包裹精确短语
   ```
   /issues "Connection refused"
   ```

2. **标签过滤**: 使用 `--label` 参数
   ```
   /issues --label bug
   /issues --label enhancement
   ```

3. **组合搜索**: 组合多个条件
   ```
   /issues "memory leak" --label bug
   ```

4. **查找相似**: 查找与当前工作相关的问题
   ```
   /issues --similar
   ```

---

## 注意事项

- 需要 `gh` CLI 工具已安装并登录
- 需要有仓库的读取权限
- 搜索结果限制为最近 20 个
- 可以点击链接直接跳转到 GitHub
