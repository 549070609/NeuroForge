#!/usr/bin/env python3
"""
GLM Integration Test Runner

运行 GLM-5 集成测试并生成报告
"""

import os
import sys
import json
import time
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

# 颜色输出
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_header(text: str):
    """打印标题"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text:^60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}\n")


def print_section(text: str):
    """打印章节"""
    print(f"\n{Colors.OKCYAN}{Colors.BOLD}[{text}]{Colors.ENDC}")


def print_success(text: str):
    """打印成功信息"""
    print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")


def print_error(text: str):
    """打印错误信息"""
    print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")


def print_warning(text: str):
    """打印警告信息"""
    print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")


def check_prerequisites():
    """检查前置条件"""
    print_section("检查前置条件")

    # 检查环境变量
    api_key = os.environ.get("GLM_API_KEY")
    if not api_key:
        print_error("GLM_API_KEY 环境变量未设置")
        print_warning("请设置: export GLM_API_KEY='your-api-key'")
        return False

    print_success("GLM_API_KEY 已设置")

    # 检查测试目录
    test_dir = Path(__file__).parent
    if not test_dir.exists():
        print_error(f"测试目录不存在: {test_dir}")
        return False

    print_success(f"测试目录存在: {test_dir}")

    # 检查依赖
    try:
        import pytest
        print_success("pytest 已安装")
    except ImportError:
        print_error("pytest 未安装")
        print_warning("请运行: pip install pytest pytest-asyncio")
        return False

    try:
        import pyagentforge
        print_success("pyagentforge 已安装")
    except ImportError:
        print_error("pyagentforge 未安装")
        return False

    try:
        import glm_provider
        print_success("glm_provider 已找到")
    except ImportError:
        print_error("glm_provider 未找到")
        return False

    return True


def run_test_category(category: str, markers: str = None) -> Dict[str, Any]:
    """运行特定分类的测试"""
    print_section(f"运行 {category} 测试")

    test_dir = Path(__file__).parent

    cmd = ["pytest", str(test_dir), "-v", "--tb=short", "--json-report", "--json-report-file=none"]

    if markers:
        cmd.extend(["-m", markers])

    # 添加超时
    cmd.extend(["--timeout=300"])

    start_time = time.time()

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600  # 10 分钟总超时
        )

        elapsed_time = time.time() - start_time

        # 解析输出
        output = result.stdout + result.stderr

        # 统计结果
        passed = output.count(" PASSED")
        failed = output.count(" FAILED")
        skipped = output.count(" SKIPPED")
        errors = output.count(" ERROR")

        return {
            "category": category,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "errors": errors,
            "total": passed + failed + skipped + errors,
            "elapsed_time": elapsed_time,
            "success_rate": (passed / (passed + failed) * 100) if (passed + failed) > 0 else 0,
            "output": output
        }

    except subprocess.TimeoutExpired:
        print_error(f"{category} 测试超时")
        return {
            "category": category,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "errors": 1,
            "total": 1,
            "elapsed_time": 600,
            "success_rate": 0,
            "output": "Test timeout"
        }
    except Exception as e:
        print_error(f"{category} 测试失败: {e}")
        return {
            "category": category,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "errors": 1,
            "total": 1,
            "elapsed_time": 0,
            "success_rate": 0,
            "output": str(e)
        }


def run_all_tests():
    """运行所有测试"""
    print_header("PyAgentForge GLM-5 集成测试")

    # 测试分类
    test_categories = [
        ("基础功能", "basic"),
        ("工具调用", "tools"),
        ("流式响应", "streaming"),
        ("高级功能", "advanced"),
        ("错误处理", "error"),
        ("边界测试", "boundary"),
        ("集成测试", "integration"),
        ("性能测试", "performance"),
    ]

    results = []
    total_start_time = time.time()

    for category_name, marker in test_categories:
        result = run_test_category(category_name, marker)
        results.append(result)

        # 打印结果
        if result["success_rate"] >= 90:
            print_success(f"{category_name}: {result['passed']}/{result['total']} 通过 ({result['success_rate']:.1f}%)")
        elif result["success_rate"] >= 70:
            print_warning(f"{category_name}: {result['passed']}/{result['total']} 通过 ({result['success_rate']:.1f}%)")
        else:
            print_error(f"{category_name}: {result['passed']}/{result['total']} 通过 ({result['success_rate']:.1f}%)")

    total_elapsed_time = time.time() - total_start_time

    return results, total_elapsed_time


def generate_report(results: List[Dict[str, Any]], total_time: float):
    """生成测试报告"""
    print_header("生成测试报告")

    # 汇总统计
    total_passed = sum(r["passed"] for r in results)
    total_failed = sum(r["failed"] for r in results)
    total_skipped = sum(r["skipped"] for r in results)
    total_errors = sum(r["errors"] for r in results)
    total_tests = sum(r["total"] for r in results)

    overall_success_rate = (total_passed / (total_passed + total_failed) * 100) if (total_passed + total_failed) > 0 else 0

    # 打印汇总
    print(f"\n总测试数: {total_tests}")
    print(f"{Colors.OKGREEN}通过: {total_passed}{Colors.ENDC}")
    print(f"{Colors.FAIL}失败: {total_failed}{Colors.ENDC}")
    print(f"{Colors.WARNING}跳过: {total_skipped}{Colors.ENDC}")
    print(f"{Colors.FAIL}错误: {total_errors}{Colors.ENDC}")
    print(f"\n总耗时: {total_time:.2f}s")
    print(f"成功率: {overall_success_rate:.1f}%\n")

    # 生成 JSON 报告
    report = {
        "timestamp": datetime.now().isoformat(),
        "model": os.environ.get("GLM_MODEL", "glm-4-flash"),
        "summary": {
            "total_tests": total_tests,
            "passed": total_passed,
            "failed": total_failed,
            "skipped": total_skipped,
            "errors": total_errors,
            "success_rate": overall_success_rate,
            "total_time": total_time
        },
        "categories": results
    }

    # 保存报告
    report_file = Path(__file__).parent / "test-report.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print_success(f"JSON 报告已保存: {report_file}")

    # 生成 Markdown 报告
    generate_markdown_report(report)

    return report


def generate_markdown_report(report: Dict[str, Any]):
    """生成 Markdown 格式的测试报告"""

    md_content = f"""# PyAgentForge GLM-5 深度测试报告

