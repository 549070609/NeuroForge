# Tool System

## Import

```python
from pyagentforge import (
    ToolRegistry, register_core_tools, BaseTool,
    BashTool, ReadTool, WriteTool, EditTool, GlobTool, GrepTool,
    LsTool, WebFetchTool, WebSearchTool, TodoWriteTool, TodoReadTool,
    QuestionTool, ConfirmTool, PlanTool, PlanEnterTool, PlanExitTool,
    MultiEditTool, BatchTool, TaskTool, CodeSearchTool, ApplyPatchTool,
    DiffTool, LSPTool, WorkspaceTool, ExternalDirectoryTool,
    TruncationTool, ContextCompactTool, InvalidTool, ToolSuggestionTool,
)
```

## ToolRegistry

```python
registry = ToolRegistry()
register_core_tools(registry)                         # bash read write edit glob grep
register_core_tools(registry, working_dir="/path")    # scoped filesystem access

registry.register(WebFetchTool())
registry.get("bash") -> BaseTool | None
registry.get_all() -> dict[str, BaseTool]
len(registry) -> int
registry.filter_by_permission(["read", "write"]) -> ToolRegistry
registry.unregister("bash")
```

## Built-in Tools

```
bash            BashTool               execute shell command
read            ReadTool               read file contents
write           WriteTool              write file
edit            EditTool               string-replace edit file
glob            GlobTool               find files by pattern
grep            GrepTool               regex search in files
ls              LsTool                 list directory
web_fetch       WebFetchTool           fetch URL content
web_search      WebSearchTool          web search
todo_write      TodoWriteTool          write structured TODO list
todo_read       TodoReadTool           read TODO list
question        QuestionTool           multi-choice prompt to user
confirm         ConfirmTool            boolean confirmation from user
plan            PlanTool               plan management
plan_enter      PlanEnterTool          enter plan mode
plan_exit       PlanExitTool           exit plan mode
multi_edit      MultiEditTool          batch file edits
batch           BatchTool              parallel tool calls
task            TaskTool               launch sub-agent task
code_search     CodeSearchTool         semantic code search
apply_patch     ApplyPatchTool         apply unified diff
diff            DiffTool               generate file diff
lsp             LSPTool                language server protocol
workspace       WorkspaceTool          workspace operations
external_dir    ExternalDirectoryTool  access external directory
truncation      TruncationTool         context truncation
context_compact ContextCompactTool     context compression
```

## Custom BaseTool

```python
class MyTool(BaseTool):
    name = "my_tool"
    description = "one-line description"

    async def execute(self, param: str, count: int = 1) -> str:
        return "result"

    def to_anthropic_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": {
                    "param": {"type": "string"},
                    "count": {"type": "integer", "default": 1},
                },
                "required": ["param"],
            },
        }

registry.register(MyTool())
```

## Direct Execution

```python
registry = ToolRegistry()
register_core_tools(registry)

tool = registry.get("bash")
result = await tool.execute(command="echo hello")
```
