# GLM-5 深度测试执行指南

本指南帮助你在本地运行 PyAgentForge 的 GLM-5 深度测试套件。

## 前置准备

### 1. 获取 GLM API Key

1. 访问 [智谱 AI 开放平台](https://open.bigmodel.cn/)
2. 注册/登录账号
3. 在控制台获取 API Key
4. 根据你的套餐选择合适的 API 端点：
   - **Coding Plan**: `https://api.z.ai/api/anthropic` (Anthropic 兼容)
   - **Coding Plan**: `https://api.z.ai/api/coding/paas/v4` (OpenAI 兼容)
   - **通用**: `https://open.bigmodel.cn/api/paas/v4`

### 2. 配置环境变量

复制并编辑 `.env` 文件：

```bash
cd demo/glm-provider
cp .env.example .env
```

编辑 `.env` 文件：

```bash
# 填入你的 GLM API Key
GLM_API_KEY=your_actual_glm_api_key_here

# 选择模型 (推荐 glm-4-flash 用于测试，速度快成本低)
GLM_MODEL=glm-4-flash

# 选择 API 端点 (根据你的套餐)
GLM_BASE_URL=https://api.z.ai/api/anthropic
```

### 3. 安装测试依赖

```bash
# 安装 PyAgentForge
cd demo/pyagentforge
pip install -e .

# 安装测试依赖
cd tests/glm_integration
pip install -r requirements.txt
```

## 快速开始

### 方式 1: 使用测试脚本（推荐）

```bash
cd demo/pyagentforge/tests/glm_integration

# 设置环境变量
export GLM_API_KEY="your-api-key"
export GLM_MODEL="glm-4-flash"

# 运行所有测试
python run_tests.py
```

### 方式 2: 直接使用 pytest

```bash
cd demo/pyagentforge/tests/glm_integration

# 设置环境变量
export GLM_API_KEY="your-api-key"

# 运行所有测试
pytest -v

# 运行特定分类
pytest -m basic -v           # 基础功能
pytest -m tools -v           # 工具调用
pytest -m integration -v     # 集成测试

# 跳过慢速测试
pytest -m "not slow" -v
```

## 测试用例详情

### 基础功能测试 (8 个用例)

**文件**: [test_basic_functionality.py](test_basic_functionality.py)

- ✅ 简单问题回答
- ✅ 数学计算
- ✅ 上下文感知（记住用户名）
- ✅ 多轮对话
- ✅ 自定义系统提示词
- ✅ 角色扮演
- ✅ 上下文管理
- ✅ 消息序列化

**预计时间**: 2-3 分钟

### 工具调用测试 (12 个用例)

**文件**: [test_tools_execution.py](test_tools_execution.py)

- ✅ Bash 命令执行 (echo, ls, pipes)
- ✅ 文件写入和读取
- ✅ 文件编辑
- ✅ 文件搜索 (glob)
- ✅ 内容搜索 (grep)
- ✅ 工具链（多步骤任务）
- ✅ 权限控制

**预计时间**: 5-8 分钟

### 流式响应测试 (4 个用例)

**文件**: [test_streaming.py](test_streaming.py)

- ✅ 流式文本响应
- ✅ 流式工具调用
- ✅ WebSocket 连接（需启动服务器）
- ✅ HTTP API（需启动服务器）

**预计时间**: 2-3 分钟

**注意**: WebSocket 和 HTTP API 测试需要先启动 GLM Provider 服务器：

```bash
cd demo/glm-provider
python server.py
```

然后在另一个终端运行测试：

```bash
pytest -m streaming --run-server-tests -v
```

### 高级功能测试 (5 个用例)

**文件**: [test_advanced_features.py](test_advanced_features.py)

- ✅ 并行执行任务
- ✅ 长上下文处理
- ✅ Skill 加载
- ✅ Command 解析
- ✅ 推理任务

**预计时间**: 3-5 分钟

### 错误处理测试 (10 个用例)

**文件**: [test_error_handling.py](test_error_handling.py)

- ✅ 无效工具请求
- ✅ 无效工具参数
- ✅ 读取不存在的文件
- ✅ 写入无效路径
- ✅ 无效命令
- ✅ 语法错误命令
- ✅ 空消息
- ✅ 超长消息
- ✅ 特殊字符

**预计时间**: 3-4 分钟

### 边界测试 (8 个用例)

**文件**: [test_boundary.py](test_boundary.py)

- ✅ 多轮对话（20 轮）
- ✅ 大上下文内容
- ✅ 读取大文件（10MB）
- ✅ 多文件操作（100 个文件）
- ✅ 连续工具调用（10 次）
- ✅ 并发会话（5 个并发）
- ✅ Token 限制
- ✅ 特殊输入（Unicode、代码块、Markdown）

**预计时间**: 10-15 分钟

**标记**: 大部分为 `@pytest.mark.slow`

### 集成测试 (8 个用例)

**文件**: [test_integration.py](test_integration.py)

- ✅ 生成 Python 脚本
- ✅ 生成并运行代码
- ✅ 重构 Python 代码
- ✅ 完整项目搭建
- ✅ 数据分析任务
- ✅ 保存和恢复会话
- ✅ 跨文件操作
- ✅ Bug 修复场景
- ✅ 文档生成

**预计时间**: 8-12 分钟

**标记**: 大部分为 `@pytest.mark.slow`

### 性能测试 (6 个用例)

**文件**: [test_performance.py](test_performance.py)

- ✅ 简单查询响应时间
- ✅ 复杂查询响应时间
- ✅ 文件读取性能
- ✅ 多次工具调用性能
- ✅ 顺序请求吞吐量
- ✅ 并发会话性能
- ✅ 内存使用测试

**预计时间**: 5-8 分钟

## 测试报告

测试完成后，会在 `tests/glm_integration/` 目录生成：

1. **test-report.md** - Markdown 格式总结报告
2. **test-report.json** - 详细 JSON 数据

### 示例报告

```markdown
# PyAgentForge GLM-5 深度测试报告

**测试时间**: 2026-02-16T14:30:00
**测试模型**: glm-4-flash
**总耗时**: 45.23s

## 测试概览

| 指标 | 数值 |
|------|------|
| 总测试数 | 57 |
| 通过 | 54 ✅ |
| 失败 | 2 ❌ |
| 跳过 | 1 ⚠️ |
| 错误 | 0 💥 |
| **成功率** | **96.4%** |

## 分类测试结果

### ✅ 基础功能
- **通过**: 8/8
- **成功率**: 100.0%
- **耗时**: 2.34s

...
```

## 常见问题

### Q: GLM_API_KEY 环境变量未设置

**A**: 确保在运行测试前设置环境变量：

```bash
export GLM_API_KEY="your-key-here"
```

或者在 `.env` 文件中设置。

### Q: 测试超时

**A**: 某些测试可能需要较长时间。增加超时时间：

```bash
export TEST_TIMEOUT=60  # 60 秒
```

### Q: 依赖缺失

**A**: 确保安装所有依赖：

```bash
pip install -r requirements.txt
pip install -e ../../  # 安装 pyagentforge
```

### Q: WebSocket 测试失败

**A**: WebSocket 测试需要先启动 GLM Provider 服务器：

```bash
# 终端 1
cd demo/glm-provider
python server.py

# 终端 2
pytest -m streaming --run-server-tests -v
```

### Q: 并发测试失败

**A**: 并发测试可能受 API 速率限制影响。可以：

1. 减少并发数量（修改测试代码）
2. 增加 API Key 配额
3. 跳过并发测试：`pytest -m "not slow" -v`

### Q: 性能测试数值波动

**A**: 性能受网络状况影响。建议：

1. 在网络稳定时测试
2. 多次运行取平均值
3. 主要关注相对趋势而非绝对值

## 自定义测试

### 添加新测试

1. 在对应的 `test_*.py` 文件中添加测试函数
2. 使用适当的 pytest 标记：
   ```python
   @pytest.mark.basic
   @pytest.mark.asyncio
   async def test_new_feature(agent_engine):
       # 测试代码
       pass
   ```
3. 在 `TEST_PLAN.md` 中记录

### 修改测试配置

编辑 `conftest.py` 文件：

```python
# 修改默认超时
TEST_TIMEOUT = 60  # 秒

# 修改模型
GLM_MODEL = "glm-5"

# 修改临时目录
TEST_TEMP_DIR = Path("/tmp/test")
```

## 成功标准

根据测试结果评估系统质量：

| 成功率 | 等级 | 建议 |
|--------|------|------|
| ≥ 95% | 优秀 ✅ | 可以部署到生产环境 |
| 90-95% | 良好 ⚠️ | 修复失败用例后可部署 |
| 70-90% | 及格 ⚠️ | 需要改进 |
| < 70% | 不及格 ❌ | 需要重大修复 |

## 下一步

测试通过后，可以：

1. 查看 `test-report.md` 了解详细结果
2. 分析失败用例并修复
3. 运行覆盖率测试：`pytest --cov=pyagentforge`
4. 集成到 CI/CD 流程

## 支持

如有问题，请查看：

- [测试计划](TEST_PLAN.md)
- [测试分类文档](README.md)
- [PyAgentForge 文档](../../README.md)
