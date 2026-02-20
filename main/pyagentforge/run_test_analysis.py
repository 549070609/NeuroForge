#!/usr/bin/env python3
"""
PyAgentForge 测试运行和分析工具
"""
import subprocess
import sys
import json
import re
from pathlib import Path
from datetime import datetime

def run_command(cmd, description):
    """运行命令并返回结果"""
    print(f"\n{'='*60}")
    print(f"执行: {description}")
    print(f"命令: {' '.join(cmd)}")
    print('='*60)
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300
        )
        return result
    except subprocess.TimeoutExpired:
        print(f"✗ 命令超时")
        return None
    except Exception as e:
        print(f"✗ 命令执行失败: {e}")
        return None

def analyze_test_output(output):
    """分析测试输出"""
    # 统计测试结果
    passed = len(re.findall(r' PASSED', output))
    failed = len(re.findall(r' FAILED', output))
    skipped = len(re.findall(r' SKIPPED', output))
    errors = len(re.findall(r' ERROR', output))
    
    return {
        'passed': passed,
        'failed': failed,
        'skipped': skipped,
        'errors': errors,
        'total': passed + failed + skipped + errors
    }

def main():
    print("="*60)
    print("PyAgentForge 测试运行和分析")
    print("="*60)
    
    # Step 1: 检查环境
    print(f"\n1. 环境信息:")
    print(f"   Python: {sys.version}")
    print(f"   当前目录: {Path.cwd()}")
    
    # Step 2: 检查测试文件
    test_files = list(Path("tests").rglob("test_*.py"))
    print(f"\n2. 测试文件统计:")
    print(f"   找到 {len(test_files)} 个测试文件")
    
    # 按类别统计
    categories = {}
    for tf in test_files:
        category = tf.parent.name
        categories[category] = categories.get(category, 0) + 1
    
    print("\n   按类别分布:")
    for cat, count in sorted(categories.items()):
        print(f"   - {cat:20s}: {count:2d} 个文件")
    
    # Step 3: 尝试安装依赖
    print(f"\n3. 检查并安装测试依赖...")
    install_result = run_command(
        [sys.executable, "-m", "pip", "install", "-q", 
         "pytest>=8.0.0", "pytest-asyncio>=0.23.0", "pytest-cov>=4.1.0"],
        "安装测试依赖"
    )
    
    if install_result and install_result.returncode == 0:
        print("✓ 依赖安装成功")
    else:
        print("⚠ 依赖安装可能失败，继续尝试...")
    
    # Step 4: 检查 pytest
    print(f"\n4. 检查 pytest...")
    pytest_check = run_command(
        [sys.executable, "-m", "pytest", "--version"],
        "检查 pytest 版本"
    )
    
    if pytest_check and pytest_check.returncode == 0:
        print("✓ pytest 可用")
        print(pytest_check.stdout)
    else:
        print("✗ pytest 不可用")
        return
    
    # Step 5: 运行测试收集
    print(f"\n5. 收集测试用例...")
    collect_result = run_command(
        [sys.executable, "-m", "pytest", "tests/", "--collect-only", "-q"],
        "收集测试用例"
    )
    
    if collect_result:
        test_count_match = re.search(r'(\d+) tests?', collect_result.stdout)
        if test_count_match:
            print(f"✓ 找到 {test_count_match.group(1)} 个测试用例")
    
    # Step 6: 运行测试（选择一个简单的测试文件开始）
    print(f"\n6. 运行示例测试...")
    
    # 找一个简单的测试文件
    simple_test = "tests/kernel/test_message.py"
    if Path(simple_test).exists():
        test_result = run_command(
            [sys.executable, "-m", "pytest", simple_test, "-v", "--tb=short"],
            f"运行 {simple_test}"
        )
        
        if test_result:
            print("\n测试输出:")
            print(test_result.stdout)
            if test_result.stderr:
                print("错误输出:")
                print(test_result.stderr)
            
            stats = analyze_test_output(test_result.stdout + test_result.stderr)
            print(f"\n测试统计:")
            print(f"  通过: {stats['passed']}")
            print(f"  失败: {stats['failed']}")
            print(f"  跳过: {stats['skipped']}")
            print(f"  错误: {stats['errors']}")
            print(f"  总计: {stats['total']}")
    
    # Step 7: 尝试运行更多测试
    print(f"\n7. 运行 Kernel 层测试...")
    kernel_result = run_command(
        [sys.executable, "-m", "pytest", "tests/kernel/", "-v", "--tb=short", "-x"],
        "运行 Kernel 层测试"
    )
    
    if kernel_result:
        stats = analyze_test_output(kernel_result.stdout + kernel_result.stderr)
        print(f"\nKernel 层测试统计:")
        print(f"  通过: {stats['passed']}")
        print(f"  失败: {stats['failed']}")
        print(f"  跳过: {stats['skipped']}")
    
    # 生成报告
    print(f"\n{'='*60}")
    print("测试分析总结")
    print('='*60)
    
    report = {
        'timestamp': datetime.now().isoformat(),
        'test_files_count': len(test_files),
        'categories': categories,
        'environment': {
            'python_version': sys.version,
            'cwd': str(Path.cwd())
        }
    }
    
    # 保存报告
    report_path = Path("test_analysis_report.json")
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ 分析报告已保存到: {report_path}")
    print(f"\n建议:")
    print(f"  1. 如果测试失败，检查依赖是否完整安装")
    print(f"  2. 查看详细错误信息修复失败测试")
    print(f"  3. 运行 'python -m pytest tests/ -v' 查看完整测试结果")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n用户中断执行")
    except Exception as e:
        print(f"\n\n执行出错: {e}")
        import traceback
        traceback.print_exc()
