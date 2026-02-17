# PyAgentForge GLM-5 深度测试计划

## 测试目标

基于 `glm-provider` 提供的 GLM-5 模型，对 PyAgentForge 进行全面深度测试，验证功能完整性、稳定性和性能。

## 测试环境

- **模型**: GLM-5 / GLM-4-Flash
- **后端**: `demo/glm-provider/server.py`
- **测试对象**: `demo/pyagentforge/`
- **测试框架**: pytest + asyncio
- **测试时间**: 2026-02-16

## 测试分类

### 1. 基础功能测试 (BasicFunctionalityTest)

**目标**: 验证核心组件基本功能

| 测试用例 | 描述 | 预期结果 |
|---------|------|---------|
| test_basic_conversation | 简单对话 | 返回合理回复 |
| test_context_management | 上下文管理 | 正确维护历史 |
| test_message_serialization | 消息序列化 | 可序列化/反序列化 |
| test_system_prompt | 系统提示词 | 遵循系统设定 |

### 2. 工具调用测试 (ToolExecutionTest)

**目标**: 验证各种工具的正确执行

| 测试用例 | 描述 | 预期结果 |
|---------|------|---------|
| test_bash_tool | Bash 命令执行 | 正确执行并返回结果 |
| test_read_tool | 文件读取 | 正确读取文件内容 |
| test_write_tool | 文件写入 | 成功写入文件 |
| test_edit_tool | 文件编辑 | 正确编辑内容 |
| test_glob_tool | 文件搜索 | 返回匹配文件列表 |
| test_grep_tool | 内容搜索 | 返回匹配行 |
| test_tool_chain | 工具链调用 | 多个工具连续执行 |
| test_tool_permission | 权限控制 | 正确过滤工具 |

### 3. 流式响应测试 (StreamingTest)

**目标**: 验证流式通信功能

| 测试用例 | 描述 | 预期结果 |
|---------|------|---------|
| test_stream_text | 流式文本 | 逐步返回文本块 |
| test_stream_tool_use | 流式工具调用 | 正确处理工具调用 |
| test_websocket_connection | WebSocket 连接 | 成功建立连接 |
| test_websocket_message | WebSocket 消息 | 正确收发消息 |

### 4. 高级功能测试 (AdvancedFeaturesTest)

**目标**: 验证复杂功能

| 测试用例 | 描述 | 预期结果 |
|---------|------|---------|
| test_parallel_subagent | 并行子代理 | 并行执行任务 |
| test_context_compression | 上下文压缩 | 有效压缩上下文 |
| test_skill_loading | Skill 加载 | 按需加载知识 |
| test_command_parsing | Command 解析 | 正确解析 !cmd`` 语法 |
| test_thinking_process | 思考过程 | 返回推理步骤 |

### 5. 错误处理测试 (ErrorHandlingTest)

**目标**: 验证异常处理能力

| 测试用例 | 描述 | 预期结果 |
|---------|------|---------|
| test_invalid_tool | 无效工具 | 友好错误提示 |
| test_tool_failure | 工具失败 | 正确处理错误 |
| test_rate_limit | 速率限制 | 正确限制请求 |
| test_timeout | 超时处理 | 超时后正确处理 |
| test_invalid_input | 无效输入 | 验证输入并拒绝 |

### 6. 边界测试 (BoundaryTest)

**目标**: 验证边界条件处理

| 测试用例 | 描述 | 预期结果 |
|---------|------|---------|
| test_long_context | 长上下文 | 正确处理或压缩 |
| test_large_file | 大文件 | 处理大文件读取 |
| test_many_tools | 大量工具调用 | 稳定执行多次调用 |
| test_concurrent_sessions | 并发会话 | 正确处理并发 |
| test_token_limit | Token 限制 | 遵循 Token 限制 |

### 7. 集成测试 (IntegrationTest)

**目标**: 验证端到端场景

| 测试用例 | 描述 | 预期结果 |
|---------|------|---------|
| test_code_generation | 代码生成 | 生成可运行代码 |
| test_file_refactoring | 文件重构 | 正确重构代码 |
| test_multi_step_task | 多步任务 | 完成复杂任务 |
| test_session_persistence | 会话持久化 | 正确保存/恢复 |

### 8. 性能测试 (PerformanceTest)

**目标**: 验证性能表现

| 测试用例 | 描述 | 指标 |
|---------|------|------|
| test_response_time | 响应时间 | < 5s (简单请求) |
| test_throughput | 吞吐量 | > 10 req/min |
| test_memory_usage | 内存使用 | < 500MB/会话 |
| test_concurrent_load | 并发负载 | 支持 10+ 并发会话 |

## 测试执行计划

### 阶段 1: 准备 (10 分钟)
- [ ] 启动 GLM Provider 后端
- [ ] 配置测试环境变量
- [ ] 安装测试依赖

### 阶段 2: 单元测试 (15 分钟)
- [ ] 运行基础功能测试
- [ ] 运行工具调用测试
- [ ] 收集测试结果

### 阶段 3: 集成测试 (20 分钟)
- [ ] 运行流式响应测试
- [ ] 运行高级功能测试
- [ ] 运行集成场景测试

### 阶段 4: 压力测试 (15 分钟)
- [ ] 运行边界测试
- [ ] 运行性能测试
- [ ] 运行错误处理测试

### 阶段 5: 报告生成 (10 分钟)
- [ ] 汇总测试结果
- [ ] 生成测试报告
- [ ] 分析失败用例

## 测试工具

```bash
# 运行所有测试
pytest tests/glm_integration/ -v

# 运行特定分类
pytest tests/glm_integration/ -m "basic" -v
pytest tests/glm_integration/ -m "tools" -v
pytest tests/glm_integration/ -m "streaming" -v

# 生成覆盖率报告
pytest tests/glm_integration/ --cov=pyagentforge --cov-report=html

# 并行运行
pytest tests/glm_integration/ -n 4
```

## 成功标准

| 指标 | 目标 | 可接受 |
|------|------|--------|
| 测试通过率 | > 95% | > 90% |
| 代码覆盖率 | > 80% | > 70% |
| 响应时间 | < 5s | < 10s |
| 并发支持 | > 20 会话 | > 10 会话 |
| 错误恢复 | 100% | > 95% |

## 测试报告

测试完成后将生成：
1. `test-report.md` - 测试总结报告
2. `test-results.json` - 详细测试结果
3. `coverage-report/` - 代码覆盖率报告
4. `performance-metrics.json` - 性能指标

---

**创建日期**: 2026-02-16
**维护者**: PyAgentForge 测试团队
