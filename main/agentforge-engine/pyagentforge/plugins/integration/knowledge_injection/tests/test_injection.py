"""
Tests for Knowledge Injector
"""

import os
import tempfile
import pytest

from pyagentforge.core.knowledge_injector import (
    InjectionResult,
    KnowledgeInjector,
    KnowledgeSource,
)


class TestKnowledgeInjector:
    """Tests for KnowledgeInjector"""

    def test_estimate_tokens(self):
        """Test token estimation"""
        injector = KnowledgeInjector()

        # Empty text
        assert injector.estimate_tokens("") == 0

        # Some text
        text = "Hello world"
        tokens = injector.estimate_tokens(text)
        assert tokens > 0
        assert tokens < len(text)

    def test_find_readme(self):
        """Test finding README files"""
        injector = KnowledgeInjector()

        with tempfile.TemporaryDirectory() as tmpdir:
            # No README
            assert injector.find_readme(tmpdir) is None

            # Create README.md
            readme_path = os.path.join(tmpdir, "README.md")
            with open(readme_path, "w") as f:
                f.write("# Test Project")

            found = injector.find_readme(tmpdir)
            assert found == readme_path

    def test_inject_readme(self):
        """Test README injection"""
        injector = KnowledgeInjector()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create README
            readme_path = os.path.join(tmpdir, "README.md")
            with open(readme_path, "w") as f:
                f.write("# Test Project\n\nThis is a test.")

            result = injector.inject_readme(tmpdir)

            assert result.success
            assert len(result.sources_injected) == 1
            assert result.total_tokens > 0
            assert "Test Project" in result.content

    def test_inject_readme_already_injected(self):
        """Test that README is not re-injected"""
        injector = KnowledgeInjector()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create README
            readme_path = os.path.join(tmpdir, "README.md")
            with open(readme_path, "w") as f:
                f.write("# Test")

            # First injection
            result1 = injector.inject_readme(tmpdir)
            assert result1.success

            # Second injection (should be skipped)
            result2 = injector.inject_readme(tmpdir)
            assert not result2.sources_injected

            # Force injection
            result3 = injector.inject_readme(tmpdir, force=True)
            assert result3.success

    def test_find_rules(self):
        """Test finding rules files"""
        injector = KnowledgeInjector()

        with tempfile.TemporaryDirectory() as tmpdir:
            # No rules
            rules = injector.find_rules(tmpdir)
            assert len(rules) == 0

            # Create .cursorrules
            rules_path = os.path.join(tmpdir, ".cursorrules")
            with open(rules_path, "w") as f:
                f.write("Use 4 spaces for indentation")

            rules = injector.find_rules(tmpdir)
            assert rules_path in rules

    def test_find_file_type_rules(self):
        """Test finding file-type specific rules"""
        injector = KnowledgeInjector()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create Python rules
            os.makedirs(os.path.join(tmpdir, ".agent"), exist_ok=True)
            python_rules = os.path.join(tmpdir, ".agent/rules/python")
            with open(python_rules, "w") as f:
                f.write("Use type hints")

            # Test finding Python rules
            rules = injector.find_rules(tmpdir, "test.py")
            assert python_rules in rules

            # Test finding rules for other file types
            rules = injector.find_rules(tmpdir, "test.js")
            assert python_rules not in rules

    def test_inject_rules(self):
        """Test rules injection"""
        injector = KnowledgeInjector()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create rules file
            rules_path = os.path.join(tmpdir, ".cursorrules")
            with open(rules_path, "w") as f:
                f.write("Always use const in JavaScript")

            result = injector.inject_rules(tmpdir)

            assert result.success
            assert rules_path in result.sources_injected
            assert "const" in result.content

    def test_inject_knowledge(self):
        """Test combined knowledge injection"""
        injector = KnowledgeInjector()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create README
            readme_path = os.path.join(tmpdir, "README.md")
            with open(readme_path, "w") as f:
                f.write("# Project\n\nDescription")

            # Create rules
            rules_path = os.path.join(tmpdir, ".cursorrules")
            with open(rules_path, "w") as f:
                f.write("Rules content")

            result = injector.inject_knowledge(
                directory=tmpdir,
                file_path=os.path.join(tmpdir, "test.py"),
            )

            assert result.success
            assert len(result.sources_injected) >= 1

    def test_token_limit(self):
        """Test token limit enforcement"""
        injector = KnowledgeInjector(max_total_tokens=100)

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create large README
            readme_path = os.path.join(tmpdir, "README.md")
            with open(readme_path, "w") as f:
                f.write("x" * 10000)

            result = injector.inject_readme(tmpdir)

            assert result.success
            assert result.total_tokens <= injector.max_total_tokens

    def test_cache(self):
        """Test caching"""
        injector = KnowledgeInjector(cache_enabled=True)

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create README
            readme_path = os.path.join(tmpdir, "README.md")
            with open(readme_path, "w") as f:
                f.write("# Test")

            # First read (not cached)
            content1 = injector.read_file_safe(readme_path)

            # Cache it
            injector.set_cached(f"readme:{tmpdir}", content1)

            # Second read (should use cache)
            content2 = injector.get_cached(f"readme:{tmpdir}")

            assert content1 == content2

    def test_reset_cache(self):
        """Test cache reset"""
        injector = KnowledgeInjector()

        injector.set_cached("test", "content")
        assert injector.get_cached("test") == "content"

        injector.reset_cache()
        assert injector.get_cached("test") is None


class TestInjectionResult:
    """Tests for InjectionResult"""

    def test_empty_result(self):
        """Test empty result"""
        result = InjectionResult(success=True)

        assert result.success
        assert len(result.sources_injected) == 0
        assert result.total_tokens == 0
        assert len(result.errors) == 0

    def test_result_with_content(self):
        """Test result with content"""
        result = InjectionResult(
            success=True,
            sources_injected=["README.md"],
            total_tokens=500,
            content="Test content",
        )

        assert result.success
        assert "README.md" in result.sources_injected
        assert result.total_tokens == 500
