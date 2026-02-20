#!/usr/bin/env python3
"""
PyAgentForge 全量测试运行器

功能:
- 按优先级执行测试
- 生成详细测试报告
- 收集覆盖率数据
- 输出改进建议
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime
import json
import re
from typing import Any


class TestRunner:
    """测试运行器"""
    
    def __init__(self):
        self.results: dict[str, Any] = {}
        self.start_time: datetime | None = None

    def run_tests(
        self,
        category: str,
        markers: str | None = None,
        extra_args: list[str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """执行指定类别的测试"""
        cmd = ["pytest", f"tests/{category}/", "-v", "--tb=short", "--color=yes"]
        
        if markers:
            cmd.extend(["-m", markers])
        if extra_args:
            cmd.extend(extra_args)
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result

    def parse_test_results(self, output: str) -> dict[str, int]:
        """解析测试输出结果"""
        # 解析 pytest 输出
        passed = len(re.findall(r" PASSED", output))
        failed = len(re.findall(r" FAILED", output))
        skipped = len(re.findall(r" SKIPPED", output))
        errors = len(re.findall(r" ERROR", output))
        
        return {
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "errors": errors,
        }

    def run_all_tests(self) -> dict[str, Any]:
        """执行全量测试"""
        self.start_time = datetime.now()
        
        # P0: 核心测试
        print("=" * 60)
        print("Running P0 Critical Tests...")
        print("=" * 60)
        
        self.results["kernel"] = self.run_tests("kernel")
        self.results["core"] = self.run_tests("core")
        self.results["providers"] = self.run_tests("providers")
        
        # P1: 重要测试
        print("\n" + "=" * 60)
        print("Running P1 High Priority Tests...")
        print("=" * 60)
        
        self.results["tools"] = self.run_tests(
            "tools", extra_args=["--timeout=60"]
        )
        self.results["plugin"] = self.run_tests("plugin")
        self.results["integration"] = self.run_tests(
            "integration", extra_args=["--timeout=300"]
        )
        
        # P2: 其他测试
        print("\n" + "=" * 60)
        print("Running P2 Medium Priority Tests...")
        print("=" * 60)
        
        self.results["e2e"] = self.run_tests("e2e", extra_args=["--timeout=600"])
        self.results["boundary"] = self.run_tests("boundary")
        self.results["performance"] = self.run_tests("performance")
        
        return self.generate_report()

    def generate_report(self) -> dict[str, Any]:
        """生成测试报告"""
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds() if self.start_time else 0
        
        report: dict[str, Any] = {
            "timestamp": self.start_time.isoformat() if self.start_time else None,
            "duration_seconds": duration,
            "categories": {},
        }
        
        total_passed = 0
        total_failed = 0
        total_skipped = 0
        total_errors = 0
        
        for category, result in self.results.items():
            output = result.stdout + result.stderr
            
            # 解析测试结果
            parsed = self.parse_test_results(output)
            
            total_passed += parsed["passed"]
            total_failed += parsed["failed"]
            total_skipped += parsed["skipped"]
            total_errors += parsed["errors"]
            
            report["categories"][category] = {
                **parsed,
                "returncode": result.returncode,
            }
        
        report["summary"] = {
            "total_passed": total_passed,
            "total_failed": total_failed,
            "total_skipped": total_skipped,
            "total_errors": total_errors,
            "total_tests": total_passed + total_failed + total_skipped,
            "pass_rate": f"{total_passed / (total_passed + total_failed) * 100:.1f}%"
            if (total_passed + total_failed) > 0
            else "N/A",
        }
        
        return report

    def print_summary(self, report: dict[str, Any]) -> None:
        """打印测试摘要"""
        print("\n" + "=" * 60)
        print("TEST REPORT SUMMARY")
        print("=" * 60)
        
        for category, data in report["categories"].items():
            status = "✓" if data["returncode"] == 0 else "✗"
            print(
                f"{status} {category:20s} - "
                f"PASSED: {data['passed']:3d}, "
                f"FAILED: {data['failed']:3d}, "
                f"SKIPPED: {data['skipped']:3d}"
            )
        
        print("-" * 60)
        summary = report["summary"]
        print(f"Total Tests:  {summary['total_tests']}")
        print(f"PASSED:       {summary['total_passed']}")
        print(f"FAILED:       {summary['total_failed']}")
        print(f"SKIPPED:      {summary['total_skipped']}")
        print(f"ERRORS:       {summary['total_errors']}")
        print(f"Pass Rate:    {summary['pass_rate']}")
        print(f"Duration:     {report['duration_seconds']:.1f}s")
        print("=" * 60)


def main() -> int:
    """主函数"""
    runner = TestRunner()
    report = runner.run_all_tests()
    
    # 打印摘要
    runner.print_summary(report)
    
    # 保存报告
    report_path = Path("test_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nReport saved to: {report_path}")
    
    # 生成改进建议
    generate_improvement_suggestions(report)
    
    # 返回退出码
    if report["summary"]["total_failed"] > 0:
        return 1
    return 0


def generate_improvement_suggestions(report: dict[str, Any]) -> None:
    """生成改进建议"""
    suggestions = []
    
    for category, data in report["categories"].items():
        if data["failed"] > 0:
            suggestions.append(
                f"- Fix {data['failed']} failing tests in {category}"
            )
        if data["skipped"] > 5:
            suggestions.append(
                f"- Review {data['skipped']} skipped tests in {category}"
            )
    
    if suggestions:
        print("\n" + "=" * 60)
        print("IMPROVEMENT SUGGESTIONS")
        print("=" * 60)
        for suggestion in suggestions:
            print(suggestion)
        print("=" * 60)


if __name__ == "__main__":
    sys.exit(main())
