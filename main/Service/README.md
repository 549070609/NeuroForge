# Service Layer

FastAPI-based gateway that sits in front of the `pyagentforge` SDK and exposes
NeuroForge's Agent, Proxy, Model-config and Tool capabilities as REST APIs.

The SDK (`pyagentforge`) is the execution engine; this package (`main/Service`)
is the API surface. Both modes are first-class and intentionally maintained in
parallel — SDK users import `pyagentforge` directly, API users talk to this
service.

## Architecture

```
┌──────────────────────────────── Clients ───────────────────────────────┐
│            Web · IDE · CLI · Other services                             │
└─────────────────────────────┬──────────────────────────────────────────┘
                              ▼
┌───────────────────────── Gateway (FastAPI) ────────────────────────────┐
│  Middleware stack (outer → inner):                                      │
│    CORS → AuthMiddleware → RateLimitMiddleware → ErrorHandlerMiddleware │
│                                                                         │
│  Routes (all under /api/v1 unless noted):                               │
│    /health   /health/deep   /agents/active    (unversioned)             │
│    /tools                   (list + execute)                            │
│    /agents   /plans         (AgentService)                              │
│    /models                  (ModelConfigService)                        │
│    /proxy/workspaces|sessions|execute|workflows|approvals|slo|…         │
└─────────────────────────────┬──────────────────────────────────────────┘
                              ▼
┌───────────────────── Service Layer (Business Logic) ────────────────────┐
│  AgentService · AgentProxyService · ModelConfigService                   │
│  Governance (guardrails, HITL, SLO) · SessionManager · WorkspaceManager  │
└─────────────────────────────┬──────────────────────────────────────────┘
                              ▼
┌──────────────────── Core Layer + pyagentforge SDK ──────────────────────┐
│  ServiceRegistry (singleton)                                             │
│  persistence/store.py (SQLite/Redis)                                     │
│  pyagentforge.kernel.* · pyagentforge.tools.builtin.* · plugins          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Quick start

```bash
# install in editable mode from repo root
pip install -e main/Service

# run the API
uvicorn Service.gateway.app:create_app --factory --reload --port 8000

# health check
curl http://localhost:8000/health
```

Or from Python:

```python
from Service import create_app, run

