# Service API 文档（按类型分类）

本文档基于 `main/Service/gateway/routes`、`main/Service/schemas`、`main/Service/services` 当前实现整理。

## 目录结构

```text
docs/
├─ 00-common/
│  ├─ api-conventions.md
│  └─ llm-adapter.md
├─ 01-health/
│  └─ health-root.md
├─ 02-tools/
│  └─ tools.md
├─ 03-agents/
│  └─ agents.md
├─ 04-plans/
│  └─ plans.md
├─ 05-proxy/
│  ├─ workspaces.md
│  ├─ sessions.md
│  └─ execution.md
└─ 99-llm/
   └─ endpoint-catalog.md
```

## API 类型分类

1. 基础与健康类: `/`、`/health`
2. 工具管理类: `/api/v1/tools*`
3. Agent 管理与执行类: `/api/v1/agents*`
4. Plan 管理类: `/api/v1/plans*`
5. Proxy 工作空间类: `/api/v1/proxy/workspaces*`
6. Proxy 会话类: `/api/v1/proxy/sessions*`
7. Proxy 执行与流式类: `/api/v1/proxy/execute*`
8. 统计类: `/api/v1/agents/stats`、`/api/v1/plans/stats`、`/api/v1/proxy/stats`

## 快速开始

```bash
export BASE_URL="http://localhost:8000"
curl "$BASE_URL/health"
```

Windows PowerShell:

```powershell
$env:BASE_URL = "http://localhost:8000"
curl "$env:BASE_URL/health"
```

## LLM 适配入口

- 通用规范: `00-common/llm-adapter.md`
- 机读端点目录: `99-llm/endpoint-catalog.md`
