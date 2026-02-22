"""
WebFetch 工具

获取网页内容
"""

from typing import Any

import httpx

from pyagentforge.tools.base import BaseTool
from pyagentforge.tools.permission import PermissionChecker
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class WebFetchTool(BaseTool):
    """WebFetch 工具 - 获取网页内容"""

    name = "webfetch"
    description = """获取网页内容。

使用场景:
- 获取网页的原始 HTML 或渲染后内容
- 读取 API 响应
- 检查网页可访问性

支持:
- 自动跟随重定向
- 超时控制
- User-Agent 设置
"""
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "要获取的 URL",
            },
            "timeout": {
                "type": "integer",
                "description": "超时时间(秒)",
                "default": 30,
            },
            "follow_redirects": {
                "type": "boolean",
                "description": "是否跟随重定向",
                "default": True,
            },
            "selector": {
                "type": "string",
                "description": "CSS 选择器，提取特定内容",
            },
        },
        "required": ["url"],
    }
    timeout = 60
    risk_level = "low"

    def __init__(
        self,
        permission_checker: PermissionChecker | None = None,
    ) -> None:
        self.permission_checker = permission_checker

    async def execute(
        self,
        url: str,
        timeout: int = 30,
        follow_redirects: bool = True,
        selector: str | None = None,
    ) -> str:
        """获取网页内容"""
        logger.info(
            "Fetching URL",
            extra_data={"url": url, "timeout": timeout},
        )

        # 检查主机权限
        if self.permission_checker:
            from urllib.parse import urlparse
            from pyagentforge.tools.permission import PermissionResult

            host = urlparse(url).netloc
            if self.permission_checker.check_host(host) == PermissionResult.DENY:
                return f"Error: Access to host '{host}' is denied"

        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; PyAgentForge/1.0)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(
                    url,
                    headers=headers,
                    follow_redirects=follow_redirects,
                )
                response.raise_for_status()

                content_type = response.headers.get("content-type", "")

                # 处理 JSON 响应
                if "application/json" in content_type:
                    import json
                    return json.dumps(response.json(), indent=2, ensure_ascii=False)

                # 获取文本内容
                text = response.text

                # 如果有选择器，尝试提取
                if selector:
                    try:
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(text, "html.parser")
                        elements = soup.select(selector)
                        extracted = "\n".join(e.get_text(strip=True) for e in elements)
                        return f"Extracted {len(elements)} elements:\n{extracted}"
                    except ImportError:
                        pass

                # 截断过长内容
                if len(text) > 50000:
                    text = text[:50000] + "\n... (truncated)"

                return text

        except httpx.TimeoutException:
            return f"Error: Request timed out after {timeout} seconds"
        except httpx.HTTPStatusError as e:
            return f"Error: HTTP {e.response.status_code} - {e.response.reason_phrase}"
        except Exception as e:
            logger.error(
                "WebFetch error",
                extra_data={"url": url, "error": str(e)},
            )
            return f"Error fetching URL: {str(e)}"
