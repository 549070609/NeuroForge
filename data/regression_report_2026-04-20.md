# NeuroForge 系统性回归测试报告

- **执行日期**: 2026-04-20
- **执行环境**: Windows / Python 3.12.10 / `.venv`
- **执行范围**: 全仓库（agentforge-engine + Service + Long-memory）
- **原始日志**:
  - `data/regression_engine.log`
  - `data/regression_service.log`
  - `data/regression_longmemory.log`

---

## 1. 总览

| 模块 | 用例数 | 通过 | 失败 | 错误 | 跳过 | 耗时 | 结论 |
|---|---|---|---|---|---|---|---|
| `main/agentforge-engine` (SDK) | 884 | **827** | 40 | 0 | 17 | 33.9s | 局部回归 |
| `main/Service` (API) | 28 | **28** | 0 | 0 | 0 | 1.7s | **全部通过** |
| `main/Long-memory/long-memory` | 31 | **24** | 1 | 6 | 0 | 25.8s | 环境相关失败 |
| **合计** | **943** | **879 (93.2%)** | **41** | **6** | **17** | ~61s | 主干健康，存在已知类别缺陷 |

> Embeddings 子模块 (`main/Long-memory/embeddings`) 本次未执行（非核心路径）。

---

## 2. agentforge-engine (SDK) 结果

整体通过率 **93.5% (827/884)**，全部 40 个失败集中在 **Agent 构建子系统**（`tests/building/**`）+ 1 个 Bash 工具小问题。核心内核 `kernel/`、`tools/`、`plugin/`、`kernel/executor`、`llm_client`、`integration/task_system` 等全部通过。

### 2.1 失败聚类

| 类别 | 数量 | 典型失败 | 根因判定 |
|---|---|---|---|
| **A. Factory 并发上限** (`max concurrent limit reached`) | 22 | `TestAgentFactory::test_factory_create_from_schema` 等 | Factory 未在 fixture 之间清理 `_spawn_counter`/ registry，同名 schema 第二次注册即超过 `max_instances` |
| **B. ToolRegistry 缺少 `set_permission_checker`** | 2 | `test_factory_create_from_name`、`test_get_stats_with_data` | 代码-测试契约不一致：`factory._create_filtered_tool_registry` 调用了 `ToolRegistry.set_permission_checker(checker)`，但 `ToolRegistry` 类未提供该方法 |
| **C. `AgentConfig.readonly` 属性缺失** | 1 | `test_get_stats_with_data` 关联 | Schema 模型缺字段或测试与模型版本漂移 |
| **D. Windows 临时文件锁** (`WinError 32`) | 14 | `test_loader.py::*`、`test_integration.py::test_yaml_load_and_run` | Loader 在打开 YAML/JSON/PY 后未关闭句柄（或子进程未退出）即 `tempfile.unlink`；Windows 独占锁 |
| **E. `TestBashTool::test_invalid_command`** | 1 | `tests/test_tools.py:118` | 断言用大小写敏感的 `"Error" in result`；Windows PowerShell 输出为小写 `error`，属**测试用例缺陷**（修复：`"error" in lowered`） |

### 2.2 根因归类

- **阻塞性缺陷 (产品代码)**：`B` — `ToolRegistry.set_permission_checker` 方法缺失，且 `D` 中 Loader 未释放文件句柄。
- **测试隔离缺陷**：`A` — `AgentFactory` 单例/计数器缺失 per-test reset fixture。
- **模型漂移**：`C` — `AgentConfig` 缺 `readonly` 字段或测试过期。
- **平台相关测试 bug**：`E` — 断言大小写错误。

### 2.3 建议修复优先级

