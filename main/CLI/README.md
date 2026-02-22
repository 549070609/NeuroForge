# CLI - Command Line Interface

基于 Service 层构建的命令行交互工具，支持单命令模式和交互式 REPL 模式。

## 安装依赖

```bash
cd E:\localproject\Agent Learn\main\CLI
pip install -r requirements.txt
```

## 使用方式

### 单命令模式

```bash
# 进入 main 目录
cd "E:\localproject\Agent Learn\main"

# 查看帮助
py -m CLI --help

# Agent 命令
py -m CLI agent list
py -m CLI agent get <agent_id>
py -m CLI agent stats
py -m CLI agent refresh

# Workspace 命令
py -m CLI workspace list
py -m CLI workspace create dev --path /workspace/dev
py -m CLI workspace get dev
py -m CLI workspace remove dev

# Session 命令
py -m CLI session list
py -m CLI session create --workspace dev --agent my-agent
py -m CLI session get <session_id>
py -m CLI session delete <session_id>

# Execute 命令
py -m CLI execute run <session_id> "你的任务"
py -m CLI execute stream <session_id> "你的任务"
py -m CLI execute chat --workspace dev --agent my-agent "你的任务"

# Plan 命令
py -m CLI plan list
py -m CLI plan get <plan_id>
py -m CLI plan create --title "计划标题" --objective "目标描述"
py -m CLI plan delete <plan_id>
py -m CLI plan step add <plan_id> --title "步骤标题"
py -m CLI plan step update <plan_id> <step_id> --status completed

# Model 命令
py -m CLI model list
py -m CLI model get <model_id>
py -m CLI model providers
py -m CLI model stats
```

### 交互式 REPL 模式

```bash
py -m CLI repl
```

REPL 模式下的命令示例：

```
>>> help                          # 显示帮助
>>> agent list                    # 列出所有 agent
>>> agent get my-agent            # 获取 agent 详情
>>> workspace create dev --path /workspace/dev   # 创建工作区
>>> session create --workspace dev --agent my-agent  # 创建会话
>>> execute <session_id> 你的任务  # 执行任务
>>> chat --workspace dev --agent my-agent 你的任务  # 一次性对话
>>> exit                          # 退出 REPL
```

## 目录结构

```
CLI/
├── __init__.py           # 包初始化
├── __main__.py           # 模块入口 (python -m CLI)
├── main.py               # Typer 主应用
├── requirements.txt      # 依赖列表
├── commands/             # 命令模块
│   ├── __init__.py
│   ├── agent.py          # agent 命令组
│   ├── workspace.py      # workspace 命令组
│   ├── session.py        # session 命令组
│   ├── execute.py        # execute 命令
│   ├── plan.py           # plan 命令组
│   ├── model.py          # model 命令组
│   └── repl.py           # REPL 交互模式
├── core/                 # 核心组件
│   ├── __init__.py
│   ├── context.py        # 服务上下文管理
│   └── output.py         # Rich 输出格式化
└── utils/                # 工具函数
    ├── __init__.py
    └── async_runner.py   # 异步运行器
```

## 输出格式

支持两种输出格式：

- **表格格式**（默认）：使用 Rich 库美化输出
- **JSON 格式**：使用 `--json` 或 `-j` 参数

```bash
py -m CLI agent list --json
py -m CLI model list -j
```

## 命令概览

| 命令 | 描述 |
|------|------|
| `agent` | Agent 管理（list, get, stats, refresh, namespaces） |
| `workspace` | 工作区管理（create, list, get, remove, stats） |
| `session` | 会话管理（create, list, get, delete） |
| `execute` | Agent 执行（run, stream, chat） |
| `plan` | 计划管理（list, get, create, delete, stats, step） |
| `model` | 模型配置（list, get, create, update, delete, stats, providers） |
| `repl` | 启动交互式 REPL 模式 |
| `version` | 显示 CLI 版本 |

## 架构说明

CLI 通过 `CLIContext` 类管理 Service 层的生命周期：

1. **初始化**：创建 `ServiceRegistry`，注册所有服务
2. **执行**：通过 `async_command` 装饰器处理异步命令
3. **清理**：命令完成后关闭所有服务

核心流程：
```python
# 1. 获取上下文
ctx = get_context()

# 2. 访问服务
agent_service = ctx.agent
proxy_service = ctx.proxy
model_service = ctx.model_config

# 3. 调用服务方法
agents = agent_service.list_agents()
workspaces = proxy_service.list_workspaces()
```

## 扩展

添加新命令的步骤：

1. 在 `commands/` 目录下创建新的命令文件
2. 使用 `@async_command` 装饰器包装异步函数
3. 在 `main.py` 中注册命令组

示例：
```python
# commands/mycommand.py
import typer
from CLI.core import async_command, get_context, console

app = typer.Typer(help="My command")

@app.command("hello")
@async_command
async def hello(name: str = typer.Argument(..., help="Name to greet")):
    """Say hello."""
    console.print(f"Hello, {name}!")
```

```python
# main.py
from CLI.commands.mycommand import app as mycommand_app
app.add_typer(mycommand_app, name="mycommand")
```

## Config Docs

- English: `main/JSON_CONFIG_README.md`
- Chinese: `main/Docs/JSON_CONFIG_README.zh-CN.md`
