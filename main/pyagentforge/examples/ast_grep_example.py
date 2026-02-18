"""
AST-Grep 插件使用示例

演示如何使用 AST-Grep 工具进行代码搜索和替换
"""

import asyncio
from pyagentforge import create_engine
from pyagentforge.providers import AnthropicProvider
from pyagentforge.config.plugin_config import PluginConfig


async def example_with_config_file():
    """
    使用配置文件的方式启用 AST-Grep 插件
    """
    # 创建 provider
    provider = AnthropicProvider(api_key="your-anthropic-key")

    # 方式 1: 从 YAML 文件加载配置
    # 首先创建 plugin_config.yaml:
    # """
    # enabled:
    #   - tool.ast-grep
    # config:
    #   tool.ast-grep:
    #     auto_install: false
    # """
    plugin_config = PluginConfig.from_yaml("plugin_config.yaml")

    # 创建引擎
    engine = await create_engine(
        provider=provider,
        plugin_config=plugin_config,
        working_dir="/path/to/your/project",
    )

    # 使用 AST-Grep 搜索
    result = await engine.run("""
请使用 ast_grep_search 搜索项目中所有的 print 语句。
参数:
- pattern: print($MSG)
- lang: python
""")
    print(result)


async def example_with_code_config():
    """
    使用代码直接配置的方式启用 AST-Grep 插件
    """
    # 创建 provider
    provider = AnthropicProvider(api_key="your-anthropic-key")

    # 方式 2: 代码直接配置
    plugin_config = PluginConfig(
        enabled=["tool.ast-grep"],
        config={
            "tool.ast-grep": {
                "auto_install": True,  # 自动安装 ast-grep
            }
        }
    )

    # 创建引擎
    engine = await create_engine(
        provider=provider,
        plugin_config=plugin_config,
    )

    # 示例 1: 搜索所有 console.log
    result = await engine.run("""
使用 ast_grep_search 搜索所有 console.log 调用:
- pattern: console.log($MSG)
- lang: javascript
- paths: ["./src"]
""")
    print("=== 搜索 console.log ===")
    print(result)

    # 示例 2: 搜索 Python 函数定义
    result = await engine.run("""
使用 ast_grep_search 搜索所有异步函数定义:
- pattern: async def $NAME($$$)
- lang: python
""")
    print("\n=== 搜索 async 函数 ===")
    print(result)

    # 示例 3: 预览替换 (dry-run)
    result = await engine.run("""
使用 ast_grep_replace 预览将 print 替换为 logger.info:
- pattern: print($MSG)
- rewrite: logger.info($MSG)
- lang: python
- dry_run: true
""")
    print("\n=== 预览替换 ===")
    print(result)

    # 示例 4: 实际替换
    result = await engine.run("""
使用 ast_grep_replace 将 console.log 替换为 logger.info:
- pattern: console.log($MSG)
- rewrite: logger.info($MSG)
- lang: javascript
- dry_run: false  # 实际修改文件
""")
    print("\n=== 实际替换 ===")
    print(result)


async def example_direct_tool_usage():
    """
    直接使用工具 (不通过 Agent)
    """
    from pyagentforge.plugins.tools.ast_grep import (
        BinaryManager,
        AstGrepSearchTool,
        AstGrepReplaceTool,
    )

    # 创建二进制管理器
    manager = BinaryManager(auto_install=False)

    # 检查可用性
    if not await manager.is_available():
        print(manager.get_install_hint())
        return

    # 创建搜索工具
    search_tool = AstGrepSearchTool(binary_manager=manager)

    # 执行搜索
    result = await search_tool.execute(
        pattern="def $FUNC($$$):",
        lang="python",
        paths=["."],
        globs=["!**/test_*.py"],  # 排除测试文件
    )
    print("=== 搜索函数定义 ===")
    print(result)

    # 创建替换工具
    replace_tool = AstGrepReplaceTool(binary_manager=manager)

    # 预览替换
    result = await replace_tool.execute(
        pattern="print($MSG)",
        rewrite="logging.info($MSG)",
        lang="python",
        dry_run=True,
    )
    print("\n=== 预览替换 ===")
    print(result)


# 支持的语言列表
SUPPORTED_LANGUAGES = [
    "bash", "c", "cpp", "csharp", "css", "elixir", "go", "haskell",
    "html", "java", "javascript", "json", "kotlin", "lua", "nix",
    "php", "python", "ruby", "rust", "scala", "solidity", "swift",
    "typescript", "tsx", "yaml",
]

# 常用模式示例
PATTERN_EXAMPLES = {
    "python": {
        "函数定义": "def $NAME($$$):",
        "异步函数": "async def $NAME($$$):",
        "类定义": "class $NAME($$$):",
        "print 语句": "print($MSG)",
        "import 语句": "import $MODULE",
    },
    "javascript": {
        "函数声明": "function $NAME($$$) { $$$ }",
        "箭头函数": "const $NAME = ($$$) => $BODY",
        "console.log": "console.log($MSG)",
        "export 函数": "export function $NAME($$$) { $$$ }",
    },
    "typescript": {
        "接口定义": "interface $NAME { $$$ }",
        "类型定义": "type $NAME = $TYPE",
        "泛型函数": "function $NAME<$T>($$$): $RET { $$$ }",
    },
}


if __name__ == "__main__":
    print("AST-Grep 插件使用示例")
    print("=" * 50)
    print("\n支持的语言:", ", ".join(SUPPORTED_LANGUAGES))
    print("\n常用模式示例:")
    for lang, patterns in PATTERN_EXAMPLES.items():
        print(f"\n{lang}:")
        for name, pattern in patterns.items():
            print(f"  {name}: {pattern}")

    # 运行示例
    # asyncio.run(example_with_code_config())
    # asyncio.run(example_direct_tool_usage())
