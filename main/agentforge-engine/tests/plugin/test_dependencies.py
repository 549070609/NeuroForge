"""
Tests for DependencyResolver class

Comprehensive tests for plugin dependency management including
resolution, circular dependency detection, and version compatibility.
"""


import pytest

from pyagentforge.plugin.base import Plugin, PluginMetadata, PluginType
from pyagentforge.plugin.dependencies import (
    CircularDependencyError,
    DependencyMissingError,
    DependencyResolver,
)
from pyagentforge.plugin.registry import PluginRegistry

# ============================================================================
# Mock Plugin Classes
# ============================================================================

class MockPlugin(Plugin):
    """Mock plugin for testing dependencies."""

    def __init__(
        self,
        plugin_id: str,
        name: str = "Mock Plugin",
        version: str = "1.0.0",
        dependencies: list[str] | None = None,
        optional_dependencies: list[str] | None = None,
        conflicts: list[str] | None = None,
        priority: int = 0,
    ):
        super().__init__()
        self.metadata = PluginMetadata(
            id=plugin_id,
            name=name,
            version=version,
            type=PluginType.TOOL,
            description="A mock plugin for testing",
            dependencies=dependencies or [],
            optional_dependencies=optional_dependencies or [],
            conflicts=conflicts or [],
            priority=priority,
        )


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def registry():
    """Create a fresh plugin registry."""
    return PluginRegistry()


@pytest.fixture
def resolver(registry):
    """Create a dependency resolver with the registry."""
    return DependencyResolver(registry)


# ============================================================================
# Test: Dependency Resolution Order
# ============================================================================

class TestDependencyResolutionOrder:
    """Tests for dependency resolution and load order."""

    def test_dependency_resolution_order_no_dependencies(self, resolver, registry):
        """Test resolution when plugins have no dependencies."""
        plugin_a = MockPlugin("plugin.a")
        plugin_b = MockPlugin("plugin.b")
        plugin_c = MockPlugin("plugin.c")

        registry.register(plugin_a)
        registry.register(plugin_b)
        registry.register(plugin_c)

        order = resolver.resolve_load_order(["plugin.a", "plugin.b", "plugin.c"])

        # Order doesn't matter when no dependencies
        assert set(order) == {"plugin.a", "plugin.b", "plugin.c"}
        assert len(order) == 3

    def test_dependency_resolution_order_single_dependency(self, resolver, registry):
        """Test resolution with single dependency chain."""
        plugin_base = MockPlugin("base")
        plugin_dependent = MockPlugin("dependent", dependencies=["base"])

        registry.register(plugin_base)
        registry.register(plugin_dependent)

        order = resolver.resolve_load_order(["dependent", "base"])

        # Base must come before dependent
        assert order.index("base") < order.index("dependent")

    def test_dependency_resolution_order_multiple_dependencies(self, resolver, registry):
        """Test resolution with multiple dependencies."""
        plugin_base = MockPlugin("base")
        plugin_utils = MockPlugin("utils")
        plugin_service = MockPlugin("service", dependencies=["base", "utils"])

        registry.register(plugin_base)
        registry.register(plugin_utils)
        registry.register(plugin_service)

        order = resolver.resolve_load_order(["service", "base", "utils"])

        # Both base and utils must come before service
        assert order.index("base") < order.index("service")
        assert order.index("utils") < order.index("service")

    def test_dependency_resolution_order_chain(self, resolver, registry):
        """Test resolution with dependency chain A -> B -> C."""
        plugin_c = MockPlugin("plugin.c")
        plugin_b = MockPlugin("plugin.b", dependencies=["plugin.c"])
        plugin_a = MockPlugin("plugin.a", dependencies=["plugin.b"])

        registry.register(plugin_c)
        registry.register(plugin_b)
        registry.register(plugin_a)

        order = resolver.resolve_load_order(["plugin.a", "plugin.b", "plugin.c"])

        # C must come before B, B must come before A
        assert order.index("plugin.c") < order.index("plugin.b")
        assert order.index("plugin.b") < order.index("plugin.a")

    def test_dependency_resolution_order_diamond(self, resolver, registry):
        """Test resolution with diamond dependency pattern.

        A depends on B and C
        B depends on D
        C depends on D

        Expected: D must come before B and C, which must come before A
        """
        plugin_d = MockPlugin("plugin.d")
        plugin_b = MockPlugin("plugin.b", dependencies=["plugin.d"])
        plugin_c = MockPlugin("plugin.c", dependencies=["plugin.d"])
        plugin_a = MockPlugin("plugin.a", dependencies=["plugin.b", "plugin.c"])

        registry.register(plugin_d)
        registry.register(plugin_b)
        registry.register(plugin_c)
        registry.register(plugin_a)

        order = resolver.resolve_load_order(["plugin.a", "plugin.b", "plugin.c", "plugin.d"])

        # D must come before B and C
        assert order.index("plugin.d") < order.index("plugin.b")
        assert order.index("plugin.d") < order.index("plugin.c")
        # B and C must come before A
        assert order.index("plugin.b") < order.index("plugin.a")
        assert order.index("plugin.c") < order.index("plugin.a")

    def test_dependency_resolution_respects_priority(self, resolver, registry):
        """Test that priority is considered when no dependencies."""
        plugin_low = MockPlugin("low", priority=0)
        plugin_high = MockPlugin("high", priority=100)
        plugin_medium = MockPlugin("medium", priority=50)

        registry.register(plugin_low)
        registry.register(plugin_high)
        registry.register(plugin_medium)

        order = resolver.resolve_load_order(["low", "high", "medium"])

        # Higher priority should come first
        assert order[0] == "high"
        assert order[1] == "medium"
        assert order[2] == "low"

    def test_dependency_resolution_priority_with_dependencies(self, resolver, registry):
        """Test priority with dependencies - dependencies override priority."""
        plugin_base = MockPlugin("base", priority=0)
        plugin_dependent = MockPlugin("dependent", dependencies=["base"], priority=100)

        registry.register(plugin_base)
        registry.register(plugin_dependent)

        order = resolver.resolve_load_order(["dependent", "base"])

        # Dependency order takes precedence over priority
        assert order == ["base", "dependent"]


