#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test cli_glm.py initialization"""

import sys
import os
from pathlib import Path

# Add paths
base_path = Path(__file__).parent
sys.path.insert(0, str(base_path.parent / "pyagentforge"))
sys.path.insert(0, str(base_path.parent / "glm-provider"))

print("=" * 60)
print("Testing cli_glm.py initialization")
print("=" * 60)

# Step 1: Import GLMProvider
print("\n[Step 1] Importing GLMProvider...")
try:
    from glm_provider import GLMProvider
    print("   [OK] GLMProvider imported")
except Exception as e:
    print(f"   [FAIL] Failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 2: Check config file
print("\n[Step 2] Checking config file...")
env_file = Path(__file__).parent.parent / "glm-provider" / ".env"
if not env_file.exists():
    print(f"   [FAIL] Config file not found: {env_file}")
    print("   Please run: python setup_glm.py")
    sys.exit(1)
print(f"   [OK] Config file found: {env_file}")

# Step 3: Create GLM Provider
print("\n[Step 3] Creating GLM Provider...")
try:
    provider = GLMProvider()
    print(f"   [OK] GLM Provider created (model: {provider.model})")
except Exception as e:
    print(f"   [FAIL] Failed to create provider: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 4: Import remaining modules
print("\n[Step 4] Importing remaining modules...")
try:
    from pyagentforge.kernel.engine import AgentEngine, AgentConfig
    from pyagentforge.kernel.executor import ToolRegistry
    from pyagentforge.kernel.context import ContextManager
    from pyagentforge.core.message import Message
    print("   [OK] All modules imported")
except Exception as e:
    print(f"   [FAIL] Failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 5: Create AgentInfo
print("\n[Step 5] Creating AgentInfo...")
try:
    class AgentInfo:
        def __init__(self, name, description, category, system_prompt):
            self.name = name
            self.description = description
            self.category = category
            self.system_prompt = system_prompt

    agent = AgentInfo(
        name="test-agent",
        description="Test agent",
        category="test",
        system_prompt="You are a helpful assistant."
    )
    print(f"   [OK] AgentInfo created: {agent.name}")
except Exception as e:
    print(f"   [FAIL] Failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 6: Create ToolRegistry
print("\n[Step 6] Creating ToolRegistry...")
try:
    tool_registry = ToolRegistry()
    print(f"   [OK] ToolRegistry created")
except Exception as e:
    print(f"   [FAIL] Failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 7: Create AgentConfig
print("\n[Step 7] Creating AgentConfig...")
try:
    config = AgentConfig(system_prompt=agent.system_prompt)
    print(f"   [OK] AgentConfig created")
except Exception as e:
    print(f"   [FAIL] Failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 8: Create AgentEngine
print("\n[Step 8] Creating AgentEngine...")
try:
    engine = AgentEngine(
        provider=provider,
        tool_registry=tool_registry,
        config=config,
    )
    print(f"   [OK] AgentEngine created (session: {engine.session_id})")
except Exception as e:
    print(f"   [FAIL] Failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 9: Test context access
print("\n[Step 9] Testing context access...")
try:
    messages = engine.context.messages
    print(f"   [OK] Context messages accessible (count: {len(messages)})")
except Exception as e:
    print(f"   [FAIL] Failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("SUCCESS! All initialization tests passed!")
print("=" * 60)
print("\nYou can now run: py cli_glm.py")
