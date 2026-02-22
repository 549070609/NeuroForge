"""
WebSearch 工具

搜索网页
"""

from typing import Any

import httpx

from pyagentforge.tools.base import BaseTool
from pyagentforge.tools.permission import PermissionChecker
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class WebSearchTool(BaseTool):
    """WebSearch 工具 - 搜索网页"""

    name = "websearch"
    description = """搜索网页内容。

使用场景:
- 搜索最新信息
- 查找技术文档
- 获取实时数据

返回搜索结果摘要列表。
"""
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索查询",
            },
            "num_results": {
                "type": "integer",
                "description": "返回结果数量",
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
        """执行网页搜索"""
        logger.info(
            "Searching web",
            extra_data={"query": query, "num_results": num_results},
        )

        # 如果配置了 Google Custom Search API
        if self.api_key and self.search_engine_id:
            return await self._google_search(query, num_results)

        # 否则使用 DuckDuckGo (不需要 API key)
        return await self._duckduckgo_search(query, num_results)

    async def _google_search(self, query: str, num_results: int) -> str:
        """使用 Google Custom Search API"""
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": self.api_key,
            "cx": self.search_engine_id,
            "q": query,
            "num": num_results,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

            results = []
            for item in data.get("items", []):
                results.append({
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                })

            return self._format_results(results)

        except Exception as e:
            return f"Error: Search failed - {str(e)}"

    async def _duckduckgo_search(self, query: str, num_results: int) -> str:
        """使用 DuckDuckGo 搜索 (模拟)"""
        # 注意: 这是简化实现，实际使用可能需要更复杂的处理
        # 建议使用 duckduckgo-search 库或类似工具

        try:
            # 尝试使用 duckduckgo-search 库
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
                # 如果没有安装库，返回提示
                return (
                    f"Web search requires 'duckduckgo-search' package.\n"
                    f"Install with: pip install duckduckgo-search\n\n"
                    f"Query: {query}\n"
                    f"Alternatively, configure Google Custom Search API."
                )

        except Exception as e:
            logger.error(
                "WebSearch error",
                extra_data={"query": query, "error": str(e)},
            )
            return f"Error: Search failed - {str(e)}"

    def _format_results(self, results: list[dict]) -> str:
        """格式化搜索结果"""
        if not results:
            return "No results found."

        lines = [f"Found {len(results)} results:\n"]

        for i, r in enumerate(results, 1):
            lines.append(f"## {i}. {r['title']}")
            lines.append(f"URL: {r['link']}")
            lines.append(f"{r['snippet']}\n")

        return "\n".join(lines)
