"""
PoC 验证：ATON/TOON 解析与格式检测

运行: cd Agent-Learn/main && python -m perception.test_parser
或:   cd perception && python test_parser.py
"""

import sys
from pathlib import Path

# 确保能导入 perception 模块
_main = Path(__file__).resolve().parent.parent
if str(_main) not in sys.path:
    sys.path.insert(0, str(_main))
try:
    from perception.detector import detect_format
    from perception.parser import parse_log
except ImportError:
    from detector import detect_format
    from parser import parse_log


def test_detect_format():
    """测试格式检测"""
    # ATON
    aton_sample = """
@schema[id:int, level:str, message:str]
events(2):
  1, "error", "Connection timeout"
  2, "info", "User login"
"""
    assert detect_format(aton_sample) == "aton"

    # TOON
    toon_sample = """
events[2]{id,level,message}:
  1,error,Connection timeout
  2,info,User login
"""
    assert detect_format(toon_sample) == "toon"

    # unknown
    assert detect_format("plain text") == "unknown"
    assert detect_format("") == "unknown"

    print("[OK] detect_format passed")


def test_parse_aton():
    """测试 ATON 解析"""
    aton_sample = """
@schema[id:int, level:str, message:str]
events(2):
  1, "error", "Connection timeout"
  2, "info", "User login"
"""
    result = parse_log(aton_sample)
    assert "events" in result
    assert len(result["events"]) == 2
    assert result["events"][0]["level"] == "error"
    assert result["events"][1]["message"] == "User login"
    print("[OK] parse_log (ATON) passed")


def test_parse_toon():
    """测试 TOON 解析"""
    toon_sample = """
events[2]{id,level,message}:
  1,error,Connection timeout
  2,info,User login
"""
    result = parse_log(toon_sample)
    # toon-formatter 可能返回 list 或 dict，取决于结构
    if isinstance(result, list):
        assert len(result) == 2
        assert result[0]["level"] == "error"
    else:
        assert "events" in result or len(result) >= 2
    print("[OK] parse_log (TOON) passed")


def test_parse_with_explicit_format():
    """测试显式指定格式"""
    aton_sample = '@schema[id:int]\ndata(1):\n  1'
    result = parse_log(aton_sample, fmt="aton")
    assert result is not None
    print("[OK] parse_log (explicit fmt) passed")


def test_perceive():
    """测试感知与决策"""
    try:
        from perception.perception import perceive, DecisionType
    except ImportError:
        from perception import perceive, DecisionType

    # 有 error 时应触发
    data = {"events": [{"id": 1, "level": "error", "message": "Connection timeout"}]}
    r = perceive(data)
    assert r.decision == DecisionType.FIND_USER
    assert "error" in r.reason.lower()

    # 无异常时应返回 NONE
    data2 = {"events": [{"id": 1, "level": "info", "message": "OK"}]}
    r2 = perceive(data2)
    assert r2.decision == DecisionType.NONE
    print("[OK] perceive passed")


if __name__ == "__main__":
    print("Running PoC validation...\n")
    try:
        test_detect_format()
        test_parse_aton()
        test_parse_toon()
        test_parse_with_explicit_format()
        test_perceive()
        print("\n[PASS] All tests passed")
    except ImportError as e:
        print(f"\n[FAIL] Missing dependency: {e}")
        print("Run: pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"\n[FAIL] Test failed: {e}")
        raise
