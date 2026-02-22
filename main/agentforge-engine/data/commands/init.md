---
name: init
description: 初始化新项目 - 创建基本项目结构
alias:
  - initialize
  - setup
category: project
tools:
  - bash
  - write
  - read
---

# 初始化项目

在当前目录初始化一个新的 Python 项目。

## 当前状态

当前目录: !`pwd`
已有文件: !`ls -la`

---

## 初始化任务

请根据项目类型创建基本的项目结构：

### 1. **检测项目类型**

检查是否已存在：
- `pyproject.toml` - 现代 Python 项目
- `setup.py` - 传统 Python 包
- `requirements.txt` - 依赖列表
- `.git/` - Git 仓库

### 2. **创建基础文件**

如果文件不存在，建议创建：

**pyproject.toml**
```toml
[project]
name = "my-project"
version = "0.1.0"
description = "A new Python project"
requires-python = ">=3.10"

[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"
```

**README.md**
```markdown
# Project Name

Description of the project.

## Installation

\`\`\`bash
pip install -e .
\`\`\`

## Usage

TODO: Add usage instructions
```

**.gitignore**
```
__pycache__/
*.py[cod]
*$py.class
.env
.venv/
venv/
dist/
build/
*.egg-info/
```

### 3. **初始化 Git**（如果未初始化）

执行：
```bash
git init
git add .
git commit -m "Initial commit"
```

### 4. **创建目录结构**

建议结构：
```
.
├── src/
│   └── __init__.py
├── tests/
│   └── __init__.py
├── docs/
├── pyproject.toml
├── README.md
└── .gitignore
```

---

请执行初始化操作，并报告创建的文件和目录。
