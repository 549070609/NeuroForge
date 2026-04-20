"""
LSP 使用示例

演示如何使用 LSP 客户端和管理器
"""

import asyncio

from pyagentforge.lsp import (
    LSP_SERVER_CONFIGS,
    LSPClient,
    LSPManager,
    LSPServerConfig,
    Position,
)


async def example_basic_lsp_client():
    """
    示例: 基本的 LSP 客户端使用
    """
    # 创建 Python LSP 客户端
    config = LSP_SERVER_CONFIGS["python"]

    client = LSPClient(
        config=config,
        workspace_root="/path/to/workspace",
    )

    # 启动并初始化
    if not await client.start():
        print("Failed to start LSP server")
        return

    if not await client.initialize():
        await client.stop()
        print("Failed to initialize LSP server")
        return

    print("LSP server initialized!")
    print(f"Capabilities: {client.capabilities}")

    # 打开文件
    file_path = "/path/to/workspace/main.py"
    await client.did_open(file_path)

    # 跳转到定义
    locations = await client.goto_definition(
        file_path,
        Position(line=10, character=5),  # 0-indexed
    )
    print(f"Definition locations: {locations}")

    # 查找引用
    references = await client.find_references(
        file_path,
        Position(line=10, character=5),
    )
    print(f"References: {references}")

    # 获取悬停信息
    hover = await client.hover(
        file_path,
        Position(line=10, character=5),
    )
    print(f"Hover: {hover}")

    # 获取补全
    completion = await client.completion(
        file_path,
        Position(line=10, character=5),
    )
    print(f"Completions: {len(completion.items)} items")

    # 关闭文件
    await client.did_close(file_path)

    # 关闭客户端
    await client.shutdown()
    print("LSP client stopped")


async def example_lsp_manager():
    """
    示例: 使用 LSP 管理器管理多个语言
    """
    async with LSPManager(workspace_root="/path/to/workspace") as manager:
        # 启动 Python LSP
        python_client = await manager.start_client("python")
        if python_client:
            print("Python LSP started")

        # 启动 TypeScript LSP
        ts_client = await manager.start_client("typescript")
        if ts_client:
            print("TypeScript LSP started")

        # 自动检测文件语言并使用对应的 LSP
        python_file = "/path/to/workspace/main.py"
        symbols = await manager.document_symbols(python_file)
        print(f"Python symbols: {[s.name for s in symbols]}")

        ts_file = "/path/to/workspace/app.ts"
        locations = await manager.goto_definition(
            ts_file,
            line=20,
            character=10,
        )
        print(f"TypeScript definitions: {locations}")

        # 工作区符号搜索
        all_symbols = await manager.workspace_symbols("User")
        print(f"Found {len(all_symbols)} symbols matching 'User'")


async def example_diagnostics_handler():
    """
    示例: 处理诊断信息
    """
    from pyagentforge.lsp import Diagnostic

    def on_diagnostics(uri: str, diagnostics: list[Diagnostic]):
        """诊断处理器"""
        print(f"\nDiagnostics for {uri}:")
        for diag in diagnostics:
            severity = diag.severity.name
            line = diag.range.start.line + 1
            message = diag.message
            print(f"  [{severity}] Line {line}: {message}")

    manager = LSPManager(workspace_root="/path/to/workspace")
    manager.set_diagnostics_handler(on_diagnostics)

    # 启动客户端
    await manager.start_client("python")

    # 打开文件会触发诊断
    await manager.open_file("/path/to/workspace/main.py")

    # 等待诊断
    await asyncio.sleep(2)

    await manager.stop_all()


async def example_custom_lsp_server():
    """
    示例: 使用自定义 LSP 服务器配置
    """
    # 自定义配置
    custom_config = LSPServerConfig(
        language="python",
        command=["pyright", "--output-json"],
        extensions=[".py", ".pyi"],
        initialization_options={
            "python": {
                "analysis": {
                    "typeCheckingMode": "strict",
                }
            }
        },
    )

    manager = LSPManager(workspace_root="/path/to/workspace")

    # 使用自定义配置启动
    client = await manager.start_client("python", config=custom_config)
    if client:
        print("Custom LSP server started")


async def example_tool_usage():
    """
    示例: 在 Agent 中使用 LSP 工具
    """
    from pyagentforge.tools.builtin.lsp import LSPTool

    tool = LSPTool(workspace_root="/path/to/workspace")

    # 获取文档符号
    result = await tool.execute(
        action="document_symbols",
        file_path="/path/to/workspace/main.py",
    )
    print(result)

    # 跳转到定义
    result = await tool.execute(
        action="goto_definition",
        file_path="/path/to/workspace/main.py",
        line=10,
        column=5,
    )
    print(result)

    # 工作区符号搜索
    result = await tool.execute(
        action="workspace_symbols",
        file_path="",  # 不需要
        query="Database",
        language="python",
    )
    print(result)


async def example_supported_languages():
    """
    示例: 查看支持的语言
    """
    print("Supported LSP servers:")
    print("-" * 60)

    for lang, config in LSP_SERVER_CONFIGS.items():
        extensions = ", ".join(config.extensions[:4])
        command = " ".join(config.command[:2])
        print(f"{lang:12} | {extensions:20} | {command}")

    print("-" * 60)
    print("\nNote: You need to install the corresponding LSP server:")
    print("  Python:     pip install python-lsp-server")
    print("  TypeScript: npm install -g typescript-language-server typescript")
    print("  Go:         go install golang.org/x/tools/gopls@latest")
    print("  Rust:       rustup component add rust-analyzer")
    print("  C++:        Install clangd from your package manager")
    print("  Java:       Install jdtls (Eclipse JDT Language Server)")


async def main():
    """运行示例"""
    print("=" * 60)
    print("LSP (Language Server Protocol) 使用示例")
    print("=" * 60)

    # 显示支持的语言
    await example_supported_languages()

    # 运行示例（需要实际安装 LSP 服务器）
    # await example_basic_lsp_client()
    # await example_lsp_manager()
    # await example_diagnostics_handler()
    # await example_custom_lsp_server()
    # await example_tool_usage()

    print("\n示例代码已准备就绪，取消注释以运行具体示例")


if __name__ == "__main__":
    asyncio.run(main())
