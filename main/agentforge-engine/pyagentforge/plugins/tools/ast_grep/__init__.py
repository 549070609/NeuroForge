"""
AST-Grep 工具插件

提供 AST 语法树级别的代码搜索和替换能力

使用方式:
    1. 在 plugin_config.yaml 中启用:
       enabled:
         - tool.ast-grep

    2. 或在代码中直接配置:
       plugin_config = PluginConfig(enabled=["tool.ast-grep"])

前置条件:
    安装 ast-grep CLI:
        pip install ast-grep-cli
        cargo install ast-grep --locked
        brew install ast-grep
"""

from pyagentforge.plugins.tools.ast_grep.PLUGIN import AstGrepPlugin
from pyagentforge.plugins.tools.ast_grep.tools import AstGrepSearchTool, AstGrepReplaceTool
from pyagentforge.plugins.tools.ast_grep.types import SgMatch, SgResult, Position, Range
from pyagentforge.plugins.tools.ast_grep.binary_manager import BinaryManager
from pyagentforge.plugins.tools.ast_grep.constants import CLI_LANGUAGES, LANG_EXTENSIONS

__all__ = [
    # 插件
    "AstGrepPlugin",
    # 工具
    "AstGrepSearchTool",
    "AstGrepReplaceTool",
    # 类型
    "SgMatch",
    "SgResult",
    "Position",
    "Range",
    # 管理
    "BinaryManager",
    # 常量
    "CLI_LANGUAGES",
    "LANG_EXTENSIONS",
]
