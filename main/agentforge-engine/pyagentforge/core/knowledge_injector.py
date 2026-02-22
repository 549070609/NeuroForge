"""
Knowledge Injector

Auto-inject project knowledge (README, rules) into agent context.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class KnowledgeSource:
    """Knowledge source definition"""

    name: str
    path: str
    priority: int = 0  # Higher = more important
    max_tokens: int = 8000  # Max tokens to include
    required: bool = False  # Fail if not found


@dataclass
class InjectionResult:
    """Result of knowledge injection"""

    success: bool
    sources_injected: list[str] = field(default_factory=list)
    total_tokens: int = 0
    errors: list[str] = field(default_factory=list)
    content: str = ""


class KnowledgeInjector:
    """
    Knowledge Injector

    Automatically injects project knowledge into agent context:
    - README.md files when entering directories
    - Project rules based on file type (.cursorrules, .agent/rules)
    - Custom knowledge sources
    """

    # Default knowledge sources
    DEFAULT_README_NAMES = ["README.md", "readme.md", "Readme.md"]

    # Default rules file patterns
    DEFAULT_RULES_PATTERNS = [
        ".cursorrules",
        ".agent/rules",
        ".agent/rules.md",
        ".agent/rules.txt",
        ".claude/rules",
        ".claude/rules.md",
    ]

    # File extension to rules mapping
    FILE_TYPE_RULES = {
        ".py": [".agent/rules/python", ".agent/rules.py"],
        ".ts": [".agent/rules/typescript", ".agent/rules.ts"],
        ".tsx": [".agent/rules/react", ".agent/rules.tsx"],
        ".js": [".agent/rules/javascript", ".agent/rules.js"],
        ".go": [".agent/rules/go", ".agent/rules.go"],
        ".rs": [".agent/rules/rust", ".agent/rules.rs"],
        ".java": [".agent/rules/java"],
        ".md": [".agent/rules/markdown", ".agent/rules.md"],
    }

    def __init__(
        self,
        max_total_tokens: int = 16000,
        cache_enabled: bool = True,
    ):
        """
        Initialize knowledge injector

        Args:
            max_total_tokens: Maximum total tokens to inject
            cache_enabled: Enable content caching
        """
        self.max_total_tokens = max_total_tokens
        self.cache_enabled = cache_enabled
        self._cache: dict[str, str] = {}
        self._last_directory: str | None = None
        self._injected_sources: set[str] = set()

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text"""
        if not text:
            return 0
        # Rough estimation: chars / 4
        return len(text) // 4

    def read_file_safe(self, path: str) -> str | None:
        """
        Safely read file contents

        Args:
            path: File path

        Returns:
            File contents or None
        """
        try:
            path_obj = Path(path)
            if not path_obj.exists() or not path_obj.is_file():
                return None

            with open(path_obj, "r", encoding="utf-8") as f:
                content = f.read()

            return content

        except Exception as e:
            logger.debug(f"Failed to read {path}: {e}")
            return None

    def get_cached(self, key: str) -> str | None:
        """Get cached content"""
        if not self.cache_enabled:
            return None
        return self._cache.get(key)

    def set_cached(self, key: str, content: str) -> None:
        """Set cached content"""
        if self.cache_enabled:
            self._cache[key] = content

    def find_readme(self, directory: str) -> str | None:
        """
        Find README file in directory

        Args:
            directory: Directory to search

        Returns:
            README path or None
        """
        for name in self.DEFAULT_README_NAMES:
            path = os.path.join(directory, name)
            if os.path.isfile(path):
                return path
        return None

    def find_rules(self, directory: str, file_path: str | None = None) -> list[str]:
        """
        Find applicable rules files

        Args:
            directory: Project directory
            file_path: Optional file being edited (for file-type rules)

        Returns:
            List of rules file paths
        """
        rules = []

        # Check default patterns
        for pattern in self.DEFAULT_RULES_PATTERNS:
            path = os.path.join(directory, pattern)
            if os.path.isfile(path):
                rules.append(path)

        # Check file-type specific rules
        if file_path:
            ext = os.path.splitext(file_path)[1].lower()
            file_type_patterns = self.FILE_TYPE_RULES.get(ext, [])

            for pattern in file_type_patterns:
                path = os.path.join(directory, pattern)
                if os.path.isfile(path):
                    rules.append(path)

        return rules

    def inject_readme(
        self,
        directory: str,
        force: bool = False,
    ) -> InjectionResult:
        """
        Inject README if exists

        Args:
            directory: Directory to check
            force: Force injection even if already injected

        Returns:
            Injection result
        """
        result = InjectionResult(success=True)

        cache_key = f"readme:{directory}"

        # Check if already injected
        if not force and cache_key in self._injected_sources:
            return result

        # Find README
        readme_path = self.find_readme(directory)
        if not readme_path:
            return result

        # Get content (from cache or file)
        content = self.get_cached(cache_key)
        if content is None:
            content = self.read_file_safe(readme_path)
            if content:
                self.set_cached(cache_key, content)

        if not content:
            return result

        # Estimate tokens
        tokens = self.estimate_tokens(content)
        if tokens > self.max_total_tokens:
            # Truncate if too long
            max_chars = self.max_total_tokens * 4
            content = content[:max_chars] + "\n... (truncated)"
            tokens = self.estimate_tokens(content)

        # Build injection content
        result.content = f"[Project README from {directory}]\n\n{content}"
        result.sources_injected = [readme_path]
        result.total_tokens = tokens
        result.success = True

        # Mark as injected
        self._injected_sources.add(cache_key)
        self._last_directory = directory

        logger.info(
            "Injected README",
            extra_data={
                "directory": directory,
                "tokens": tokens,
            },
        )

        return result

    def inject_rules(
        self,
        directory: str,
        file_path: str | None = None,
        force: bool = False,
    ) -> InjectionResult:
        """
        Inject project rules

        Args:
            directory: Project directory
            file_path: Optional file being edited
            force: Force injection

        Returns:
            Injection result
        """
        result = InjectionResult(success=True)

        # Find rules files
        rules_paths = self.find_rules(directory, file_path)

        if not rules_paths:
            return result

        contents = []
        total_tokens = 0

        for rules_path in rules_paths:
            cache_key = f"rules:{rules_path}"

            # Check if already injected
            if not force and cache_key in self._injected_sources:
                continue

            # Get content
            content = self.get_cached(cache_key)
            if content is None:
                content = self.read_file_safe(rules_path)
                if content:
                    self.set_cached(cache_key, content)

            if content:
                rule_name = os.path.basename(rules_path)
                section = f"[{rule_name}]\n{content}"
                tokens = self.estimate_tokens(section)

                if total_tokens + tokens > self.max_total_tokens:
                    break

                contents.append(section)
                total_tokens += tokens
                result.sources_injected.append(rules_path)
                self._injected_sources.add(cache_key)

        if contents:
            result.content = "\n\n".join(contents)
            result.total_tokens = total_tokens
            result.success = True

            logger.info(
                "Injected rules",
                extra_data={
                    "sources": result.sources_injected,
                    "tokens": total_tokens,
                },
            )

        return result

    def inject_knowledge(
        self,
        directory: str,
        file_path: str | None = None,
        include_readme: bool = True,
        include_rules: bool = True,
    ) -> InjectionResult:
        """
        Inject all applicable knowledge

        Args:
            directory: Project directory
            file_path: Optional file being edited
            include_readme: Include README
            include_rules: Include rules

        Returns:
            Combined injection result
        """
        result = InjectionResult(success=True)
        contents = []
        total_tokens = 0

        # Check if directory changed
        directory_changed = self._last_directory != directory

        # Inject README if directory changed
        if include_readme and directory_changed:
            readme_result = self.inject_readme(directory)
            if readme_result.content:
                contents.append(readme_result.content)
                total_tokens += readme_result.total_tokens
                result.sources_injected.extend(readme_result.sources_injected)

        # Inject rules
        if include_rules and file_path:
            rules_result = self.inject_rules(directory, file_path)
            if rules_result.content:
                contents.append(rules_result.content)
                total_tokens += rules_result.total_tokens
                result.sources_injected.extend(rules_result.sources_injected)

        if contents:
            result.content = "\n\n---\n\n".join(contents)
            result.total_tokens = total_tokens
            result.success = True

        return result

    def reset_cache(self) -> None:
        """Reset content cache"""
        self._cache.clear()
        self._injected_sources.clear()
        self._last_directory = None

    def mark_injected(self, source: str) -> None:
        """Manually mark a source as injected"""
        self._injected_sources.add(source)

    def is_injected(self, source: str) -> bool:
        """Check if source has been injected"""
        return source in self._injected_sources
