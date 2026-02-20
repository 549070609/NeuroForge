#!/usr/bin/env python3
"""运行覆盖率测试"""

import subprocess
import sys


def run_coverage() -> int:
    """运行覆盖率测试并返回退出码"""
    cmd = [
        "pytest",
        "tests/",
        "--cov=pyagentforge",
        "--cov-report=html:htmlcov",
        "--cov-report=term",
        "--cov-fail-under=80",
        "-v",
    ]

    result = subprocess.run(cmd)
    return result.returncode


if __name__ == "__main__":
    sys.exit(run_coverage())
