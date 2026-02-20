#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test GLM-5 model configuration"""

import sys
from pathlib import Path

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent / "pyagentforge"))
sys.path.insert(0, str(Path(__file__).parent.parent / "glm-provider"))

print("=" * 60)
print("Testing GLM-5 Model Configuration")
print("=" * 60)

# Import GLMProvider
from glm_provider import GLMProvider

# Test 1: Default model from .env
print("\n[Test 1] Default model (from .env)...")
try:
    provider = GLMProvider()
    print(f"  Model: {provider.model}")
    print(f"  Expected: glm-5")
    if provider.model == "glm-5":
        print("  [OK] Model is GLM-5")
    else:
        print(f"  [WARNING] Model is {provider.model}, expected glm-5")
except Exception as e:
    print(f"  [FAIL] {e}")

# Test 2: Explicit GLM-5
print("\n[Test 2] Explicit GLM-5...")
try:
    provider = GLMProvider(model="glm-5")
    print(f"  Model: {provider.model}")
    if provider.model == "glm-5":
        print("  [OK] Model is GLM-5")
    else:
        print(f"  [FAIL] Model is {provider.model}")
except Exception as e:
    print(f"  [FAIL] {e}")

# Test 3: Check cli_glm.py configuration
print("\n[Test 3] Check cli_glm.py configuration...")
with open("cli_glm.py", "r", encoding="utf-8") as f:
    content = f.read()
    if 'GLMProvider(model="glm-5")' in content:
        print("  [OK] cli_glm.py uses GLM-5")
    else:
        print("  [FAIL] cli_glm.py does not specify GLM-5")

print("\n" + "=" * 60)
print("Configuration test complete!")
print("=" * 60)