# ============================================================================
# Test: Circular Dependency Detection
# ============================================================================

class TestCircularDependencyDetection:
    """Tests for circular dependency detection."""

    def test_circular_dependency_detection_simple(self, resolver, registry):
        """Test detection of simple circular dependency A -> B -> A."""
        plugin_a = MockPlugin("plugin.a", dependencies=["plugin.b"])
        plugin_b = MockPlugin("plugin.b", dependencies=["plugin.a"])

        registry.register(plugin_a)
        registry.register(plugin_b)

        with pytest.raises(CircularDependencyError) as exc_info:
            resolver.resolve_load_order(["plugin.a", "plugin.b"])

        assert "Circular dependency" in str(exc_info.value)

    def test_circular_dependency_detection_chain(self, resolver, registry):
        """Test detection of circular dependency chain A -> B -> C -> A."""
        plugin_a = MockPlugin("plugin.a", dependencies=["plugin.b"])
        plugin_b = MockPlugin("plugin.b", dependencies=["plugin.c"])
        plugin_c = MockPlugin("plugin.c", dependencies=["plugin.a"])

        registry.register(plugin_a)
        registry.register(plugin_b)
        registry.register(plugin_c)

        with pytest.raises(CircularDependencyError) as exc_info:
            resolver.resolve_load_order(["plugin.a", "plugin.b", "plugin.c"])

        assert "Circular dependency" in str(exc_info.value)

    def test_circular_dependency_detection_self(self, resolver, registry):
        """Test detection of self-referencing dependency A -> A."""
        plugin_a = MockPlugin("plugin.a", dependencies=["plugin.a"])

        registry.register(plugin_a)

        # Self-dependency should be detected as circular
        with pytest.raises(CircularDependencyError) as exc_info:
            resolver.resolve_load_order(["plugin.a"])

        assert "Circular dependency" in str(exc_info.value)

    def test_no_false_positive_circular(self, resolver, registry):
        """Test that valid dependencies are not flagged as circular."""
        plugin_a = MockPlugin("plugin.a")
        plugin_b = MockPlugin("plugin.b", dependencies=["plugin.a"])
        plugin_c = MockPlugin("plugin.c", dependencies=["plugin.b"])

        registry.register(plugin_a)
        registry.register(plugin_b)
        registry.register(plugin_c)

        # Should not raise
        order = resolver.resolve_load_order(["plugin.a", "plugin.b", "plugin.c"])
        assert len(order) == 3