1. **P0** 补齐 `pyagentforge/tools/registry.py::ToolRegistry.set_permission_checker` 或把 `factory._create_filtered_tool_registry` 改为构造函数注入。
2. **P0** 在 `tests/building/conftest.py` 增加 `autouse` fixture，在每个 test 结束时：`AgentFactory.reset()` + 清理 `AgentRegistry` 内的 schema/计数器。
3. **P1** `AgentLoader` 内部改用 `with open(...)` 显式关闭；或测试中在 `unlink` 前执行 `gc.collect()` + 容错重试（`tenacity`）。
4. **P1** 对齐 `AgentConfig` 与测试期望的 `readonly` 字段。
5. **P2** 修正 `tests/test_tools.py:118` 断言为大小写不敏感。

---

## 3. Service (API) 结果

**28/28 全部通过**，覆盖：

- `gateway/` — `agents/execute`、Proxy P1 路由、workflow/trace/governance 路由
- `services/` — `AgentProxyService` P1/P2（guardrail、review、circuit、handoff）、`AgentService.execute`、`ServiceRegistry`、`SessionManager` 持久化 + 并发隔离、`PersistenceStore` (memory / sqlite)
- `health`、`tools`

**结论**：API 层当前回归通过，契约稳定。

### 3.1 非阻塞告警

- 149 条 `DeprecationWarning: datetime.datetime.utcnow()`，集中于 `services/proxy/session_manager.py`、`services/proxy/agent_proxy_service.py`、`services/agent_service.py`。
  - 建议统一替换为 `datetime.now(timezone.utc)`，避免 Python 3.13 移除后破坏。

---

## 4. Long-memory 结果

**24/31**。1 个失败 + 6 个 errors，**全部为 Windows 下 ChromaDB 临时目录无法释放**（`PermissionError: WinError 32 ... data_level0.bin`），非产品逻辑缺陷。

- 失败：`tests/test_standalone.py::test_basic_operations`（`shutil.rmtree(tmpdir)` 在 chromadb 客户端仍持有 mmap 时触发）。
- 错误：`tests/test_vector_store.py::TestChromaVectorStore::*`（teardown 阶段同类问题）。

### 4.1 建议修复

1. **P1** 测试 fixture 在删除目录前显式 `client.reset()` / `collection.close()` 并 `gc.collect()`。
2. **P2** 使用 `shutil.rmtree(tmpdir, ignore_errors=True)` 或 `pytest` 的 `tmp_path` fixture 并容忍 Windows 清理。
3. **P3** 日志中 `chromadb.telemetry.product.posthog` 报错（`capture() takes 1 positional argument but 3 were given`）来自 chromadb 与 posthog 版本不匹配，可固定 `posthog` 版本或关闭 telemetry。

---

## 5. 关键风险与结论

- **API (Service) 层**：回归健康，可发布。
- **SDK (agentforge-engine) 内核**：健康；**Agent Building 子系统存在 2 个阻塞性代码-测试契约缺陷**（`ToolRegistry.set_permission_checker`、`AgentConfig.readonly`）+ fixture 隔离缺失，建议在发布前修复。
- **Long-memory**：逻辑通过，Windows 下测试清理脆弱，建议加固 fixture。

### 推荐下一步

1. 新建 issue：`[engine] ToolRegistry 缺少 set_permission_checker 方法`（P0）。
2. 新建 issue：`[engine] AgentFactory 单例/计数器未 per-test reset`（P0）。
3. 新建 issue：`[engine] AgentLoader Windows 临时文件句柄未释放`（P1）。
4. 新建 issue：`[service] 替换全部 datetime.utcnow()`（P1，技术债）。
5. 新建 issue：`[long-memory] ChromaDB fixture teardown Windows 兼容`（P1）。

---

## 6. 复现命令

```powershell
# Engine
..\..\.venv\Scripts\python.exe -m pytest -v --tb=short
# CWD: main/agentforge-engine

# Service
..\..\.venv\Scripts\python.exe -m pytest tests/ -v --tb=short
# CWD: main/Service

# Long-memory
..\..\..\.venv\Scripts\python.exe -m pytest tests/ -v --tb=short
# CWD: main/Long-memory/long-memory
```
