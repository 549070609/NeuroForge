```

================================================================================
                      MateAgent REST API 集成测试报告
================================================================================

测试时间: 2026-02-22 01:26:56 - 01:26:56
总耗时: 463ms

测试统计:
  - 总数: 6
  - 通过: 6
  - 失败: 0
  - 成功率: 100.0%

--------------------------------------------------------------------------------
                              测试详情
--------------------------------------------------------------------------------

1. [PASS] 创建小说大纲 Agent
   耗时: 415ms
   agent_id: novel-outline-agent
   config_file: main\Agent\novel-outline-agent\agent.yaml
   prompt_file: main\Agent\novel-outline-agent\system_prompt.md

2. [PASS] 列出所有 Agent
   耗时: 13ms
   total_agents: 2
   mate_agent_found: True
   novel_agent_found: True
   agent_list: ['mate-agent', 'novel-outline-agent']

3. [PASS] 执行小说大纲 Agent
   耗时: 10ms
   agent_id: novel-outline-agent
   agent_name: novel-outline-agent
   description: AI小说大纲生成专家 - 专门用于创作和优化小说大纲，包括世界观设定、角色设计、情节规划等
   has_system_prompt: True
   config_path: main\Agent\novel-outline-agent\agent.yaml

4. [PASS] Service 层集成验证
   耗时: 2ms
   file_structure: valid
   integration_checks: ['AgentDirectory 导入', 'WorkspaceManager', 'SessionManager', 'AgentExecutor']
   api_endpoints: ['/workspaces', '/sessions', '/execute']

5. [PASS] 工具 Schema 验证
   耗时: 0ms
   total_tools: 11
   valid_schemas: 11
   tool_names: ['create_agent', 'modify_agent', 'delete_agent', 'list_agents', 'validate_agent', 'analyze_requirements', 'check_dependencies', 'render_template', 'edit_config', 'write_prompt', 'spawn_subagent']

6. [PASS] 清理测试 Agent
   耗时: 21ms
   deleted_agent: novel-outline-agent

================================================================================
                              测试结论
================================================================================
所有测试通过! MateAgent REST API 功能正常。

```