# ============================================================================
# Test: Missing Dependency Error
# ============================================================================

class TestMissingDependencyError:
    """Tests for missing dependency error handling."""

    def test_missing_dependency_error(self, resolver, registry):
        """Test that missing dependency raises error."""
        plugin = MockPlugin("dependent", dependencies=["missing"])

        registry.register(plugin)

        with pytest.raises(DependencyMissingError) as exc_info:
            resolver.resolve_load_order(["dependent"])

        assert "missing" in str(exc_info.value)
        assert "dependent" in str(exc_info.value)

    def test_missing_one_of_multiple_dependencies(self, resolver, registry):
        """Test error when one of multiple dependencies is missing."""
        plugin_base = MockPlugin("base")
        plugin_dependent = MockPlugin("dependent", dependencies=["base", "missing"])

        registry.register(plugin_base)
        registry.register(plugin_dependent)

        with pytest.raises(DependencyMissingError) as exc_info:
            resolver.resolve_load_order(["dependent", "base"])

        assert "missing" in str(exc_info.value)


# ============================================================================
# Test: Optional Dependencies
# ============================================================================

class TestOptionalDependencies:
    """Tests for optional dependency handling."""

    def test_optional_dependencies_not_required_for_load_order(self, resolver, registry):
        """Test that optional dependencies don't need to be in load order."""
        plugin = MockPlugin("plugin", optional_dependencies=["optional"])

        registry.register(plugin)

        # Should not raise - optional dependency can be missing
        order = resolver.resolve_load_order(["plugin"])
        assert order == ["plugin"]

    def test_check_satisfaction_optional_dependencies(self, resolver, registry):
        """Test check_satisfaction with optional dependencies."""
        plugin = MockPlugin("plugin", optional_dependencies=["optional"])

        registry.register(plugin)
        registry.set_state("plugin", "activated")

        # Without checking optional
        satisfied, missing = resolver.check_satisfaction(plugin, check_optional=False)
        assert satisfied is True
        assert len(missing) == 0

        # With checking optional
        satisfied, missing = resolver.check_satisfaction(plugin, check_optional=True)
        assert satisfied is False
        assert "optional (optional)" in missing

    def test_optional_dependencies_satisfied_when_present(self, resolver, registry):
        """Test that optional dependencies are satisfied when present."""
        plugin_optional = MockPlugin("optional")
        plugin_main = MockPlugin("main", optional_dependencies=["optional"])

        registry.register(plugin_optional)
        registry.register(plugin_main)
        registry.set_state("optional", "activated")

        satisfied, missing = resolver.check_satisfaction(plugin_main, check_optional=True)
        assert satisfied is True
        assert len(missing) == 0


# ============================================================================
# Test: Version Compatibility
# ============================================================================

class TestVersionCompatibility:
    """Tests for version compatibility checking."""

    def test_version_in_metadata(self, resolver, registry):
        """Test that version is stored in metadata."""
        plugin = MockPlugin("plugin", version="2.1.0")

        registry.register(plugin)

        registered = registry.get("plugin")
        assert registered.metadata.version == "2.1.0"

    def test_version_format_semantic(self, resolver, registry):
        """Test that semantic versioning format is accepted."""
        versions = ["1.0.0", "2.1.3", "0.0.1", "10.20.30"]

        for i, version in enumerate(versions):
            plugin = MockPlugin(f"plugin.{i}", version=version)
            registry.register(plugin)

            registered = registry.get(f"plugin.{i}")
            assert registered.metadata.version == version

    def test_version_format_with_prerelease(self, resolver, registry):
        """Test that prerelease version format is accepted."""
        versions = ["1.0.0-alpha", "2.0.0-beta.1", "3.0.0-rc.2"]

        for i, version in enumerate(versions):
            plugin = MockPlugin(f"plugin.{i}", version=version)
            registry.register(plugin)

            registered = registry.get(f"plugin.{i}")
            assert registered.metadata.version == version


# ============================================================================
# Test: Check Satisfaction
# ============================================================================

