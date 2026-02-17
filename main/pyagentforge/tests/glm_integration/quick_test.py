#!/usr/bin/env python3
"""
快速测试执行脚本 - 运行关键测试并生成摘要报告
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
    print(f"\n{Colors.HEADER}{'='*60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text:^60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*60}{Colors.ENDC}\n")


def print_success(text: str):
    print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")


def print_error(text: str):
    print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")


def run_test_suite(name: str, test_files: List[str]) -> Dict:
    """运行测试套件"""
    print(f"\n{Colors.OKCYAN}[运行 {name}]{Colors.ENDC}")

    cmd = ["pytest"] + test_files + ["-v", "--tb=line", "-x"]

    start_time = time.time()

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            env=os.environ.copy()
        )

        elapsed_time = time.time() - start_time
        output = result.stdout + result.stderr

        # 统计结果
        passed = output.count(" PASSED")
        failed = output.count(" FAILED")
        skipped = output.count(" SKIPPED")

        total = passed + failed + skipped
        success_rate = (passed / total * 100) if total > 0 else 0

        # 打印结果
        if success_rate >= 90:
            print_success(f"{name}: {passed}/{total} 通过 ({success_rate:.0f}%) - {elapsed_time:.1f}s")
        else:
            print_error(f"{name}: {passed}/{total} 通过 ({success_rate:.0f}%) - {elapsed_time:.1f}s")

        return {
            "name": name,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "total": total,
            "success_rate": success_rate,
            "elapsed_time": elapsed_time
        }

    except Exception as e:
        print_error(f"{name} 失败: {e}")
        return {
            "name": name,
            "passed": 0,
            "failed": 1,
            "skipped": 0,
            "total": 1,
            "success_rate": 0,
            "elapsed_time": 0
        }


def generate_summary_report(results: List[Dict]):
    """生成摘要报告"""
    print_header("测试报告")

    total_passed = sum(r["passed"] for r in results)
    total_failed = sum(r["failed"] for r in results)
    total_skipped = sum(r["skipped"] for r in results)
    total_tests = sum(r["total"] for r in results)
    total_time = sum(r["elapsed_time"] for r in results)

    overall_success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0

    # 控制台输出
    print(f"总测试数: {total_tests}")
    print(f"{Colors.OKGREEN}通过: {total_passed}{Colors.ENDC}")
    if total_failed > 0:
        print(f"{Colors.FAIL}失败: {total_failed}{Colors.ENDC}")
    if total_skipped > 0:
        print(f"{Colors.WARNING}跳过: {total_skipped}{Colors.ENDC}")
    print(f"\n总耗时: {total_time:.1f}s")
    print(f"成功率: {overall_success_rate:.1f}%\n")

    # 生成 Markdown 报告
    report = f"""# PyAgentForge GLM-5 深度测试报告

**测试时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**测试模型**: {os.environ.get('GLM_MODEL', 'glm-4-flash')}
**总耗时**: {total_time:.1f}s

## 测试概览

| 指标 | 数值 |
|------|------|
| 总测试数 | {total_tests} |
| 通过 | {total_passed} ✅ |
| 失败 | {total_failed} {'❌' if total_failed > 0 else '✅'} |
| 跳过 | {total_skipped} {'⚠️' if total_skipped > 0 else '✅'} |
| **成功率** | **{overall_success_rate:.1f}%** |

## 测试分类结果

"""

    for r in results:
        status = "✅" if r["success_rate"] >= 90 else "⚠️" if r["success_rate"] >= 70 else "❌"
        report += f"""### {status} {r['name']}

- **通过**: {r['passed']}/{r['total']}
- **成功率**: {r['success_rate']:.1f}%
- **耗时**: {r['elapsed_time']:.1f}s

"""

    report += f"""## 测试覆盖范围

### ✅ 基础功能 (已测试)
- 简单对话和问答
- 数学计算
- 上下文感知和多轮对话
- 系统提示词定制
- 消息序列化

### ✅ 工具调用 (部分测试)
- Bash 命令执行
- 文件读写操作
- 工具链组合

### ⚠️ 高级功能 (未完全测试)
- 流式响应
- 并行子代理
- 上下文压缩
- 集成场景

## 测试建议

"""

    if overall_success_rate >= 95:
        report += "测试结果优秀，所有核心功能正常 ✅\n"
    elif overall_success_rate >= 80:
        report += "测试结果良好，建议修复失败用例 ⚠️\n"
    else:
        report += "测试结果需要改进，请检查失败用例 ❌\n"

    # 保存报告
    report_file = Path(__file__).parent / "test-report.md"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report)

    print_success(f"报告已保存: {report_file}")

    # 保存 JSON 数据
    json_data = {
        "timestamp": datetime.now().isoformat(),
        "model": os.environ.get("GLM_MODEL", "glm-4-flash"),
        "summary": {
            "total_tests": total_tests,
            "passed": total_passed,
            "failed": total_failed,
            "skipped": total_skipped,
            "success_rate": overall_success_rate,
            "total_time": total_time
        },
        "suites": results
    }

    json_file = Path(__file__).parent / "test-report.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)

    print_success(f"JSON 数据已保存: {json_file}")

    return overall_success_rate


def main():
    print_header("PyAgentForge GLM-5 快速测试")

    # 检查环境变量
    if not os.environ.get("GLM_API_KEY"):
        print_error("GLM_API_KEY 环境变量未设置")
        print("请运行: export GLM_API_KEY='your-key'")
        sys.exit(1)

    # 定义测试套件
    test_suites = [
        ("基础功能", ["test_basic_functionality.py"]),
        ("Bash 工具", ["test_tools_execution.py::TestBashTool"]),
        ("文件操作", ["test_tools_execution.py::TestFileTools"]),
        ("搜索工具", ["test_tools_execution.py::TestSearchTools"]),
    ]

    results = []

    # 运行每个测试套件
    for name, test_files in test_suites:
        result = run_test_suite(name, test_files)
        results.append(result)

    # 生成报告
    success_rate = generate_summary_report(results)

    # 返回退出码
    if success_rate >= 80:
        print_header("测试完成 ✅")
        sys.exit(0)
    else:
        print_header("测试需要改进 ⚠️")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_error("\n测试被用户中断")
        sys.exit(1)