**测试时间**: {report['timestamp']}
**测试模型**: {report['model']}
**总耗时**: {report['summary']['total_time']:.2f}s

## 测试概览

| 指标 | 数值 |
|------|------|
| 总测试数 | {report['summary']['total_tests']} |
| 通过 | {report['summary']['passed']} ✅ |
| 失败 | {report['summary']['failed']} ❌ |
| 跳过 | {report['summary']['skipped']} ⚠️ |
| 错误 | {report['summary']['errors']} 💥 |
| **成功率** | **{report['summary']['success_rate']:.1f}%** |

## 分类测试结果

"""

    for category in report['categories']:
        status = "✅" if category['success_rate'] >= 90 else "⚠️" if category['success_rate'] >= 70 else "❌"

        md_content += f"""### {status} {category['category']}

- **通过**: {category['passed']}/{category['total']}
- **成功率**: {category['success_rate']:.1f}%
- **耗时**: {category['elapsed_time']:.2f}s

"""

    # 添加建议
    md_content += """## 测试建议

"""

    failed_categories = [c for c in report['categories'] if c['success_rate'] < 90]

    if failed_categories:
        md_content += "### 需要改进的领域\n\n"
        for cat in failed_categories:
            md_content += f"- **{cat['category']}**: 成功率 {cat['success_rate']:.1f}%\n"
    else:
        md_content += "所有测试分类均达到 90% 以上通过率 ✅\n"

    # 保存 Markdown 报告
    report_file = Path(__file__).parent / "test-report.md"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(md_content)

    print_success(f"Markdown 报告已保存: {report_file}")


def main():
    """主函数"""
    # 检查前置条件
    if not check_prerequisites():
        print_error("前置条件检查失败，请修复后重试")
        sys.exit(1)

    # 运行测试
    results, total_time = run_all_tests()

    # 生成报告
    report = generate_report(results, total_time)

    # 退出码
    if report['summary']['success_rate'] >= 90:
        print_header("测试完成 - 优秀 ✅")
        sys.exit(0)
    elif report['summary']['success_rate'] >= 70:
        print_header("测试完成 - 良好 ⚠️")
        sys.exit(0)
    else:
        print_header("测试完成 - 需要改进 ❌")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_error("\n测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print_error(f"测试运行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
