#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test tool integration in cli_glm.py"""

import sys
from pathlib import Path

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent / "pyagentforge"))
sys.path.insert(0, str(Path(__file__).parent.parent / "glm-provider"))

print("=" * 70)
print(" AGent Tool Integration Test")
print("=" * 70)

# Test 1: Import tools
print("\n[Test 1] Importing built-in tools...")
try:
    from pyagentforge.tools.builtin import (
        ReadTool,
        WriteTool,
        EditTool,
        GlobTool,
        GrepTool,
        PlanTool,
        TodoWriteTool,
        TodoReadTool,
    )
    print("  [OK] All tools imported successfully")
    TOOLS_AVAILABLE = True
except ImportError as e:
    print(f"  [FAIL] Failed to import tools: {e}")
    TOOLS_AVAILABLE = False

# Test 2: Create tool registry
print("\n[Test 2] Creating ToolRegistry...")
try:
    from pyagentforge.kernel.executor import ToolRegistry
    registry = ToolRegistry()
    print("  [OK] ToolRegistry created")
except Exception as e:
    print(f"  [FAIL] Failed: {e}")
    sys.exit(1)

# Test 3: Register tools
if TOOLS_AVAILABLE:
    print("\n[Test 3] Registering tools...")

    # 独立工具
    independent_tools = [
        ("ReadTool", ReadTool),
        ("WriteTool", WriteTool),
        ("EditTool", EditTool),
        ("GlobTool", GlobTool),
        ("GrepTool", GrepTool),
        ("PlanTool", PlanTool),
    ]

    registered_count = 0
    for tool_name, tool_class in independent_tools:
        try:
            registry.register(tool_class())
            print(f"  [OK] {tool_name} registered")
            registered_count += 1
        except Exception as e:
            print(f"  [FAIL] {tool_name}: {e}")

    # TodoWriteTool 和 TodoReadTool（有依赖关系）
    try:
        todo_write = TodoWriteTool()
        registry.register(todo_write)
        print(f"  [OK] TodoWriteTool registered")
        registered_count += 1

        registry.register(TodoReadTool(todo_write))
        print(f"  [OK] TodoReadTool registered")
        registered_count += 1
    except Exception as e:
        print(f"  [FAIL] TodoTools: {e}")

    print(f"\n  Total: {registered_count}/8 tools registered")

    # Test 4: Check tool schemas
    print("\n[Test 4] Checking tool schemas...")
    schemas = registry.get_schemas()
    print(f"  [OK] {len(schemas)} tool schemas available")

    for schema in schemas[:3]:  # Show first 3
        print(f"    - {schema.get('name', 'unknown')}")

    # Test 5: Verify in AgentEngine
    print("\n[Test 5] Creating AgentEngine with tools...")
    try:
        from pyagentforge.kernel.engine import AgentEngine, AgentConfig
        from glm_provider import GLMProvider

        provider = GLMProvider(model="glm-5")
        config = AgentConfig(system_prompt="Test agent")

        engine = AgentEngine(
            provider=provider,
            tool_registry=registry,
            config=config,
        )

        print(f"  [OK] AgentEngine created with {len(registry.get_all())} tools")
        print(f"  Session ID: {engine.session_id}")

    except Exception as e:
        print(f"  [FAIL] Failed to create AgentEngine: {e}")
        import traceback
        traceback.print_exc()

else:
    print("\n[SKIP] Tool tests skipped (tools not available)")

# Summary
print("\n" + "=" * 70)
print(" TEST SUMMARY")
print("=" * 70)

if TOOLS_AVAILABLE and registered_count == 8:
    print("\n[SUCCESS] All tools integrated successfully!")
    print("\nAvailable capabilities:")
    print("  - File operations: read, write, edit")
    print("  - Search: glob, grep")
    print("  - Task management: plan, todo_write, todo_read")
    print("\nYour Agent now has powerful capabilities!")
else:
    print("\n[WARNING] Some tools failed to integrate")
    print(f"Registered: {registered_count if TOOLS_AVAILABLE else 0}/8")

print("\n" + "=" * 70)