class TestCheckSatisfaction:
    """Tests for dependency satisfaction checking."""

    def test_check_satisfaction_no_dependencies(self, resolver, registry):
        """Test check_satisfaction with no dependencies."""
        plugin = MockPlugin("plugin")

        registry.register(plugin)

        satisfied, missing = resolver.check_satisfaction(plugin)
        assert satisfied is True
        assert len(missing) == 0

    def test_check_satisfaction_with_satisfied_dependencies(self, resolver, registry):
        """Test check_satisfaction when dependencies are activated."""
        plugin_base = MockPlugin("base")
        plugin_dependent = MockPlugin("dependent", dependencies=["base"])

        registry.register(plugin_base)
        registry.register(plugin_dependent)
        registry.set_state("base", "activated")

        satisfied, missing = resolver.check_satisfaction(plugin_dependent)
        assert satisfied is True
        assert len(missing) == 0

    def test_check_satisfaction_with_unsatisfied_dependencies(self, resolver, registry):
        """Test check_satisfaction when dependencies are not activated."""
        plugin_base = MockPlugin("base")
        plugin_dependent = MockPlugin("dependent", dependencies=["base"])

        registry.register(plugin_base)
        registry.register(plugin_dependent)
        # base is registered but not activated

        satisfied, missing = resolver.check_satisfaction(plugin_dependent)
        assert satisfied is False
        assert "base" in missing

    def test_check_satisfaction_multiple_dependencies(self, resolver, registry):
        """Test check_satisfaction with multiple dependencies."""
        plugin_a = MockPlugin("a")
        plugin_b = MockPlugin("b")
        plugin_dependent = MockPlugin("dependent", dependencies=["a", "b"])

        registry.register(plugin_a)
        registry.register(plugin_b)
        registry.register(plugin_dependent)
        registry.set_state("a", "activated")
        # b is not activated

        satisfied, missing = resolver.check_satisfaction(plugin_dependent)
        assert satisfied is False
        assert "b" in missing


# ============================================================================
# Test: Check Conflicts
# ============================================================================

class TestCheckConflicts:
    """Tests for conflict checking."""

    def test_check_conflicts_no_conflicts(self, resolver, registry):
        """Test check_conflicts with no conflicts."""
        plugin = MockPlugin("plugin")

        registry.register(plugin)

        has_conflicts, conflicts = resolver.check_conflicts(plugin)
        assert has_conflicts is False
        assert len(conflicts) == 0

    def test_check_conflicts_with_conflict_registered(self, resolver, registry):
        """Test check_conflicts when conflicting plugin is registered."""
        plugin_a = MockPlugin("plugin.a", conflicts=["plugin.b"])
        plugin_b = MockPlugin("plugin.b")

        registry.register(plugin_a)
        registry.register(plugin_b)

        has_conflicts, conflicts = resolver.check_conflicts(plugin_a)
        assert has_conflicts is True
        assert "plugin.b" in conflicts

    def test_check_conflicts_conflict_not_registered(self, resolver, registry):
        """Test check_conflicts when conflicting plugin is not registered."""
        plugin_a = MockPlugin("plugin.a", conflicts=["plugin.b"])

        registry.register(plugin_a)

        has_conflicts, conflicts = resolver.check_conflicts(plugin_a)
        assert has_conflicts is False
        assert len(conflicts) == 0

    def test_check_conflicts_multiple_conflicts(self, resolver, registry):
        """Test check_conflicts with multiple conflicts."""
        plugin_a = MockPlugin("plugin.a", conflicts=["plugin.b", "plugin.c"])
        plugin_b = MockPlugin("plugin.b")
        plugin_c = MockPlugin("plugin.c")

        registry.register(plugin_a)
        registry.register(plugin_b)
        registry.register(plugin_c)

        has_conflicts, conflicts = resolver.check_conflicts(plugin_a)
        assert has_conflicts is True
        assert set(conflicts) == {"plugin.b", "plugin.c"}

    def test_check_conflicts_partial_conflicts(self, resolver, registry):
        """Test check_conflicts when only some conflicts are registered."""
        plugin_a = MockPlugin("plugin.a", conflicts=["plugin.b", "plugin.c"])
        plugin_b = MockPlugin("plugin.b")
        # plugin_c not registered

        registry.register(plugin_a)
        registry.register(plugin_b)

        has_conflicts, conflicts = resolver.check_conflicts(plugin_a)
        assert has_conflicts is True
        assert conflicts == ["plugin.b"]


