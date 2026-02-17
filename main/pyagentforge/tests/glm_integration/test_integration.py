"""
集成测试

测试端到端的真实场景
"""

import pytest
from pathlib import Path
import time

from conftest import check_api_key, run_agent_with_timeout


# ============ 代码生成测试 ============

@pytest.mark.integration
@pytest.mark.asyncio
class TestCodeGeneration:
    """代码生成测试"""

    async def test_generate_python_script(self, agent_engine, temp_dir):
        """测试生成 Python 脚本"""
        check_api_key()

        script_file = temp_dir / "generated.py"

        response = await run_agent_with_timeout(
            agent_engine,
            f"""
            请生成一个 Python 脚本 {script_file}，包含以下功能：
            1. 定义一个函数 fibonacci(n)，返回斐波那契数列的第 n 项
            2. 主程序调用该函数并打印结果
            3. 包含适当的注释
            """,
            timeout=90
        )

        assert response is not None

        # 验证文件已创建
        assert script_file.exists()

        # 验证代码可运行
        content = script_file.read_text()
        assert "fibonacci" in content.lower()
        assert "def" in content

    async def test_generate_and_run_code(self, agent_engine, temp_dir):
        """测试生成并运行代码"""
        check_api_key()

        script_file = temp_dir / "calculator.py"

        response = await run_agent_with_timeout(
            agent_engine,
            f"""
            任务：
            1. 创建 Python 文件 {script_file}
            2. 实现一个简单的计算器，支持加、减、乘、除
            3. 运行该脚本并测试 5 + 3
            """,
            timeout=90
        )

        assert response is not None


# ============ 文件重构测试 ============

@pytest.mark.integration
@pytest.mark.asyncio
class TestFileRefactoring:
    """文件重构测试"""

    async def test_refactor_python_code(self, agent_engine, temp_dir):
        """测试重构 Python 代码"""
        check_api_key()

        # 创建原始文件
        original_file = temp_dir / "original.py"
        original_file.write_text("""
def calculate(x, y):
    return x + y

result = calculate(1, 2)
print(result)
""")

        response = await run_agent_with_timeout(
            agent_engine,
            f"""
            请重构文件 {original_file}：
            1. 添加类型注解
            2. 添加文档字符串
            3. 改进变量命名
            """,
            timeout=90
        )

        assert response is not None

        # 验证文件已修改
        modified_content = original_file.read_text()
        assert len(modified_content) > len(original_file.read_text())  # 内容应该增加


# ============ 多步任务测试 ============

@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.slow
class TestMultiStepTasks:
    """多步任务测试"""

    async def test_complete_project_setup(self, agent_engine, temp_dir):
        """测试完整项目搭建"""
        check_api_key()

        project_dir = temp_dir / "myproject"

        response = await run_agent_with_timeout(
            agent_engine,
            f"""
            请完成以下项目搭建任务：
            1. 创建项目目录 {project_dir}
            2. 创建 README.md 文件，包含项目说明
            3. 创建 main.py 文件，包含主程序
            4. 创建 requirements.txt 文件，列出依赖
            5. 列出项目目录结构
            """,
            timeout=120
        )

        assert response is not None

        # 验证文件创建
        assert (project_dir / "README.md").exists()
        assert (project_dir / "main.py").exists()
        assert (project_dir / "requirements.txt").exists()

    async def test_data_analysis_task(self, agent_engine, temp_dir):
        """测试数据分析任务"""
        check_api_key()

        # 创建数据文件
        data_file = temp_dir / "data.csv"
        data_file.write_text("""name,score
Alice,85
Bob,92
Charlie,78
David,95
Eve,88
""")

        response = await run_agent_with_timeout(
            agent_engine,
            f"""
            分析数据文件 {data_file}：
            1. 读取 CSV 数据
            2. 计算平均分
            3. 找出最高分和最低分
            4. 生成分析报告
            """,
            timeout=90
        )

        assert response is not None
        # 验证包含分析结果
        assert "平均" in response or "average" in response.lower()


# ============ 会话持久化测试 ============

@pytest.mark.integration
@pytest.mark.asyncio
class TestSessionPersistence:
    """会话持久化测试"""

    async def test_save_and_restore_session(self, agent_engine, temp_dir):
        """测试保存和恢复会话"""
        check_api_key()

        # 第一阶段：创建会话并记住信息
        response1 = await run_agent_with_timeout(
            agent_engine,
            "请记住我的名字是测试用户，我的邮箱是 test@example.com"
        )
        assert response1 is not None

        # 保存上下文
        context_json = agent_engine.context.to_json()
        session_file = temp_dir / "session.json"
        session_file.write_text(context_json)

        # 第二阶段：恢复会话
        from pyagentforge.core.context import ContextManager

        restored_context = ContextManager.from_json(session_file.read_text())

        # 验证上下文已恢复
        assert len(restored_context) == len(agent_engine.context)


# ============ 跨文件操作测试 ============

@pytest.mark.integration
@pytest.mark.asyncio
class TestCrossFileOperations:
    """跨文件操作测试"""

    async def test_extract_and_aggregate(self, agent_engine, temp_dir):
        """测试提取和聚合"""
        check_api_key()

        # 创建多个文件
        for i in range(3):
            file_path = temp_dir / f"data_{i}.txt"
            file_path.write_text(f"Value: {i * 10}")

        summary_file = temp_dir / "summary.txt"

        response = await run_agent_with_timeout(
            agent_engine,
            f"""
            任务：
            1. 读取 {temp_dir} 中的所有 data_*.txt 文件
            2. 提取数值
            3. 计算总和
            4. 将结果写入 {summary_file}
            """,
            timeout=90
        )

        assert response is not None
        assert summary_file.exists()


# ============ 真实场景测试 ============

@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.slow
class TestRealWorldScenarios:
    """真实场景测试"""

    async def test_bug_fixing_scenario(self, agent_engine, temp_dir):
        """测试 Bug 修复场景"""
        check_api_key()

        # 创建有 Bug 的代码
        buggy_code = temp_dir / "buggy.py"
        buggy_code.write_text("""
def divide(a, b):
    return a / b

result = divide(10, 0)
print(result)
""")

        response = await run_agent_with_timeout(
            agent_engine,
            f"""
            文件 {buggy_code} 中有一个 Bug：
            1. 找出 Bug
            2. 修复 Bug（添加异常处理）
            3. 测试修复后的代码
            """,
            timeout=90
        )

        assert response is not None

    async def test_documentation_generation(self, agent_engine, temp_dir):
        """测试文档生成"""
        check_api_key()

        # 创建代码文件
        code_file = temp_dir / "module.py"
        code_file.write_text("""
def add(a, b):
    return a + b

def multiply(a, b):
    return a * b
""")

        doc_file = temp_dir / "README.md"

        response = await run_agent_with_timeout(
            agent_engine,
            f"""
            为 {code_file} 生成文档：
            1. 分析代码中的函数
            2. 生成 Markdown 格式的 API 文档
            3. 保存到 {doc_file}
            """,
            timeout=90
        )

        assert response is not None
        assert doc_file.exists()


# ============ 导入 ============

from pathlib import Path
