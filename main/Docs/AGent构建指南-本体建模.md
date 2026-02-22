# AGent构建指南（本体建模版）

> 输出位置：`E:\localproject\Agent Learn\main\Docs\AGent构建指南-本体建模.md`  
> 扫描基线日期：**2026-02-22**  
> 扫描范围：`main/agentforge-engine/pyagentforge`（以源码为唯一事实源）

## 第1章 范围与架构基线

### 1.1 范围
本指南聚焦 Agent 的“构建”与“装配”：

1. Agent 本体（Schema/Metadata/Config）
2. 构建方法全集（工厂、Builder、Loader、Registry）
3. 工具全集（内置工具、命令工具、技能工具、插件工具、MCP 动态工具）
4. 运行工作流（从定义到执行到运维）

### 1.2 架构基线（重要）
当前代码呈现“**kernel 主栈 + core 兼容栈**”并存：

1. 对外顶层入口 `pyagentforge.__init__.py` 默认走 `kernel` 栈。
2. 代码内仍存在大量 `core` 路径引用（兼容层与插件中都存在）。
3. 文档中的工作流按“当前可见主路径”描述，同时标注一致性注意点。

关键入口：

- `main/agentforge-engine/pyagentforge/__init__.py`
- `main/agentforge-engine/pyagentforge/kernel/engine.py`
- `main/agentforge-engine/pyagentforge/building/*`
- `main/agentforge-engine/pyagentforge/tools/registry.py`

---

## 第2章 Agent 本体模型（Ontology）

### 2.1 本体类（Classes）

| 本体类 | 语义 | 关键属性 | 源码 |
|---|---|---|---|
| `AgentSchema` | Agent 的声明式总定义 | `identity/category/cost/capabilities/model/behavior/limits/dependencies/memory/metadata` | `main/agentforge-engine/pyagentforge/building/schema.py` |
| `AgentIdentity` | 身份标识本体 | `name/version/namespace/description/tags/author/license` | `main/agentforge-engine/pyagentforge/building/schema.py` |
| `ModelConfiguration` | 模型配置本体 | `provider/model/temperature/max_tokens/reasoning_effort/timeout` | `main/agentforge-engine/pyagentforge/building/schema.py` |
| `CapabilityDefinition` | 能力与权限本体 | `tools/denied_tools/ask_tools/skills/commands/path/host/command_*` | `main/agentforge-engine/pyagentforge/building/schema.py` |
| `BehaviorDefinition` | 行为策略本体 | `system_prompt/prompt_append/use_when/avoid_when/key_trigger/triggers/lifecycle hooks` | `main/agentforge-engine/pyagentforge/building/schema.py` |
| `ExecutionLimits` | 执行约束本体 | `is_readonly/supports_background/max_concurrent/timeout/max_iterations/max_subagent_depth` | `main/agentforge-engine/pyagentforge/building/schema.py` |
| `DependencyDefinition` | 依赖关系本体 | `requires/optional_requires/conflicts_with` | `main/agentforge-engine/pyagentforge/building/schema.py` |
| `MemoryConfiguration` | 记忆策略本体 | `enabled/max_messages/persistent_session/compaction_threshold` | `main/agentforge-engine/pyagentforge/building/schema.py` |
| `AgentMetadata` | 运行时选型元数据本体 | `category/cost/tools/use_when/avoid_when/triggers/tags/...` | `main/agentforge-engine/pyagentforge/agents/metadata.py` |
| `AgentConfig` | 运行参数本体 | `model/system_prompt/allowed_tools/permission_checker/...` | `main/agentforge-engine/pyagentforge/agents/config.py` |
| `AgentEngine` | 执行器本体 | `provider/tools/context/executor/config/session_id` | `main/agentforge-engine/pyagentforge/kernel/engine.py` |
| `ToolRegistry` | 工具集合本体 | `_tools/_tool_factories` | `main/agentforge-engine/pyagentforge/tools/registry.py` |
| `PermissionConfig` + `PermissionChecker` | 安全策略本体 | `allowed/denied/ask/path/host/command/parameter_rules` | `main/agentforge-engine/pyagentforge/tools/permission.py` |
| `ModelRegistry` + `ModelConfig` | 模型目录本体 | `provider/api_type/capability/cost/context_window` | `main/agentforge-engine/pyagentforge/kernel/model_registry.py` |
| `PluginManager` | 插件编排本体 | `registry/hooks/resolver/loader/context` | `main/agentforge-engine/pyagentforge/plugin/manager.py` |

