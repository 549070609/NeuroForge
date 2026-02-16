#!/usr/bin/env python3
"""
压力测试执行脚本

运行 PyAgentForge 的压力测试并生成详细报告
"""

import os
import sys
import json
import time
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List

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


def print_header(text: str):
    print(f"\n{Colors.HEADER}{'='*70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text:^70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*70}{Colors.ENDC}\n")


def print_section(text: str):
    print(f"\n{Colors.OKCYAN}{Colors.BOLD}[{text}]{Colors.ENDC}")


def print_success(text: str):
    print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")


def print_error(text: str):
    print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")


def print_warning(text: str):
    print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")


def print_metric(label: str, value: str, status: str = "info"):
    """打印指标"""
    color = {
        "good": Colors.OKGREEN,
        "warning": Colors.WARNING,
        "error": Colors.FAIL,
        "info": Colors.OKCYAN,
    }.get(status, "")

    print(f"  {label:.<40} {color}{value}{Colors.ENDC}")


def run_stress_tests():
    """运行压力测试"""
    print_header("PyAgentForge 压力测试套件")

    # 检查环境
    if not os.environ.get("GLM_API_KEY"):
        print_error("GLM_API_KEY 环境变量未设置")
        print_warning("请运行: export GLM_API_KEY='your-key'")
        return None

    # 定义测试组
    test_groups = [
        {
            "name": "并发压力测试",
            "tests": [
                "test_stress.py::TestConcurrencyStress::test_concurrent_5_sessions",
                "test_stress.py::TestConcurrencyStress::test_concurrent_10_sessions",
            ],
            "description": "测试系统并发处理能力"
        },
        {
            "name": "长时间运行测试",
            "tests": [
                "test_stress.py::TestLongRunningStress::test_20_turns_conversation",
                "test_stress.py::TestLongRunningStress::test_memory_leak_detection",
            ],
            "description": "测试系统稳定性和内存管理"
        },
        {
            "name": "大数据量测试",
            "tests": [
                "test_stress.py::TestDataVolumeStress::test_large_context_accumulation",
                "test_stress.py::TestDataVolumeStress::test_rapid_requests",
            ],
            "description": "测试大数据处理能力"
        },
        {
            "name": "极限条件测试",
            "tests": [
                "test_stress.py::TestExtremeConditions::test_max_token_limit",
                "test_stress.py::TestExtremeConditions::test_empty_and_special_input",
            ],
            "description": "测试边界条件处理"
        },
        {
            "name": "性能基准测试",
            "tests": [
                "test_stress.py::TestPerformanceBenchmark::test_response_time_benchmark",
            ],
            "description": "测试性能基准"
        },
    ]

    results = []
    total_start_time = time.time()

    # 运行每个测试组
    for group in test_groups:
        print_section(f"运行 {group['name']}")
        print(f"描述: {group['description']}\n")

        group_start_time = time.time()
        group_results = []

        for test in group["tests"]:
            print(f"\n执行: {test}")

            cmd = ["pytest", test, "-v", "-s", "--tb=short"]
            start_time = time.time()

            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300,  # 5分钟超时
                    env=os.environ.copy()
                )

                elapsed_time = time.time() - start_time
                output = result.stdout + result.stderr

                # 解析结果
                passed = "PASSED" in output
                failed = "FAILED" in output

                if passed and not failed:
                    print_success(f"通过 ({elapsed_time:.1f}s)")
                    status = "passed"
                else:
                    print_error(f"失败 ({elapsed_time:.1f}s)")
                    status = "failed"

                group_results.append({
                    "test": test,
                    "status": status,
                    "time": elapsed_time,
                    "output": output[-500:] if failed else ""  # 保存错误输出
                })

            except subprocess.TimeoutExpired:
                print_error("超时")
                group_results.append({
                    "test": test,
                    "status": "timeout",
                    "time": 300,
                    "output": "Test timeout after 300s"
                })

            except Exception as e:
                print_error(f"异常: {e}")
                group_results.append({
                    "test": test,
                    "status": "error",
                    "time": 0,
                    "output": str(e)
                })

        group_time = time.time() - group_start_time
        passed_count = sum(1 for r in group_results if r["status"] == "passed")
        total_count = len(group_results)
        success_rate = (passed_count / total_count * 100) if total_count > 0 else 0

        results.append({
            "name": group["name"],
            "description": group["description"],
            "total": total_count,
            "passed": passed_count,
            "failed": total_count - passed_count,
            "success_rate": success_rate,
            "time": group_time,
            "tests": group_results
        })

        # 打印组摘要
        if success_rate >= 80:
            print_success(f"{group['name']}: {passed_count}/{total_count} 通过 ({success_rate:.0f}%)")
        else:
            print_warning(f"{group['name']}: {passed_count}/{total_count} 通过 ({success_rate:.0f}%)")

    total_time = time.time() - total_start_time

    return results, total_time


