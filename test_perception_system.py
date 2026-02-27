#!/usr/bin/env python3
"""
感知器系统快速验证脚本

运行此脚本以验证感知器的日志格式解析和规则匹配功能。

使用方法:
  cd D:\localproject\1.project\NeuroForge
  python test_perception_system.py
"""

import sys
import json
from pathlib import Path

# 添加 main/perception 到路径
sys.path.insert(0, str(Path(__file__).parent / "main" / "perception"))

try:
    from perception import (
        detect_format,
        parse_log,
        perceive,
        DecisionType
    )
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    print("请确保在项目根目录运行此脚本")
    sys.exit(1)


def print_section(title):
    """打印分节标题"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def test_format_detection():
    """测试格式检测"""
    print_section("测试 1: 日志格式检测")

    test_cases = [
        ("@schema[id:int, level:str]", "aton", "ATON 格式"),
        ("events[3]{id,level,message}:", "toon", "TOON 格式"),
        ("plain random text", "unknown", "未知格式"),
        ("", "unknown", "空字符串"),
    ]

    passed = 0
    for raw, expected, desc in test_cases:
        result = detect_format(raw)
        status = "✅" if result == expected else "❌"
        print(f"{status} {desc}: {result} (期望: {expected})")
        if result == expected:
            passed += 1

    print(f"\n通过: {passed}/{len(test_cases)}")
    return passed == len(test_cases)


def test_aton_parsing():
    """测试 ATON 解析"""
    print_section("测试 2: ATON 格式解析")

    raw = '''@schema[id:int, level:str, message:str]
events(3):
  1, "error", "Database connection failed"
  2, "warn", "Cache miss"
  3, "info", "Request processed"
'''

    try:
        data = parse_log(raw, fmt="aton")
        print(f"✅ 解析成功")
        print(f"   事件数量: {len(data.get('events', []))}")

        if len(data.get('events', [])) == 3:
            print("✅ 事件数量正确")
            return True
        else:
            print("❌ 事件数量不正确")
            return False
    except Exception as e:
        print(f"❌ 解析失败: {e}")
        return False


def test_toon_parsing():
    """测试 TOON 解析"""
    print_section("测试 3: TOON 格式解析")

    raw = "events[3]{id,level,message}:\n  1,error,Database timeout\n  2,warn,High memory\n  3,info,OK"

    try:
        data = parse_log(raw, fmt="toon")
        print(f"✅ 解析成功")
        print(f"   事件数量: {len(data.get('events', []))}")

        if len(data.get('events', [])) == 3:
            print("✅ 事件数量正确")
            return True
        else:
            print("❌ 事件数量不正确")
            return False
    except Exception as e:
        print(f"❌ 解析失败: {e}")
        return False


def test_error_perception():
    """测试错误级别感知"""
    print_section("测试 4: Error 级别感知")

    data = {
        "events": [
            {"id": 1, "level": "error", "message": "Database down"}
        ]
    }

    rules = {"error_triggers": "find_user"}

    try:
        result = perceive(data, rules)
        print(f"决策: {result.decision.value}")
        print(f"原因: {result.reason}")

        if result.decision == DecisionType.FIND_USER:
            print("✅ 正确触发 find_user")
            return True
        else:
            print("❌ 决策类型不正确")
            return False
    except Exception as e:
        print(f"❌ 感知失败: {e}")
        return False


def test_warn_perception():
    """测试警告级别感知"""
    print_section("测试 5: Warning 级别感知")

    data = {
        "events": [
            {"id": 1, "level": "warn", "message": "High CPU usage"}
        ]
    }

    rules = {"warn_triggers": "execute"}

    try:
        result = perceive(data, rules)
        print(f"决策: {result.decision.value}")
        print(f"原因: {result.reason}")

        if result.decision == DecisionType.EXECUTE:
            print("✅ 正确触发 execute")
            return True
        else:
            print("❌ 决策类型不正确")
            return False
    except Exception as e:
        print(f"❌ 感知失败: {e}")
        return False


def test_info_perception():
    """测试信息级别（不应触发）"""
    print_section("测试 6: Info 级别感知（不触发）")

    data = {
        "events": [
            {"id": 1, "level": "info", "message": "User login"}
        ]
    }

    try:
        result = perceive(data, {})
        print(f"决策: {result.decision.value}")
        print(f"原因: {result.reason}")

        if result.decision == DecisionType.NONE:
            print("✅ 正确未触发动作")
            return True
        else:
            print("❌ 不应该触发动作")
            return False
    except Exception as e:
        print(f"❌ 感知失败: {e}")
        return False


def test_field_aliases():
    """测试字段别名"""
    print_section("测试 7: 字段别名")

    test_cases = [
        ({"severity": "error"}, "severity 别名"),
        ({"log_level": "warn"}, "log_level 别名"),
        ({"type": "error"}, "type 别名"),
    ]

    passed = 0
    for event_data, desc in test_cases:
        data = {"events": [event_data]}
        try:
            result = perceive(data, {"error_triggers": "find_user", "warn_triggers": "execute"})

            expected_decision = (
                DecisionType.FIND_USER if event_data.get("severity") == "error" or event_data.get("type") == "error"
                else DecisionType.EXECUTE
            )

            if result.decision == expected_decision:
                print(f"✅ {desc} 识别成功")
                passed += 1
            else:
                print(f"❌ {desc} 识别失败")
        except Exception as e:
            print(f"❌ {desc} 测试失败: {e}")

    print(f"\n通过: {passed}/{len(test_cases)}")
    return passed == len(test_cases)


def test_priority():
    """测试多事件优先级"""
    print_section("测试 8: 多事件优先级")

    data = {
        "events": [
            {"id": 1, "level": "warn", "message": "Warning 1"},
            {"id": 2, "level": "error", "message": "Error 1"},
            {"id": 3, "level": "info", "message": "Info 1"}
        ]
    }

    try:
        result = perceive(data, {"error_triggers": "find_user"})
        print(f"决策: {result.decision.value}")
        print(f"原因: {result.reason}")

        if result.decision == DecisionType.FIND_USER and "error" in result.reason.lower():
            print("✅ 正确优先处理 Error 级别")
            return True
        else:
            print("❌ 优先级处理不正确")
            return False
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


def test_container_keys():
    """测试容器键名识别"""
    print_section("测试 9: 容器键名识别")

    test_keys = ["events", "logs", "records", "data", "items"]

    passed = 0
    for key in test_keys:
        data = {key: [{"level": "error", "message": "Test"}]}
        try:
            result = perceive(data, {"error_triggers": "find_user"})
            if result.decision == DecisionType.FIND_USER:
                print(f"✅ 键名 '{key}' 识别成功")
                passed += 1
            else:
                print(f"❌ 键名 '{key}' 识别失败")
        except Exception as e:
            print(f"❌ 键名 '{key}' 测试失败: {e}")

    print(f"\n通过: {passed}/{len(test_keys)}")
    return passed == len(test_keys)


def test_edge_cases():
    """测试边界情况"""
    print_section("测试 10: 边界情况")

    test_cases = [
        ({"events": []}, "空事件列表"),
        ({"events": [{"message": "No level"}]}, "缺少 level 字段"),
        ({"events": [{"level": None, "message": "Null level"}]}, "level 为 None"),
    ]

    passed = 0
    for data, desc in test_cases:
        try:
            result = perceive(data, {})
            if result.decision == DecisionType.NONE:
                print(f"✅ {desc}: 正确处理为 none")
                passed += 1
            else:
                print(f"❌ {desc}: 处理不正确")
        except Exception as e:
            print(f"❌ {desc} 测试失败: {e}")

    print(f"\n通过: {passed}/{len(test_cases)}")
    return passed == len(test_cases)


def test_case_insensitivity():
    """测试大小写不敏感"""
    print_section("测试 11: 大小写不敏感")

    test_cases = [
        ("ERROR", "全大写"),
        ("Warning", "首字母大写"),
        ("error", "全小写"),
    ]

    passed = 0
    for level, desc in test_cases:
        data = {"events": [{"level": level, "message": "Test"}]}
        try:
            result = perceive(data, {"error_triggers": "find_user", "warn_triggers": "execute"})

            is_error = level.lower() == "error"
            expected = DecisionType.FIND_USER if is_error else DecisionType.EXECUTE

            if result.decision == expected:
                print(f"✅ {desc} ({level}): 正确识别")
                passed += 1
            else:
                print(f"❌ {desc} ({level}): 识别失败")
        except Exception as e:
            print(f"❌ {desc} ({level}) 测试失败: {e}")

    print(f"\n通过: {passed}/{len(test_cases)}")
    return passed == len(test_cases)


def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("  感知器系统验证测试")
    print("="*60)

    tests = [
        test_format_detection,
        test_aton_parsing,
        test_toon_parsing,
        test_error_perception,
        test_warn_perception,
        test_info_perception,
        test_field_aliases,
        test_priority,
        test_container_keys,
        test_edge_cases,
        test_case_insensitivity,
    ]

    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"\n❌ 测试 {test.__name__} 异常: {e}")
            results.append(False)

    # 打印总结
    print_section("测试总结")

    total = len(results)
    passed = sum(results)
    failed = total - passed

    print(f"\n总测试数: {total}")
    print(f"✅ 通过: {passed}")
    print(f"❌ 失败: {failed}")

    if all(results):
        print("\n🎉 所有测试通过！感知器系统工作正常。")
        return 0
    else:
        print("\n⚠️  部分测试失败，请检查相关功能。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