### 2.2 对象属性（Object Properties）

1. `AgentSchema hasIdentity AgentIdentity`
2. `AgentSchema hasModelConfiguration ModelConfiguration`
3. `AgentSchema hasCapabilities CapabilityDefinition`
4. `AgentSchema hasBehavior BehaviorDefinition`
5. `AgentSchema hasLimits ExecutionLimits`
6. `AgentSchema hasDependencies DependencyDefinition`
7. `AgentSchema hasMemory MemoryConfiguration`
8. `AgentSchema transformsTo AgentMetadata`
9. `AgentSchema transformsTo AgentConfig`
10. `AgentFactory instantiates AgentEngine`
11. `AgentEngine uses BaseProvider`
12. `AgentEngine uses ToolRegistry`
13. `ToolExecutor checks PermissionChecker`
14. `PluginManager injects BaseTool`
15. `MCPClient wraps RemoteToolAs BaseTool`

### 2.3 数据属性（Datatype Properties）

1. Agent 分类：`exploration/planning/coding/review/research/reasoning`
2. 成本等级：`free/cheap/moderate/expensive`
3. 推理强度：`low/medium/high/xhigh`
4. 工具风险等级：`low/medium/high`
5. 权限判定：`allow/deny/ask`

### 2.4 约束（Constraints）

1. `AgentSchema` 各子模型 `extra="forbid"`，禁止未知字段。
2. 温度、token、timeout、并发、迭代等字段有上下界。
3. `ToolRegistry` 使用工具名唯一键，重复注册会覆盖旧实例。
4. `PermissionChecker` 按“参数级 -> 工具级 -> 默认拒绝”顺序判定。

---

## 第3章 构建方法全集（Methods）

### 3.1 顶层创建入口

1. `async create_engine(provider, config, plugin_config, working_dir, **kwargs)`
2. `create_minimal_engine(provider, working_dir, **kwargs)`

源码：`main/agentforge-engine/pyagentforge/__init__.py`

### 3.2 `AgentSchema` 方法全集

1. `to_agent_metadata`
2. `to_agent_config`
3. `from_metadata`
4. `compute_content_hash`
5. `get_full_name`
6. `__hash__`
7. `__eq__`

源码：`main/agentforge-engine/pyagentforge/building/schema.py`

### 3.3 `AgentBuilder` Fluent API（全量穷举）

身份域：

1. `with_name`
2. `with_version`
3. `with_description`
4. `with_tags`
5. `add_tag`
6. `with_namespace`
7. `with_author`

模型域：

1. `with_model`
2. `with_provider`
3. `with_temperature`
4. `with_max_tokens`
5. `with_reasoning_effort`
6. `with_timeout`

能力域：

1. `add_tool`
2. `add_tools`
3. `with_all_tools`
4. `allow_tools`
5. `deny_tools`
6. `ask_for_tools`
7. `add_skill`
8. `add_command`

行为域：

1. `with_prompt`
2. `append_prompt`
3. `with_trigger`
4. `with_key_trigger`
5. `use_when`
6. `avoid_when`
7. `on_init`
8. `on_activate`
9. `on_deactivate`

限制与依赖域：

1. `readonly`
2. `background`
3. `max_concurrent`
4. `with_max_iterations`
5. `with_max_subagent_depth`
6. `requires`
7. `optional_requires`
8. `conflicts_with`

记忆与元数据域：

1. `with_memory`
2. `without_memory`
3. `persistent_session`
4. `with_category`
5. `with_cost`
6. `with_metadata`

继承与构建域：

1. `inherit_from`
2. `extend_from`
3. `build`
4. `build_and_register`

模板方法：

1. `AgentTemplate.explorer`
2. `AgentTemplate.planner`
3. `AgentTemplate.coder`
4. `AgentTemplate.reviewer`
5. `AgentTemplate.researcher`
6. `AgentTemplate.advisor`

源码：`main/agentforge-engine/pyagentforge/building/builder.py`

### 3.4 `AgentFactory` 方法全集

实例创建与过滤：

1. `create_from_schema`
2. `create_from_name`
3. `_create_filtered_tool_registry`

单例管理：

1. `get_or_create_singleton`
2. `has_singleton`
3. `destroy_singleton`
4. `list_singletons`

对象池管理：

1. `create_pool`
2. `get_pool`
3. `get_from_pool`
4. `return_to_pool`
5. `destroy_pool`
6. `list_pools`

原型管理：

1. `register_prototype`
2. `create_from_prototype`
3. `_apply_overrides`
4. `list_prototypes`

