# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Purpose

This is a **knowledge base for AI Agent learning materials**, containing:
- **OpenClaw** - 个人 AI 助手平台技术文档 (TypeScript/多通道消息集成)
- **PyAgentForge** - Python AI Agent 开发框架分析与实现
- **OpenCode Server** - TypeScript/Bun-based AI development platform 深度分析
- **Claude Code** - 渐进式 Agent 教程 (v0-v4)

This is a documentation repository with reference source code. Focus on content organization and knowledge structure.

## Directory Structure

```
Agent Learn/
├── Docs/                          # 主要文档目录 (重点)
│   ├── OpenClaw/                  # OpenClaw 功能说明书 (33章)
│   │   ├── 00-系统总览.md
│   │   ├── 01-总览与入门/
│   │   ├── 02-架构设计/
│   │   ├── 03-核心模块/           # Gateway, Agent, Session, 配置
│   │   ├── 04-消息通道/
│   │   ├── 05-AI能力/
│   │   ├── 06-高级功能/
│   │   ├── 07-客户端应用/
│   │   ├── 08-扩展开发/
│   │   └── 09-运维与安全/
│   ├── PyAgentForge/              # PyAgentForge 分析报告
│   │   ├── PyAgentForge-vs-OpenCodeServer-完整对比.md
│   │   ├── 三方对比报告.md        # OpenClaw vs PyAgentForge vs OpenCodeServer
│   │   └── plan/                  # 产品规划
│   ├── OpenCode/                  # OpenCode Server 深度功能说明书 (36章+附录)
│   │   └── OpenCode-Server深度功能说明书/
│   ├── plan/                      # 跨项目规划文档
│   └── README.md                  # 文档索引入口
├── Learncode/                     # 源码学习目录
│   ├── OpenClaw/                  # OpenClaw 完整源码 (pnpm monorepo)
│   ├── OpencodeServer/            # OpenCode Server 源码 (Bun)
│   └── oh-my-code/                # 示例项目
├── demo/                          # 演示项目
│   └── pyagentforge/              # PyAgentForge 可运行示例
├── .claude/                       # Claude Code 配置
└── README.md                      # 项目入口
```

## Key Projects Overview

### OpenClaw (Learncode/OpenClaw + Docs/OpenClaw)

个人 AI 助手平台，专注于多通道消息集成。

**核心技术栈:** TypeScript, pnpm monorepo, Bun runtime

**五层架构:**
1. User Interface (CLI/TUI, GitHub, Desktop, Web)
2. Service Access (ACP, GitHub Webhook, Auth, MCP)
3. Core Engine (Agent, Session, Event Bus, Extensions)
4. AI Services (OpenAI, Anthropic, etc.)
5. Infrastructure (Bun, SST, Cloudflare, PlanetScale)

**四大扩展点:**
| Type | Location | Format | Purpose |
|------|----------|--------|---------|
| Agent | `.agent/` | .md | Define agent roles |
| Command | `.agents/commands/` | .md | User commands |
| Skill | `skills/` | SKILL.md | Domain knowledge |
| Tool | `extensions/` | .ts | Function implementations |

### PyAgentForge (demo/pyagentforge + Docs/PyAgentForge)

基于 Python 的 AI Agent 开发框架，目标是复现 OpenCode Server 的核心功能。

**核心特性:**
- 多模型支持 (OpenAI, Anthropic, Google)
- 并行子代理 (ParallelSubAgent)
- 上下文压缩
- Command 系统 + `!`cmd`` 语法
- 动态工具注册

**运行示例:**
```bash
cd demo/pyagentforge
pip install -e .
cp .env.example .env  # Add API keys
python examples/basic_usage.py
```

### Claude Code 学习笔记 (Docs/learn/02-Claude-Code-学习笔记)

渐进式 Agent 教程，从 50 行代码到 550 行的完整 Agent。

**Agent Evolution (v0 → v4):**

| Version | Lines | Tools | Key Concept |
|---------|-------|-------|-------------|
| v0 | ~50 | bash | One tool is enough; recursive self-calling = subagent |
| v1 | ~200 | bash, read, write, edit | Model IS the agent |
| v2 | ~300 | +TodoWrite | Explicit planning with constraints |
| v3 | ~450 | +Task | Context isolation via subagents |
| v4 | ~550 | +Skill | On-demand knowledge loading |

**Agent Core Loop:**
```python
while True:
    response = model(messages, tools)
    if response.stop_reason != "tool_use":
        return response.text
    results = execute(response.tool_calls)
    messages.append(results)
```

## Documentation Conventions

- **Language:** Chinese is the primary language for documentation
- **Technical terms:** Often kept in English (Agent, Tool, Skill, Gateway, Channel, etc.)
- **Code examples:** Python (PyAgentForge) or TypeScript (OpenClaw/OpenCode)
- **Architecture diagrams:** ASCII art preferred

## Documentation Output Rules

All generated documentation should be output to `Docs/`:
1. **OpenClaw 相关** → `Docs/OpenClaw/`
2. **PyAgentForge 相关** → `Docs/PyAgentForge/`
3. **OpenCode 相关** → `Docs/OpenCode/`
4. **跨项目对比/规划** → `Docs/plan/`
5. **学习资料归档** → `Docs/learn/`
6. After creating any document, **always update** `Docs/README.md` index

## Important Notes

- `Learncode/OpenClaw/node_modules/` contains large dependencies - avoid reading
- `Learncode/OpencodeServer/node_modules/` same as above
- Source code in `Learncode/` is for reference only, not for modification
- Run PyAgentForge demos in `demo/pyagentforge/`, not in `Learncode/`

## Build/Development Focus

**When performing build or development tasks:**

默认**仅关注** `demo/pyagentforge/` 目录，**忽略其他目录**，除非用户明确指定。

| 目录 | 构建时行为 |
|------|-----------|
| `demo/pyagentforge/` | ✅ 默认工作目录 |
| `Learncode/` | ❌ 忽略 (参考源码) |
| `Docs/` | ❌ 忽略 (文档) |
| 其他目录 | ❌ 忽略 |

This prevents accidental modifications to reference source code and keeps focus on the active development project.

## Quick Reference Links

| Resource | Location |
|----------|----------|
| 文档索引 | [Docs/README.md](Docs/README.md) |
| OpenClaw 总览 | [Docs/OpenClaw/00-系统总览.md](Docs/OpenClaw/00-系统总览.md) |
| OpenClaw 功能目录 | [Docs/OpenClaw/README.md](Docs/OpenClaw/README.md) |
| PyAgentForge 对比 | [Docs/PyAgentForge/PyAgentForge-vs-OpenCodeServer-2026-02-16-完整对比.md](Docs/PyAgentForge/PyAgentForge-vs-OpenCodeServer-2026-02-16-完整对比.md) |
| 三方对比报告 | [Docs/PyAgentForge/三方对比报告-OpenClaw-PyAgentForge-OpenCodeServer.md](Docs/PyAgentForge/三方对比报告-OpenClaw-PyAgentForge-OpenCodeServer.md) |
| OpenCode 深度说明书 | [Docs/OpenCode/OpenCode-Server深度功能说明书/README.md](Docs/OpenCode/OpenCode-Server深度功能说明书/README.md) |

---
*Last updated: 2026-02-16*