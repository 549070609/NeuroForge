# LLM 机读端点目录

## 端点总表

| endpoint_id | method | path | request_model | response_model | type |
|---|---|---|---|---|---|
| root_info | GET | `/` | - | inline object | health |
| health_check | GET | `/health` | - | `HealthResponse` | health |
| list_tools | GET | `/api/v1/tools` | - | `ToolInfo[]` | tools |
| execute_tool | POST | `/api/v1/tools/{tool_name}/execute` | `ExecuteToolRequest` | `ExecuteToolResponse`(当前501) | tools |
| list_agents | GET | `/api/v1/agents` | query | `AgentListResponse` | agents |
| get_agent_stats | GET | `/api/v1/agents/stats` | - | `AgentStatsResponse` | agents |
| list_namespaces | GET | `/api/v1/agents/namespaces` | - | `NamespaceListResponse` | agents |
| refresh_agents | GET | `/api/v1/agents/refresh` | - | inline object | agents |
| get_agent | GET | `/api/v1/agents/{agent_id}` | path | `AgentInfoResponse` | agents |
| execute_agent | POST | `/api/v1/agents/{agent_id}/execute` | `AgentExecuteRequest` | `AgentExecuteResponse` | agents |
| list_plans | GET | `/api/v1/plans` | query | `PlanListResponse` | plans |
| get_plan_stats | GET | `/api/v1/plans/stats` | - | `PlanStatsResponse` | plans |
| create_plan | POST | `/api/v1/plans` | `PlanCreate` | `PlanResponse` | plans |
| get_plan | GET | `/api/v1/plans/{plan_id}` | path | `PlanResponse` | plans |
| delete_plan | DELETE | `/api/v1/plans/{plan_id}` | path | inline object | plans |
| update_step | PATCH | `/api/v1/plans/{plan_id}/steps/{step_id}` | `StepUpdateRequest` | `PlanResponse` | plans |
| add_step | POST | `/api/v1/plans/{plan_id}/steps` | `StepAddRequest` | `PlanResponse` | plans |
| create_workspace | POST | `/api/v1/proxy/workspaces` | `WorkspaceCreate` | `WorkspaceResponse` | proxy_workspace |
| list_workspaces | GET | `/api/v1/proxy/workspaces` | - | `WorkspaceListResponse` | proxy_workspace |
| get_workspace | GET | `/api/v1/proxy/workspaces/{workspace_id}` | path | `WorkspaceResponse` | proxy_workspace |
| remove_workspace | DELETE | `/api/v1/proxy/workspaces/{workspace_id}` | path | inline object | proxy_workspace |
| create_session | POST | `/api/v1/proxy/sessions` | `SessionCreate` | `SessionResponse` | proxy_session |
| list_sessions | GET | `/api/v1/proxy/sessions` | query | `SessionListResponse` | proxy_session |
| get_session | GET | `/api/v1/proxy/sessions/{session_id}` | path | `SessionResponse` | proxy_session |
| delete_session | DELETE | `/api/v1/proxy/sessions/{session_id}` | path | inline object | proxy_session |
| proxy_execute | POST | `/api/v1/proxy/execute` | `ProxyExecuteRequest` | `ProxyExecuteResponse` | proxy_exec |
| proxy_execute_stream | POST | `/api/v1/proxy/execute/stream` | `ProxyExecuteRequest` | `ProxyStreamEvent`(SSE) | proxy_exec |
| proxy_stats | GET | `/api/v1/proxy/stats` | - | `ProxyStatsResponse` | proxy_exec |

## 错误码映射

| code | 场景 |
|---|---|
| `400` | 业务参数错误（如 session/workspace 不存在） |
| `404` | 资源不存在 |
| `422` | 请求体验证失败 |
| `501` | 未实现接口（tool execute） |
| `503` | Proxy 服务不可用 |

## 机读 JSON（可直接喂给大模型）

```json
{
  "base_url": "http://localhost:8000",
  "prefix": "/api/v1",
  "sse_endpoint": "/api/v1/proxy/execute/stream",
  "key_models": [
    "AgentExecuteRequest",
    "AgentExecuteResponse",
    "PlanCreate",
    "PlanResponse",
    "WorkspaceCreate",
    "SessionCreate",
    "ProxyExecuteRequest",
    "ProxyExecuteResponse",
    "ProxyStreamEvent"
  ]
}
```
