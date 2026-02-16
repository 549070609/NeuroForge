# GLM Integration Tests

基于 GLM-5 模型的 PyAgentForge 深度集成测试套件

## 快速开始

### 1. 配置环境变量

```bash
export GLM_API_KEY="your-glm-api-key"
export GLM_MODEL="glm-4-flash"  # 可选，默认 glm-4-flash
```

### 2. 安装依赖

```bash
cd demo/pyagentforge
pip install -e .

pip install pytest pytest-asyncio pytest-timeout pytest-json-report
```

### 3. 运行测试

```bash
# 运行所有测试
cd tests/glm_integration
python run_tests.py

# 或使用 pytest
pytest -v
```

## 测试分类

| 分类 | 标记 | 描述 | 文件 |
|------|------|------|------|
| 基础功能 | `@pytest.mark.basic` | 消息、上下文、引擎 | test_basic_functionality.py |
| 工具调用 | `@pytest.mark.tools` | 内置工具执行 | test_tools_execution.py |
| 流式响应 | `@pytest.mark.streaming` | WebSocket 和流式通信 | test_streaming.py |
| 高级功能 | `@pytest.mark.advanced` | 并行代理、压缩 | test_advanced_features.py |
| 错误处理 | `@pytest.mark.error` | 异常处理 | test_error_handling.py |
| 边界测试 | `@pytest.mark.boundary` | 边界条件 | test_boundary.py |
| 集成测试 | `@pytest.mark.integration` | 端到端场景 | test_integration.py |
| 性能测试 | `@pytest.mark.performance` | 性能指标 | test_performance.py |

## 运行特定测试

```bash
# 仅运行基础功能测试
pytest -m basic -v

# 仅运行工具测试
pytest -m tools -v

# 跳过慢速测试
pytest -m "not slow" -v

# 运行需要服务器的测试（需先启动 server.py）
pytest --run-server-tests -v

# 运行 Web 测试
pytest --run-web-tests -v
```

## 测试报告

测试完成后会生成：

1. **test-report.md** - Markdown 格式总结报告
2. **test-report.json** - 详细 JSON 数据

## 测试覆盖

### 基础功能 (BasicFunctionalityTest)
- ✅ 简单对话
- ✅ 数学计算
- ✅ 上下文感知
- ✅ 多轮对话
- ✅ 系统提示词
- ✅ 消息序列化

### 工具调用 (ToolExecutionTest)
- ✅ Bash 命令执行
- ✅ 文件读写
- ✅ 文件编辑
- ✅ 文件搜索 (glob)
- ✅ 内容搜索 (grep)
- ✅ 工具链
- ✅ 权限控制

### 流式响应 (StreamingTest)
- ✅ 流式文本
- ✅ 流式工具调用
- ✅ WebSocket 连接
- ✅ HTTP API

### 高级功能 (AdvancedFeaturesTest)
- ✅ 并行子代理
- ✅ 上下文压缩
- ✅ Skill 加载
- ✅ Command 解析
- ✅ 思考过程

### 错误处理 (ErrorHandlingTest)
- ✅ 无效工具
- ✅ 文件操作错误
- ✅ 命令执行错误
- ✅ 输入验证
- ✅ 超时处理

### 边界测试 (BoundaryTest)
- ✅ 长上下文 (20 轮对话)
- ✅ 大文件 (10MB)
- ✅ 多文件操作 (100 个文件)
- ✅ 并发会话 (5 个并发)
- ✅ Token 限制

### 集成测试 (IntegrationTest)
- ✅ 代码生成
- ✅ 文件重构
- ✅ 多步任务
- ✅ 会话持久化
- ✅ 真实场景

### 性能测试 (PerformanceTest)
- ✅ 响应时间
- ✅ 工具执行性能
- ✅ 吞吐量
- ✅ 并发性能
- ✅ 内存使用

## 故障排查

### GLM_API_KEY 未设置

```bash
export GLM_API_KEY="your-key-here"
```

### 依赖缺失

```bash
pip install pytest pytest-asyncio pytest-timeout
```

### 测试超时

增加超时时间：

```bash
export TEST_TIMEOUT=60
```

### 连接失败

检查网络连接和 API Key 有效性

## 贡献测试

添加新测试：

1. 选择合适的测试文件或创建新文件
2. 使用适当的 pytest 标记
3. 在 TEST_PLAN.md 中记录测试用例
4. 运行测试确保通过

## 许可证

MIT
