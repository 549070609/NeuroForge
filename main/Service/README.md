# Service Layer

Service-oriented architecture layer providing REST API and Agent proxy services.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          External Clients                            │
│                        (Web / IDE / API)                             │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        Service Layer (Gateway)                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  FastAPI Routes                                               │   │
│  │  /api/v1/agents | /api/v1/plans | /api/v1/workspaces         │   │
│  │  /api/v1/sessions | /api/v1/execute                           │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                               │                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  AgentProxyService                                            │   │
│  │  - 代理 Agent 基座所有操作                                    │   │
│  │  - 工作区域隔离                                               │   │
│  │  - 会话管理                                                   │   │
│  └──────────────────────────────────────────────────────────────┘   │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
          ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐
│  Agent 底座      │  │  pyagentforge   │  │  工作区域管理器          │
│  - AgentDirectory│  │  - AgentEngine  │  │  - WorkspaceManager     │
│  - PlanManager   │  │  - Provider     │  │  - PathValidator        │
│  - AgentInfo     │  │  - ToolRegistry │  │  - PermissionChecker    │
└─────────────────┘  └─────────────────┘  └─────────────────────────┘
```

## Design Documents

- [Service Agent Proxy 设计文档](docs/SERVICE_AGENT_PROXY_DESIGN.md) - 完整架构设计

## Quick Start

### 1. Install

```bash
cd "E:\localproject\Agent Learn\main\Service"
pip install -e .
```

### 2. Run Server

```bash
uvicorn Service.gateway.app:create_app --factory --reload --port 8000
```

### 3. Health Check

```bash
curl http://localhost:8000/health
```

## API Endpoints

### Core Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Root endpoint |
| GET | `/health` | Health check |
| GET | `/api/v1/tools` | List tools |

### Agent Management

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/agents` | List all agents |
| GET | `/api/v1/agents/{id}` | Get agent details |
| GET | `/api/v1/agents/stats` | Agent statistics |
| POST | `/api/v1/agents/{id}/execute` | Execute agent |

### Workspace Management (New)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/workspaces` | Create workspace |
| GET | `/api/v1/workspaces` | List workspaces |
| GET | `/api/v1/workspaces/{id}` | Get workspace details |
| DELETE | `/api/v1/workspaces/{id}` | Delete workspace |

### Session Management (New)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/sessions` | Create session |
| GET | `/api/v1/sessions` | List sessions |
| GET | `/api/v1/sessions/{id}` | Get session details |
| DELETE | `/api/v1/sessions/{id}` | Close session |

### Execution (New)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/execute` | Execute agent with workspace |
| POST | `/api/v1/execute/stream` | Stream execute (SSE) |

### Plan Management

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/plans` | List plans |
| POST | `/api/v1/plans` | Create plan |
| GET | `/api/v1/plans/{id}` | Get plan details |
| PATCH | `/api/v1/plans/{id}/steps/{step_id}` | Update step |

## Directory Structure

```
Service/
├── services/               # Service implementations
│   ├── __init__.py
│   ├── base.py             # BaseService
│   ├── agent_service.py    # Agent management
│   └── agent_proxy.py      # Agent proxy service (New)
│
├── workspace/              # Workspace management (New)
│   ├── __init__.py
│   ├── manager.py          # WorkspaceManager
│   ├── context.py          # WorkspaceContext
│   └── validator.py        # PathValidator
│
├── execution/              # Execution engine (New)
│   ├── __init__.py
│   ├── executor.py         # AgentExecutor
│   ├── options.py          # ExecutionOptions
│   └── result.py           # ExecutionResult
│
├── sessions/               # Session management (New)
│   ├── __init__.py
│   ├── manager.py          # SessionManager
│   └── models.py           # AgentSession
│
├── core/                   # Core infrastructure
│   ├── __init__.py
│   └── registry.py         # ServiceRegistry
│
├── events/                 # SSE event system
│   ├── __init__.py
│   ├── types.py
│   └── filter.py
│
├── persistence/            # Storage backends
│   ├── __init__.py
│   └── store.py
│
├── gateway/                # FastAPI application
│   ├── __init__.py
│   ├── app.py
│   ├── middleware/
│   │   ├── auth.py
│   │   ├── rate_limit.py
│   │   └── workspace.py    # Workspace middleware (New)
│   └── routes/
│       ├── health.py
│       ├── tools.py
│       ├── agents.py
│       ├── workspaces.py   # New
│       ├── sessions.py     # New
│       └── execute.py      # New
│
├── config/                 # Configuration
│   ├── __init__.py
│   └── settings.py
│
├── schemas/                # Request/Response schemas
│   ├── __init__.py
│   ├── agents.py
│   ├── workspace.py        # New
│   ├── session.py          # New
│   └── execution.py        # New
│
├── docs/                   # Design documents
│   └── SERVICE_AGENT_PROXY_DESIGN.md
│
└── tests/                  # Test suite
```

## Configuration

Environment variables (prefix: `SERVICE_`):

| Variable | Default | Description |
|----------|---------|-------------|
| `SERVICE_HOST` | `0.0.0.0` | Server host |
| `SERVICE_PORT` | `8000` | Server port |
| `SERVICE_DEBUG` | `false` | Debug mode |
| `SERVICE_LOG_LEVEL` | `INFO` | Log level |
| `SERVICE_API_KEY` | `None` | API key |

## Development

```bash
# Run tests
pytest tests/ -v

# With coverage
pytest tests/ -v --cov=Service --cov-report=html
```

## License

MIT
