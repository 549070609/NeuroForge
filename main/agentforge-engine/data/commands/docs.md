---
name: docs
description: 生成和维护项目文档
alias:
  - document
  - documentation
category: docs
tools:
  - read
  - write
  - edit
  - glob
---

# 文档生成和维护

使用最佳实践生成和维护项目文档，支持多种文档格式。

## 用法

```
/docs generate API       - 生成 API 文档
/docs check              - 检查文档链接和结构
/docs structure          - 分析文档结构
/docs update             - 更新过时文档
```

## 参数

$ARGUMENTS

---

## 文档最佳实践

### 写作原则

1. **第二人称**: 使用 "you" 而非 "the user"
2. **主动语态**: 使用主动语态，避免被动
3. **句首大写**: 使用 Sentence case，而非 Title Case
4. **先是什么再怎么用**: 先解释是什么，再说怎么用

### 避免的内容

- ❌ 营销语言（"amazing", "revolutionary"）
- ❌ 填充短语（"in order to", "basically"）
- ❌ 过度连词（"and", "but", "so" 连续使用）
- ❌ 装饰性格式（过多的粗体、颜色）

### 推荐的组件

- ✅ `<Accordion>` - 可选的详细信息
- ✅ `<Steps>` - 分步骤说明
- ✅ `<Tabs>` - 多种选项/语言
- ✅ `<CodeGroup>` - 多语言代码示例
- ✅ `<Note>` - 提示信息
- ✅ `<Warning>` - 警告信息

---

## 命令详解

### /docs generate API

生成 API 文档：

#### 1. 扫描 API 端点
```bash
# 扫描路由定义
grep -r "@app.route\|@router\|def.*endpoint" src/api/
```

#### 2. 提取文档字符串
读取每个端点的 docstring。

#### 3. 生成 OpenAPI 规范
```yaml
openapi: 3.0.0
info:
  title: API Documentation
  version: 1.0.0
paths:
  /api/agents:
    get:
      summary: List all agents
      responses:
        '200':
          description: Successful response
```

#### 4. 生成 Markdown 文档
```markdown
# API Reference

## Agents

### List Agents

GET /api/agents

List all available agents.

#### Parameters

| Name | Type | Required | Description |
|------|------|----------|-------------|
| limit | integer | No | Maximum number of results |

#### Response

```json
{
  "agents": [
    {"id": "agent-1", "name": "Helper"}
  ]
}
```
```

---

### /docs check

检查文档链接和结构：

#### 1. 检查断链
```bash
# 使用 markdown-link-check
markdown-link-check docs/**/*.md
```

#### 2. 检查结构
- 所有页面是否在导航中
- 是否有孤立页面
- 层级是否合理

#### 3. 检查代码示例
- 代码是否可运行
- 语法是否正确
- 输出是否与示例匹配

---

### /docs structure

分析文档结构：

#### 1. 生成文档树
```
docs/
├── getting-started/
│   ├── installation.md
│   ├── quickstart.md
│   └── configuration.md
├── guides/
│   ├── creating-agents.md
│   ├── using-tools.md
│   └── extending-commands.md
├── api/
│   ├── agents.md
│   ├── tools.md
│   └── commands.md
└── reference/
    ├── configuration.md
    └── cli.md
```

#### 2. 分析覆盖范围
- 是否覆盖所有功能
- 是否有重复内容
- 是否有缺失的主题

#### 3. 建议改进
- 合并重复内容
- 添加缺失文档
- 优化导航结构

---

### /docs update

更新过时文档：

#### 1. 对比代码和文档
```bash
# 检查 API 变更
git diff HEAD~10 -- src/api/ docs/api/

# 检查配置变更
git diff HEAD~10 -- src/config/ docs/reference/configuration.md
```

#### 2. 识别过时内容
- API 端点已删除但文档仍存在
- 参数已更改但文档未更新
- 代码示例已过时

#### 3. 更新文档
- 更新 API 文档
- 更新代码示例
- 更新配置说明

---

## 文档模板

### 功能文档模板

```markdown
# Feature Name

Brief description of what this feature does.

## Overview

Explain the purpose and use cases.

## Usage

### Basic Usage

```python
from package import Feature

feature = Feature()
result = feature.run()
```

### Advanced Usage

```python
feature = Feature(option="value")
result = feature.run(custom_param="value")
```

## Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| option | string | "default" | Description of option |

## Examples

### Example 1: Common Use Case

Description of the example.

```python
# Code example
```

## API Reference

### Class: Feature

#### Methods

##### run()

Execute the feature.

**Parameters:**
- `custom_param` (str, optional): Description

**Returns:**
- `Result`: Description

## Troubleshooting

### Common Issues

#### Issue 1

**Problem**: Description
**Solution**: Steps to fix

## See Also

- Related feature 1
- Related feature 2
```

---

## 文档组织原则

### 1. 渐进式披露
- 入门 → 指南 → API 参考
- 从简单到复杂
- 从常用到高级

### 2. 任务导向
- 按用户任务组织
- 不是按功能组织
- 每页一个任务

### 3. 可发现性
- 清晰的导航
- 良好的搜索
- 相关链接

### 4. 可维护性
- 单一来源原则
- 模块化结构
- 版本控制

---

## 注意事项

1. **保持更新**: 代码变更时同步更新文档
2. **代码示例**: 确保代码可运行
3. **用户视角**: 从用户角度编写
4. **简洁明了**: 避免冗长解释
5. **视觉辅助**: 适当使用图表
