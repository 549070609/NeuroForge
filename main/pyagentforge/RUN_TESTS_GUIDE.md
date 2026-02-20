# PyAgentForge 测试运行指南

## 环境准备

### 1. 安装项目依赖

```bash
cd "E:/localproject/Agent Learn/main/pyagentforge"

# 安装项目（开发模式，包含测试依赖）
pip install -e ".[dev]"
```

### 2. 验证安装

```bash
# 检查 pytest 是否安装
python -m pytest --version

# 检查项目是否可导入
python -c "import pyagentforge; print('✓ pyagentforge installed')"
```

## 运行测试

### 方式 1: 使用测试运行器（推荐）

```bash
# 运行全量测试
python tests/run_tests.py
```

### 方式 2: 使用 pytest 直接运行

```bash
# 运行所有测试
python -m pytest tests/ -v

# 运行特定类别
python -m pytest tests/kernel/ -v
python -m pytest tests/core/ -v
python -m pytest tests/providers/ -v
python -m pytest tests/tools/ -v
python -m pytest tests/plugin/ -v
python -m pytest tests/integration/ -v
```

### 方式 3: 运行覆盖率测试

```bash
python tests/run_coverage.py
# 或
python -m pytest tests/ --cov=pyagentforge --cov-report=html --cov-report=term
```

## 常见问题

### Q: 提示 "pytest: command not found"

**解决:**
```bash
pip install pytest pytest-asyncio pytest-cov
# 或
pip install -e ".[dev]"
```

### Q: 提示 "ModuleNotFoundError: No module named 'pyagentforge'"

**解决:**
```bash
pip install -e .
```

### Q: 测试运行失败

**排查步骤:**
1. 确认 Python 版本 >= 3.11
2. 确认所有依赖已安装: `pip list`
3. 检查是否在正确的目录: `pwd` (应该显示 main/pyagentforge)
4. 尝试单独运行一个测试文件: `python -m pytest tests/kernel/test_message.py -v`

## 快速测试命令

```bash
# 最简单的测试（单个文件）
python -m pytest tests/kernel/test_message.py -v

# 测试特定功能
python -m pytest tests/ -k "test_simple" -v

# 并行测试（需要安装 pytest-xdist）
python -m pytest tests/ -n auto

# 只运行失败的测试
python -m pytest tests/ --lf -v

# 停止于第一个失败
python -m pytest tests/ -x -v
```

## 查看测试报告

运行测试后，会生成以下报告：

- **控制台输出** - 实时测试进度和结果
- **test_report.json** - JSON 格式的详细报告
- **htmlcov/index.html** - HTML 覆盖率报告（运行覆盖率测试后）

## 下一步

1. 运行测试: `python tests/run_tests.py`
2. 查看报告: `cat test_report.json`
3. 查看覆盖率: `python tests/run_coverage.py && open htmlcov/index.html`
