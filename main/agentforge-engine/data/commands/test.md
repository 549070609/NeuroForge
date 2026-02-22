---
name: test
description: 运行测试并分析结果
alias:
  - pytest
  - run-tests
category: testing
tools:
  - bash
  - read
---

# 运行测试

请运行项目的测试套件并分析结果。

## 项目信息
!`ls -la`

## 测试文件
!`find . -name "test_*.py" -o -name "*_test.py" | head -20`

## 依赖
!`cat requirements.txt 2>/dev/null || cat pyproject.toml 2>/dev/null | head -30`

---

请执行以下操作：

1. 检测测试框架 (pytest/unittest/nose)
2. 运行测试
3. 分析测试结果
4. 对失败的测试提供修复建议
