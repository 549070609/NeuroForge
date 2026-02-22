---
name: run
description: 运行命令或脚本
alias:
  - execute
  - exec
category: basic
tools:
  - bash
  - read
---

# 运行命令

执行用户指定的命令或脚本。

## 使用方式

用户输入格式：`/run [命令]`

示例：
- `/run python main.py`
- `/run pytest tests/`
- `/run npm start`

---

## 执行任务

### 1. **解析命令**

从用户输入中提取要执行的命令

### 2. **安全检查**

在执行前检查：
- 命令是否在安全白名单内
- 是否涉及敏感操作（rm -rf, sudo 等）
- 是否需要用户确认

### 3. **显示执行计划**

执行前显示：
- 完整的命令
- 工作目录
- 预期的影响

### 4. **执行命令**

使用 bash 工具执行命令：
- 捕获标准输出和错误
- 显示执行进度
- 报告退出码

### 5. **处理结果**

- 成功：显示输出结果
- 失败：显示错误信息和诊断建议
- 超时：报告超时并提供解决方案

---

## 常用命令示例

```bash
# Python 相关
python script.py          # 运行 Python 脚本
python -m pytest         # 运行测试
python -m pip list       # 列出已安装包

# 项目管理
pip install -e .         # 安装项目
pip install -r requirements.txt  # 安装依赖

# Git 操作
git status               # 查看状态
git log --oneline -10    # 查看日志

# 系统命令
ls -la                   # 列出文件
find . -name "*.py"      # 查找文件
```

---

请等待用户提供要执行的命令。