统计：

1. `get_stats`

源码：`main/agentforge-engine/pyagentforge/building/factory.py`

### 3.5 `AgentLoader` 方法全集

加载：

1. `load_from_yaml`
2. `load_from_json`
3. `load_from_python`
4. `load`
5. `load_directory`

卸载与重载：

1. `unload`
2. `unload_all`
3. `reload`

热加载：

1. `enable_hot_reload`
2. `disable_hot_reload`

依赖与状态：

1. `resolve_dependencies`
2. `get_loaded`
3. `list_loaded`
4. `get_state`

内部解析：

1. `_parse_schema`
2. `_register_loaded`

依赖解析器：

1. `resolve_load_order`
2. `check_conflicts`

源码：`main/agentforge-engine/pyagentforge/building/loader.py`

### 3.6 `AgentRegistry` 方法全集

注册与查询：

1. `register`
2. `unregister`
3. `get`
4. `list_all`
5. `list_names`

分类与成本筛选：

1. `get_by_category`
2. `get_by_cost`
3. `get_readonly`
4. `get_background_capable`

工具可用集与匹配：

1. `set_tool_registry`
2. `get_available_tools`
3. `match_agent`
4. `find_by_capability`
5. `find_by_tags`
6. `find_best_for_task`

实例并发管理：

1. `register_instance`
2. `unregister_instance`
3. `get_instance`
4. `list_active_instances`
5. `get_concurrency_usage`
6. `can_spawn`

源码：`main/agentforge-engine/pyagentforge/agents/registry.py`

### 3.7 `ToolRegistry` 方法全集

1. `register`
2. `unregister`
3. `get`
4. `has`
5. `get_all`
6. `get_schemas`
7. `filter_by_permission`
8. `register_builtin_tools`
9. `register_p0_tools`
10. `register_p1_tools`
11. `register_p2_tools`
12. `register_extended_tools`
13. `register_task_tool`
14. `register_factory`
15. `get_or_create`
16. `auto_discover_tools`
17. `register_all_tools`
18. `register_command_tools`

源码：`main/agentforge-engine/pyagentforge/tools/registry.py`

---

## 第4章 工具全集（穷举）

### 4.1 运行时“默认工具面”与“全量工具面”

1. 顶层 `create_engine` / `create_minimal_engine` 默认仅注册 `kernel/core_tools` 的 6 个核心工具。
2. `tools/registry.py` 维护的是扩展工具全集（P0/P1/P2/extended/task/command）。
3. 因此要区分：
   - 默认运行时工具面（最小）
   - 全量注册工具面（按注册函数组合）

### 4.2 默认核心 6 工具（`kernel/core_tools`）

| 工具名 | 类 | 风险 | 源码 |
|---|---|---|---|
| `bash` | `BashTool` | high | `main/agentforge-engine/pyagentforge/kernel/core_tools/bash.py` |
| `read` | `ReadTool` | low | `main/agentforge-engine/pyagentforge/kernel/core_tools/read.py` |
| `write` | `WriteTool` | medium | `main/agentforge-engine/pyagentforge/kernel/core_tools/write.py` |
| `edit` | `EditTool` | medium | `main/agentforge-engine/pyagentforge/kernel/core_tools/edit.py` |
| `glob` | `GlobTool` | low | `main/agentforge-engine/pyagentforge/kernel/core_tools/glob.py` |
| `grep` | `GrepTool` | low | `main/agentforge-engine/pyagentforge/kernel/core_tools/grep.py` |

### 4.3 内置工具全集（`tools/builtin`，29 个）