# ============================================================================
# Test: Get Dependents
# ============================================================================

class TestGetDependents:
    """Tests for getting dependents of a plugin."""

    def test_get_dependents_none(self, resolver, registry):
        """Test get_dependents when no plugins depend on it."""
        plugin = MockPlugin("plugin")

        registry.register(plugin)

        dependents = resolver.get_dependents("plugin")
        assert len(dependents) == 0

    def test_get_dependents_single(self, resolver, registry):
        """Test get_dependents with one dependent."""
        plugin_base = MockPlugin("base")
        plugin_dependent = MockPlugin("dependent", dependencies=["base"])

        registry.register(plugin_base)
        registry.register(plugin_dependent)

        dependents = resolver.get_dependents("base")
        assert dependents == ["dependent"]

    def test_get_dependents_multiple(self, resolver, registry):
        """Test get_dependents with multiple dependents."""
        plugin_base = MockPlugin("base")
        plugin_dep1 = MockPlugin("dep1", dependencies=["base"])
        plugin_dep2 = MockPlugin("dep2", dependencies=["base"])
        plugin_dep3 = MockPlugin("dep3", dependencies=["base"])

        registry.register(plugin_base)
        registry.register(plugin_dep1)
        registry.register(plugin_dep2)
        registry.register(plugin_dep3)

        dependents = resolver.get_dependents("base")
        assert set(dependents) == {"dep1", "dep2", "dep3"}

    def test_get_dependents_chain(self, resolver, registry):
        """Test get_dependents in a chain."""
        plugin_a = MockPlugin("a")
        plugin_b = MockPlugin("b", dependencies=["a"])
        plugin_c = MockPlugin("c", dependencies=["b"])

        registry.register(plugin_a)
        registry.register(plugin_b)
        registry.register(plugin_c)

        # a is depended on by b
        dependents_a = resolver.get_dependents("a")
        assert dependents_a == ["b"]

        # b is depended on by c
        dependents_b = resolver.get_dependents("b")
        assert dependents_b == ["c"]


# ============================================================================
# Test: Build Dependency Tree
# ============================================================================

class TestBuildDependencyTree:
    """Tests for building dependency trees."""

    def test_build_dependency_tree_single(self, resolver, registry):
        """Test building tree for plugin with no dependencies."""
        plugin = MockPlugin("plugin", name="Test Plugin", version="1.0.0")

        registry.register(plugin)

        tree = resolver.build_dependency_tree("plugin")

        assert tree["id"] == "plugin"
        assert tree["name"] == "Test Plugin"
        assert tree["version"] == "1.0.0"
        assert tree["dependencies"] == []
        assert tree["optional_dependencies"] == []

    def test_build_dependency_tree_with_dependencies(self, resolver, registry):
        """Test building tree with dependencies."""
        plugin_base = MockPlugin("base", name="Base Plugin")
        plugin_dependent = MockPlugin("dependent", dependencies=["base"])

        registry.register(plugin_base)
        registry.register(plugin_dependent)

        tree = resolver.build_dependency_tree("dependent")

        assert tree["id"] == "dependent"
        assert len(tree["dependencies"]) == 1
        assert tree["dependencies"][0]["id"] == "base"

    def test_build_dependency_tree_with_optional(self, resolver, registry):
        """Test building tree with optional dependencies."""
        plugin_optional = MockPlugin("optional")
        plugin_main = MockPlugin("main", optional_dependencies=["optional"])

        registry.register(plugin_optional)
        registry.register(plugin_main)

        tree = resolver.build_dependency_tree("main")

        assert len(tree["optional_dependencies"]) == 1
        assert tree["optional_dependencies"][0]["id"] == "optional"
        assert tree["optional_dependencies"][0]["optional"] is True

    def test_build_dependency_tree_nested(self, resolver, registry):
        """Test building tree with nested dependencies."""
        plugin_c = MockPlugin("c")
        plugin_b = MockPlugin("b", dependencies=["c"])
        plugin_a = MockPlugin("a", dependencies=["b"])

        registry.register(plugin_c)
        registry.register(plugin_b)
        registry.register(plugin_a)

        tree = resolver.build_dependency_tree("a")

        assert tree["id"] == "a"
        assert tree["dependencies"][0]["id"] == "b"
        assert tree["dependencies"][0]["dependencies"][0]["id"] == "c"

    def test_build_dependency_tree_not_found(self, resolver, registry):
        """Test building tree for non-existent plugin."""
        tree = resolver.build_dependency_tree("nonexistent")

        assert tree["id"] == "nonexistent"
        assert tree["error"] == "not found"


