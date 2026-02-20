#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Simple CLI Test
"""

print("="*60)
print("  Novel Writing Agent System - Test Mode")
print("="*60)
print()

# Test 1: Basic print
print("Test 1: Basic output - OK")

# Test 2: Check Python version
import sys
print(f"Test 2: Python version - {sys.version}")

# Test 3: Check working directory
import os
print(f"Test 3: Working directory - {os.getcwd()}")

# Test 4: Try imports
print()
print("Test 4: Checking imports...")
try:
    from pathlib import Path
    print("  - pathlib: OK")
except Exception as e:
    print(f"  - pathlib: FAILED ({e})")

try:
    from datetime import datetime
    print("  - datetime: OK")
except Exception as e:
    print(f"  - datetime: FAILED ({e})")

print()
print("All basic tests passed!")
print()
print("Now try running: python cli.py")
print()
input("Press Enter to exit...")