| 工具名 | 类 | 注册入口 | 风险 | timeout(s) | 源码 |
|---|---|---|---|---:|---|
| `apply_patch` | `ApplyPatchTool` | `register_p1_tools` | high | 60 | `main/agentforge-engine/pyagentforge/tools/builtin/apply_patch.py` |
| `bash` | `BashTool` | `register_builtin_tools` | high | 120 | `main/agentforge-engine/pyagentforge/tools/builtin/bash.py` |
| `batch` | `auto_discover/manual`（默认不含） | 手工注册 | medium | 120 | `main/agentforge-engine/pyagentforge/tools/builtin/batch.py` |
| `codesearch` | `CodeSearchTool` | `register_p1_tools` | low | 60 | `main/agentforge-engine/pyagentforge/tools/builtin/codesearch.py` |
| `compact` | `ContextCompactTool` | `register_p2_tools` | low | 30 | `main/agentforge-engine/pyagentforge/tools/builtin/truncation.py` |
| `confirm` | `ConfirmTool` | `register_p0_tools` | low | 120 | `main/agentforge-engine/pyagentforge/tools/builtin/question.py` |
| `diff` | `DiffTool` | `register_p1_tools` | low | 30 | `main/agentforge-engine/pyagentforge/tools/builtin/apply_patch.py` |
| `edit` | `EditTool` | `register_builtin_tools` | medium | 30 | `main/agentforge-engine/pyagentforge/tools/builtin/edit.py` |
| `external_directory` | `ExternalDirectoryTool` | `register_p2_tools` | high | 120 | `main/agentforge-engine/pyagentforge/tools/builtin/external_directory.py` |
| `glob` | `GlobTool` | `register_builtin_tools` | low | 30 | `main/agentforge-engine/pyagentforge/tools/builtin/glob.py` |
| `grep` | `GrepTool` | `register_builtin_tools` | low | 60 | `main/agentforge-engine/pyagentforge/tools/builtin/grep.py` |
| `invalid` | `InvalidTool` | `register_p2_tools` | low | 5 | `main/agentforge-engine/pyagentforge/tools/builtin/invalid.py` |
| `ls` | `LsTool` | `register_p0_tools` | low | 30 | `main/agentforge-engine/pyagentforge/tools/builtin/ls.py` |
| `lsp` | `LSPTool` | `register_p0_tools` | low | 60 | `main/agentforge-engine/pyagentforge/tools/builtin/lsp.py` |
| `multiedit` | `MultiEditTool` | `register_extended_tools` | medium | 60 | `main/agentforge-engine/pyagentforge/tools/builtin/multiedit.py` |
| `plan` | `PlanTool` | `register_p1_tools` | low | 10 | `main/agentforge-engine/pyagentforge/tools/builtin/plan.py` |
| `plan_enter` | `PlanEnterTool` | `auto_discover/manual`（默认不含） | low | 10 | `main/agentforge-engine/pyagentforge/tools/builtin/plan.py` |
| `plan_exit` | `PlanExitTool` | `auto_discover/manual`（默认不含） | low | 10 | `main/agentforge-engine/pyagentforge/tools/builtin/plan.py` |
| `question` | `QuestionTool` | `register_p0_tools` | low | 300 | `main/agentforge-engine/pyagentforge/tools/builtin/question.py` |
| `read` | `ReadTool` | `register_builtin_tools` | low | 30 | `main/agentforge-engine/pyagentforge/tools/builtin/read.py` |
| `suggest_tool` | `ToolSuggestionTool` | `register_p2_tools` | low | 5 | `main/agentforge-engine/pyagentforge/tools/builtin/invalid.py` |
| `Task` | `TaskTool` | `register_task_tool` | medium | 300 | `main/agentforge-engine/pyagentforge/tools/builtin/task.py` |
| `todoread` | `TodoReadTool` | `register_extended_tools` | low | 10 | `main/agentforge-engine/pyagentforge/tools/builtin/todo.py` |
| `todowrite` | `TodoWriteTool` | `register_extended_tools` | low | 10 | `main/agentforge-engine/pyagentforge/tools/builtin/todo.py` |
| `truncation` | `TruncationTool` | `register_p2_tools` | low | 10 | `main/agentforge-engine/pyagentforge/tools/builtin/truncation.py` |
| `webfetch` | `WebFetchTool` | `register_extended_tools` | low | 60 | `main/agentforge-engine/pyagentforge/tools/builtin/webfetch.py` |
| `websearch` | `WebSearchTool` | `register_extended_tools` | low | 60 | `main/agentforge-engine/pyagentforge/tools/builtin/websearch.py` |
| `workspace` | `WorkspaceTool` | `register_p2_tools` | medium | 30 | `main/agentforge-engine/pyagentforge/tools/builtin/external_directory.py` |
| `write` | `WriteTool` | `register_builtin_tools` | medium | 30 | `main/agentforge-engine/pyagentforge/tools/builtin/write.py` |

### 4.4 命令工具与技能工具

| 工具名 | 类 | 注册入口 | 源码 |
|---|---|---|---|
| `command` | `CommandTool` | `ToolRegistry.register_command_tools` | `main/agentforge-engine/pyagentforge/commands/tool.py` |
| `list_commands` | `ListCommandsTool` | `ToolRegistry.register_command_tools` | `main/agentforge-engine/pyagentforge/commands/tool.py` |
| `Skill` | `SkillTool` | 手工注入（非默认） | `main/agentforge-engine/pyagentforge/skills/tool.py` |

