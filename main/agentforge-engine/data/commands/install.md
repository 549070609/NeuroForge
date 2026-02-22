---
name: install
description: 安装项目依赖
alias:
  - deps
  - dependencies
category: project
tools:
  - bash
  - read
---

# 安装依赖

安装项目的依赖包。

## 当前环境

Python: !`python --version 2>&1`
pip: !`pip --version 2>&1`

## 依赖文件检查

!`test -f requirements.txt && echo "✓ requirements.txt" || echo "✗ No requirements.txt"`
!`test -f pyproject.toml && echo "✓ pyproject.toml" || echo "✗ No pyproject.toml"`
!`test -f setup.py && echo "✓ setup.py" || echo "✗ No setup.py"`

---

## 安装任务

### 1. **检测依赖管理方式**

检查并使用适当的工具：
- **pyproject.toml** → `pip install -e .`
- **requirements.txt** → `pip install -r requirements.txt`
- **setup.py** → `pip install -e .`
- **Pipfile** → `pipenv install`
- **poetry.lock** → `poetry install`

### 2. **检查虚拟环境**

验证是否在虚拟环境中：
- 检查 `VIRTUAL_ENV` 环境变量
- 如果没有，建议创建虚拟环境
- 提供创建命令：`python -m venv .venv`

### 3. **执行安装**

运行安装命令：
```bash
pip install -e .  # 开发模式安装
# 或
pip install -r requirements.txt
```

### 4. **验证安装**

安装完成后：
- 列出新安装的包
- 验证关键依赖
- 测试导入

---

## 常见场景

### 场景 1: 新项目
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# 或 .venv\Scripts\activate  # Windows
pip install -e .
```

### 场景 2: 从 requirements.txt
```bash
pip install -r requirements.txt
```

### 场景 3: 开发依赖
```bash
pip install -e ".[dev]"
pip install -e ".[test]"
```

### 场景 4: 特定包
```bash
pip install package_name
```

---

请执行依赖安装，并报告安装的包和可能的警告。
