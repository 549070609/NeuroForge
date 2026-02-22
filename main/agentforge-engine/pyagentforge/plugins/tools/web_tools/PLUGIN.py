"""
Web Tools Plugin

Provides webfetch and websearch tools
"""

import logging
from typing import Any, List

from pyagentforge.plugin.base import Plugin, PluginMetadata, PluginType
from pyagentforge.kernel.base_tool import BaseTool
from pyagentforge.tools.permission import PermissionChecker


class WebFetchTool(BaseTool):
    """WebFetch Tool - Fetch web content"""

    name = "webfetch"
    description = """Fetch web page content.

    Use scenarios:
    - Get web page HTML or rendered content
    - Read API responses
    - Check web page accessibility

    Supports:
    - Automatic redirect following
    - Timeout control
    - User-Agent settings
    """
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "URL to fetch",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds",
                "default": 30,
            },
            "follow_redirects": {
                "type": "boolean",
                "description": "Whether to follow redirects",
                "default": True,
            },
        },
        "required": ["url"],
    }
    timeout = 60
    risk_level = "low"

    def __init__(self, permission_checker: PermissionChecker | None = None) -> None:
        self.permission_checker = permission_checker

    async def execute(
        self,
        url: str,
        timeout: int = 30,
        follow_redirects: bool = True,
    ) -> str:
        """Fetch web content"""
        try:
            import httpx

            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; PyAgentForge/1.0)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }

            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(
                    url,
                    headers=headers,
                    follow_redirects=follow_redirects,
                )
                response.raise_for_status()

                content_type = response.headers.get("content-type", "")

                # Handle JSON response
                if "application/json" in content_type:
                    import json
                    return json.dumps(response.json(), indent=2, ensure_ascii=False)

                # Get text content
                text = response.text

                # Truncate long content
                if len(text) > 50000:
                    text = text[:50000] + "\n... (truncated)"

                return text

        except ImportError:
            return "Error: httpx package required. Install with: pip install httpx"
        except Exception as e:
            return f"Error fetching URL: {str(e)}"


class WebSearchTool(BaseTool):
    """WebSearch Tool - Search the web"""

    name = "websearch"
    description = """Search web content.

    Use scenarios:
    - Search for latest information
    - Find technical documentation
    - Get real-time data

    Returns search result summary list.
    """
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query",
            },
            "num_results": {
                "type": "integer",
                "description": "Number of results to return",
                "default": 10,
            },
        },
        "required": ["query"],
    }
    timeout = 60
    risk_level = "low"

    def __init__(
        self,
        permission_checker: PermissionChecker | None = None,
        api_key: str | None = None,
        search_engine_id: str | None = None,
    ) -> None:
        self.permission_checker = permission_checker
        self.api_key = api_key
        self.search_engine_id = search_engine_id

    async def execute(
        self,
        query: str,
        num_results: int = 10,
    ) -> str:
        """Execute web search"""
        # Use DuckDuckGo (no API key required)
        try:
            from duckduckgo_search import DDGS

            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=num_results):
                    results.append({
                        "title": r.get("title", ""),
                        "link": r.get("href", ""),
                        "snippet": r.get("body", ""),
                    })

            return self._format_results(results)

        except ImportError:
            return (
                f"Web search requires 'duckduckgo-search' package.\n"
                f"Install with: pip install duckduckgo-search\n\n"
                f"Query: {query}"
            )
        except Exception as e:
            return f"Error: Search failed - {str(e)}"

    def _format_results(self, results: list[dict]) -> str:
        """Format search results"""
        if not results:
            return "No results found."

        lines = [f"Found {len(results)} results:\n"]

        for i, r in enumerate(results, 1):
            lines.append(f"## {i}. {r['title']}")
            lines.append(f"URL: {r['link']}")
            lines.append(f"{r['snippet']}\n")

        return "\n".join(lines)


class WebToolsPlugin(Plugin):
    """Web tools plugin"""

    metadata = PluginMetadata(
        id="tool.web_tools",
        name="Web Tools",
        version="1.0.0",
        type=PluginType.TOOL,
        description="Provides webfetch and websearch tools for web interaction",
        author="PyAgentForge",
        provides=["tools.web"],
        dependencies=[],
    )

    def __init__(self):
        super().__init__()
        self._webfetch_tool: WebFetchTool | None = None
        self._websearch_tool: WebSearchTool | None = None

    async def on_plugin_activate(self) -> None:
        """Activate plugin"""
        await super().on_plugin_activate()

        config = self.context.config or {}

        # Create tools
        self._webfetch_tool = WebFetchTool()
        self._websearch_tool = WebSearchTool(
            api_key=config.get("google_api_key"),
            search_engine_id=config.get("google_search_engine_id"),
        )

        self.context.logger.info("Web tools plugin initialized")

    def get_tools(self) -> List[BaseTool]:
        """Return plugin provided tools"""
        tools = []
        if self._webfetch_tool:
            tools.append(self._webfetch_tool)
        if self._websearch_tool:
            tools.append(self._websearch_tool)
        return tools