def generate_stress_report(results: List[Dict], total_time: float):
    """生成压力测试报告"""
    print_header("压力测试报告")

    # 汇总统计
    total_tests = sum(r["total"] for r in results)
    total_passed = sum(r["passed"] for r in results)
    total_failed = sum(r["failed"] for r in results)
    overall_success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0

    # 控制台报告
    print("\n📊 测试概览\n")
    print_metric("总测试数", str(total_tests))
    print_metric("通过", str(total_passed), "good" if total_passed > total_failed else "error")
    print_metric("失败", str(total_failed), "error" if total_failed > 0 else "good")
    print_metric("成功率", f"{overall_success_rate:.1f}%",
                 "good" if overall_success_rate >= 80 else "warning")
    print_metric("总耗时", f"{total_time:.1f}s ({total_time/60:.1f}min)")

    print("\n📋 分组详情\n")
    for r in results:
        status = "good" if r["success_rate"] >= 80 else "warning" if r["success_rate"] >= 60 else "error"
        print_metric(r["name"], f"{r['passed']}/{r['total']} ({r['success_rate']:.0f}%)", status)
        print(f"    └─ 耗时: {r['time']:.1f}s")

    # 性能评估
    print("\n⚡ 性能评估\n")

    if overall_success_rate >= 90:
        grade = "A"
        comment = "系统性能优秀，能够承受压力"
    elif overall_success_rate >= 80:
        grade = "B"
        comment = "系统性能良好，基本能承受压力"
    elif overall_success_rate >= 70:
        grade = "C"
        comment = "系统性能一般，部分场景需要优化"
    else:
        grade = "F"
        comment = "系统性能不足，需要重大改进"

    print_metric("性能等级", grade, "good" if grade in ["A", "B"] else "warning")
    print(f"  {comment}")

    # 生成 Markdown 报告
    md_report = f"""# PyAgentForge 压力测试报告

**测试时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**测试模型**: {os.environ.get('GLM_MODEL', 'glm-4-flash')}
**总耗时**: {total_time:.1f}s ({total_time/60:.1f}min)

---

## 📊 测试概览

| 指标 | 数值 |
|------|------|
| 总测试数 | {total_tests} |
| 通过 | {total_passed} ✅ |
| 失败 | {total_failed} {'❌' if total_failed > 0 else '✅'} |
| **成功率** | **{overall_success_rate:.1f}%** |
| **性能等级** | **{grade}** |

---

## 📋 测试分组结果

"""

    for r in results:
        status = "✅" if r["success_rate"] >= 80 else "⚠️" if r["success_rate"] >= 60 else "❌"

        md_report += f"""### {status} {r['name']}

**描述**: {r['description']}
**通过率**: {r['success_rate']:.1f}% ({r['passed']}/{r['total']})
**耗时**: {r['time']:.1f}s

<details>
<summary>详细测试结果</summary>

"""

        for test in r["tests"]:
            status_icon = "✅" if test["status"] == "passed" else "❌"
            md_report += f"- {status_icon} `{test['test']}` - {test['time']:.1f}s\n"

        md_report += "\n</details>\n\n"

    md_report += f"""## ⚡ 性能评估

**等级**: {grade}
**评价**: {comment}

### 性能矩阵

| 测试类别 | 通过率 | 评级 |
|---------|--------|------|
"""

    for r in results:
        rating = "A" if r["success_rate"] >= 90 else "B" if r["success_rate"] >= 80 else "C" if r["success_rate"] >= 70 else "F"
        md_report += f"| {r['name']} | {r['success_rate']:.1f}% | {rating} |\n"

    md_report += f"""
---

## 💡 建议

### 优化建议

"""

    if overall_success_rate >= 90:
        md_report += "- ✅ 系统性能优秀，建议保持当前配置\n"
        md_report += "- 💡 可以尝试更高的并发数测试极限\n"
    elif overall_success_rate >= 80:
        md_report += "- ⚠️ 部分测试未通过，建议检查失败用例\n"
        md_report += "- 💡 考虑优化响应时间或增加资源\n"
    else:
        md_report += "- ❌ 性能不达标，需要重大改进\n"
        md_report += "- 🔍 重点关注失败的测试组\n"
        md_report += "- 📈 建议进行性能分析找出瓶颈\n"

    md_report += f"""
### 下一步行动

1. **立即**: 检查失败的测试用例
2. **短期**: 优化性能瓶颈
3. **长期**: 建立性能监控体系

---

**报告生成时间**: {datetime.now().isoformat()}
**测试环境**: {sys.platform}
"""

    # 保存报告
    report_file = Path(__file__).parent / "stress-test-report.md"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(md_report)

    print(f"\n{Colors.OKGREEN}✓ Markdown 报告已保存: {report_file}{Colors.ENDC}")

    # 保存 JSON 数据
    json_data = {
        "timestamp": datetime.now().isoformat(),
        "model": os.environ.get("GLM_MODEL", "glm-4-flash"),
        "summary": {
            "total_tests": total_tests,
            "passed": total_passed,
            "failed": total_failed,
            "success_rate": overall_success_rate,
            "total_time": total_time,
            "grade": grade
        },
        "groups": results
    }

    json_file = Path(__file__).parent / "stress-test-report.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)

    print(f"{Colors.OKGREEN}✓ JSON 数据已保存: {json_file}{Colors.ENDC}\n")

    return overall_success_rate


def main():
    """主函数"""
    try:
        # 运行压力测试
        results, total_time = run_stress_tests()

        if results is None:
            sys.exit(1)

        # 生成报告
        success_rate = generate_stress_report(results, total_time)

        # 返回退出码
        if success_rate >= 80:
            print_header("压力测试完成 - 系统性能良好 ✅")
            sys.exit(0)
        elif success_rate >= 60:
            print_header("压力测试完成 - 系统性能一般 ⚠️")
            sys.exit(0)
        else:
            print_header("压力测试完成 - 系统性能不足 ❌")
            sys.exit(1)

    except KeyboardInterrupt:
        print_error("\n测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print_error(f"测试运行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