### 4.5 插件静态工具全集（42 个）

说明：以下是 `plugins` 目录下静态定义的 `BaseTool` 子类名称；实际可用集取决于插件是否启用。

| 工具名 | 类 | 风险 | 源码 |
|---|---|---|---|
| `ast_grep_replace` | `AstGrepReplaceTool` | medium | `main/agentforge-engine/pyagentforge/plugins/tools/ast_grep/tools.py` |
| `ast_grep_search` | `AstGrepSearchTool` | low | `main/agentforge-engine/pyagentforge/plugins/tools/ast_grep/tools.py` |
| `background_cancel` | `BackgroundCancelTool` | medium | `main/agentforge-engine/pyagentforge/plugins/tools/background_tools.py` |
| `background_list` | `BackgroundListTool` | low | `main/agentforge-engine/pyagentforge/plugins/tools/background_tools.py` |
| `background_output` | `BackgroundOutputTool` | low | `main/agentforge-engine/pyagentforge/plugins/tools/background_tools.py` |
| `batch` | `BatchTool` | medium | `main/agentforge-engine/pyagentforge/plugins/tools/interact_tools/PLUGIN.py` |
| `call_agent` | `CallAgentTool` | medium | `main/agentforge-engine/pyagentforge/plugins/tools/call_agent.py` |
| `confirm` | `ConfirmTool` | low | `main/agentforge-engine/pyagentforge/plugins/tools/interact_tools/PLUGIN.py` |
| `cot_analyze` | `AnalyzeCoTTool` | low | `main/agentforge-engine/pyagentforge/plugins/integration/chain_of_thought/cot_tools.py` |
| `cot_clone` | `CloneCoTTool` | low | `main/agentforge-engine/pyagentforge/plugins/integration/chain_of_thought/cot_tools.py` |
| `cot_combine` | `CombineCoTTool` | medium | `main/agentforge-engine/pyagentforge/plugins/integration/chain_of_thought/cot_tools.py` |
| `cot_create` | `CreateCoTTool` | medium | `main/agentforge-engine/pyagentforge/plugins/integration/chain_of_thought/cot_tools.py` |
| `cot_delete` | `DeleteCoTTool` | high | `main/agentforge-engine/pyagentforge/plugins/integration/chain_of_thought/cot_tools.py` |
| `cot_export` | `ExportCoTTool` | low | `main/agentforge-engine/pyagentforge/plugins/integration/chain_of_thought/cot_tools.py` |
| `cot_import` | `ImportCoTTool` | medium | `main/agentforge-engine/pyagentforge/plugins/integration/chain_of_thought/cot_tools.py` |
| `cot_improve` | `ImproveCoTTool` | medium | `main/agentforge-engine/pyagentforge/plugins/integration/chain_of_thought/cot_tools.py` |
| `cot_info` | `GetCoTInfoTool` | low | `main/agentforge-engine/pyagentforge/plugins/integration/chain_of_thought/cot_tools.py` |
| `cot_list_all` | `ListAllCoTTool` | low | `main/agentforge-engine/pyagentforge/plugins/integration/chain_of_thought/cot_tools.py` |
| `cot_load` | `LoadCoTTool` | low | `main/agentforge-engine/pyagentforge/plugins/integration/chain_of_thought/cot_tools.py` |
| `cot_reflect` | `ReflectCoTTool` | low | `main/agentforge-engine/pyagentforge/plugins/integration/chain_of_thought/cot_tools.py` |
| `cot_stats` | `StatsCoTTool` | low | `main/agentforge-engine/pyagentforge/plugins/integration/chain_of_thought/cot_tools.py` |
| `cot_update` | `UpdateCoTTool` | low | `main/agentforge-engine/pyagentforge/plugins/integration/chain_of_thought/cot_tools.py` |
| `cot_validate_plan` | `ValidatePlanTool` | low | `main/agentforge-engine/pyagentforge/plugins/integration/chain_of_thought/cot_tools.py` |
| `cot_version` | `VersionCoTTool` | low | `main/agentforge-engine/pyagentforge/plugins/integration/chain_of_thought/cot_tools.py` |
| `ls` | `LsTool` | low | `main/agentforge-engine/pyagentforge/plugins/tools/file_tools/PLUGIN.py` |
| `lsp` | `LSPTool` | low | `main/agentforge-engine/pyagentforge/plugins/protocol/lsp/PLUGIN.py` |
| `python_analyze_complexity` | `PythonASTAnalyzeComplexityTool` | low | `main/agentforge-engine/pyagentforge/plugins/tools/python_ast/tools.py` |
| `python_extract_classes` | `PythonASTExtractClassesTool` | low | `main/agentforge-engine/pyagentforge/plugins/tools/python_ast/tools.py` |
| `python_find_calls` | `PythonASTFindCallsTool` | low | `main/agentforge-engine/pyagentforge/plugins/tools/python_ast/tools.py` |
| `python_find_definitions` | `PythonASTFindDefinitionsTool` | low | `main/agentforge-engine/pyagentforge/plugins/tools/python_ast/tools.py` |
| `python_find_imports` | `PythonASTFindImportsTool` | low | `main/agentforge-engine/pyagentforge/plugins/tools/python_ast/tools.py` |
| `question` | `QuestionTool` | low | `main/agentforge-engine/pyagentforge/plugins/tools/interact_tools/PLUGIN.py` |
| `skill` | `SkillTool` | low | `main/agentforge-engine/pyagentforge/plugins/skills/skill_loader/PLUGIN.py` |
| `task_create` | `TaskCreateTool` | low | `main/agentforge-engine/pyagentforge/plugins/integration/task_system/PLUGIN.py` |
| `task_get` | `TaskGetTool` | low | `main/agentforge-engine/pyagentforge/plugins/integration/task_system/PLUGIN.py` |
| `task_list` | `TaskListTool` | low | `main/agentforge-engine/pyagentforge/plugins/integration/task_system/PLUGIN.py` |
| `task_progress` | `TaskProgressTool` | low | `main/agentforge-engine/pyagentforge/plugins/integration/task_system/PLUGIN.py` |
| `task_report` | `TaskReportTool` | low | `main/agentforge-engine/pyagentforge/plugins/integration/task_system/PLUGIN.py` |
| `task_update` | `TaskUpdateTool` | medium | `main/agentforge-engine/pyagentforge/plugins/integration/task_system/PLUGIN.py` |
| `truncation` | `TruncationTool` | low | `main/agentforge-engine/pyagentforge/plugins/tools/file_tools/PLUGIN.py` |
| `webfetch` | `WebFetchTool` | low | `main/agentforge-engine/pyagentforge/plugins/tools/web_tools/PLUGIN.py` |
| `websearch` | `WebSearchTool` | low | `main/agentforge-engine/pyagentforge/plugins/tools/web_tools/PLUGIN.py` |

