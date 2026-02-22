"""Tool management routes."""

from fastapi import APIRouter, Depends, HTTPException

from ...schemas import ExecuteToolRequest, ExecuteToolResponse, ToolInfo

router = APIRouter()


@router.get("/tools", response_model=list[ToolInfo])
async def list_tools() -> list[ToolInfo]:
    """
    List available tools.

    Returns:
        List of tool information
    """
    # TODO: Integrate with pyagentforge ToolRegistry
    return [
        ToolInfo(
            name="bash",
            description="Execute bash commands",
            parameters={
                "command": {"type": "string", "description": "Command to execute"},
            },
        ),
        ToolInfo(
            name="read",
            description="Read file contents",
            parameters={
                "file_path": {"type": "string", "description": "Path to file"},
            },
        ),
        ToolInfo(
            name="write",
            description="Write file contents",
            parameters={
                "file_path": {"type": "string", "description": "Path to file"},
                "content": {"type": "string", "description": "Content to write"},
            },
        ),
    ]


@router.post("/tools/{tool_name}/execute", response_model=ExecuteToolResponse)
async def execute_tool(
    tool_name: str,
    request: ExecuteToolRequest,
) -> ExecuteToolResponse:
    """
    Execute a tool directly.

    Path params:
        - tool_name: Tool name

    Request body:
        - parameters: Tool parameters

    Returns:
        Tool execution result
    """
    # TODO: Implement direct tool execution
    raise HTTPException(status_code=501, detail="Direct tool execution not yet implemented")
