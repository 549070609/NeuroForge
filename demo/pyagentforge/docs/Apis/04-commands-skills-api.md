# PyAgentForge 命令与技能系统 API 文档

> **版本:** v2.0.0
> **最后更新:** 2026-02-17

本文档详细说明 PyAgentForge 的命令 (Command) 和技能 (Skill) 系统。

---

## 目录

- [1. 命令系统概述](#1-命令系统概述)
- [2. Command 数据模型](#2-command-数据模型)
- [3. CommandLoader - 命令加载器](#3-commandloader---命令加载器)
- [4. 命令语法](#4-命令语法)
- [5. 技能系统概述](#5-技能系统概述)
- [6. Skill 数据模型](#6-skill-数据模型)
- [7. SkillLoader - 技能加载器](#7-skillloader---技能加载器)
- [8. 技能文件格式](#8-技能文件格式)
- [9. 使用示例](#9-使用示例)

---

## 1. 命令系统概述

命令系统允许用户定义可重用的提示词模板，支持动态内容注入和参数化执行。

**核心特性:**
- Markdown 文件格式
- YAML Front Matter 元数据
- 动态命令注入 (`!`cmd`` 语法)
- 命令别名支持
- 分类管理

**文件位置:** `data/commands/*.md`

---

## 2. Command 数据模型

### 2.1 CommandMetadata

**位置:** `pyagentforge.commands.models.CommandMetadata`

命令元数据，定义命令的基本信息和配置。

```python
class CommandMetadata(BaseModel):
    """命令元数据"""

    name: str = Field(..., description="命令名称 (不含 / 前缀)")
    description: str = Field(..., description="命令描述")
    version: str = Field(default="1.0.0", description="版本号")
    author: str = Field(default="", description="作者")

    # 命令配置
    alias: list[str] = Field(default_factory=list, description="命令别名")
    category: str = Field(default="general", description="命令分类")

    # 工具权限
    tools: list[str] = Field(
        default_factory=lambda: ["*"],
        description="允许使用的工具",
    )

    # 执行配置
    timeout: int = Field(default=300, description="超时时间 (秒)")
    confirm: bool = Field(default=False, description="执行前是否需要确认")

    # 提示词配置
    model: str | None = Field(default=None, description="指定使用的模型")
    temperature: float | None = Field(default=None, description="温度参数")
    max_tokens: int | None = Field(default=None, description="最大输出 token")
```

**参数说明:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `name` | `str` | **必需** | 命令名称 (不含 / 前缀) |
| `description` | `str` | **必需** | 命令描述 |
| `version` | `str` | `"1.0.0"` | 版本号 |
| `author` | `str` | `""` | 作者 |
| `alias` | `list[str]` | `[]` | 命令别名列表 |
| `category` | `str` | `"general"` | 命令分类 |
| `tools` | `list[str]` | `["*"]` | 允许使用的工具 |
| `timeout` | `int` | `300` | 超时时间 (秒) |
| `confirm` | `bool` | `False` | 执行前是否需要确认 |
| `model` | `str \| None` | `None` | 指定使用的模型 |
| `temperature` | `float \| None` | `None` | 温度参数 |
| `max_tokens` | `int \| None` | `None` | 最大输出 token |

---

### 2.2 Command

**位置:** `pyagentforge.commands.models.Command`

命令模型，包含元数据和内容。

```python
class Command(BaseModel):
    """命令模型"""

    metadata: CommandMetadata
    body: str = Field(..., description="命令内容 (Markdown, 支持动态命令注入)")
    path: Path | None = Field(default=None, description="命令文件路径")

    class Config:
        arbitrary_types_allowed = True
```

#### 方法

##### `get_full_content()`

```python
def get_full_content(self) -> str
```

获取完整内容 (用于注入到上下文)。

**返回值:** `str` - 格式化的命令内容

---

##### `get_description_for_prompt()`

```python
def get_description_for_prompt(self) -> str
```

获取用于系统提示词的描述。

**返回值:** `str` - 命令描述字符串

---

##### `name` (属性)

```python
@property
def name(self) -> str
```

获取命令名称。

---

##### `all_names` (属性)

```python
@property
def all_names(self) -> list[str]
```

获取所有可用的命令名称 (包括别名)。

---

## 3. CommandLoader - 命令加载器

**位置:** `pyagentforge.commands.loader.CommandLoader`

扫描和加载命令目录。

### 构造函数

```python
def __init__(
    self,
    commands_dir: Path | None = None,
    parser: CommandParser | None = None,
    dynamic_executor: DynamicCommandExecutor | None = None,
) -> None
```

**参数说明:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `commands_dir` | `Path \| None` | `None` | 命令目录 |
| `parser` | `CommandParser \| None` | `None` | 命令解析器 |
| `dynamic_executor` | `DynamicCommandExecutor \| None` | `None` | 动态命令执行器 |

---

### 方法

#### `load_all()`

```python
def load_all(self, inject_dynamic: bool = True) -> dict[str, Command]
```

加载所有命令。

**参数:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `inject_dynamic` | `bool` | `True` | 是否注入动态命令 |

**返回值:** `dict[str, Command]` - 命令名称到命令对象的映射

---

#### `load_all_async()`

```python
async def load_all_async(self, inject_dynamic: bool = True) -> dict[str, Command]
```

异步加载所有命令 (支持并行解析)。

---

#### `get()`

```python
def get(self, name: str) -> Command | None
```

获取命令。

**参数:**

| 参数 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | 命令名称 (可以有或没有 / 前缀) |

**返回值:** `Command | None` - 命令对象或 None

---

#### `get_command_content()`

```python
def get_command_content(self, name: str, inject_dynamic: bool = False) -> str
```

获取命令内容 (用于注入到上下文)。

**返回值:** `str` - 格式化的命令内容

---

#### `get_descriptions()`

```python
def get_descriptions(self) -> str
```

获取所有命令的描述 (用于系统提示词)。

**返回值:** `str` - 命令描述列表

---

#### `match_command()`

```python
def match_command(self, text: str) -> Command | None
```

从文本中匹配命令。

**参数:**

| 参数 | 类型 | 说明 |
|------|------|------|
| `text` | `str` | 用户输入文本 (如 "/commit") |

**返回值:** `Command | None` - 匹配的命令或 None

---

#### `reload()`

```python
def reload(self, inject_dynamic: bool = True) -> dict[str, Command]
```

重新加载所有命令。

---

## 4. 命令语法

### 4.1 命令文件格式

命令文件使用 Markdown 格式，包含 YAML Front Matter:

```markdown
---
name: commit
description: 创建 Git 提交
version: 1.0.0
alias:
  - ci
category: git
tools:
  - bash
  - read
  - write
timeout: 120
confirm: false
---

# Commit 命令

请按照以下步骤创建 Git 提交:

1. 检查当前状态: !`git status --short`
2. 查看变更: !`git diff`
3. 编写提交信息并提交
```

---

### 4.2 动态命令注入

使用 `!`cmd`` 语法在命令内容中嵌入 Shell 命令:

```markdown
当前分支: !`git branch --show-current`

最近的提交:
!`git log --oneline -5`

请分析以上信息并提供建议。
```

**执行时机:** 命令加载时执行，结果替换命令文本。

---

## 5. 技能系统概述

技能系统提供领域知识的按需加载机制，通过触发关键词自动注入相关上下文。

**核心特性:**
- Markdown 文件格式 (SKILL.md)
- YAML Front Matter 元数据
- 触发关键词匹配
- 技能依赖管理
- 按需加载

**文件位置:** `data/skills/{skill_name}/SKILL.md`

---

## 6. Skill 数据模型

### 6.1 SkillMetadata

**位置:** `pyagentforge.skills.models.SkillMetadata`

技能元数据。

```python
class SkillMetadata(BaseModel):
    """技能元数据"""

    name: str = Field(..., description="技能 ID")
    description: str = Field(..., description="技能描述")
    version: str = Field(default="1.0.0", description="版本号")
    author: str = Field(default="", description="作者")
    tags: list[str] = Field(default_factory=list, description="标签")

    # 触发配置
    triggers: list[str] = Field(default_factory=list, description="触发关键词")
    auto_load: bool = Field(default=False, description="是否自动加载")

    # 依赖
    dependencies: list[str] = Field(default_factory=list, description="依赖的其他技能")

    # 工具权限
    tools: list[str] = Field(default_factory=lambda: ["*"], description="允许使用的工具")
```

**参数说明:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `name` | `str` | **必需** | 技能 ID |
| `description` | `str` | **必需** | 技能描述 |
| `version` | `str` | `"1.0.0"` | 版本号 |
| `author` | `str` | `""` | 作者 |
| `tags` | `list[str]` | `[]` | 标签 |
| `triggers` | `list[str]` | `[]` | 触发关键词 |
| `auto_load` | `bool` | `False` | 是否自动加载 |
| `dependencies` | `list[str]` | `[]` | 依赖的其他技能 |
| `tools` | `list[str]` | `["*"]` | 允许使用的工具 |

---

### 6.2 Skill

**位置:** `pyagentforge.skills.models.Skill`

技能模型。

```python
class Skill(BaseModel):
    """技能模型"""

    metadata: SkillMetadata
    body: str = Field(..., description="技能内容 (Markdown)")
    path: Path | None = Field(default=None, description="技能文件路径")

    class Config:
        arbitrary_types_allowed = True
```

#### 方法

##### `get_full_content()`

```python
def get_full_content(self) -> str
```

获取完整内容 (用于注入到上下文)。

---

##### `name`, `description`, `triggers` (属性)

获取对应元数据字段。

---

## 7. SkillLoader - 技能加载器

**位置:** `pyagentforge.skills.loader.SkillLoader`

扫描和加载技能目录。

### 构造函数

```python
def __init__(
    self,
    skills_dir: Path | None = None,
    parser: SkillParser | None = None,
) -> None
```

---

### 方法

#### `load_all()`

```python
def load_all(self) -> dict[str, Skill]
```

加载所有技能。

**返回值:** `dict[str, Skill]` - 技能名称到技能对象的映射

---

#### `get()`

```python
def get(self, name: str) -> Skill | None
```

获取技能。

---

#### `get_skill_content()`

```python
def get_skill_content(self, name: str) -> str
```

获取技能内容 (用于注入到上下文)。

**返回值:** `str` - XML 格式的技能内容

```xml
<skill name="skill_name">
... content ...
</skill>
```

---

#### `get_descriptions()`

```python
def get_descriptions(self) -> str
```

获取所有技能的描述 (用于系统提示词)。

---

#### `get_trigger_keywords()`

```python
def get_trigger_keywords(self) -> dict[str, list[str]]
```

获取所有技能的触发关键词。

**返回值:** `dict[str, list[str]]` - 技能名称到触发词列表的映射

---

#### `match_skill()`

```python
def match_skill(self, text: str) -> str | None
```

根据文本匹配技能。

**参数:**

| 参数 | 类型 | 说明 |
|------|------|------|
| `text` | `str` | 用户输入文本 |

**返回值:** `str | None` - 匹配的技能名称或 None

---

#### `get_dependencies()`

```python
def get_dependencies(self, name: str) -> list[str]
```

获取技能的依赖列表 (递归)。

**返回值:** `list[str]` - 所有依赖的技能名称列表

---

## 8. 技能文件格式

### 8.1 目录结构

```
data/skills/
├── python/
│   └── SKILL.md
├── typescript/
│   └── SKILL.md
├── git/
│   └── SKILL.md
└── testing/
    └── SKILL.md
```

每个技能一个独立目录，包含 `SKILL.md` 文件。

---

### 8.2 文件格式

```markdown
---
name: python
description: Python 开发技能
version: 1.0.0
author: PyAgentForge Team
tags:
  - python
  - development
triggers:
  - python
  - py
  - pip
  - pytest
auto_load: false
dependencies:
  - git
  - testing
tools:
  - bash
  - read
  - write
  - edit
---

# Python 开发技能

本技能提供 Python 开发相关的最佳实践和指南。

## 代码风格

遵循 PEP 8 规范...

## 测试

使用 pytest 进行测试...

## 常用命令

- 运行测试: `pytest tests/`
- 格式化: `black .`
- 类型检查: `mypy src/`
```

---

## 9. 使用示例

### 9.1 加载和使用命令

```python
from pathlib import Path
from pyagentforge.commands import CommandLoader

# 创建加载器
loader = CommandLoader(commands_dir=Path("./data/commands"))

# 加载所有命令
commands = loader.load_all()
print(f"Loaded {len(commands)} commands")

# 获取特定命令
commit_cmd = loader.get("commit")
if commit_cmd:
    print(f"Description: {commit_cmd.description}")
    print(f"Content:\n{commit_cmd.get_full_content()}")

# 获取命令描述 (用于系统提示词)
descriptions = loader.get_descriptions()
print(descriptions)

# 匹配命令
matched = loader.match_command("/commit")
if matched:
    print(f"Matched: {matched.name}")

# 获取命令内容
content = loader.get_command_content("commit", inject_dynamic=True)
print(content)
```

---

### 9.2 加载和使用技能

```python
from pathlib import Path
from pyagentforge.skills import SkillLoader

# 创建加载器
loader = SkillLoader(skills_dir=Path("./data/skills"))

# 加载所有技能
skills = loader.load_all()
print(f"Loaded {len(skills)} skills")

# 获取特定技能
python_skill = loader.get("python")
if python_skill:
    print(f"Description: {python_skill.description}")
    print(f"Triggers: {python_skill.triggers}")

# 匹配技能
matched = loader.match_skill("Please help me with this python code")
if matched:
    print(f"Matched skill: {matched}")
    content = loader.get_skill_content(matched)
    print(content)

# 获取依赖
deps = loader.get_dependencies("python")
print(f"Dependencies: {deps}")

# 获取触发关键词
keywords = loader.get_trigger_keywords()
for skill_name, triggers in keywords.items():
    print(f"{skill_name}: {triggers}")
```

---

### 9.3 命令文件示例

**文件:** `data/commands/review.md`

```markdown
---
name: review
description: 代码审查命令
version: 1.0.0
alias:
  - pr
category: development
tools:
  - bash
  - read
  - grep
timeout: 300
---

# Code Review

请审查当前 Pull Request 的代码变更。

## 当前分支

!`git branch --show-current`

## 变更文件

!`git diff --name-only origin/main...HEAD`

## 代码变更

!`git diff origin/main...HEAD`

## 审查要求

1. 检查代码质量
2. 检查潜在 bug
3. 检查测试覆盖率
4. 提供改进建议
```

---

### 9.4 技能文件示例

**文件:** `data/skills/testing/SKILL.md`

```markdown
---
name: testing
description: 测试开发技能
version: 1.0.0
tags:
  - testing
  - pytest
  - unittest
triggers:
  - test
  - testing
  - pytest
  - unittest
dependencies: []
---

# 测试开发技能

本技能提供测试开发的最佳实践。

## 测试原则

1. 单元测试应该快速、独立
2. 使用清晰的测试命名
3. 遵循 AAA 模式 (Arrange, Act, Assert)

## Pytest 示例

```python
def test_user_creation():
    # Arrange
    user_data = {"name": "Alice", "email": "alice@example.com"}

    # Act
    user = User.create(user_data)

    # Assert
    assert user.name == "Alice"
    assert user.email == "alice@example.com"
```

## 常用命令

- 运行所有测试: `pytest`
- 运行特定测试: `pytest tests/test_user.py`
- 显示覆盖率: `pytest --cov=src`
```

---

## 相关文档

- [核心 API 文档](./01-core-api.md)
- [工具系统 API 文档](./03-tools-api.md)
- [插件系统 API 文档](./05-plugin-system-api.md)
- [配置 API 文档](./06-configuration-api.md)

---

## 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| v2.0.0 | 2026-02-17 | 初始版本，支持命令和技能系统 |

---

*本文档由 Claude Code 自动生成*
