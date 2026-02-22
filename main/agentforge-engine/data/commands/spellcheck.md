---
name: spellcheck
description: 检查 Markdown 文件的拼写和语法错误
alias:
  - spell
  - grammar
category: docs
tools:
  - read
  - grep
---

# Markdown 拼写和语法检查

检查 Markdown 文件中的拼写和语法错误，特别关注未暂存的更改。

## 用法

```
/spellcheck              - 检查所有未暂存的 .md/.mdx 文件
/spellcheck docs/        - 检查 docs 目录下的文件
/spellcheck --all        - 检查所有 Markdown 文件
/spellcheck README.md    - 检查特定文件
```

## 参数

$ARGUMENTS

---

## 检查范围

### 默认行为（无参数）
检查 git diff 中未暂存的 Markdown 文件：
```bash
git diff --name-only --diff-filter=d | grep -E '\.(md|mdx)$'
```

### 指定目录
检查指定目录下的所有 Markdown 文件。

### --all 标志
检查整个项目中的所有 Markdown 文件。

---

## 检查类型

### 1. 拼写检查

使用 cspell 或类似工具检查常见拼写错误。

**常见问题**:
- teh → the
- recieve → receive
- occured → occurred
- seperately → separately
- enviroment → environment

### 2. 语法检查

使用 markdownlint 检查 Markdown 语法：

- 标题层级是否正确
- 列表格式是否一致
- 代码块是否有语言标识
- 链接是否有效

### 3. 敏感性检查

使用 alex 检查可能不敏感的用词：

- gender-inclusive language
- ableist language
- insensitive phrases

### 4. 写作风格

使用 write-good 检查写作风格：

- 被动语态
- 冗余短语
- 模糊语言

---

## 执行步骤

### 1. 确定检查文件

根据参数确定要检查的文件列表。

### 2. 提取更改内容

如果检查未暂存的更改：
```bash
git diff --unified=0 <file> | grep "^+" | grep -v "^+++"
```

### 3. 运行检查

对每个文件运行：
1. 拼写检查
2. 语法检查
3. 敏感性检查
4. 风格检查

### 4. 生成报告

输出格式：
```
📄 README.md

  ❌ Spelling (line 15)
     "recieve" → "receive"

  ⚠️  Grammar (line 23)
     Missing language identifier for code block

  💡 Style (line 42)
     Consider replacing "very important" with "important"

---
📊 Summary: 3 files checked, 5 issues found
```

---

## 集成工具建议

### cspell
```bash
# 安装
npm install -g cspell

# 使用
cspell "**/*.md"
```

### markdownlint
```bash
# 安装
npm install -g markdownlint-cli

# 使用
markdownlint **/*.md
```

### alex
```bash
# 安装
npm install -g alex

# 使用
alex *.md
```

### write-good
```bash
# 安装
npm install -g write-good

# 使用
write-good *.md
```

---

## 配置文件

可以在项目根目录创建配置文件：

### .cspell.json
```json
{
  "version": "0.2",
  "language": "en",
  "words": ["pyagentforge", "openclaw", "opencode"],
  "ignorePaths": ["node_modules", "dist"]
}
```

### .markdownlint.json
```json
{
  "default": true,
  "MD013": false,
  "MD033": false
}
```

---

## 自定义词典

对于项目特有的术语，可以添加到自定义词典：

```json
{
  "words": [
    "PyAgentForge",
    "OpenClaw",
    "OpenCode",
    "subagent",
    "toolcalling"
  ]
}
```

---

## 忽略规则

使用注释忽略特定行：

```markdown
<!-- cspell:disable -->
This text won't be spell checked.
<!-- cspell:enable -->

<!-- markdownlint-disable MD013 -->
This long line will not trigger a warning.
<!-- markdownlint-enable MD013 -->
```

---

## 注意事项

1. 优先修复实际问题，而非风格建议
2. 对于技术术语，添加到自定义词典
3. 某些规则可能不适合所有文件
4. 保持文档的可读性优先于完美通过检查