### 4.6 动态工具（非静态穷举）

1. MCP 客户端可把远程 MCP 工具动态包装为 `MCPToolWrapper`。
2. 这类工具名来自远程服务端，静态源码无法提前穷举。

源码：`main/agentforge-engine/pyagentforge/mcp/client.py`

---

## 第5章 Provider/Model 本体与适配方法

### 5.1 Provider 类型本体

`ProviderType` 穷举：

1. `anthropic`
2. `openai`
3. `google`
4. `azure`
5. `bedrock`
6. `custom`

源码：`main/agentforge-engine/pyagentforge/kernel/model_registry.py`

### 5.2 ModelRegistry 方法全集

1. `register_model`
2. `unregister_model`
3. `register_provider`
4. `get_model`
5. `get_all_models`
6. `get_models_by_provider`
7. `get_provider`
8. `resolve_model_pattern`
9. `create_provider_instance`
10. `refresh`

### 5.3 Provider 工厂方法全集（`ModelAdapterFactory`）

1. `create_provider`
2. `_create_provider_for_model`
3. `_create_anthropic_provider`
4. `_create_openai_provider`
5. `_create_google_provider`
6. `_create_azure_provider`
7. `_create_bedrock_provider`
8. `_create_custom_provider`
9. `get_supported_models`
10. `get_model_info`

便捷函数：

1. `create_provider(model_id, **kwargs)`
2. `get_supported_models()`

源码：`main/agentforge-engine/pyagentforge/providers/factory.py`

---

## 第6章 权限与安全本体

### 6.1 权限模型实体

1. `PermissionConfig`
2. `ParameterPermissionConfig`
3. `ParameterPermissionRule`
4. `PermissionChecker`
5. `PermissionResult(allow/deny/ask)`

源码：`main/agentforge-engine/pyagentforge/tools/permission.py`

### 6.2 判定顺序（核心语义）

`PermissionChecker.check(tool_name, tool_input)` 逻辑顺序：

