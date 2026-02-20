#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Final verification script for cli_glm.py
"""

import sys
import subprocess
from pathlib import Path

def run_command(cmd, description):
    """Run a command and report results"""
    print(f"\n[Testing] {description}...")
    print(f"Command: {' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        print(f"[OK] {description} - SUCCESS")
        if result.stdout:
            print(result.stdout[:500])
        return True
    else:
        print(f"[FAIL] {description} - FAILED")
        if result.stderr:
            print(f"Error: {result.stderr[:500]}")
        return False

def main():
    print("=" * 70)
    print(" AGent GLM - Final Verification Script")
    print("=" * 70)

    base_path = Path(__file__).parent

    tests = [
        # Test 1: Check files exist
        {
            "name": "File existence check",
            "type": "file_check",
            "files": [
                "cli_glm.py",
                "test_imports.py",
                "test_init.py",
                "start_glm.bat",
                "GLM_FIX_SUMMARY.md",
            ]
        },
        # Test 2: Import test
        {
            "name": "Import test",
            "type": "command",
            "cmd": ["py", "test_imports.py"]
        },
        # Test 3: Initialization test
        {
            "name": "Initialization test",
            "type": "command",
            "cmd": ["py", "test_init.py"]
        },
    ]

    passed = 0
    failed = 0

    for test in tests:
        print(f"\n{'=' * 70}")
        print(f"Test: {test['name']}")
        print('=' * 70)

        if test["type"] == "file_check":
            all_exist = True
            for file in test["files"]:
                file_path = base_path / file
                if file_path.exists():
                    print(f"  [OK] {file}")
                else:
                    print(f"  [FAIL] {file} - NOT FOUND")
                    all_exist = False

            if all_exist:
                passed += 1
                print(f"\n[SUCCESS] {test['name']}")
            else:
                failed += 1
                print(f"\n[FAILED] {test['name']}")

        elif test["type"] == "command":
            result = run_command(test["cmd"], test["name"])
            if result:
                passed += 1
            else:
                failed += 1

    # Summary
    print("\n" + "=" * 70)
    print(" VERIFICATION SUMMARY")
    print("=" * 70)
    print(f"Passed: {passed}/{len(tests)}")
    print(f"Failed: {failed}/{len(tests)}")

    if failed == 0:
        print("\n[SUCCESS] All verification tests passed!")
        print("\nYou can now run:")
        print("  - py cli_glm.py")
        print("  - start_glm.bat")
        print("  - py start.py (then select option 1)")
        return 0
    else:
        print("\n[WARNING] Some tests failed. Please check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
