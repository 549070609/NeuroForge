"""
MCP stdio 传输使用示例

演示如何使用 stdio 传输连接本地 MCP 服务器
"""

import asyncio

from pyagentforge.mcp import (
    MCPClient,
    MCPClientManager,
    MCPConfig,
    TransportType,
)


async def example_stdio_filesystem():
    """
    示例: 使用 stdio 连接文件系统 MCP 服务器

    需要先安装: npx @modelcontextprotocol/server-filesystem
    """
    # 方式 1: 使用工厂方法
    client = MCPClient.from_stdio(
        command="npx",
        args=[
            "@modelcontextprotocol/server-filesystem",
            "/home/user/workspace",  # 允许访问的目录
        ],
    )

    # 连接到服务器
    if await client.connect():
        print("Connected to filesystem MCP server!")

        # 列出可用工具
        tools = await client.list_tools()
        print(f"Available tools: {[t['name'] for t in tools]}")

        # 调用工具
        result = await client.call_tool(
            "read_file",
            {"path": "/home/user/workspace/README.md"},
        )
        print(f"File content:\n{result}")

        # 断开连接
        await client.disconnect()


async def example_stdio_github():
    """
    示例: 使用 stdio 连接 GitHub MCP 服务器

    需要先安装: npx @modelcontextprotocol/server-github
    需要设置: GITHUB_TOKEN 环境变量
    """
    import os

    client = MCPClient.from_stdio(
        command="npx",
        args=["@modelcontextprotocol/server-github"],
        env={
            "GITHUB_TOKEN": os.environ.get("GITHUB_TOKEN", ""),
        },
    )

    if await client.connect():
        print("Connected to GitHub MCP server!")

        tools = await client.list_tools()
        print(f"Available tools: {[t['name'] for t in tools]}")

        # 搜索仓库
        result = await client.call_tool(
            "search_repositories",
            {"query": "python mcp"},
        )
        print(f"Search results:\n{result}")

        await client.disconnect()


async def example_http_server():
    """
    示例: 使用 HTTP 连接远程 MCP 服务器
    """
    client = MCPClient.from_http(
        url="http://localhost:8080",
        timeout=30,
    )

    if await client.connect():
        print("Connected to HTTP MCP server!")

        tools = await client.list_tools()
        print(f"Available tools: {[t['name'] for t in tools]}")

        await client.disconnect()


async def example_from_config():
    """
    示例: 从配置字典创建客户端
    """
    # stdio 配置
    stdio_config = {
        "transport": "stdio",
        "command": "npx",
        "args": ["@modelcontextprotocol/server-filesystem", "/workspace"],
        "env": {"DEBUG": "1"},
    }

    client = MCPClient.from_config(stdio_config)

    if await client.connect():
        print("Connected from config!")
        await client.disconnect()


async def example_multiple_servers():
    """
    示例: 同时管理多个 MCP 服务器
    """
    manager = MCPClientManager()

    # 添加 stdio 服务器
    await manager.add_stdio_server(
        name="filesystem",
        command="npx",
        args=["@modelcontextprotocol/server-filesystem", "/workspace"],
    )

    # 添加 HTTP 服务器
    await manager.add_http_server(
        name="remote",
        url="http://localhost:8080",
    )

    # 获取所有工具
    all_tools = await manager.get_all_tools()
    print(f"Total tools from all servers: {len(all_tools)}")

    # 使用特定服务器的工具
    fs_client = manager.get_client("filesystem")
    if fs_client:
        result = await fs_client.call_tool("list_directory", {"path": "/workspace"})
        print(f"Directory listing:\n{result}")

    # 断开所有连接
    await manager.disconnect_all()


async def example_tool_wrapper():
    """
    示例: 使用工具包装器将 MCP 工具集成到 Agent
    """
    from pyagentforge.tools.registry import ToolRegistry

    # 连接到 MCP 服务器
    client = MCPClient.from_stdio(
        command="npx",
        args=["@modelcontextprotocol/server-filesystem", "/workspace"],
    )

    if not await client.connect():
        print("Failed to connect")
        return

    # 列出工具并创建包装器
    tools = await client.list_tools()
    wrappers = client.get_all_tool_wrappers()

    # 将 MCP 工具注册到本地工具注册表
    registry = ToolRegistry()
    for wrapper in wrappers:
        registry.register(wrapper)
        print(f"Registered MCP tool: {wrapper.name}")

    # 现在可以像本地工具一样使用
    tool = registry.get("read_file")
    if tool:
        result = await tool.execute(path="/workspace/README.md")
        print(f"Result: {result}")

    await client.disconnect()


async def main():
    """运行示例"""
    print("=" * 60)
    print("MCP stdio 传输示例")
    print("=" * 60)

    # 运行示例（需要实际安装 MCP 服务器）
    # await example_stdio_filesystem()
    # await example_stdio_github()
    # await example_http_server()
    # await example_from_config()
    # await example_multiple_servers()
    # await example_tool_wrapper()

    print("\n示例代码已准备就绪，取消注释以运行具体示例")


if __name__ == "__main__":
    asyncio.run(main())