1. 参数级规则先判定（可能返回 `deny/ask`）
2. 命中工具级 `denied` => `deny`
3. 命中工具级 `ask` => `ask`
4. 参数级存在 `ask` => `ask`
5. 命中工具级 `allowed` => `allow`
6. 兜底 `deny`

### 6.3 细粒度控制面

1. 命令白名单/黑名单（`check_command`）
2. 路径允许/拒绝（`check_path`）
3. 主机允许/拒绝（`check_host`）
4. 参数模式匹配（glob/exact）

---

## 第7章 扩展本体（插件/命令/技能/MCP/LSP/Prompt）

### 7.1 插件本体

插件类型（`PluginType`）

1. `interface`
2. `protocol`
3. `tool`
4. `skill`
5. `provider`
6. `middleware`
7. `integration`

插件生命周期方法：

1. `on_plugin_load`
2. `on_plugin_activate`
3. `on_plugin_deactivate`
4. 各类 hook（`on_before_llm_call`、`on_after_tool_call` 等）

插件管理器方法：

1. `initialize`
2. `activate_plugin`
3. `deactivate_plugin`
4. `emit_hook`
5. `get_tools_from_plugins`

源码：`main/agentforge-engine/pyagentforge/plugin/base.py`, `main/agentforge-engine/pyagentforge/plugin/manager.py`

### 7.2 插件 preset（源码字面值）

`PluginManager._get_preset_plugins`：

1. `minimal`：空集合
2. `standard`：`tools.code_tools`, `tools.file_tools`, `middleware.compaction`, `integration.events`
3. `full`：`protocol.mcp_server`, `protocol.mcp_client`, `protocol.lsp`, `tools.web_tools`, `tools.code_tools`, `tools.file_tools`, `tools.interact_tools`, `middleware.compaction`, `middleware.failover`, `middleware.thinking`, `middleware.rate_limit`, `integration.persistence`, `integration.events`, `integration.context_aware`

### 7.3 命令系统

`CommandRegistry` 方法全集：

1. `load_commands/load_commands_async/reload_commands`
2. `register/register_handler/unregister`
3. `get/get_all_commands/get_command_names/get_descriptions/has_command`
4. `get_prompt_for_command/get_prompt_for_command_async`
5. `add_pre_hook/add_post_hook`

命令工具：`command`, `list_commands`

源码：`main/agentforge-engine/pyagentforge/commands/*`

### 7.4 技能系统

`SkillLoader` 方法全集：

1. `load_all`
2. `get`
3. `get_skill_content`
4. `get_descriptions`
5. `get_trigger_keywords`
6. `match_skill`
7. `get_dependencies`
8. `reload`

技能工具：

1. 核心层：`Skill`
2. 插件层：`skill`

源码：`main/agentforge-engine/pyagentforge/skills/*`, `main/agentforge-engine/pyagentforge/plugins/skills/skill_loader/PLUGIN.py`

### 7.5 MCP 与 LSP

MCP：

1. `MCPClient.from_http/from_stdio/from_config`
2. `connect/disconnect/list_tools/call_tool/get_all_tool_wrappers`
3. `MCPClientManager.add_*_server/get_all_tools`

LSP：

1. `LSPManager.start_client/ensure_client_for_file`
2. `goto_definition/find_references/hover/completion/document_symbols/rename/format`

源码：`main/agentforge-engine/pyagentforge/mcp/*`, `main/agentforge-engine/pyagentforge/lsp/*`

### 7.6 Prompt 自适应

流程方法：

1. `PromptAdapterManager.adapt_prompt`
2. `PromptTemplateRegistry.select_variant`
3. `PromptTemplateRegistry.get_capability_modules`
4. `_assemble_prompt`

源码：`main/agentforge-engine/pyagentforge/prompts/*`

---

## 第8章 Agent 构建工作流（端到端）

### 8.1 工作流 A：最小化运行时构建

1. 选择 provider（模型实例）。
2. 创建 `ToolRegistry` 并注册 `kernel/core_tools` 六件套。
3. 构建 `AgentEngine(provider, tool_registry, config)`。
4. `run(prompt)` 进入循环：LLM -> tool_calls -> ToolExecutor -> 写回上下文。
5. 达到“无工具调用”或迭代上限后结束。

适用：快速落地、低复杂度任务。

### 8.2 工作流 B：声明式构建

1. 用 `AgentBuilder` 链式定义 Agent。
2. `build()` 产出 `AgentSchema`。
3. `AgentFactory.create_from_schema(schema)` 生成实例。
4. 或 `AgentLoader.load_from_yaml/json/python` 从文件体系加载。
5. 注册到 `AgentRegistry`，按任务匹配分发。