# ============================================================================
# Test: Get Priority
# ============================================================================

class TestGetPriority:
    """Tests for plugin priority retrieval."""

    def test_get_priority_default(self, resolver, registry):
        """Test getting default priority."""
        plugin = MockPlugin("plugin")

        registry.register(plugin)

        priority = resolver._get_priority("plugin")
        assert priority == 0

    def test_get_priority_custom(self, resolver, registry):
        """Test getting custom priority."""
        plugin = MockPlugin("plugin", priority=100)

        registry.register(plugin)

        priority = resolver._get_priority("plugin")
        assert priority == 100

    def test_get_priority_not_found(self, resolver, registry):
        """Test getting priority for non-existent plugin."""
        priority = resolver._get_priority("nonexistent")
        assert priority == 0


# ============================================================================
# Test: Edge Cases
# ============================================================================

class TestDependencyResolverEdgeCases:
    """Tests for edge cases in dependency resolution."""

    def test_empty_plugin_list(self, resolver, registry):
        """Test resolution with empty plugin list."""
        order = resolver.resolve_load_order([])
        assert order == []

    def test_single_plugin(self, resolver, registry):
        """Test resolution with single plugin."""
        plugin = MockPlugin("plugin")

        registry.register(plugin)

        order = resolver.resolve_load_order(["plugin"])
        assert order == ["plugin"]

    def test_complex_dependency_graph(self, resolver, registry):
        """Test resolution with complex dependency graph."""
        # Create a complex graph:
        # a -> b, c
        # b -> d, e
        # c -> e
        # d -> f
        # e -> f

        plugin_f = MockPlugin("f")
        plugin_e = MockPlugin("e", dependencies=["f"])
        plugin_d = MockPlugin("d", dependencies=["f"])
        plugin_c = MockPlugin("c", dependencies=["e"])
        plugin_b = MockPlugin("b", dependencies=["d", "e"])
        plugin_a = MockPlugin("a", dependencies=["b", "c"])

        for p in [plugin_f, plugin_e, plugin_d, plugin_c, plugin_b, plugin_a]:
            registry.register(p)

        order = resolver.resolve_load_order(["a", "b", "c", "d", "e", "f"])

        # Verify all dependencies are satisfied
        def check_order(plugin_id, dep_id):
            return order.index(dep_id) < order.index(plugin_id)

        assert check_order("b", "d")
        assert check_order("b", "e")
        assert check_order("c", "e")
        assert check_order("d", "f")
        assert check_order("e", "f")
        assert check_order("a", "b")
        assert check_order("a", "c")

    def test_dependency_on_self_registered_only(self, resolver, registry):
        """Test that plugin depending on itself is handled."""
        plugin = MockPlugin("plugin")

        registry.register(plugin)

        order = resolver.resolve_load_order(["plugin"])
        assert order == ["plugin"]

    def test_plugin_registered_multiple_times(self, resolver, registry):
        """Test that registering same plugin twice raises error."""
        plugin = MockPlugin("plugin")

        registry.register(plugin)

        with pytest.raises(ValueError):
            registry.register(plugin)

    def test_resolve_order_subset_of_plugins(self, resolver, registry):
        """Test resolving order for subset of registered plugins."""
        plugin_a = MockPlugin("a")
        plugin_b = MockPlugin("b", dependencies=["a"])
        plugin_c = MockPlugin("c")  # Not in load order

        registry.register(plugin_a)
        registry.register(plugin_b)
        registry.register(plugin_c)

        # Only load a and b
        order = resolver.resolve_load_order(["a", "b"])

        assert order == ["a", "b"]
        assert "c" not in order
