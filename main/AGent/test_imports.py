#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test imports for cli_glm.py"""

import sys
import os
from pathlib import Path

# Add paths
base_path = Path(__file__).parent
sys.path.insert(0, str(base_path.parent / "pyagentforge"))
sys.path.insert(0, str(base_path.parent / "glm-provider"))

print("=" * 60)
print("Testing imports for cli_glm")
print("=" * 60)

# Test 1: GLM Provider
print("\n1. Testing GLM Provider import...")
try:
    from glm_provider import GLMProvider
    print("   [OK] GLMProvider imported successfully")
except Exception as e:
    print(f"   [FAIL] GLMProvider import failed: {e}")
    import traceback
    traceback.print_exc()

# Test 2: AgentEngine
print("\n2. Testing AgentEngine import...")
try:
    from pyagentforge.kernel.engine import AgentEngine, AgentConfig
    print("   [OK] AgentEngine imported successfully")
except Exception as e:
    print(f"   [FAIL] AgentEngine import failed: {e}")
    import traceback
    traceback.print_exc()

# Test 3: ToolRegistry
print("\n3. Testing ToolRegistry import...")
try:
    from pyagentforge.kernel.executor import ToolRegistry
    print("   [OK] ToolRegistry imported successfully")
except Exception as e:
    print(f"   [FAIL] ToolRegistry import failed: {e}")
    import traceback
    traceback.print_exc()

# Test 4: ContextManager
print("\n4. Testing ContextManager import...")
try:
    from pyagentforge.kernel.context import ContextManager
    print("   [OK] ContextManager imported successfully")
except Exception as e:
    print(f"   [FAIL] ContextManager import failed: {e}")
    import traceback
    traceback.print_exc()

# Test 5: Message
print("\n5. Testing Message import...")
try:
    from pyagentforge.core.message import Message
    print("   [OK] Message imported successfully")
except Exception as e:
    print(f"   [FAIL] Message import failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("All tests completed!")
print("=" * 60)