适用：多 Agent 编排、团队规范化。

### 8.3 工作流 C：全量扩展构建

1. 先完成 A 或 B。
2. 通过 `ToolRegistry` 追加 P0/P1/P2/extended/task/command 工具。
3. 初始化 `PluginManager`，按 preset + enabled + disabled 计算最终插件集。
4. 激活插件并注入插件工具、钩子、协议能力（MCP/LSP）。
5. 加入权限策略（工具级 + 参数级 + 路径/主机/命令级）。

适用：企业级运行面、协议/插件能力丰富场景。

### 8.4 工作流 D：运维闭环

1. 以 Schema 哈希做构建可追踪（`compute_content_hash`）。
2. 用 Loader 热重载和依赖顺序控制变更。
3. 使用 AgentPool/Singleton 约束资源与并发。
4. 用插件 hook 注入观测、恢复、压缩、任务系统。

---

## 第9章 典型装配蓝图

### 9.1 蓝图一：最小只读探索 Agent

```python
from pyagentforge import create_minimal_engine

# provider 由外部先构建
engine = create_minimal_engine(provider=provider, working_dir='.')
# 默认仅 6 核心工具: bash/read/write/edit/glob/grep
```

### 9.2 蓝图二：声明式编码 Agent

```python
from pyagentforge.building import AgentBuilder

schema = (
    AgentBuilder()
    .with_name("coder_a")
    .with_model("claude-sonnet-4-20250514")
    .with_all_tools()
    .with_max_iterations(80)
    .with_max_subagent_depth(3)
    .with_prompt("你是高可靠编码代理")
    .build()
)
```

### 9.3 蓝图三：文件化批量加载

```yaml
identity:
  name: reviewer_a
  version: 1.0.0
model:
  provider: anthropic
  model: claude-sonnet-4-20250514
capabilities:
  tools: ["bash", "read", "glob", "grep"]
limits:
  is_readonly: true
  max_iterations: 50
```

配合：`AgentLoader.load_directory(...)` + `resolve_dependencies(...)`

---

## 第10章 构建检查清单与反模式

### 10.1 上线前检查清单

1. 是否明确采用 `kernel` 主栈还是兼容 `core` 路径。
2. 是否区分“默认 6 工具”与“全量工具面”。
3. 是否配置权限策略（工具/参数/路径/主机/命令）。
4. 是否验证插件 preset 与真实插件 ID 一致。
5. 是否为 Task/Command/Skill/MCP 工具设计显式注册路径。
6. 是否覆盖并发与迭代上限。

### 10.2 常见反模式

1. 误以为 `create_engine()` 自动拥有全部工具。
2. 只配 `allowed_tools`，未配参数级规则，导致高风险命令缺乏细粒度控制。
3. 直接启用大量插件但不校验依赖和冲突。
4. 将动态 MCP 工具当成静态内建工具处理。

### 10.3 当前源码一致性注意点（深度检查结论）

1. `create_engine` 默认注册的是 `kernel/core_tools`，不是 `tools/registry` 的全量集合。
2. `register_all_tools()` 不包含 `Task`、`command/list_commands`、`batch`、`plan_enter`、`plan_exit`。
3. `auto_discover_tools()` 只能实例化无参工具；`Task`、`Batch` 等仍需专门装配。
4. `AgentFactory._create_filtered_tool_registry` 调用了 `subset.set_permission_checker(...)`，而 `ToolRegistry` 中未见该方法定义。
5. `AgentFactory.create_from_schema` 里 `ContextManager(...)` 传参与 `kernel/context.py` 构造签名存在差异。
6. `AgentRegistry.get_available_tools` 依赖 `tool_registry.list_names()`，但 `ToolRegistry` 中未见该方法定义。
7. 插件 preset 中的若干 ID（如 `tools.file_tools`、`tools.code_tools`、`middleware.rate_limit`）需与实际插件元数据二次核对。

---

## 第11章 建议的实施策略

1. 若要稳定落地，建议以 `kernel` 为主栈，逐步收敛 `core` 兼容路径。
2. 先跑“最小 6 工具 + 权限策略”，再按场景逐层增开 P0/P1/P2/extended。
3. 对插件工具采用“白名单启用”，并记录每次注入的工具名与风险级别。
4. 把本指南中的工具表和方法表作为 CI 文档校验基线，避免后续演化失配。
