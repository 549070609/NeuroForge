"""
gitignore 文件过滤

解析 .gitignore 规则并过滤文件/目录
"""

import fnmatch
from collections.abc import Callable
from pathlib import Path

from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class GitignoreParser:
    """解析 .gitignore 规则"""

    def __init__(self, gitignore_path: Path | None = None, content: str | None = None) -> None:
        """
        初始化解析器

        Args:
            gitignore_path: .gitignore 文件路径
            content: 直接提供的 .gitignore 内容
        """
        self._patterns: list[tuple[str, bool, bool, bool]] = []  # (pattern, is_negation, is_dir_only, is_anchored)

        if gitignore_path and gitignore_path.exists():
            content = gitignore_path.read_text(encoding="utf-8")
            self._parse(content)
        elif content:
            self._parse(content)

    def _parse(self, content: str) -> None:
        """解析 .gitignore 内容"""
        for line in content.splitlines():
            line = line.rstrip()

            # 跳过空行和注释
            if not line or line.startswith("#"):
                continue

            # 处理转义的 #
            if line.startswith("\\#"):
                line = "#" + line[1:]

            is_negation = line.startswith("!")
            if is_negation:
                line = line[1:]

            # 处理尾部空格 (转义的空格保留)
            trailing_spaces = len(line) - len(line.rstrip(" "))
            if trailing_spaces > 0 and not line.endswith("\\"):
                line = line.rstrip(" ")
            elif line.endswith("\\"):
                line = line[:-1] + " "

            is_dir_only = line.endswith("/")
            if is_dir_only:
                line = line[:-1]

            # 处理开头的 /
            is_anchored = line.startswith("/")
            if is_anchored:
                line = line[1:]

            # 处理 **
            if "**" in line:
                # **/ 表示任意深度目录
                # /** 匹配任意字符
                pass  # fnmatch 支持 **

            self._patterns.append((line, is_negation, is_dir_only, is_anchored))

        logger.debug(
            "Parsed gitignore patterns",
            extra_data={"pattern_count": len(self._patterns)},
        )

    def _match_pattern(
        self,
        path: str,
        pattern: str,
        is_anchored: bool,
    ) -> bool:
        """
        匹配单个模式

        Args:
            path: 相对路径
            pattern: gitignore 模式
            is_anchored: 是否锚定到根目录

        Returns:
            是否匹配
        """
        # 转换 gitignore 模式到 fnmatch 模式
        fnmatch_pattern = pattern

        # 处理 ** 模式
        if "**" in fnmatch_pattern:
            # **/ 匹配任意目录深度
            fnmatch_pattern = fnmatch_pattern.replace("**/", "*")
            fnmatch_pattern = fnmatch_pattern.replace("/**", "*")
            fnmatch_pattern = fnmatch_pattern.replace("**", "*")

        if is_anchored:
            # 锚定模式：必须从头匹配
            return fnmatch.fnmatch(path, fnmatch_pattern)
        else:
            # 非锚定：可以匹配任意部分
            # 1. 尝试完整匹配
            if fnmatch.fnmatch(path, fnmatch_pattern):
                return True
            # 2. 尝试从任意目录开始匹配
            if fnmatch.fnmatch(path, f"*/{fnmatch_pattern}"):
                return True
            # 3. 尝试匹配文件名
            if "/" not in fnmatch_pattern:
                basename = Path(path).name
                if fnmatch.fnmatch(basename, fnmatch_pattern):
                    return True
            return False

    def is_ignored(
        self,
        path: str,
        is_dir: bool = False,
    ) -> bool:
        """
        检查路径是否被忽略

        Args:
            path: 相对路径
            is_dir: 是否是目录

        Returns:
            是否被忽略
        """
        result = False

        for pattern, is_negation, is_dir_only, is_anchored in self._patterns:
            # 如果模式只匹配目录但路径不是目录，跳过
            if is_dir_only and not is_dir:
                continue

            if self._match_pattern(path, pattern, is_anchored):
                result = not is_negation

        return result


class GitignoreFilter:
    """gitignore 过滤器"""

    def __init__(self, root_path: Path) -> None:
        """
        初始化过滤器

        Args:
            root_path: 项目根目录
        """
        self.root_path = root_path
        self._parsers: dict[Path, GitignoreParser] = {}
        self._load_gitignores()

    def _load_gitignores(self) -> None:
        """加载所有 .gitignore 文件"""
        # 加载根目录 .gitignore
        root_gitignore = self.root_path / ".gitignore"
        if root_gitignore.exists():
            self._parsers[self.root_path] = GitignoreParser(root_gitignore)
            logger.debug(
                "Loaded root gitignore",
                extra_data={"path": str(root_gitignore)},
            )

        # 加载子目录 .gitignore
        for gitignore in self.root_path.rglob(".gitignore"):
            if gitignore.parent not in self._parsers:
                self._parsers[gitignore.parent] = GitignoreParser(gitignore)

        logger.info(
            "Loaded all gitignore files",
            extra_data={"count": len(self._parsers)},
        )

    def is_ignored(self, path: Path) -> bool:
        """
        检查路径是否被忽略

        Args:
            path: 要检查的路径

        Returns:
            是否被忽略
        """
        try:
            rel_path = path.relative_to(self.root_path)
        except ValueError:
            return False

        str(rel_path).replace("\\", "/")
        is_dir = path.is_dir()

        # 从当前目录向上检查所有相关的 .gitignore
        current = path.parent if not is_dir else path

        while True:
            try:
                current.relative_to(self.root_path)
            except ValueError:
                break

            # 检查这个目录下是否有 .gitignore
            if current in self._parsers:
                parser = self._parsers[current]
                # 转换为相对于 .gitignore 所在目录的路径
                try:
                    rel_to_gitignore = path.relative_to(current)
                    rel_to_gitignore_str = str(rel_to_gitignore).replace("\\", "/")
                    if parser.is_ignored(rel_to_gitignore_str, is_dir):
                        return True
                except ValueError:
                    pass

            if current == self.root_path:
                break
            current = current.parent

        return False

    def filter_paths(
        self,
        paths: list[Path],
    ) -> list[Path]:
        """
        过滤路径列表

        Args:
            paths: 路径列表

        Returns:
            过滤后的路径列表
        """
        return [p for p in paths if not self.is_ignored(p)]

    def create_filter_func(self) -> Callable[[Path], bool]:
        """
        创建过滤函数

        Returns:
            过滤函数，返回 True 表示保留
        """
        def filter_func(path: Path) -> bool:
            return not self.is_ignored(path)

        return filter_func


def create_gitignore_filter(root_path: Path) -> GitignoreFilter | None:
    """
    创建 gitignore 过滤器

    Args:
        root_path: 项目根目录

    Returns:
        GitignoreFilter 实例或 None (如果没有 .gitignore)
    """
    gitignore_path = root_path / ".gitignore"
    if not gitignore_path.exists():
        logger.debug(
            "No .gitignore found",
            extra_data={"root_path": str(root_path)},
        )
        return None

    return GitignoreFilter(root_path)


def is_path_ignored(
    path: Path,
    root_path: Path,
) -> bool:
    """
    快速检查路径是否被忽略

    Args:
        path: 要检查的路径
        root_path: 项目根目录

    Returns:
        是否被忽略
    """
    filter_obj = create_gitignore_filter(root_path)
    if filter_obj is None:
        return False
    return filter_obj.is_ignored(path)