app = create_app()  # for ASGI servers
run()               # uvicorn launcher using SERVICE_* env vars
```

## Route reference

All application routes live under `/api/v1`. Health, readiness and root stay
unversioned so infrastructure probes never need to know the API version.

### Unversioned

| Method | Path              | Description                               |
|--------|-------------------|-------------------------------------------|
| GET    | `/`               | Root greeting with docs pointer.          |
| GET    | `/health`         | Lightweight liveness probe.               |
| GET    | `/health/deep`    | Per-service health + uptime.              |
| GET    | `/agents/active`  | Currently running agent sessions.         |
| GET    | `/docs`           | Swagger UI.                               |
| GET    | `/redoc`          | ReDoc.                                    |
| GET    | `/openapi.json`   | OpenAPI schema.                           |

### Tools (`/api/v1`)

| Method | Path                              | Description                         |
|--------|-----------------------------------|-------------------------------------|
| GET    | `/api/v1/tools`                   | List canonical builtin tools.       |
| POST   | `/api/v1/tools/{tool_name}/execute` | Execute a tool in system context. |

### Agents & Plans (`/api/v1/agents`, `/api/v1/plans`)

| Method | Path                                       | Description                  |
|--------|--------------------------------------------|------------------------------|
| GET    | `/api/v1/agents`                           | List agents (filters).       |
| GET    | `/api/v1/agents/stats`                     | Registry statistics.         |
| GET    | `/api/v1/agents/namespaces`                | Known namespaces.            |
| GET    | `/api/v1/agents/refresh`                   | Rescan on-disk directory.    |
| GET    | `/api/v1/agents/{agent_id}`                | Agent detail.                |
| POST   | `/api/v1/agents/{agent_id}/execute`        | Execute agent with task.     |
| GET    | `/api/v1/plans`                            | List plans.                  |
| POST   | `/api/v1/plans`                            | Create plan.                 |
| GET    | `/api/v1/plans/stats`                      | Plan statistics.             |
| GET    | `/api/v1/plans/{plan_id}`                  | Plan detail.                 |
| DELETE | `/api/v1/plans/{plan_id}`                  | Delete plan.                 |
| POST   | `/api/v1/plans/{plan_id}/steps`            | Append step.                 |
| PATCH  | `/api/v1/plans/{plan_id}/steps/{step_id}`  | Update step state.           |

### Model configs (`/api/v1/models`)

| Method | Path                              | Description                |
|--------|-----------------------------------|----------------------------|
| GET    | `/api/v1/models`                  | List registered LLM configs.|
| GET    | `/api/v1/models/stats`            | Stats snapshot.            |
| GET    | `/api/v1/models/{model_id}`       | Detail.                    |
| POST   | `/api/v1/models`                  | Register a new config.     |
| PATCH  | `/api/v1/models/{model_id}`       | Patch a config.            |
| DELETE | `/api/v1/models/{model_id}`       | Remove a config.           |

### Agent proxy (`/api/v1/proxy`)

Workspaces, sessions and agent execution with full governance pipeline.

| Method | Path                                            | Description              |
|--------|-------------------------------------------------|--------------------------|
| POST   | `/api/v1/proxy/workspaces`                      | Create workspace.        |
| GET    | `/api/v1/proxy/workspaces`                      | List workspaces.         |
| GET    | `/api/v1/proxy/workspaces/{workspace_id}`       | Detail.                  |
| DELETE | `/api/v1/proxy/workspaces/{workspace_id}`       | Delete.                  |
| POST   | `/api/v1/proxy/sessions`                        | Create session.          |
| GET    | `/api/v1/proxy/sessions`                        | List sessions.           |
| GET    | `/api/v1/proxy/sessions/{session_id}`           | Detail.                  |
| DELETE | `/api/v1/proxy/sessions/{session_id}`           | Close session.           |
| POST   | `/api/v1/proxy/execute`                         | Execute agent.           |
| POST   | `/api/v1/proxy/execute/stream`                  | SSE stream execution.    |
| POST   | `/api/v1/proxy/workflows`                       | Create workflow.         |
| GET    | `/api/v1/proxy/workflows/{workflow_id}`         | Detail.                  |
| POST   | `/api/v1/proxy/workflows/{workflow_id}/start`   | Start.                   |
| POST   | `/api/v1/proxy/workflows/{workflow_id}/pause`   | Pause.                   |
| POST   | `/api/v1/proxy/workflows/{workflow_id}/resume`  | Resume.                  |
| GET    | `/api/v1/proxy/traces/{trace_id}`               | Trace detail.            |
| GET    | `/api/v1/proxy/approvals`                       | HITL approval queue.     |
| GET    | `/api/v1/proxy/approvals/{approval_id}`         | Approval detail.         |
| POST   | `/api/v1/proxy/approvals/{approval_id}/approve` | Approve.                 |
| POST   | `/api/v1/proxy/approvals/{approval_id}/reject`  | Reject.                  |
| GET    | `/api/v1/proxy/slo`                             | SLO dashboard.           |
| POST   | `/api/v1/proxy/handoff/parse`                   | Handoff payload parser.  |
| GET    | `/api/v1/proxy/stats`                           | Proxy service stats.     |

## Middleware

Registered in `gateway/app.py`. Ordered from outermost to innermost:

| Order | Middleware                 | Purpose                                              |
|-------|----------------------------|------------------------------------------------------|
| 1     | `CORSMiddleware`           | Permissive CORS. Tune in production.                 |
| 2     | `AuthMiddleware`           | API-Key header check (`SERVICE_API_KEY`). Public paths bypass automatically. |
| 3     | `RateLimitMiddleware`      | In-memory sliding window by client IP.               |
| 4     | `ErrorHandlerMiddleware`   | Catches un-handled exceptions → JSON 500.            |

Authentication and rate limiting are feature-flag driven:

- `SERVICE_API_KEY` unset → auth middleware is a no-op.
- `SERVICE_RATE_LIMIT_ENABLED=false` (default) → rate limiter is a no-op.

## Package layout

```
Service/
├── __init__.py              # re-exports create_app, run, registry + keys
├── config/                  # Pydantic-settings (SERVICE_*)
├── core/                    # ServiceRegistry + canonical service keys
├── events/                  # SSE event types and filters
├── gateway/
│   ├── app.py               # FastAPI factory, middleware + route mount
│   ├── middleware/          # auth / rate_limit / error_handler
│   └── routes/              # health, tools, agents, models, proxy
├── persistence/             # SQLite + Redis store abstraction
├── schemas/                 # Pydantic request/response models
├── services/                # AgentService, ModelConfigService, proxy/*
└── tests/                   # Gateway + service tests
```

## Configuration

All settings are loaded from environment variables with the `SERVICE_` prefix.

| Variable                          | Default                 | Purpose                            |
|-----------------------------------|-------------------------|------------------------------------|
| `SERVICE_HOST`                    | `0.0.0.0`               | Bind host.                         |
| `SERVICE_PORT`                    | `8000`                  | Bind port.                         |
| `SERVICE_DEBUG`                   | `false`                 | FastAPI debug + reload hint.       |
| `SERVICE_LOG_LEVEL`               | `INFO`                  | Root logger level.                 |
| `SERVICE_API_KEY`                 | *unset*                 | If set, required via header.       |
| `SERVICE_API_KEY_HEADER`          | `X-API-Key`             | Custom header name.                |
| `SERVICE_RATE_LIMIT_ENABLED`      | `false`                 | Toggle rate limiter.               |
| `SERVICE_RATE_LIMIT_REQUESTS`     | `100`                   | Requests per window.               |
| `SERVICE_RATE_LIMIT_WINDOW`       | `60`                    | Window (seconds).                  |
| `SERVICE_SQLITE_PATH`             | `data/service.db`       | Local persistence file.            |
| `SERVICE_REDIS_URL` / `_ENABLED`  | *unset* / `false`       | Optional Redis backing.            |
| `SERVICE_SESSION_TTL`             | `3600`                  | Proxy session TTL (s).             |
| `SERVICE_MAX_SESSIONS`            | `100`                   | Cap on live sessions.              |
| `SERVICE_GUARDRAILS_ENABLED`      | `true`                  | Toggle governance guardrails.      |
| `SERVICE_HITL_ENABLED`            | `true`                  | Toggle human-in-the-loop pipeline. |

## Development

```bash
# run the full Service test suite
pytest main/Service/tests -v

# with coverage
pytest main/Service/tests -v --cov=Service --cov-report=html
```

## Related docs

- Repo root [`AGENTS.md`](../../AGENTS.md) — agent contribution rules.
- SDK docs — [`docs/sdk/`](../../docs/sdk/).
- Design notes — [`main/Service/docs/`](docs/).
